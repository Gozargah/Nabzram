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


class GuiManager:
    """GUI manager for Nabzram application."""

    def __init__(self):
        self.system = platform.system().lower()
        self.storage_path = str(DATA_DIR / "storage")
        self.icon_path = self._get_icon_path()
        self.gui_type = self._get_gui_type()
        self.easy_drag = self._get_easy_drag()
        self._setup_environment()

    def _get_icon_path(self) -> str:
        """Get the appropriate icon path for the current platform."""
        if self.system == "windows":
            return os.path.abspath(APP_ROOT / "assets" / "icon.ico")
        elif self.system == "darwin":
            return os.path.abspath(APP_ROOT / "assets" / "icon.icns")
        else:
            return os.path.abspath(APP_ROOT / "assets" / "icon.png")

    def _get_gui_type(self) -> str:
        """Get the appropriate GUI type for the current platform."""
        if self.system == "windows":
            return "edgechromium"
        elif self.system == "darwin":
            return "cocoa"
        else:
            return "gtk"

    def _get_easy_drag(self) -> bool:
        """Get the easy drag setting for the current platform."""
        return self.system not in ("windows", "darwin")

    def _setup_environment(self):
        """Setup environment variables for the current platform."""
        if self.system == "linux":
            os.environ["WEBKIT_DISABLE_COMPOSITING_MODE"] = "1"

    def _setup_tray(self, window, api: WindowApi):
        """Setup system tray with left click = toggle, right click = menu."""

        def toggle(icon, item=None):
            api.toggle()

        def on_quit(icon, item):
            api.quit()
            icon.stop()

        tray_icon = pystray.Icon(
            "Nabzram",
            Image.open(self.icon_path),
            menu=pystray.Menu(
                Item("Show Window", toggle, default=True),  # 👈 default = left click
                Item("Quit", on_quit),
            ),
        )

        tray_icon.run_detached()
        return tray_icon

    def create_main_window(self, url: str, **kwargs) -> webview.Window:
        """Create the main application window."""
        return webview.create_window(
            "Nabzram",
            url,
            width=kwargs.pop("width", 500),
            height=kwargs.pop("height", 900),
            min_size=kwargs.pop("min_size", (500, 900)),
            resizable=kwargs.pop("resizable", True),
            frameless=kwargs.pop("frameless", True),
            easy_drag=kwargs.pop("easy_drag", self.easy_drag),
            background_color=kwargs.pop("background_color", "#020817"),
            **kwargs,
        )

    def _register_api(self, window: webview.Window, api: Any):
        """Register API methods with the webview window."""
        methods = [
            getattr(api, name)
            for name in dir(api)
            if not name.startswith("_") and callable(getattr(api, name))
        ]
        window.expose(*methods)

    def start_tray(self, window: webview.Window):
        """Start the tray application."""
        self._setup_tray(window, WindowApi(window))

    def start_gui(self, window: webview.Window, **kwargs):
        """Start the GUI application."""

        self._register_api(window, WindowApi(window))
        self._register_api(window, OperationsApi(window))

        webview.start(
            lambda w: w.evaluate_js("document.body.style.zoom = '1.0'"),
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
