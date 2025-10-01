"""Log operations."""

from typing import Any

from app.ops.utils import error_reply
from app.services.process_service import process_manager


def get_log_snapshot(limit: int = 100) -> dict[str, Any]:
    """Get a snapshot of recent logs."""
    try:
        current_server_id = process_manager.get_current_server_id()
        if not current_server_id:
            return {
                "success": True,
                "message": "No server is currently running",
                "server_id": None,
                "logs": [],
            }

        logs = process_manager.get_log_snapshot(current_server_id, limit)

        return {
            "success": True,
            "message": "Log snapshot retrieved successfully",
            "server_id": str(current_server_id),
            "logs": logs,
        }
    except Exception as e:
        return error_reply(f"Failed to get log snapshot: {e!s}")


def get_log_stream_batch(
    since_ms: int | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Get a batch of logs since the specified timestamp."""
    try:
        current_server_id = process_manager.get_current_server_id()
        if not current_server_id:
            return {
                "success": True,
                "message": "No server is currently running",
                "server_id": None,
                "logs": [],
                "next_since_ms": None,
            }

        if since_ms is not None:
            logs = process_manager.get_logs_since(current_server_id, since_ms, limit)
        else:
            logs = process_manager.get_log_snapshot(current_server_id, limit)

        # Calculate next_since_ms for pagination
        next_since_ms = None
        if logs:
            # Parse the timestamp from the last log entry
            from datetime import datetime

            last_timestamp = datetime.fromisoformat(logs[-1]["timestamp"])
            next_since_ms = int(last_timestamp.timestamp() * 1000)

        return {
            "success": True,
            "message": "Log stream batch retrieved successfully",
            "server_id": str(current_server_id),
            "logs": logs,
            "next_since_ms": next_since_ms,
        }
    except Exception as e:
        return error_reply(f"Failed to get log stream batch: {e!s}")
