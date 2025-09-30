"""
Common utilities for ops modules.
"""

from typing import Any, Dict
from uuid import UUID


def to_uuid(value: Any) -> UUID:
    """Convert value to UUID."""
    return value if isinstance(value, UUID) else UUID(str(value))


def error_reply(message: str, data: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Create error response."""
    return {"success": False, "message": message, "data": data or {}}
