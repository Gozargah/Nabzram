from app.gui import GuiManager
from settings import APP_ROOT

if __name__ == "__main__":
    gui = GuiManager()

    ui_dir = APP_ROOT / "ui/dist/index.html"
    window = gui.create_main_window(str(ui_dir))

    gui.start_gui(window)
