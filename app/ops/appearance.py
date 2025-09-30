from typing import Any, Dict

from app.database import db
from app.models.database import AppearanceModel
from app.models.schemas import AppearanceUpdate


def get_appearance() -> Dict[str, Any]:
    """Get current appearance."""
    a = db.get_appearance()
    return {
        "theme": a.theme,
        "font": a.font,
    }


def update_appearance(payload: AppearanceUpdate) -> Dict[str, Any]:
    """Update appearance."""
    a = db.update_appearance(AppearanceModel.model_validate(payload))
    return {
        "success": True,
        "message": "Appearance updated successfully",
        "theme": a.theme,
        "font": a.font,
    }
