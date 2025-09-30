import sys
from pathlib import Path

from decouple import config
from platformdirs import user_data_dir


def get_app_root() -> Path:
    # In Nuitka --onefile, the bundled files live next to the executable
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    # In dev/normal Python, use this file’s folder (adjust if your structure differs)
    return Path(__file__).resolve().parent


APP_ROOT: Path = get_app_root()

DATA_DIR: Path = Path(user_data_dir("nabzram", "nabzram"))

DEBUG = config("DEBUG", default=False, cast=bool)

DATABASE_PATH = config("DATABASE_PATH", default=str(DATA_DIR / "db.json"))
