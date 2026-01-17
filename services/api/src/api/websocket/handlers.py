"""
WebSocket message handlers.
"""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ai_core import get_logger
from ai_messaging import MessageBus, RedisClient

from .manager import Connection, ConnectionManager

logger = get_logger(__name__)


class MessageHandler:
    """
    Handles incoming WebSocket messages and routes them appropriately.
    """

    def __init__(
        self,
        manager: ConnectionManager,
        redis: RedisClient,
    ):
        self.manager = manager
        self.redis = redis
        self.message_bus = MessageBus(redis)

    async def handle_message(
        self,
        connection: Connection,
        data: dict[str, Any],
    ) -> None:
        """
        Route incoming message to appropriate handler.

        Args:
            connection: The WebSocket connection
            data: Parsed message data
        """
        message_type = data.get("type", "chat")

        handlers = {
            "chat": self._handle_chat_message,
            "ping": self._handle_ping,
            "typing": self._handle_typing,
            "subscribe": self._handle_subscribe,
            "unsubscribe": self._handle_unsubscribe,
        }

        handler = handlers.get(message_type)
        if handler:
            try:
                await handler(connection, data)
            except Exception as e:
                logger.error(
                    "Message handler error",
                    type=message_type,
                    error=str(e),
                )
                await self._send_error(connection, str(e))
        else:
            logger.warning("Unknown message type", type=message_type)
            await self._send_error(connection, f"Unknown message type: {message_type}")

    async def _handle_chat_message(
        self,
        connection: Connection,
        data: dict[str, Any],
    ) -> None:
        """
        Handle chat message from user.

        Routes the message to the supervisor agent via Redis.
        """
        content = data.get("content", "").strip()
        conversation_id = data.get("conversation_id")

        if not content:
            await self._send_error(connection, "Message content is required")
            return

        if not conversation_id:
            await self._send_error(connection, "Conversation ID is required")
            return

        # Generate message ID
        message_id = str(uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        # Store message in Redis
        msg_key = f"message:{message_id}"
        await self.redis.hset(
            msg_key,
            mapping={
                "id": message_id,
                "conversation_id": conversation_id,
                "user_id": connection.user_id,
                "role": "user",
                "content": content,
                "timestamp": timestamp,
            },
        )

        # Add to conversation message list
        conv_msgs_key = f"conversation:{conversation_id}:messages"
        await self.redis.lpush(conv_msgs_key, message_id)

        # Update conversation
        conv_key = f"conversation:{conversation_id}"
        await self.redis.hset(conv_key, "updated_at", timestamp)
        await self.redis.hincrby(conv_key, "message_count", 1)

        # Send acknowledgment to user
        await self.manager.send_personal(
            connection.user_id,
            {
                "type": "message_ack",
                "message_id": message_id,
                "conversation_id": conversation_id,
                "timestamp": timestamp,
            },
        )

        # Route to supervisor agent
        correlation_id = str(uuid4())

        await self.message_bus.publish(
            channel="supervisor:tasks",
            message={
                "type": "task_request",
                "correlation_id": correlation_id,
                "user_id": connection.user_id,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "content": content,
                "timestamp": timestamp,
            },
        )

        logger.info(
            "Chat message routed to supervisor",
            message_id=message_id,
            correlation_id=correlation_id,
            user_id=connection.user_id,
        )

    async def _handle_ping(
        self,
        connection: Connection,
        data: dict[str, Any],
    ) -> None:
        """Handle ping/heartbeat message."""
        await connection.websocket.send_json({
            "type": "pong",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def _handle_typing(
        self,
        connection: Connection,
        data: dict[str, Any],
    ) -> None:
        """Handle typing indicator (for future multi-user chat)."""
        conversation_id = data.get("conversation_id")
        if conversation_id:
            # Could broadcast to other users in the conversation
            pass

    async def _handle_subscribe(
        self,
        connection: Connection,
        data: dict[str, Any],
    ) -> None:
        """Handle subscription to specific events."""
        channels = data.get("channels", [])
        # Store subscription info for this connection
        # Implementation depends on subscription model
        await connection.websocket.send_json({
            "type": "subscribed",
            "channels": channels,
        })

    async def _handle_unsubscribe(
        self,
        connection: Connection,
        data: dict[str, Any],
    ) -> None:
        """Handle unsubscription from events."""
        channels = data.get("channels", [])
        await connection.websocket.send_json({
            "type": "unsubscribed",
            "channels": channels,
        })

    async def _send_error(
        self,
        connection: Connection,
        error: str,
    ) -> None:
        """Send error message to connection."""
        try:
            await connection.websocket.send_json({
                "type": "error",
                "error": error,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.warning("Failed to send error", error=str(e))


class AgentResponseHandler:
    """
    Handles responses from agents and routes them to WebSocket clients.

    Listens to Redis pub/sub for agent responses and streams them to users.
    """

    def __init__(
        self,
        manager: ConnectionManager,
        redis: RedisClient,
    ):
        self.manager = manager
        self.redis = redis
        self._running = False

    async def start(self) -> None:
        """Start listening for agent responses."""
        self._running = True
        logger.info("Agent response handler started")

        # Subscribe to agent response channels
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("agent:responses")

        try:
            while self._running:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )

                if message and message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await self._handle_agent_response(data)
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON in agent response")
                    except Exception as e:
                        logger.error("Error handling agent response", error=str(e))

        finally:
            await pubsub.unsubscribe("agent:responses")
            logger.info("Agent response handler stopped")

    async def stop(self) -> None:
        """Stop listening for agent responses."""
        self._running = False

    async def _handle_agent_response(self, data: dict[str, Any]) -> None:
        """Process an agent response and route to user."""
        user_id = data.get("user_id")
        if not user_id:
            return

        response_type = data.get("type", "response")

        if response_type == "token":
            # Streaming token
            await self.manager.send_personal(
                user_id,
                {
                    "type": "token",
                    "conversation_id": data.get("conversation_id"),
                    "message_id": data.get("message_id"),
                    "token": data.get("token"),
                    "agent": data.get("agent"),
                },
            )

        elif response_type == "response":
            # Complete response
            await self.manager.send_personal(
                user_id,
                {
                    "type": "message",
                    "conversation_id": data.get("conversation_id"),
                    "message_id": data.get("message_id"),
                    "content": data.get("content"),
                    "agent": data.get("agent"),
                    "timestamp": data.get("timestamp"),
                },
            )

        elif response_type == "status":
            # Agent status update
            await self.manager.send_personal(
                user_id,
                {
                    "type": "agent_status",
                    "agent": data.get("agent"),
                    "status": data.get("status"),
                    "task": data.get("task"),
                },
            )

        elif response_type == "error":
            # Error from agent
            await self.manager.send_personal(
                user_id,
                {
                    "type": "error",
                    "conversation_id": data.get("conversation_id"),
                    "error": data.get("error"),
                    "agent": data.get("agent"),
                },
            )
