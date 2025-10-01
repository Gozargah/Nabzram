from app.database.tinydb_manager import DatabaseManager
from settings import DATABASE_PATH

db = DatabaseManager(DATABASE_PATH)

__all__ = [
    "DatabaseManager",
    "db",
]
