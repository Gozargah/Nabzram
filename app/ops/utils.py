"""Common utilities for ops modules."""

from typing import Any
from uuid import UUID


def to_uuid(value: Any) -> UUID:
    """Convert value to UUID."""
    return value if isinstance(value, UUID) else UUID(str(value))


def error_reply(message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create error response."""
    return {"success": False, "message": message, "data": data or {}}
