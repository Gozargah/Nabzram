"""
Log streaming API routes
"""

import asyncio
import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.services.process_service import process_manager

router = APIRouter()


@router.get("/stream")
async def stream_logs():
    """Stream real-time logs from the currently running server using Server-Sent Events"""

    async def log_generator():
        """Generate log events"""
        try:
            # Stream logs from the currently running server
            if not process_manager.is_any_server_running():
                yield {
                    "event": "info",
                    "data": json.dumps({"message": "No server is currently running"}),
                }
                # Wait for a server to start
                while not process_manager.is_any_server_running():
                    await asyncio.sleep(1)
                yield {
                    "event": "info",
                    "data": json.dumps(
                        {"message": "Server started, beginning log stream"}
                    ),
                }

            async for log_entry in process_manager.get_current_server_logs():
                yield {
                    "event": "log",
                    "data": json.dumps(
                        {
                            "timestamp": log_entry["timestamp"].isoformat(),
                            "message": log_entry["message"],
                        }
                    ),
                }

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": f"Log streaming error: {str(e)}"}),
            }

    return EventSourceResponse(log_generator())


# Note: /running-servers endpoint removed - use /server/status instead for single server info
