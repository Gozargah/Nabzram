"""Update operations."""

import logging
from typing import Any

from app.ops.utils import error_reply
from app.services.process_service import process_manager
from app.services.xray_update_service import GeodataUpdateService, XrayUpdateService

logger = logging.getLogger(__name__)


def get_xray_version_info() -> dict[str, Any]:
    """Get Xray version information."""
    service = XrayUpdateService()
    try:
        xray_info = process_manager.check_xray_availability()
        current_version = xray_info.get("version")
        latest_version = service.get_latest_version()
        version_sizes = service.get_available_versions_with_sizes(limit=10)
        available_versions = [{"version": ver, "size_bytes": version_sizes.get(ver)} for ver in version_sizes]
        return {
            "current_version": current_version,
            "latest_version": latest_version,
            "available_versions": available_versions,
        }
    except Exception as e:
        return error_reply(f"Failed to get version info: {e!s}")


def update_xray(payload: dict[str, Any]) -> dict[str, Any]:
    """Update Xray to specified or latest version."""
    service = XrayUpdateService()
    try:
        request_version = payload.get("version")
        xray_info = process_manager.check_xray_availability()
        xray_binary = process_manager.get_effective_xray_binary()
        current_version = xray_info.get("version")

        if request_version:
            available = service.get_available_versions(limit=50)
            if request_version not in available and f"v{request_version}" not in available:
                return error_reply(f"Version {request_version} is not available")
        else:
            request_version = service.get_latest_version()

        if current_version and current_version == request_version:
            return {
                "success": True,
                "message": f"Xray is already up to date (version {request_version})",
                "version": request_version,
                "current_version": current_version,
            }

        ok = service.download_xray(request_version, xray_binary)
        if ok:
            # Restart currently running server
            try:
                if process_manager.current_server_id and process_manager.is_server_running(
                    process_manager.current_server_id,
                ):
                    server_info = process_manager.running_processes.get(
                        process_manager.current_server_id,
                    )
                    if server_info:
                        process_manager.stop_server(process_manager.current_server_id)
                        process_manager.start_single_server(
                            server_info.server_id,
                            server_info.subscription_id,
                            server_info.config,
                        )

            except Exception as e:
                logger.exception(f"Failed to restart server after xray update: {e}")

            return {
                "success": True,
                "message": f"Successfully updated Xray to version {request_version}",
                "version": request_version,
                "current_version": current_version,
            }
        return error_reply("Update failed")
    finally:
        pass


def update_geodata() -> dict[str, Any]:
    """Update Xray geodata files."""
    service = GeodataUpdateService()
    assets_folder = process_manager.get_xray_assets_folder()
    if not assets_folder:
        return error_reply(
            "Xray assets folder is not configured. Please set it in settings first.",
        )
    results = service.update_geodata(assets_folder)
    all_success = all(results.values())
    failed_files = [k for k, v in results.items() if not v]
    message = (
        "Successfully updated all geodata files"
        if all_success
        else f"Partially updated geodata. Failed files: {', '.join(failed_files)}"
    )
    # Restart current server if any
    try:
        if process_manager.is_any_server_running():
            process_manager.stop_current_server()
            info = process_manager.get_current_server_info()
            if info:
                process_manager.start_single_server(
                    info.server_id,
                    info.subscription_id,
                    info.config,
                )

    except Exception as e:
        logger.exception(f"Failed to restart server after geodata update: {e}")
    return {
        "success": all_success,
        "message": message,
        "updated_files": results,
        "assets_folder": assets_folder,
    }
