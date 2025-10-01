"""
Settings operations
"""

import logging
from typing import Any, Dict

from pydantic import ValidationError

from app.database import db
from app.models.schemas import SettingsUpdate
from app.ops.utils import error_reply, validation_error_reply
from app.services.process_service import process_manager

logger = logging.getLogger(__name__)


def get_settings() -> Dict[str, Any]:
    """Get current settings."""
    s = db.get_settings()
    return {
        "socks_port": s.socks_port,
        "http_port": s.http_port,
        "xray_binary": s.xray_binary,
        "xray_assets_folder": s.xray_assets_folder,
        "xray_log_level": getattr(s, "xray_log_level", None),
        "system_proxy": getattr(s, "system_proxy", True),
    }


def update_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Update settings and optionally restart current server."""
    try:
        update = SettingsUpdate.model_validate(payload)
    except ValidationError as e:
        return validation_error_reply(e)
    except Exception as e:
        return error_reply(f"Invalid settings: {str(e)}")

    update_data = update.model_dump(exclude_unset=True)

    s = db.get_settings()
    s = s.model_copy(update=update_data)

    db.update_settings(s)

    # Optionally restart current server if running with new ports
    try:
        if process_manager.current_server_id and process_manager.is_server_running(
            process_manager.current_server_id
        ):
            server_info = process_manager.running_processes.get(
                process_manager.current_server_id
            )
            if server_info:
                process_manager.stop_server(process_manager.current_server_id)
                ok, _err = process_manager.start_single_server(
                    server_info.server_id,
                    server_info.subscription_id,
                    server_info.config,
                    s.socks_port,
                    s.http_port,
                )

                if ok:
                    logger.info("Server restarted after settings update")
    except Exception as e:
        logger.error(f"Failed to restart server after settings update: {e}")

    return {
        "success": True,
        "message": "Settings updated successfully",
        "socks_port": s.socks_port,
        "http_port": s.http_port,
        "xray_binary": s.xray_binary,
        "xray_assets_folder": s.xray_assets_folder,
        "xray_log_level": getattr(s, "xray_log_level", None),
        "system_proxy": getattr(s, "system_proxy", True),
    }
