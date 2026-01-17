"""
Redis Pub/Sub implementation for real-time messaging.
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import redis.asyncio as redis

from ai_core import get_logger, messages_consumed_total, messages_published_total

from .client import RedisClient

logger = get_logger(__name__)

MessageHandler = Callable[[str, dict[str, Any]], asyncio.coroutine]


@dataclass
class Subscription:
    """Subscription to a channel."""
    channel: str
    handler: MessageHandler
    pattern: bool = False


class PubSubManager:
    """
    Manages Redis Pub/Sub subscriptions.

    Provides:
    - Channel subscriptions
    - Pattern subscriptions
    - Message handlers
    - Graceful shutdown
    """

    def __init__(self, client: RedisClient):
        self._client = client
        self._pubsub: redis.client.PubSub | None = None
        self._subscriptions: dict[str, Subscription] = {}
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the pub/sub listener."""
        if self._running:
            return

        self._pubsub = self._client.client.pubsub()
        self._running = True
        self._task = asyncio.create_task(self._listen())
        logger.info("PubSub manager started")

    async def stop(self) -> None:
        """Stop the pub/sub listener."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._pubsub:
            await self._pubsub.close()
        logger.info("PubSub manager stopped")

    async def subscribe(
        self,
        channel: str,
        handler: MessageHandler,
        pattern: bool = False,
    ) -> None:
        """
        Subscribe to a channel.

        Args:
            channel: Channel name or pattern
            handler: Async function to handle messages
            pattern: If True, treat channel as pattern
        """
        if self._pubsub is None:
            raise RuntimeError("PubSub not started. Call start() first.")

        subscription = Subscription(channel=channel, handler=handler, pattern=pattern)
        self._subscriptions[channel] = subscription

        if pattern:
            await self._pubsub.psubscribe(channel)
            logger.info("Subscribed to pattern", pattern=channel)
        else:
            await self._pubsub.subscribe(channel)
            logger.info("Subscribed to channel", channel=channel)

    async def unsubscribe(self, channel: str, pattern: bool = False) -> None:
        """Unsubscribe from a channel."""
        if self._pubsub is None:
            return

        if channel in self._subscriptions:
            del self._subscriptions[channel]

        if pattern:
            await self._pubsub.punsubscribe(channel)
            logger.info("Unsubscribed from pattern", pattern=channel)
        else:
            await self._pubsub.unsubscribe(channel)
            logger.info("Unsubscribed from channel", channel=channel)

    async def publish(self, channel: str, message: dict[str, Any]) -> int:
        """
        Publish message to channel.

        Args:
            channel: Channel name
            message: Message data (will be JSON serialized)

        Returns:
            Number of subscribers that received the message
        """
        data = json.dumps(message)
        count = await self._client.client.publish(channel, data)
        messages_published_total.labels(channel=channel).inc()
        logger.debug("Published message", channel=channel, subscribers=count)
        return count

    async def _listen(self) -> None:
        """Listen for messages."""
        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if message is not None:
                    await self._handle_message(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in pub/sub listener", error=str(e))
                await asyncio.sleep(1)

    async def _handle_message(self, message: dict[str, Any]) -> None:
        """Handle incoming message."""
        msg_type = message.get("type")
        if msg_type not in ("message", "pmessage"):
            return

        channel = message.get("channel", "")
        if isinstance(channel, bytes):
            channel = channel.decode()

        # For pattern subscriptions, use the pattern as key
        pattern = message.get("pattern")
        if pattern:
            if isinstance(pattern, bytes):
                pattern = pattern.decode()
            subscription = self._subscriptions.get(pattern)
        else:
            subscription = self._subscriptions.get(channel)

        if subscription is None:
            logger.warning("No handler for channel", channel=channel)
            return

        try:
            data = message.get("data", "{}")
            if isinstance(data, bytes):
                data = data.decode()
            parsed = json.loads(data)

            await subscription.handler(channel, parsed)
            messages_consumed_total.labels(channel=channel, status="success").inc()
        except json.JSONDecodeError as e:
            logger.error("Failed to parse message", channel=channel, error=str(e))
            messages_consumed_total.labels(channel=channel, status="error").inc()
        except Exception as e:
            logger.error("Error handling message", channel=channel, error=str(e))
            messages_consumed_total.labels(channel=channel, status="error").inc()


# Predefined channels
class Channels:
    """Standard channel names."""
    TASK_REQUESTS = "ai:tasks:requests"
    TASK_RESPONSES = "ai:tasks:responses"
    AGENT_STATUS = "ai:agents:status"
    AGENT_EVENTS = "ai:agents:events"
    SYSTEM_ALERTS = "ai:system:alerts"
    USER_NOTIFICATIONS = "ai:users:notifications"

    # Pattern for agent-specific channels
    AGENT_PATTERN = "ai:agents:*"
    TASK_PATTERN = "ai:tasks:*"
