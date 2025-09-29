import sys
from pathlib import Path


def get_app_root() -> Path:
    # In Nuitka --onefile, the bundled files live next to the executable
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    # In dev/normal Python, use this file’s folder (adjust if your structure differs)
    return Path(__file__).resolve().parent
