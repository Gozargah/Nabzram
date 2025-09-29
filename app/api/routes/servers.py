"""
Server management API routes (scoped to subscriptions)
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.database.tinydb_manager import DatabaseManager
from app.dependencies import get_database
from app.models.schemas import (
    AllocatedPort,
    ServerStartResponse,
    ServerStatusResponse,
    ServerStopResponse,
    ServerTestResult,
    SubscriptionUrlTestResponse,
)
from app.services.process_service import process_manager

router = APIRouter()


@router.post(
    "/{subscription_id}/servers/{server_id}/start", response_model=ServerStartResponse
)
async def start_server(
    subscription_id: UUID, server_id: UUID, db: DatabaseManager = Depends(get_database)
):
    """Start a specific server"""
    try:
        server = db.get_server(subscription_id, server_id)

        if not server:
            raise HTTPException(status_code=404, detail="Server not found")

        # Check if server is already running
        if process_manager.is_server_running(server_id):
            return ServerStartResponse(
                success=True,
                message=f"Server '{server.remarks}' is already running",
                server_id=server_id,
                status="running",
                remarks=server.remarks,
            )

        # Get current settings for port overrides
        settings = db.get_settings()

        # Start the server (this will stop any currently running server)
        success, error_msg = await process_manager.start_single_server(
            server_id,
            subscription_id,
            server.raw,
            settings.socks_port,
            settings.http_port,
        )

        if success:
            # Update status in database
            db.update_server_status(subscription_id, server_id, "running")

            return ServerStartResponse(
                success=True,
                message=f"Server '{server.remarks}' started successfully",
                server_id=server_id,
                status="running",
                remarks=server.remarks,
            )
        else:
            # Update status to error
            db.update_server_status(subscription_id, server_id, "error")

            # Create detailed error message for HTTPException
            if error_msg:
                error_detail = error_msg
            else:
                error_detail = f"Failed to start server '{server.remarks}'"

            raise HTTPException(status_code=500, detail=error_detail)

    except HTTPException:
        raise
    except Exception as e:
        # Update status to error
        try:
            db.update_server_status(subscription_id, server_id, "error")
            # Try to get server details for detailed error message
            server = db.get_server(subscription_id, server_id)
            server_remarks = server.remarks if server else "Unknown"
        except Exception:
            server_remarks = "Unknown"

        raise HTTPException(
            status_code=500,
            detail=f"Failed to start server '{server_remarks}' due to internal error: {str(e)}",
        )


# Simplified single server endpoints (no server_id needed)
@router.post("/server/stop", response_model=ServerStopResponse)
async def stop_current_server(db: DatabaseManager = Depends(get_database)):
    """Stop the currently running server"""
    try:
        if not process_manager.is_any_server_running():
            return ServerStopResponse(
                success=True,
                message="No server is currently running",
                server_id=None,
                status="stopped",
            )

        current_server_id = process_manager.get_current_server_id()
        success = await process_manager.stop_current_server()

        if success and current_server_id:
            # Find and update the server status in database
            subscriptions = db.get_all_subscriptions()
            for subscription in subscriptions:
                for server in subscription.servers:
                    if server.id == current_server_id:
                        db.update_server_status(subscription.id, server.id, "stopped")
                        break

            return ServerStopResponse(
                success=True,
                message="Server stopped successfully",
                server_id=current_server_id,
                status="stopped",
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to stop server")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/server/status", response_model=ServerStatusResponse)
async def get_current_server_status(db: DatabaseManager = Depends(get_database)):
    """Get status of the currently running server"""
    try:
        if not process_manager.is_any_server_running():
            return ServerStatusResponse(
                success=True,
                message="No server is currently running",
                server_id=None,
                status="stopped",
                remarks=None,
                process_id=None,
                start_time=None,
                allocated_ports=None,
            )

        current_server_id = process_manager.get_current_server_id()
        current_info = process_manager.get_current_server_info()
        port_info = process_manager.get_current_server_port_info()
        allocated_ports = [
            AllocatedPort(port=port["port"], protocol=port["protocol"], tag=port["tag"])
            for port in port_info
        ]

        if not current_info:
            return ServerStatusResponse(
                success=True,
                message="Server status unknown",
                server_id=current_server_id,
                status="unknown",
                remarks=None,
                process_id=None,
                start_time=None,
                allocated_ports=None,
            )

        # Get server details from database
        server_remarks = "Unknown"
        subscriptions = db.get_all_subscriptions()
        for subscription in subscriptions:
            for server in subscription.servers:
                if server.id == current_server_id:
                    server_remarks = server.remarks
                    # Update status to running if needed
                    if server.status != "running":
                        db.update_server_status(subscription.id, server.id, "running")
                    break

        return ServerStatusResponse(
            success=True,
            message="Server is running",
            server_id=current_server_id,
            status="running",
            remarks=server_remarks,
            process_id=current_info.process_id,
            start_time=current_info.start_time.isoformat(),
            allocated_ports=allocated_ports,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/{subscription_id}/url-test", response_model=SubscriptionUrlTestResponse)
async def test_subscription_servers(
    subscription_id: UUID, db: DatabaseManager = Depends(get_database)
):
    """Test all servers in a subscription by starting them on random ports and checking connectivity"""
    try:
        subscription = db.get_subscription(subscription_id)

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        if not subscription.servers:
            return SubscriptionUrlTestResponse(
                success=True,
                message="No servers to test",
                subscription_id=subscription_id,
                subscription_name=subscription.name,
                total_servers=0,
                successful_tests=0,
                failed_tests=0,
                results=[],
            )

        # Stop any currently running server to free resources
        if process_manager.is_any_server_running():
            await process_manager.stop_current_server()

        # Test all servers concurrently
        test_results = await process_manager.test_subscription_servers(
            subscription.servers, subscription_id, test_timeout=5
        )

        # Convert results to response models
        server_test_results = []
        successful_tests = 0
        failed_tests = 0

        for result in test_results:
            server_result = ServerTestResult(
                server_id=result["server_id"],
                remarks=result["remarks"],
                success=result["success"],
                ping_ms=result["ping_ms"],
                error=result["error"],
                socks_port=result["socks_port"],
                http_port=result["http_port"],
            )
            server_test_results.append(server_result)

            if result["success"]:
                successful_tests += 1
            else:
                failed_tests += 1

        return SubscriptionUrlTestResponse(
            success=True,
            message=f"Tested {len(subscription.servers)} servers: {successful_tests} successful, {failed_tests} failed",
            subscription_id=subscription_id,
            subscription_name=subscription.name,
            total_servers=len(subscription.servers),
            successful_tests=successful_tests,
            failed_tests=failed_tests,
            results=server_test_results,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
