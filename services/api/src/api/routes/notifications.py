"""
Push notification routes.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ai_core import get_logger

from ..dependencies import CurrentUserDep, RedisDep

logger = get_logger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class PushSubscriptionKeys(BaseModel):
    """Web Push subscription keys."""
    p256dh: str
    auth: str


class PushSubscription(BaseModel):
    """Web Push subscription data."""
    endpoint: str
    keys: PushSubscriptionKeys


class UnsubscribeRequest(BaseModel):
    """Unsubscribe request."""
    endpoint: str


@router.post("/subscribe")
async def subscribe_push(
    subscription: PushSubscription,
    current_user: CurrentUserDep,
    redis: RedisDep,
) -> dict[str, str]:
    """
    Register a push notification subscription.

    Stores the subscription endpoint and keys for later use
    when sending push notifications to this user.
    """
    try:
        user_id = current_user.sub

        # Store subscription in Redis
        # Key: push:subscriptions:{user_id}
        # Value: Set of subscription endpoints
        sub_key = f"push:subscriptions:{user_id}"

        # Store the full subscription data
        import json
        sub_data = json.dumps({
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.keys.p256dh,
                "auth": subscription.keys.auth,
            },
            "user_id": user_id,
        })

        # Add to user's subscriptions set
        await redis.sadd(sub_key, sub_data)

        # Also store in a global set for easy lookup
        await redis.sadd("push:all_subscriptions", subscription.endpoint)

        # Map endpoint to user for reverse lookup
        await redis.set(f"push:endpoint:{subscription.endpoint}", user_id)

        logger.info(
            "Push subscription registered",
            user_id=user_id,
            endpoint=subscription.endpoint[:50] + "...",
        )

        return {"message": "Subscription registered successfully"}

    except Exception as e:
        logger.error("Failed to register push subscription", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register subscription",
        )


@router.post("/unsubscribe")
async def unsubscribe_push(
    request: UnsubscribeRequest,
    current_user: CurrentUserDep,
    redis: RedisDep,
) -> dict[str, str]:
    """
    Unregister a push notification subscription.
    """
    try:
        user_id = current_user.sub
        sub_key = f"push:subscriptions:{user_id}"

        # Get all subscriptions for this user
        subscriptions = await redis.smembers(sub_key)

        # Find and remove the matching subscription
        import json
        for sub_data in subscriptions:
            try:
                sub = json.loads(sub_data)
                if sub.get("endpoint") == request.endpoint:
                    await redis.srem(sub_key, sub_data)
                    break
            except json.JSONDecodeError:
                continue

        # Remove from global set
        await redis.srem("push:all_subscriptions", request.endpoint)

        # Remove endpoint mapping
        await redis.delete(f"push:endpoint:{request.endpoint}")

        logger.info(
            "Push subscription removed",
            user_id=user_id,
            endpoint=request.endpoint[:50] + "...",
        )

        return {"message": "Subscription removed successfully"}

    except Exception as e:
        logger.error("Failed to unregister push subscription", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unregister subscription",
        )


@router.get("/subscriptions")
async def list_subscriptions(
    current_user: CurrentUserDep,
    redis: RedisDep,
) -> dict[str, list[str]]:
    """
    List current user's push subscriptions.
    """
    try:
        user_id = current_user.sub
        sub_key = f"push:subscriptions:{user_id}"

        subscriptions = await redis.smembers(sub_key)

        # Extract just the endpoints
        import json
        endpoints = []
        for sub_data in subscriptions:
            try:
                sub = json.loads(sub_data)
                endpoints.append(sub.get("endpoint", ""))
            except json.JSONDecodeError:
                continue

        return {"subscriptions": endpoints}

    except Exception as e:
        logger.error("Failed to list subscriptions", error=str(e))
        return {"subscriptions": []}
