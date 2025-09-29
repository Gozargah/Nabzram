"""
Subscription management API routes
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.database.tinydb_manager import DatabaseManager
from app.dependencies import get_database
from app.models.schemas import (
    SubscriptionCreate,
    SubscriptionCreateResponse,
    SubscriptionDeleteResponse,
    SubscriptionDetailResponse,
    SubscriptionResponse,
    SubscriptionServersUpdateResponse,
    SubscriptionUpdate,
    SubscriptionUpdateResponse,
    SubscriptionUserInfoResponse,
)
from app.services.subscription_service import SubscriptionService

router = APIRouter()


def get_subscription_service():
    """Get subscription service instance"""
    return SubscriptionService()


def _convert_user_info_to_response(user_info) -> Optional[SubscriptionUserInfoResponse]:
    """Convert database user info to response model"""
    if not user_info:
        return None

    return SubscriptionUserInfoResponse(
        used_traffic=user_info.used_traffic,
        total=user_info.total,
        expire=user_info.expire,
    )


@router.post("", response_model=SubscriptionCreateResponse)
async def create_subscription(
    subscription_data: SubscriptionCreate,
    db: DatabaseManager = Depends(get_database),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Create a new subscription and fetch its servers"""
    try:
        # Get current settings for port overrides
        settings = db.get_settings()

        # Create subscription using service
        subscription = await service.create_subscription(
            subscription_data, settings.socks_port, settings.http_port
        )

        # Save to database
        db.create_subscription(subscription)

        return SubscriptionCreateResponse(
            success=True,
            message=f"Subscription '{subscription.name}' created successfully",
            id=subscription.id,
            name=subscription.name,
            server_count=len(subscription.servers),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        await service.close()


@router.get("", response_model=List[SubscriptionResponse])
async def list_subscriptions(db: DatabaseManager = Depends(get_database)):
    """List all subscriptions"""
    try:
        subscriptions = db.get_all_subscriptions()

        return [
            SubscriptionResponse(
                id=sub.id,
                name=sub.name,
                url=sub.url,
                last_updated=sub.last_updated,
                server_count=len(sub.servers),
                user_info=_convert_user_info_to_response(sub.user_info),
            )
            for sub in subscriptions
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{subscription_id}", response_model=SubscriptionDetailResponse)
async def get_subscription(
    subscription_id: UUID, db: DatabaseManager = Depends(get_database)
):
    """Get subscription details with servers"""
    try:
        subscription = db.get_subscription(subscription_id)

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        return SubscriptionDetailResponse(
            id=subscription.id,
            name=subscription.name,
            url=subscription.url,
            last_updated=subscription.last_updated,
            server_count=len(subscription.servers),
            user_info=_convert_user_info_to_response(subscription.user_info),
            servers=[
                {"id": server.id, "remarks": server.remarks, "status": server.status}
                for server in subscription.servers
            ],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/{subscription_id}", response_model=SubscriptionUpdateResponse)
async def update_subscription(
    subscription_id: UUID,
    updates: SubscriptionUpdate,
    db: DatabaseManager = Depends(get_database),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Update subscription details"""
    try:
        subscription = db.get_subscription(subscription_id)

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        # Prepare updates
        update_data = {}
        if updates.name is not None:
            update_data["name"] = updates.name

        if updates.url is not None:
            # Convert HttpUrl to string and normalize it (same as create_subscription)
            normalized_url = service._normalize_url(str(updates.url))
            update_data["url"] = normalized_url

        # Update subscription
        updated_subscription = db.update_subscription(subscription_id, update_data)

        return SubscriptionUpdateResponse(
            success=True,
            message="Subscription updated successfully",
            id=updated_subscription.id,
            name=updated_subscription.name,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        await service.close()


@router.delete("/{subscription_id}", response_model=SubscriptionDeleteResponse)
async def delete_subscription(
    subscription_id: UUID, db: DatabaseManager = Depends(get_database)
):
    """Delete a subscription and all its servers"""
    try:
        subscription = db.get_subscription(subscription_id)

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        # TODO: Stop all running servers for this subscription
        # This will be handled when we implement the process manager integration

        # Delete subscription
        success = db.delete_subscription(subscription_id)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete subscription")

        return SubscriptionDeleteResponse(
            success=True,
            message=f"Subscription '{subscription.name}' deleted successfully",
            id=subscription.id,
            name=subscription.name,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post(
    "/{subscription_id}/update", response_model=SubscriptionServersUpdateResponse
)
async def update_subscription_servers(
    subscription_id: UUID,
    db: DatabaseManager = Depends(get_database),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Refetch and update servers for a subscription"""
    try:
        subscription = db.get_subscription(subscription_id)

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        # Get current settings for port overrides
        settings = db.get_settings()

        # Update servers using service
        updated_subscription = await service.update_subscription_servers(
            subscription, settings.socks_port, settings.http_port
        )

        # Save updated servers and user info to database
        db.update_subscription_with_user_info(
            subscription_id,
            updated_subscription.servers,
            updated_subscription.user_info,
        )

        return SubscriptionServersUpdateResponse(
            success=True,
            message=f"Subscription '{subscription.name}' updated successfully",
            id=subscription_id,
            server_count=len(updated_subscription.servers),
            last_updated=updated_subscription.last_updated.isoformat(),
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        await service.close()
