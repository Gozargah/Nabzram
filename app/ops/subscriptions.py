"""Subscription operations"""

from typing import Any

from app.database import db
from app.models.schemas import SubscriptionCreate, SubscriptionUpdate
from app.ops.utils import error_reply, to_uuid
from app.services.subscription_service import SubscriptionService


def list_subscriptions() -> list[dict[str, Any]]:
    """List all subscriptions."""
    subs = db.get_all_subscriptions()
    result = []
    for sub in subs:
        result.append(
            {
                "id": str(sub.id),
                "name": sub.name,
                "url": sub.url,
                "last_updated": sub.last_updated.isoformat() if sub.last_updated else None,
                "server_count": len(sub.servers),
                "user_info": (
                    {
                        "used_traffic": sub.user_info.used_traffic,
                        "total": sub.user_info.total,
                        "expire": sub.user_info.expire.isoformat() if sub.user_info and sub.user_info.expire else None,
                    }
                    if sub.user_info
                    else None
                ),
            },
        )
    return result


def get_subscription(subscription_id: str) -> dict[str, Any]:
    """Get subscription details."""
    sid = to_uuid(subscription_id)
    sub = db.get_subscription(sid)
    if not sub:
        return error_reply("Subscription not found")
    return {
        "id": str(sub.id),
        "name": sub.name,
        "url": sub.url,
        "last_updated": sub.last_updated.isoformat() if sub.last_updated else None,
        "server_count": len(sub.servers),
        "user_info": (
            {
                "used_traffic": sub.user_info.used_traffic,
                "total": sub.user_info.total,
                "expire": sub.user_info.expire.isoformat() if sub.user_info and sub.user_info.expire else None,
            }
            if sub.user_info
            else None
        ),
        "servers": [{"id": str(s.id), "remarks": s.remarks, "status": s.status} for s in sub.servers],
    }


def create_subscription(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a new subscription."""
    service = SubscriptionService()
    try:
        data = SubscriptionCreate.model_validate(payload)
        settings = db.get_settings()
        subscription = service.create_subscription(
            data,
            settings.socks_port,
            settings.http_port,
        )

        db.create_subscription(subscription)
        return {
            "success": True,
            "message": f"Subscription '{subscription.name}' created successfully",
            "id": str(subscription.id),
            "name": subscription.name,
            "server_count": len(subscription.servers),
        }
    except Exception as e:
        return error_reply(str(e))
    finally:
        service.close()


def update_subscription(
    subscription_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Update an existing subscription."""
    sid = to_uuid(subscription_id)
    service = SubscriptionService()
    try:
        sub = db.get_subscription(sid)
        if not sub:
            return error_reply("Subscription not found")
        upd = SubscriptionUpdate.model_validate(payload)
        update_data: dict[str, Any] = {}
        if upd.name is not None:
            update_data["name"] = upd.name
        if upd.url is not None:
            normalized_url = service._normalize_url(str(upd.url))
            update_data["url"] = normalized_url
        updated = db.update_subscription(sid, update_data)
        return {
            "success": True,
            "message": "Subscription updated successfully",
            "id": str(updated.id),
            "name": updated.name,
        }
    finally:
        service.close()


def delete_subscription(subscription_id: str) -> dict[str, Any]:
    """Delete a subscription."""
    sid = to_uuid(subscription_id)
    sub = db.get_subscription(sid)
    if not sub:
        return error_reply("Subscription not found")
    ok = db.delete_subscription(sid)
    if not ok:
        return error_reply("Failed to delete subscription")
    return {
        "success": True,
        "message": f"Subscription '{sub.name}' deleted successfully",
        "id": str(sub.id),
        "name": sub.name,
    }


def refresh_subscription_servers(subscription_id: str) -> dict[str, Any]:
    """Refresh servers for a subscription."""
    sid = to_uuid(subscription_id)
    service = SubscriptionService()
    try:
        sub = db.get_subscription(sid)
        if not sub:
            return error_reply("Subscription not found")
        settings = db.get_settings()
        updated = service.update_subscription_servers(
            sub,
            settings.socks_port,
            settings.http_port,
        )

        db.update_subscription_with_user_info(sid, updated.servers, updated.user_info)
        return {
            "success": True,
            "message": f"Subscription '{sub.name}' updated successfully",
            "id": str(sid),
            "server_count": len(updated.servers),
            "last_updated": updated.last_updated.isoformat() if updated.last_updated else None,
        }
    finally:
        service.close()
