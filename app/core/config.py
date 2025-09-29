"""
Application configuration
"""

import random
from functools import lru_cache
from pathlib import Path
from socket import AF_INET, SO_REUSEADDR, SOCK_STREAM, SOL_SOCKET, socket

from platformdirs import user_data_dir
from pydantic_settings import BaseSettings


def find_free_port():
    """
    Find a random free 5-digit port (10000-65535).
    This works on Windows, macOS, and Linux.
    """
    for _ in range(20):
        port = random.randint(10000, 65535)
        with socket(AF_INET, SOCK_STREAM) as s:
            # SO_REUSEADDR is safe for port checking on all major OSes
            s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            try:
                s.bind(("", port))
                return port
            except OSError:
                continue
    # Fallback: let OS pick any free port
    with socket(AF_INET, SOCK_STREAM) as s:
        s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        s.bind(("", 0))
        return s.getsockname()[1]


class Settings(BaseSettings):
    """Application settings"""

    app_name: str = "nabzram"

    data_dir: Path = Path(user_data_dir(app_name, app_name))

    # Database
    database_path: str = str(data_dir / "db.json")

    # API
    api_host: str = "127.0.0.1"
    api_port: int | None = None

    # CORS
    cors_origins: list = ["*"]

    model_config = {"env_file": ".env", "env_prefix": "NABZRAM_"}


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    settings = Settings()
    if settings.api_port is None:
        # If not defined, pick a random free 5-digit port
        settings.api_port = find_free_port()
    return settings
