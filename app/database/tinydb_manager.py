"""
TinyDB database manager for persistent storage
"""

import os
import platform
import shutil
import subprocess
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from platformdirs import user_data_dir
from tinydb import Query, TinyDB

from app.models.database import ServerModel, SettingsModel, SubscriptionModel


def check_xray_command_available() -> tuple[bool, str | None]:
    """
    Check if the 'xray' command is available on the system.
    Works on Linux, Windows, and macOS.

    Returns:
        tuple: (is_available, full_path) where is_available is bool and full_path is str or None
    """
    try:
        # Use shutil.which to find the xray command in PATH
        xray_path = shutil.which("xray")
        if xray_path:
            # Try to run xray --version to verify it's actually xray-core
            # On Windows, hide the console window
            kwargs = {"capture_output": True, "text": True, "timeout": 5}
            if platform.system() == "Windows":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(["xray", "--version"], **kwargs)
            # Check if the output contains xray-core information
            is_xray_core = (
                "xray-core" in result.stdout.lower() or "xray" in result.stdout.lower()
            )
            return is_xray_core, xray_path if is_xray_core else None
        return False, None
    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        FileNotFoundError,
    ):
        return False, None


def get_xray_data_directory() -> Path:
    """
    Get the appropriate directory for storing xray binary and assets.
    Uses platformdirs to get the correct user data directory for each platform.
    """
    return Path(user_data_dir("nabzram", "nabzram")) / "xray"


def get_default_xray_binary_filename() -> str:
    """Return platform-specific xray binary filename."""
    system = platform.system().lower()
    if system == "windows":
        return "xray.exe"
    # macOS (darwin) and Linux use "xray"
    return "xray"


class DatabaseManager:
    """Manages TinyDB operations for subscriptions, servers, and settings"""

    def __init__(self, db_path: str = "data/db.json"):
        """Initialize the database manager"""
        self.db_path = db_path
        self._lock = threading.RLock()  # Reentrant lock for thread safety

        # Ensure database directory exists
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        self.db = TinyDB(db_path, indent=2)

        # Get tables
        self.subscriptions_table = self.db.table("subscriptions")
        self.settings_table = self.db.table("settings")

        # Initialize settings if not exists
        self._init_settings()

    @contextmanager
    def _db_operation(self):
        """Context manager for thread-safe database operations"""
        self._lock.acquire()
        try:
            yield
        finally:
            self._lock.release()

    def _escape_json_path(self, path: str) -> str:
        """Escape Windows path characters that can break JSON parsing"""
        if not isinstance(path, str):
            return path

        # Replace backslashes with forward slashes for cross-platform compatibility
        escaped_path = path.replace("\\", "/")

        # Handle problematic characters that can break JSON
        # Note: Python's json module handles most escaping automatically,
        # but we normalize paths to prevent issues
        return escaped_path

    def _unescape_json_path(self, path: str) -> str:
        """Unescape path for Windows compatibility"""
        if not isinstance(path, str):
            return path

        # Convert forward slashes back to backslashes on Windows
        if platform.system() == "Windows" and "/" in path and ":" in path:
            return path.replace("/", "\\")

        return path

    def _init_settings(self):
        """Ensure settings are initialized by delegating to get_settings()."""
        self.get_settings()

    def _serialize_for_db(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize data for database storage with Windows path safety"""
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                if isinstance(value, UUID):
                    result[key] = str(value)
                elif isinstance(value, datetime):
                    result[key] = value.isoformat()
                elif isinstance(value, Path):
                    # Convert Path to string and escape for JSON
                    result[key] = self._escape_json_path(str(value))
                elif isinstance(value, str) and key in [
                    "xray_binary",
                    "xray_assets_folder",
                ]:
                    # Escape path strings for JSON safety
                    result[key] = self._escape_json_path(value)
                elif isinstance(value, dict):
                    result[key] = self._serialize_for_db(value)
                elif isinstance(value, list):
                    result[key] = [
                        self._serialize_for_db(item) if isinstance(item, dict) else item
                        for item in value
                    ]
                else:
                    result[key] = value
            return result
        return data

    def _deserialize_from_db(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize data from database storage with Windows path handling"""
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                if key in ["id"] and isinstance(value, str):
                    try:
                        result[key] = UUID(value)
                    except ValueError:
                        result[key] = value
                elif key in ["last_updated"] and isinstance(value, str):
                    try:
                        result[key] = datetime.fromisoformat(value)
                    except ValueError:
                        result[key] = None
                elif key in ["xray_binary", "xray_assets_folder"] and isinstance(
                    value, str
                ):
                    # Unescape paths for Windows compatibility
                    result[key] = self._unescape_json_path(value)
                elif key == "user_info" and isinstance(value, dict):
                    # Handle nested datetime in user_info.expire
                    user_info_data = self._deserialize_from_db(value)
                    if "expire" in user_info_data and isinstance(
                        user_info_data["expire"], str
                    ):
                        try:
                            user_info_data["expire"] = datetime.fromisoformat(
                                user_info_data["expire"]
                            )
                        except ValueError:
                            user_info_data["expire"] = None
                    result[key] = user_info_data
                elif isinstance(value, dict):
                    result[key] = self._deserialize_from_db(value)
                elif isinstance(value, list):
                    result[key] = [
                        self._deserialize_from_db(item)
                        if isinstance(item, dict)
                        else item
                        for item in value
                    ]
                else:
                    result[key] = value
            return result
        return data

    # Subscription operations
    def create_subscription(self, subscription: SubscriptionModel) -> SubscriptionModel:
        """Create a new subscription"""
        with self._db_operation():
            data = self._serialize_for_db(subscription.model_dump())
            self.subscriptions_table.insert(data)
            return subscription

    def get_subscription(self, subscription_id: UUID) -> Optional[SubscriptionModel]:
        """Get a subscription by ID"""
        with self._db_operation():
            query = Query()
            result = self.subscriptions_table.search(query.id == str(subscription_id))
            if result:
                data = self._deserialize_from_db(result[0])
                return SubscriptionModel(**data)
            return None

    def get_all_subscriptions(self) -> List[SubscriptionModel]:
        """Get all subscriptions"""
        with self._db_operation():
            results = self.subscriptions_table.all()
            subscriptions = []
            for result in results:
                data = self._deserialize_from_db(result)
                subscriptions.append(SubscriptionModel(**data))
            return subscriptions

    def update_subscription(
        self, subscription_id: UUID, updates: Dict[str, Any]
    ) -> Optional[SubscriptionModel]:
        """Update a subscription"""
        with self._db_operation():
            query = Query()
            serialized_updates = self._serialize_for_db(updates)

            # Add last_updated timestamp
            if "last_updated" not in serialized_updates:
                serialized_updates["last_updated"] = datetime.now().isoformat()

            self.subscriptions_table.update(
                serialized_updates, query.id == str(subscription_id)
            )
            return self.get_subscription(subscription_id)

    def delete_subscription(self, subscription_id: UUID) -> bool:
        """Delete a subscription"""
        with self._db_operation():
            query = Query()
            result = self.subscriptions_table.remove(query.id == str(subscription_id))
            return len(result) > 0

    def update_subscription_servers(
        self, subscription_id: UUID, servers: List[ServerModel]
    ) -> Optional[SubscriptionModel]:
        """Update servers for a subscription"""
        serialized_servers = [
            self._serialize_for_db(server.model_dump()) for server in servers
        ]
        updates = {
            "servers": serialized_servers,
            "last_updated": datetime.now().isoformat(),
        }
        return self.update_subscription(subscription_id, updates)

    def update_subscription_with_user_info(
        self, subscription_id: UUID, servers: List[ServerModel], user_info
    ) -> Optional[SubscriptionModel]:
        """Update servers and user info for a subscription"""
        serialized_servers = [
            self._serialize_for_db(server.model_dump()) for server in servers
        ]
        updates = {
            "servers": serialized_servers,
            "last_updated": datetime.now().isoformat(),
        }

        # Add user_info if provided
        if user_info:
            updates["user_info"] = self._serialize_for_db(user_info.model_dump())

        return self.update_subscription(subscription_id, updates)

    # Server operations (within subscriptions)
    def get_server(
        self, subscription_id: UUID, server_id: UUID
    ) -> Optional[ServerModel]:
        """Get a server by ID within a subscription"""
        subscription = self.get_subscription(subscription_id)
        if subscription:
            for server in subscription.servers:
                if server.id == server_id:
                    return server
        return None

    def update_server_status(
        self, subscription_id: UUID, server_id: UUID, status: str
    ) -> Optional[ServerModel]:
        """Update server status"""
        with self._db_operation():
            subscription = self.get_subscription(subscription_id)
            if subscription:
                for i, server in enumerate(subscription.servers):
                    if server.id == server_id:
                        subscription.servers[i].status = status
                        self.update_subscription_servers(
                            subscription_id, subscription.servers
                        )
                        return subscription.servers[i]
            return None

    # Settings operations
    def get_settings(self) -> SettingsModel:
        """Get current settings"""
        with self._db_operation():
            result = self.settings_table.all()
            if result:
                settings = SettingsModel(**result[0])
            else:
                settings = SettingsModel()

            if not settings.xray_binary:
                is_available, xray_path = check_xray_command_available()
                if is_available and xray_path:
                    settings.xray_binary = xray_path
                    settings.xray_assets_folder = settings.xray_assets_folder
                else:
                    xray_data_dir = get_xray_data_directory()
                    xray_data_dir.mkdir(parents=True, exist_ok=True)
                    settings.xray_binary = str(
                        xray_data_dir / get_default_xray_binary_filename()
                    )
                    settings.xray_assets_folder = str(xray_data_dir)

                self.update_settings(settings)

            return settings

    def update_settings(self, settings: SettingsModel) -> SettingsModel:
        """Update settings"""
        with self._db_operation():
            data = settings.model_dump()
            self.settings_table.truncate()  # Clear existing settings
            self.settings_table.insert(data)
            return settings

    def close(self):
        """Close the database connection"""
        self.db.close()
