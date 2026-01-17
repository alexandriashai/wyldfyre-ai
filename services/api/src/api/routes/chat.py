"""
WebSocket chat endpoint.
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from ai_core import get_logger
from ai_messaging import RedisClient

from ..config import get_api_config
from ..dependencies import get_redis
from ..services.auth_service import AuthService, TokenPayload
from ..websocket.handlers import MessageHandler
from ..websocket.manager import ConnectionManager, get_connection_manager

logger = get_logger(__name__)

router = APIRouter(tags=["Chat"])


async def get_user_from_token(token: str) -> TokenPayload | None:
    """
    Validate token and return user payload.

    Used for WebSocket authentication.
    """
    try:
        config = get_api_config()
        # Create a minimal auth service for token verification
        auth_service = AuthService(db=None, config=config)  # type: ignore
        return auth_service.verify_token(token)
    except Exception as e:
        logger.warning("WebSocket auth failed", error=str(e))
        return None


@router.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
    redis: RedisClient = Depends(get_redis),
) -> None:
    """
    WebSocket endpoint for real-time chat.

    ## Authentication
    Pass JWT token as query parameter: `/ws/chat?token=<your_token>`

    ## Message Format

    ### Sending Messages
    ```json
    {
        "type": "chat",
        "conversation_id": "uuid",
        "content": "Your message here"
    }
    ```

    ### Receiving Messages
    ```json
    {
        "type": "message",
        "conversation_id": "uuid",
        "message_id": "uuid",
        "content": "Response content",
        "agent": "code-agent",
        "timestamp": "2024-01-01T00:00:00Z"
    }
    ```

    ### Streaming Tokens
    ```json
    {
        "type": "token",
        "conversation_id": "uuid",
        "message_id": "uuid",
        "token": "partial",
        "agent": "code-agent"
    }
    ```

    ### Ping/Pong
    Send: `{"type": "ping"}`
    Receive: `{"type": "pong", "timestamp": "..."}`
    """
    # Authenticate
    user = await get_user_from_token(token)
    if not user:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    # Get connection manager
    manager = get_connection_manager()

    # Connect
    try:
        connection = await manager.connect(
            websocket=websocket,
            user_id=user.sub,
            username=user.username,
        )
    except ValueError as e:
        await websocket.close(code=4002, reason=str(e))
        return

    # Create message handler
    handler = MessageHandler(manager, redis)

    # Send welcome message
    await websocket.send_json({
        "type": "connected",
        "user_id": user.sub,
        "username": user.username,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    logger.info(
        "WebSocket connected",
        user_id=user.sub,
        username=user.username,
    )

    try:
        while True:
            # Receive message
            data = await websocket.receive_json()

            # Handle message
            await handler.handle_message(connection, data)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", user_id=user.sub)
    except Exception as e:
        logger.error("WebSocket error", user_id=user.sub, error=str(e))
    finally:
        await manager.disconnect(websocket)


@router.get("/ws/stats")
async def websocket_stats() -> dict:
    """
    Get WebSocket connection statistics.

    Useful for monitoring and debugging.
    """
    manager = get_connection_manager()

    return {
        "total_connections": manager.get_connection_count(),
        "connected_users": manager.get_connected_users(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
