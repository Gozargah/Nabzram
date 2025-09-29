"""
System information API routes
"""

from fastapi import APIRouter, HTTPException

from app.models.schemas import APIResponse, SystemInfo
from app.services.process_service import process_manager

router = APIRouter()


@router.get("/xray", response_model=SystemInfo)
async def check_xray_availability():
    """Check if xray-core is installed and return version info"""
    try:
        system_info = await process_manager.check_xray_availability()

        return SystemInfo(
            available=system_info.get("available", False),
            version=system_info.get("version"),
            commit=system_info.get("commit"),
            go_version=system_info.get("go_version"),
            arch=system_info.get("arch"),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
