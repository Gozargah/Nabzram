from gui import create_main_window, start_gui
from server import settings, start_server_thread

if __name__ == "__main__":
    # Start backend
    start_server_thread()

    # Create frontend window
    url = f"http://{settings.api_host}:{settings.api_port}"
    window = create_main_window(url)

    # Run GUI + Tray
    start_gui(window)
