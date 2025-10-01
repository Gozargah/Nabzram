"""Window API - pywebview window control functions."""


class WindowApi:
    """API exposed to JavaScript for controlling the pywebview window."""

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
