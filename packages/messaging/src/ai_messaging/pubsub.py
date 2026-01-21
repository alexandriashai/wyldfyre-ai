"""
Redis Pub/Sub implementation for real-time messaging.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import redis.asyncio as redis

from ai_core import get_logger, messages_consumed_total, messages_published_total

from .client import RedisClient

logger = get_logger(__name__)

# Handler receives message content as a string (JSON)
MessageHandler = Callable[[str], Awaitable[None]]


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

    async def publish(self, channel: str, message: str | dict[str, Any]) -> int:
        """
        Publish message to channel.

        Args:
            channel: Channel name
            message: Message data (string or dict; dicts will be JSON serialized)

        Returns:
            Number of subscribers that received the message
        """
        if isinstance(message, dict):
            data = json.dumps(message)
        else:
            data = message
        count = await self._client.client.publish(channel, data)
        messages_published_total.labels(channel=channel).inc()
        logger.debug("Published message", channel=channel, subscribers=count)
        return count

    async def _listen(self) -> None:
        """Listen for messages using explicit polling with yielding."""
        logger.info("PubSub listener started")
        try:
            while self._running:
                try:
                    # Use short timeout to ensure yielding
                    message = await asyncio.wait_for(
                        self._pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=0.1
                    )

                    if message is not None:
                        # Use create_task to avoid blocking the poll loop
                        asyncio.create_task(self._handle_message(message))

                except asyncio.TimeoutError:
                    pass  # No message available, that's fine

                # Small delay between polls - 0.05s = 20 polls/second
                await asyncio.sleep(0.05)

        except asyncio.CancelledError:
            logger.info("PubSub listener cancelled")
        except Exception as e:
            logger.error("Error in pub/sub listener", error=str(e))

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
            logger.debug(
                "Pattern message received",
                pattern=pattern,
                channel=channel,
                has_subscription=subscription is not None,
            )
        else:
            subscription = self._subscriptions.get(channel)

        if subscription is None:
            logger.warning("No handler for channel", channel=channel)
            return

        try:
            data = message.get("data", "")
            if isinstance(data, bytes):
                data = data.decode()

            # Pass raw string data to handler (handler can parse as needed)
            await subscription.handler(data)
            messages_consumed_total.labels(channel=channel, status="success").inc()
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
