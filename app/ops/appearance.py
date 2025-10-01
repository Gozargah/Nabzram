from typing import Any

from pydantic import ValidationError

from app.database import db
from app.models.database import AppearanceModel
from app.models.schemas import AppearanceUpdate
from app.ops.utils import error_reply, validation_error_reply


def get_appearance() -> dict[str, Any]:
    """Get current appearance."""
    a = db.get_appearance()
    return {
        "theme": a.theme,
        "font": a.font,
    }


def update_appearance(payload: AppearanceUpdate) -> dict[str, Any]:
    """Update appearance."""
    try:
        update = db.update_appearance(AppearanceModel.model_validate(payload))
    except ValidationError as e:
        return validation_error_reply(e)
    except Exception as e:
        return error_reply(f"Invalid appearance: {str(e)}")

    update_data = update.model_dump(exclude_unset=True)

    a = db.get_appearance()
    a = a.model_copy(update=update_data)

    db.update_appearance(a)

    return {
        "success": True,
        "message": "Appearance updated successfully",
        "theme": a.theme,
        "font": a.font,
    }
