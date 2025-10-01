"""System operations."""

from typing import Any

from app.services.process_service import process_manager


def get_xray_status() -> dict[str, Any]:
    """Get Xray system status."""
    info = process_manager.check_xray_availability()
    return {
        "available": info.get("available", False),
        "version": info.get("version"),
        "commit": info.get("commit"),
        "go_version": info.get("go_version"),
        "arch": info.get("arch"),
    }
