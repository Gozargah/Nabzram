"""Server operations"""

from typing import Any

from app.database import db
from app.ops.utils import error_reply, to_uuid
from app.services.process_service import process_manager


def start_server(subscription_id: str, server_id: str) -> dict[str, Any]:
    """Start a server."""
    sid = to_uuid(subscription_id)
    srv_id = to_uuid(server_id)
    server = db.get_server(sid, srv_id)
    if not server:
        return error_reply("Server not found")
    if process_manager.is_server_running(srv_id):
        return {
            "success": True,
            "message": f"Server '{server.remarks}' is already running",
            "server_id": str(srv_id),
            "status": "running",
            "remarks": server.remarks,
        }
    settings = db.get_settings()
    ok, err = process_manager.start_single_server(
        srv_id,
        sid,
        server.raw,
        settings.socks_port,
        settings.http_port,
    )

    if ok:
        db.update_server_status(sid, srv_id, "running")
        return {
            "success": True,
            "message": f"Server '{server.remarks}' started successfully",
            "server_id": str(srv_id),
            "status": "running",
            "remarks": server.remarks,
        }
    db.update_server_status(sid, srv_id, "error")
    return error_reply(err or f"Failed to start server '{server.remarks}'")


def stop_server() -> dict[str, Any]:
    """Stop the currently running server."""
    if not process_manager.is_any_server_running():
        return {
            "success": True,
            "message": "No server is currently running",
            "server_id": None,
            "status": "stopped",
        }
    current_id = process_manager.get_current_server_id()
    ok = process_manager.stop_current_server()
    if ok and current_id:
        subs = db.get_all_subscriptions()
        for sub in subs:
            for srv in sub.servers:
                if srv.id == current_id:
                    db.update_server_status(sub.id, srv.id, "stopped")
                    break
        return {
            "success": True,
            "message": "Server stopped successfully",
            "server_id": str(current_id),
            "status": "stopped",
        }
        return error_reply("Failed to stop server")


def get_server_status() -> dict[str, Any]:
    """Get current server status."""
    if not process_manager.is_any_server_running():
        return {
            "success": True,
            "message": "No server is currently running",
            "server_id": None,
            "status": "stopped",
            "remarks": None,
            "process_id": None,
            "start_time": None,
            "allocated_ports": None,
        }
    current_id = process_manager.get_current_server_id()
    info = process_manager.get_current_server_info()
    ports = process_manager.get_current_server_port_info()
    allocated_ports = [{"port": p["port"], "protocol": p["protocol"], "tag": p["tag"]} for p in ports]
    server_remarks = "Unknown"
    subs = db.get_all_subscriptions()
    for sub in subs:
        for srv in sub.servers:
            if srv.id == current_id:
                server_remarks = srv.remarks
                if srv.status != "running":
                    db.update_server_status(sub.id, srv.id, "running")
                break
    return {
        "success": True,
        "message": "Server is running",
        "server_id": str(current_id) if current_id else None,
        "status": "running",
        "remarks": server_remarks,
        "process_id": getattr(info, "process_id", None) if info else None,
        "start_time": getattr(info, "start_time", None).isoformat()
        if info and getattr(info, "start_time", None)
        else None,
        "allocated_ports": allocated_ports,
    }


def test_subscription_servers(subscription_id: str) -> dict[str, Any]:
    """Test all servers in a subscription."""
    sid = to_uuid(subscription_id)
    sub = db.get_subscription(sid)
    if not sub:
        return error_reply("Subscription not found")
    if not sub.servers:
        return {
            "success": True,
            "message": "No servers to test",
            "subscription_id": str(sid),
            "subscription_name": sub.name,
            "total_servers": 0,
            "successful_tests": 0,
            "failed_tests": 0,
            "results": [],
        }
    if process_manager.is_any_server_running():
        process_manager.stop_current_server()
    results = process_manager.test_subscription_servers(
        sub.servers,
        sid,
        test_timeout=5,
    )

    success_cnt = sum(1 for r in results if r.get("success"))
    fail_cnt = len(results) - success_cnt
    return {
        "success": True,
        "message": f"Tested {len(sub.servers)} servers: {success_cnt} successful, {fail_cnt} failed",
        "subscription_id": str(sid),
        "subscription_name": sub.name,
        "total_servers": len(sub.servers),
        "successful_tests": success_cnt,
        "failed_tests": fail_cnt,
        "results": [
            {
                "server_id": str(r["server_id"]),
                "remarks": r["remarks"],
                "success": r["success"],
                "ping_ms": r.get("ping_ms"),
                "error": r.get("error"),
                "socks_port": r["socks_port"],
                "http_port": r["http_port"],
            }
            for r in results
        ],
    }
