"""
Browser viewport WebSocket endpoint.

Provides real-time browser streaming for AI agent browser automation,
allowing users to watch agents perform browser tasks.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import get_logger
from ai_db import Domain
from ai_messaging import PubSubManager, RedisClient

from ..config import get_api_config
from ..database import get_db_session
from ..dependencies import get_redis
from ..services.auth_service import AuthService, TokenPayload

logger = get_logger(__name__)

router = APIRouter(tags=["Browser"])


# Redis channel helpers
def frame_channel(project_id: str) -> str:
    """Get frame channel name for project."""
    return f"browser:{project_id}:frame"


def event_channel(project_id: str) -> str:
    """Get event channel name for project."""
    return f"browser:{project_id}:event"


def control_channel(project_id: str) -> str:
    """Get control channel name for project."""
    return f"browser:{project_id}:control"


def narration_channel(project_id: str) -> str:
    """Get narration channel name for project."""
    return f"browser:{project_id}:narration"


BROWSER_TASKS_CHANNEL = "browser:tasks"


async def get_project_url(project_id: str, db: AsyncSession) -> str | None:
    """Get the project's primary domain URL."""
    try:
        result = await db.execute(
            select(Domain)
            .where(Domain.project_id == project_id)
            .where(Domain.is_primary == True)
        )
        domain = result.scalar_one_or_none()

        if domain:
            return f"https://{domain.domain_name}"

        # Fall back to first domain if no primary
        result = await db.execute(
            select(Domain)
            .where(Domain.project_id == project_id)
            .limit(1)
        )
        domain = result.scalar_one_or_none()

        if domain:
            return f"https://{domain.domain_name}"

        return None
    except Exception as e:
        logger.warning("Failed to get project URL", project_id=project_id, error=str(e))
        return None


async def get_user_from_token(token: str) -> TokenPayload | None:
    """Validate token for WebSocket authentication."""
    try:
        config = get_api_config()
        auth_service = AuthService(db=None, config=config)  # type: ignore
        return auth_service.verify_token(token)
    except Exception as e:
        logger.warning("Browser WebSocket auth failed", error=str(e))
        return None


class BrowserWebSocketHandler:
    """
    Handles browser WebSocket connections.

    Streams viewport frames from the browser service and forwards
    user commands (navigate, click, type, etc.).
    """

    def __init__(
        self,
        websocket: WebSocket,
        redis: RedisClient,
        user_id: str,
        project_id: str,
        initial_url: str | None = None,
    ):
        self.websocket = websocket
        self.redis = redis
        self.pubsub = PubSubManager(redis)
        self.user_id = user_id
        self.project_id = project_id
        self.initial_url = initial_url
        self._running = False
        self._frame_task: asyncio.Task | None = None
        self._event_task: asyncio.Task | None = None
        self._correlation_counter = 0
        # Track pubsub connections for proper cleanup
        self._frame_pubsub: Any | None = None
        self._event_pubsub: Any | None = None

    async def start(self) -> None:
        """Start handling the WebSocket connection."""
        self._running = True

        # Subscribe to browser channels
        self._frame_task = asyncio.create_task(self._subscribe_frames())
        self._event_task = asyncio.create_task(self._subscribe_events())

        # Notify browser service to start streaming with optional initial URL
        start_message = {
            "type": "start_stream",
            "project_id": self.project_id,
            "user_id": self.user_id,
        }
        if self.initial_url:
            start_message["initial_url"] = self.initial_url

        await self._send_to_browser(start_message)

        logger.info(
            "Browser WebSocket started",
            user_id=self.user_id,
            project_id=self.project_id,
        )

    async def stop(self) -> None:
        """Stop handling the WebSocket connection."""
        self._running = False

        # Cancel subscription tasks
        for task in [self._frame_task, self._event_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Properly close pubsub connections to prevent connection leaks
        for pubsub in [self._frame_pubsub, self._event_pubsub]:
            if pubsub:
                try:
                    await pubsub.unsubscribe()
                    await pubsub.close()
                except Exception as e:
                    logger.warning(
                        "Error closing pubsub connection",
                        error=str(e),
                    )

        self._frame_pubsub = None
        self._event_pubsub = None

        # Notify browser service to stop streaming
        try:
            await self._send_to_browser({
                "type": "stop_stream",
                "project_id": self.project_id,
            })
        except Exception as e:
            logger.warning(
                "Error sending stop_stream",
                error=str(e),
            )

        logger.info(
            "Browser WebSocket stopped",
            user_id=self.user_id,
            project_id=self.project_id,
        )

    async def handle_message(self, data: dict[str, Any]) -> None:
        """
        Handle incoming WebSocket message from client.

        Routes commands to the browser service.
        """
        message_type = data.get("type")

        handlers = {
            "navigate": self._handle_navigate,
            "click": self._handle_click,
            "type": self._handle_type,
            "scroll": self._handle_scroll,
            "screenshot": self._handle_screenshot,
            "resize": self._handle_resize,
            "auth_response": self._handle_auth_response,
            "user_input": self._handle_user_input,
            "close": self._handle_close,
            "refresh": self._handle_refresh,
            "back": self._handle_back,
            "forward": self._handle_forward,
            "set_permissions": self._handle_set_permissions,
            "set_viewport": self._handle_set_viewport,
        }

        handler = handlers.get(message_type)
        if handler:
            await handler(data)
        else:
            logger.warning(
                "Unknown browser message type",
                type=message_type,
                user_id=self.user_id,
            )

    async def _handle_navigate(self, data: dict[str, Any]) -> None:
        """Handle navigation command."""
        url = data.get("url", "")
        if url:
            await self._send_to_browser({
                "type": "navigate",
                "project_id": self.project_id,
                "url": url,
                "wait_until": data.get("wait_until", "load"),
                "correlation_id": self._next_correlation_id(),
            })

    async def _handle_click(self, data: dict[str, Any]) -> None:
        """Handle click command."""
        await self._send_to_browser({
            "type": "click",
            "project_id": self.project_id,
            "x": data.get("x"),
            "y": data.get("y"),
            "selector": data.get("selector"),
            "button": data.get("button", "left"),
            "correlation_id": self._next_correlation_id(),
        })

    async def _handle_type(self, data: dict[str, Any]) -> None:
        """Handle type command."""
        await self._send_to_browser({
            "type": "type",
            "project_id": self.project_id,
            "text": data.get("text", ""),
            "selector": data.get("selector"),
            "clear": data.get("clear", False),
            "correlation_id": self._next_correlation_id(),
        })

    async def _handle_scroll(self, data: dict[str, Any]) -> None:
        """Handle scroll command."""
        await self._send_to_browser({
            "type": "scroll",
            "project_id": self.project_id,
            "delta_x": data.get("deltaX", 0),
            "delta_y": data.get("deltaY", 0),
            "x": data.get("x"),
            "y": data.get("y"),
            "correlation_id": self._next_correlation_id(),
        })

    async def _handle_screenshot(self, data: dict[str, Any]) -> None:
        """Handle screenshot request."""
        await self._send_to_browser({
            "type": "screenshot",
            "project_id": self.project_id,
            "full_page": data.get("full_page", False),
            "correlation_id": self._next_correlation_id(),
        })

    async def _handle_resize(self, data: dict[str, Any]) -> None:
        """Handle viewport resize."""
        # This would require creating a new context with different viewport
        # For now, just acknowledge
        await self.websocket.send_json({
            "type": "resize_ack",
            "width": data.get("width"),
            "height": data.get("height"),
        })

    async def _handle_auth_response(self, data: dict[str, Any]) -> None:
        """Handle authentication decision from user."""
        await self._send_to_browser({
            "type": "auth_response",
            "project_id": self.project_id,
            "decision": data.get("decision"),
            "correlation_id": data.get("correlation_id"),
        })

    async def _handle_user_input(self, data: dict[str, Any]) -> None:
        """Handle user input response to agent prompt."""
        await self._send_to_browser({
            "type": "user_input",
            "project_id": self.project_id,
            "value": data.get("value"),
            "correlation_id": data.get("correlation_id"),
        })

    async def _handle_close(self, data: dict[str, Any]) -> None:
        """Handle close browser command."""
        await self._send_to_browser({
            "type": "close",
            "project_id": self.project_id,
            "correlation_id": self._next_correlation_id(),
        })

    async def _handle_refresh(self, data: dict[str, Any]) -> None:
        """Handle page refresh command."""
        await self._send_to_browser({
            "type": "navigate",
            "project_id": self.project_id,
            "action": "reload",
            "correlation_id": self._next_correlation_id(),
        })

    async def _handle_back(self, data: dict[str, Any]) -> None:
        """Handle back navigation."""
        await self._send_to_browser({
            "type": "navigate",
            "project_id": self.project_id,
            "action": "back",
            "correlation_id": self._next_correlation_id(),
        })

    async def _handle_forward(self, data: dict[str, Any]) -> None:
        """Handle forward navigation."""
        await self._send_to_browser({
            "type": "navigate",
            "project_id": self.project_id,
            "action": "forward",
            "correlation_id": self._next_correlation_id(),
        })

    async def _handle_set_permissions(self, data: dict[str, Any]) -> None:
        """Handle set permissions command."""
        permissions = data.get("permissions", [])
        await self._send_to_browser({
            "type": "set_permissions",
            "project_id": self.project_id,
            "permissions": permissions,
            "correlation_id": self._next_correlation_id(),
        })

    async def _handle_set_viewport(self, data: dict[str, Any]) -> None:
        """Handle set viewport command."""
        await self._send_to_browser({
            "type": "set_viewport",
            "project_id": self.project_id,
            "width": data.get("width", 1280),
            "height": data.get("height", 720),
            "device_scale_factor": data.get("deviceScaleFactor", 1),
            "is_mobile": data.get("isMobile", False),
            "has_touch": data.get("hasTouch", False),
            "correlation_id": self._next_correlation_id(),
        })

    async def _send_to_browser(self, message: dict[str, Any]) -> None:
        """Send command to browser service via Redis."""
        message["timestamp"] = datetime.now(timezone.utc).isoformat()
        message["user_id"] = self.user_id

        await self.redis.publish(
            BROWSER_TASKS_CHANNEL,
            json.dumps(message),
        )

    async def _subscribe_frames(self) -> None:
        """Subscribe to frame updates from browser service."""
        pubsub = None
        try:
            pubsub = self.redis.pubsub()
            self._frame_pubsub = pubsub  # Store for cleanup
            await pubsub.subscribe(frame_channel(self.project_id))

            logger.debug(
                "Subscribed to frame channel",
                project_id=self.project_id,
                channel=frame_channel(self.project_id),
            )

            async for message in pubsub.listen():
                if not self._running:
                    break

                if message["type"] == "message":
                    try:
                        # Parse frame data
                        data = message["data"]
                        if isinstance(data, bytes):
                            data = data.decode("utf-8")

                        # Forward to WebSocket
                        frame_data = eval(data)  # Safe since we control the format
                        await self.websocket.send_json(frame_data)

                    except Exception as e:
                        logger.warning(
                            "Failed to forward frame",
                            error=str(e),
                        )

        except asyncio.CancelledError:
            logger.debug("Frame subscription cancelled", project_id=self.project_id)
        except Exception as e:
            logger.error(
                "Frame subscription error",
                error=str(e),
                project_id=self.project_id,
            )
        finally:
            # Ensure cleanup even if task is cancelled
            if pubsub and pubsub != self._frame_pubsub:
                try:
                    await pubsub.unsubscribe()
                    await pubsub.close()
                except Exception:
                    pass

    async def _subscribe_events(self) -> None:
        """Subscribe to events from browser service."""
        pubsub = None
        try:
            pubsub = self.redis.pubsub()
            self._event_pubsub = pubsub  # Store for cleanup
            channels = [
                event_channel(self.project_id),
                narration_channel(self.project_id),
            ]
            await pubsub.subscribe(*channels)

            logger.debug(
                "Subscribed to event channels",
                project_id=self.project_id,
                channels=channels,
            )

            async for message in pubsub.listen():
                if not self._running:
                    break

                if message["type"] == "message":
                    try:
                        data = message["data"]
                        if isinstance(data, bytes):
                            data = data.decode("utf-8")

                        event_data = json.loads(data)
                        await self.websocket.send_json(event_data)

                    except Exception as e:
                        logger.warning(
                            "Failed to forward event",
                            error=str(e),
                        )

        except asyncio.CancelledError:
            logger.debug("Event subscription cancelled", project_id=self.project_id)
        except Exception as e:
            logger.error(
                "Event subscription error",
                error=str(e),
                project_id=self.project_id,
            )
        finally:
            # Ensure cleanup even if task is cancelled
            if pubsub and pubsub != self._event_pubsub:
                try:
                    await pubsub.unsubscribe()
                    await pubsub.close()
                except Exception:
                    pass

    def _next_correlation_id(self) -> str:
        """Generate next correlation ID."""
        self._correlation_counter += 1
        return f"{self.user_id}:{self.project_id}:{self._correlation_counter}"


@router.websocket("/ws/browser")
async def browser_websocket(
    websocket: WebSocket,
    token: str = Query(...),
    project_id: str = Query(...),
    redis: RedisClient = Depends(get_redis),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Browser viewport streaming WebSocket.

    Receives: navigate, click, type, scroll, screenshot commands
    Sends: frame (base64 screenshot), url_change, console, error, narration

    Authentication via token query parameter.
    """
    # Authenticate
    user = await get_user_from_token(token)
    if not user:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    # Accept connection
    await websocket.accept()

    logger.info(
        "Browser WebSocket connected",
        user_id=user.sub,
        project_id=project_id,
    )

    # Get project's primary URL for initial navigation
    initial_url = await get_project_url(project_id, db)
    if initial_url:
        logger.info(
            "Browser will navigate to project URL",
            project_id=project_id,
            url=initial_url,
        )

    # Create handler
    handler = BrowserWebSocketHandler(
        websocket=websocket,
        redis=redis,
        user_id=user.sub,
        project_id=project_id,
        initial_url=initial_url,
    )

    try:
        # Start handler
        await handler.start()

        # Send initial ready message
        await websocket.send_json({
            "type": "connected",
            "project_id": project_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Handle incoming messages
        while True:
            try:
                data = await websocket.receive_json()
                await handler.handle_message(data)
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid JSON",
                })

    except Exception as e:
        logger.error(
            "Browser WebSocket error",
            user_id=user.sub,
            project_id=project_id,
            error=str(e),
        )

    finally:
        await handler.stop()
        logger.info(
            "Browser WebSocket disconnected",
            user_id=user.sub,
            project_id=project_id,
        )
