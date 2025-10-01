"""Settings operations."""

import logging
from typing import Any

from app.database import db
from app.models.database import SettingsModel
from app.models.schemas import SettingsUpdate
from app.ops.utils import error_reply
from app.services.process_service import process_manager

logger = logging.getLogger(__name__)


def get_settings() -> dict[str, Any]:
    """Get current settings."""
    s = db.get_settings()
    return {
        "socks_port": s.socks_port,
        "http_port": s.http_port,
        "xray_binary": s.xray_binary,
        "xray_assets_folder": s.xray_assets_folder,
        "xray_log_level": getattr(s, "xray_log_level", None),
    }


def update_settings(payload: dict[str, Any]) -> dict[str, Any]:
    """Update settings and optionally restart current server."""
    try:
        update = SettingsUpdate.model_validate(payload)
    except Exception as e:
        return error_reply(f"Invalid settings: {e!s}")

    db.update_settings(SettingsModel.model_validate(update.model_dump()))

    # Optionally restart current server if running with new ports
    try:
        if process_manager.current_server_id and process_manager.is_server_running(
            process_manager.current_server_id,
        ):
            server_info = process_manager.running_processes.get(
                process_manager.current_server_id,
            )
            if server_info:
                process_manager.stop_server(process_manager.current_server_id)
                ok, _err = process_manager.start_single_server(
                    server_info.server_id,
                    server_info.subscription_id,
                    server_info.config,
                )

                if ok:
                    logger.info("Server restarted after settings update")
    except Exception as e:
        logger.exception(f"Failed to restart server after settings update: {e}")

    s = db.get_settings()
    return {
        "success": True,
        "message": "Settings updated successfully",
        "socks_port": s.socks_port,
        "http_port": s.http_port,
        "xray_binary": s.xray_binary,
        "xray_assets_folder": s.xray_assets_folder,
        "xray_log_level": getattr(s, "xray_log_level", None),
    }
