"""
Xray and geodata update API routes
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import (
    GeodataUpdateResponse,
    XrayUpdateRequest,
    XrayUpdateResponse,
    XrayVersionInfo,
)
from app.services.process_service import process_manager
from app.services.xray_update_service import GeodataUpdateService, XrayUpdateService

router = APIRouter()
logger = logging.getLogger(__name__)


def get_xray_update_service():
    """Get Xray update service instance"""
    return XrayUpdateService()


def get_geodata_update_service():
    """Get geodata update service instance"""
    return GeodataUpdateService()


async def restart_current_server_if_running():
    """Restart the currently running server if any"""
    try:
        if process_manager.current_server_id and process_manager.is_server_running(
            process_manager.current_server_id
        ):
            logger.info(
                f"Restarting server {process_manager.current_server_id} after update"
            )

            # Get the current server info to restart it with the same configuration
            server_info = process_manager.running_processes.get(
                process_manager.current_server_id
            )
            if server_info:
                # Stop the current server
                await process_manager.stop_server(process_manager.current_server_id)

                # Restart with the same configuration
                success, error_msg = await process_manager.start_single_server(
                    server_info.server_id,
                    server_info.subscription_id,
                    server_info.config,
                )

                if success:
                    logger.info(
                        f"Successfully restarted server {process_manager.current_server_id}"
                    )
                else:
                    logger.error(
                        f"Failed to restart server {process_manager.current_server_id}: {error_msg}"
                    )
                return True
            else:
                logger.warning(
                    f"Could not find server info for {process_manager.current_server_id}"
                )
        return False
    except Exception as e:
        logger.error(f"Failed to restart server: {e}")
        return False


@router.get("/xray/info", response_model=XrayVersionInfo)
async def get_xray_version_info(
    service: XrayUpdateService = Depends(get_xray_update_service),
):
    """Get current and available Xray version information"""
    try:
        # Get version information
        xray_info = await process_manager.check_xray_availability()
        current_version = xray_info.get("version")
        latest_version = await service.get_latest_version()

        # Get available versions with sizes in a single API call
        version_sizes = await service.get_available_versions_with_sizes(limit=10)
        available_versions = list(version_sizes.keys())

        version_items = [
            {"version": ver, "size_bytes": version_sizes.get(ver)}
            for ver in available_versions
        ]

        return XrayVersionInfo(
            current_version=current_version,
            latest_version=latest_version,
            available_versions=version_items,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get version info: {str(e)}"
        )


@router.post("/xray/update", response_model=XrayUpdateResponse)
async def update_xray(
    request: XrayUpdateRequest,
    service: XrayUpdateService = Depends(get_xray_update_service),
):
    """Update Xray binary to specified version or latest"""
    try:
        xray_info = await process_manager.check_xray_availability()
        xray_binary = process_manager.get_effective_xray_binary()
        # Get current version before update
        current_version = xray_info.get("version")

        # Determine target version
        if request.version:
            target_version = request.version
            # Validate that the version exists
            available_versions = await service.get_available_versions(limit=50)
            if (
                target_version not in available_versions
                and f"v{target_version}" not in available_versions
            ):
                raise HTTPException(
                    status_code=400, detail=f"Version {target_version} is not available"
                )
        else:
            target_version = await service.get_latest_version()

        # Check if we're already on the target version
        if current_version and current_version == target_version:
            return XrayUpdateResponse(
                success=True,
                message=f"Xray is already up to date (version {target_version})",
                version=target_version,
                current_version=current_version,
            )

        # Perform the update
        success = await service.download_xray(target_version, xray_binary)

        if success:
            # Restart the currently running server if any
            restarted = await restart_current_server_if_running()

            message = f"Successfully updated Xray to version {target_version}"
            if restarted:
                message += " and restarted the running server"

            return XrayUpdateResponse(
                success=True,
                message=message,
                version=target_version,
                current_version=current_version,
            )
        else:
            raise HTTPException(status_code=500, detail="Update failed")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


@router.post("/geodata/update", response_model=GeodataUpdateResponse)
async def update_geodata(
    service: GeodataUpdateService = Depends(get_geodata_update_service),
):
    """Update Xray geodata files (geoip.dat, geosite.dat)"""
    try:
        # Get database settings to find assets folder
        assets_folder = process_manager.get_xray_assets_folder()

        if not assets_folder:
            raise HTTPException(
                status_code=400,
                detail="Xray assets folder is not configured. Please set it in settings first.",
            )

        # Perform the update
        results = await service.update_geodata(assets_folder)

        # Check if all files were updated successfully
        all_success = all(results.values())
        failed_files = [
            filename for filename, success in results.items() if not success
        ]

        if all_success:
            message = "Successfully updated all geodata files"

            # Restart the currently running server if any
            restarted = await restart_current_server_if_running()
            if restarted:
                message += " and restarted the running server"
        else:
            message = (
                f"Partially updated geodata. Failed files: {', '.join(failed_files)}"
            )

        return GeodataUpdateResponse(
            success=all_success,
            message=message,
            updated_files=results,
            assets_folder=assets_folder,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Geodata update failed: {str(e)}")
