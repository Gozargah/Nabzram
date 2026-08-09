import os
import platform
from typing import Any

import pystray
import webview
from PIL import Image
from pystray import MenuItem as Item

from app.gui.ops_api import OperationsApi
from app.gui.window_api import WindowApi
from settings import APP_ROOT, DATA_DIR, DEBUG


def _disable_pystray_dbus_notifier() -> None:
    """Avoid pystray's DBus Notifications proxy.

    pystray always constructs org.freedesktop.Notifications on tray start/stop,
    even when notifications are unused. A stuck notification daemon can block
    those sync DBus calls for ~25s and delay both startup and quit.
    """
    if platform.system().lower() != "linux":
        return
    try:
        from pystray._util import notify_dbus
    except Exception:
        return

    class _NoopNotifier:
        def notify(self, title: str, message: str, icon: str | None = None) -> None:
            return None

        def hide(self) -> None:
            return None

    notify_dbus.Notifier = _NoopNotifier  # type: ignore[misc, assignment]


class GuiManager:
    """GUI manager for Nabzram application."""

    def __init__(self) -> None:
        self.system = platform.system().lower()
        self.storage_path = str(DATA_DIR / "storage")
        self.icon_path = self._get_icon_path()
        self.gui_type = self._get_gui_type()
        self.easy_drag = self._get_easy_drag()
        self.dpi_scale = self._get_dpi_scale()
        self.tray_icon: pystray.Icon | None = None
        self._setup_environment()

    def _get_icon_path(self) -> str:
        """Get the appropriate icon path for the current platform."""
        if self.system == "windows":
            return os.path.abspath(APP_ROOT / "assets" / "icon.ico")
        if self.system == "darwin":
            return os.path.abspath(APP_ROOT / "assets" / "icon.icns")
        return os.path.abspath(APP_ROOT / "assets" / "icon.png")

    def _get_gui_type(self) -> str:
        """Get the appropriate GUI type for the current platform."""
        if self.system == "windows":
            return "edgechromium"
        if self.system == "darwin":
            return "cocoa"
        return "gtk"

    def _get_easy_drag(self) -> bool:
        """Get the easy drag setting for the current platform."""
        return self.system not in ("windows", "darwin")

    def _setup_environment(self) -> None:
        """Setup environment variables for the current platform."""
        if self.system == "linux":
            os.environ["WEBKIT_DISABLE_COMPOSITING_MODE"] = "1"

    def _get_dpi_scale(self) -> float:
        """Get the DPI scaling factor for the current display.

        Avoids tkinter (Tcl SONAME issues in Nuitka builds) and avoids early
        Gdk init, which can stall GTK/WebKit startup on Linux.
        """
        for key in ("GDK_SCALE", "QT_SCALE_FACTOR"):
            raw = os.environ.get(key)
            if not raw:
                continue
            try:
                scale = float(raw)
            except ValueError:
                continue
            if scale > 0:
                return scale

        try:
            if self.system == "windows":
                return self._get_dpi_scale_windows()
            if self.system == "darwin":
                return self._get_dpi_scale_macos()
            if self.system == "linux":
                return self._get_dpi_scale_linux()
        except Exception:
            pass
        return 1.0

    def _get_dpi_scale_windows(self) -> float:
        import ctypes

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        user32.SetProcessDPIAware()
        dc = user32.GetDC(0)
        try:
            dpi = int(gdi32.GetDeviceCaps(dc, 88))  # LOGPIXELSX
        finally:
            user32.ReleaseDC(0, dc)
        return dpi / 96.0 if dpi > 0 else 1.0

    def _get_dpi_scale_macos(self) -> float:
        from AppKit import NSScreen

        screen = NSScreen.mainScreen()
        if screen is None:
            return 1.0
        scale = float(screen.backingScaleFactor())
        return scale if scale > 0 else 1.0

    def _get_dpi_scale_linux(self) -> float:
        """Match former tkinter behavior via Xft.dpi; never use EDID mm sizes."""
        import subprocess

        try:
            out = subprocess.check_output(
                ["xrdb", "-query"],
                text=True,
                timeout=1,
                stderr=subprocess.DEVNULL,
            )
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            return 1.0

        for line in out.splitlines():
            if not line.lower().startswith("xft.dpi:"):
                continue
            try:
                dpi = float(line.split(":", 1)[1].strip())
            except ValueError:
                return 1.0
            return dpi / 96.0 if dpi > 0 else 1.0
        return 1.0

    def _setup_tray(self, window, api: WindowApi):
        """Setup system tray with left click = toggle, right click = menu."""
        _disable_pystray_dbus_notifier()

        def toggle(icon, item=None) -> None:
            api.toggle()

        def on_quit(icon, item=None) -> None:
            try:
                from app.services.process_service import process_manager

                process_manager.shutdown_all()
            except Exception:
                pass
            try:
                api.quit()
            finally:
                try:
                    icon.stop()
                except Exception:
                    pass

        tray_icon = pystray.Icon(
            "Nabzram",
            Image.open(self.icon_path),
            menu=pystray.Menu(
                Item("Show Window", toggle, default=True),
                Item("Quit", on_quit),
            ),
        )

        tray_icon.run_detached()
        self.tray_icon = tray_icon
        return tray_icon

    def create_main_window(self, url: str, **kwargs) -> webview.Window:
        """Create the main application window."""
        width = int(kwargs.pop("width", 500) * self.dpi_scale)
        height = int(kwargs.pop("height", 900) * self.dpi_scale)
        min_size = kwargs.pop("min_size", (500, 900))
        min_size = (int(min_size[0] * self.dpi_scale), int(min_size[1] * self.dpi_scale))
        return webview.create_window(
            "Nabzram",
            url,
            width=width,
            height=height,
            min_size=min_size,
            resizable=kwargs.pop("resizable", True),
            frameless=kwargs.pop("frameless", True),
            easy_drag=kwargs.pop("easy_drag", self.easy_drag),
            background_color=kwargs.pop("background_color", "#020817"),
            **kwargs,
        )

    def _register_api(self, window: webview.Window, api: Any) -> None:
        """Register API methods with the webview window."""
        methods = [getattr(api, name) for name in dir(api) if not name.startswith("_") and callable(getattr(api, name))]
        window.expose(*methods)

    def start_tray(self, window: webview.Window):
        """Start the tray application."""
        self._setup_tray(window, WindowApi(window))

    def start_gui(self, window: webview.Window, **kwargs):
        """Start the GUI application."""
        self._register_api(window, WindowApi(window))
        self._register_api(window, OperationsApi(window))

        zoom_level = 1.0 / self.dpi_scale
        webview.start(
            lambda w: w.evaluate_js(f"document.body.style.zoom = '{zoom_level}'"),
            window,
            gui=kwargs.pop("gui", self.gui_type),
            icon=kwargs.pop("icon", self.icon_path),
            storage_path=kwargs.pop("storage_path", self.storage_path),
            private_mode=kwargs.pop("private_mode", True),
            http_server=kwargs.pop("http_server", True),
            debug=kwargs.pop("debug", DEBUG),
            **kwargs,
        )


__all__ = ["GuiManager"]
