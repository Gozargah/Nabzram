import os
import platform
from pathlib import Path

import pystray
import webview
from PIL import Image
from platformdirs import user_data_dir
from pystray import MenuItem as Item

from utils import get_app_root

storage_path = str(Path(user_data_dir("nabzram", "nabzram")) / "storage")


system = platform.system().lower()

if system == "windows":
    icon_path = os.path.abspath(get_app_root() / "assets" / "icon.ico")
    gui = "edgechromium"
    easy_drag = False

elif system == "darwin":
    icon_path = os.path.abspath(get_app_root() / "assets" / "icon.icns")
    gui = "cocoa"
    easy_drag = False

else:
    icon_path = os.path.abspath(get_app_root() / "assets" / "icon.png")
    gui = "gtk"
    os.environ["WEBKIT_DISABLE_COMPOSITING_MODE"] = "1"
    easy_drag = True


class WindowApi:
    """
    API exposed to JavaScript for controlling the pywebview window.
    """

    def __init__(self, window):
        self.window = window

        self._is_hidden = False

    # ──────────────────────────────
    # Basic controls
    # ──────────────────────────────
    def show(self):
        """Show the window"""
        self.window.show()
        self.window.restore()
        self._is_hidden = False

    def hide(self):
        """Hide window (close-to-tray behavior)"""
        self.window.hide()
        self._is_hidden = True

    def minimize(self):
        """Minimize to taskbar/dock"""
        self.window.minimize()
        self._is_hidden = True

    def maximize(self):
        """Maximize the window"""
        self.window.maximize()
        self._is_hidden = False

    def restore(self):
        """Restore from minimized/maximized"""
        self.window.restore()
        self._is_hidden = False

    def close(self):
        """Alias for hide() to support close-to-tray"""
        self.hide()
        self._is_hidden = True

    def toggle(self):
        """Toggle the window"""
        if self._is_hidden:
            self.show()
            self.restore()
        else:
            self.hide()

    def quit(self):
        """Destroy the window"""
        self.window.destroy()

    # ──────────────────────────────
    # Window states
    # ──────────────────────────────
    def is_visible(self) -> bool:
        """Return True if window is visible"""
        return not self._is_hidden

    def is_focused(self) -> bool:
        """Return True if window is focused"""
        return self.window.focus

    # ──────────────────────────────
    # Advanced controls
    # ──────────────────────────────
    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        self.window.toggle_fullscreen()

    def set_on_top(self, value: bool):
        """Keep window always on top"""
        self.window.on_top = bool(value)

    def resize(self, width: int, height: int):
        """Resize window to given dimensions"""
        self.window.resize(width, height)

    def move(self, x: int, y: int):
        """Move window to (x, y) on screen"""
        self.window.move(x, y)

    def get_size(self) -> tuple[int, int]:
        """Get current window size (width, height)"""
        return self.window.width, self.window.height

    def get_position(self) -> tuple[int, int]:
        """Get current window position (x, y)"""
        return self.window.x, self.window.y


def create_main_window(url: str):
    return webview.create_window(
        "Nabzram",
        url,
        width=500,
        height=900,
        min_size=(500, 900),
        resizable=True,
        frameless=True,
        easy_drag=easy_drag,
        background_color="#020817",
    )


def setup_tray(window: webview.Window, api: WindowApi):
    """Tray with left click = toggle, right click = menu"""

    def toggle(icon, item=None):
        api.toggle()

    def on_quit(icon, item):
        api.quit()
        icon.stop()

    tray_icon = pystray.Icon(
        "Nabzram",
        Image.open(icon_path),
        menu=pystray.Menu(
            Item("Show Window", toggle, default=True),  # 👈 default = left click
            Item("Quit", on_quit),
        ),
    )

    tray_icon.run_detached()


def register_api(window, api):
    methods = [
        getattr(api, name)
        for name in dir(api)
        if not name.startswith("_") and callable(getattr(api, name))
    ]
    window.expose(*methods)


def start_gui(window: webview.Window):
    window_api = WindowApi(window)

    register_api(window, window_api)
    setup_tray(window, window_api)

    webview.start(
        lambda w: w.evaluate_js("document.body.style.zoom = '1.0'"),
        window,
        gui=gui,
        icon=icon_path,
        storage_path=storage_path,
        private_mode=False,
    )
