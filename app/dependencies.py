"""
Shared FastAPI dependencies
"""

from app.core.config import get_settings
from app.database.tinydb_manager import DatabaseManager

# Global database instance
_global_db = None


def get_global_database() -> DatabaseManager:
    """Get the global database instance (singleton)"""
    global _global_db
    if _global_db is None:
        settings = get_settings()
        _global_db = DatabaseManager(settings.database_path)
    return _global_db


def get_database():
    """Get database manager instance - FastAPI dependency"""
    return get_global_database()


def close_global_database():
    """Close the global database connection (called on app shutdown)"""
    global _global_db
    if _global_db is not None:
        _global_db.close()
        _global_db = None
