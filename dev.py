import logging
import subprocess

from app.gui import GuiManager
from settings import APP_ROOT

logging.basicConfig(level=logging.DEBUG)

if __name__ == "__main__":
    gui = GuiManager()

    dev_server = subprocess.Popen(["bun", "run", "dev", "--port", "5173", "--host"], cwd=APP_ROOT / "ui")

    def cleanup():
        if dev_server.poll() is None:
            try:
                dev_server.terminate()
                dev_server.wait(timeout=5)
            except Exception:
                dev_server.kill()

    try:
        url = "http://127.0.0.1:5173"
        window = gui.create_main_window(
            url,
            resizable=True,
            frameless=False,
            easy_drag=False,
        )

        gui.start_gui(window, private_mode=False, debug=True)
    finally:
        cleanup()
