"""
Message bus for request/response and event-driven communication.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from ai_core import get_logger, message_processing_duration_seconds, message_queue_length

from .client import RedisClient
from .messages import BaseMessage, MessageType, TaskRequest, TaskResponse

logger = get_logger(__name__)

Handler = Callable[[BaseMessage], Awaitable[None]]


@dataclass
class PendingRequest:
    """Tracks a pending request waiting for response."""
    request_id: str
    future: asyncio.Future
    timeout: float
    created_at: float


class MessageBus:
    """
    Message bus for inter-service communication.

    Provides:
    - Request/response pattern with correlation
    - Event publishing and subscription
    - Timeout handling
    - Dead letter queue
    """

    def __init__(self, client: RedisClient, service_name: str):
        self._client = client
        self._service_name = service_name
        self._handlers: dict[MessageType, list[Handler]] = {}
        self._pending_requests: dict[str, PendingRequest] = {}
        self._running = False
        self._consumer_task: asyncio.Task | None = None

        # Stream names
        self._request_stream = f"ai:bus:{service_name}:requests"
        self._response_stream = f"ai:bus:{service_name}:responses"
        self._event_stream = "ai:bus:events"
        self._dlq_stream = "ai:bus:dlq"

    async def start(self) -> None:
        """Start the message bus consumer."""
        if self._running:
            return

        self._running = True
        self._consumer_task = asyncio.create_task(self._consume_messages())
        logger.info("Message bus started", service=self._service_name)

    async def stop(self) -> None:
        """Stop the message bus consumer."""
        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

        # Cancel pending requests
        for pending in self._pending_requests.values():
            if not pending.future.done():
                pending.future.cancel()

        logger.info("Message bus stopped", service=self._service_name)

    def register_handler(self, message_type: MessageType, handler: Handler) -> None:
        """Register a handler for a message type."""
        if message_type not in self._handlers:
            self._handlers[message_type] = []
        self._handlers[message_type].append(handler)
        logger.debug("Registered handler", message_type=message_type.value)

    async def send_request(
        self,
        target_service: str,
        request: TaskRequest,
        timeout: float = 30.0,
    ) -> TaskResponse:
        """
        Send request and wait for response.

        Args:
            target_service: Target service name
            request: Task request
            timeout: Response timeout in seconds

        Returns:
            Task response

        Raises:
            asyncio.TimeoutError: If response not received within timeout
        """
        # Set correlation ID
        request.correlation_id = request.id
        request.source = self._service_name

        # Create future for response
        future: asyncio.Future[TaskResponse] = asyncio.Future()
        pending = PendingRequest(
            request_id=request.id,
            future=future,
            timeout=timeout,
            created_at=asyncio.get_event_loop().time(),
        )
        self._pending_requests[request.id] = pending

        # Send request to target service stream
        target_stream = f"ai:bus:{target_service}:requests"
        await self._client.xadd(
            target_stream,
            {"data": request.model_dump_json()},
            maxlen=10000,
        )

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                "Request timed out",
                request_id=request.id,
                target=target_service,
            )
            raise
        finally:
            self._pending_requests.pop(request.id, None)

    async def send_response(self, response: TaskResponse) -> None:
        """Send response to a request."""
        if not response.correlation_id:
            logger.error("Response missing correlation_id")
            return

        # Send to requester's response stream
        # The correlation_id contains info about the original requester
        await self._client.xadd(
            self._response_stream,
            {"data": response.model_dump_json()},
            maxlen=10000,
        )

    async def publish_event(self, event: BaseMessage) -> None:
        """Publish an event to all subscribers."""
        event.source = self._service_name
        await self._client.xadd(
            self._event_stream,
            {
                "type": event.type.value,
                "data": event.model_dump_json(),
            },
            maxlen=50000,
        )

    async def _consume_messages(self) -> None:
        """Consume messages from streams."""
        last_id = "$"  # Start from new messages
        response_last_id = "$"

        while self._running:
            try:
                # Read from request and response streams
                streams = {
                    self._request_stream: last_id,
                    self._response_stream: response_last_id,
                }

                messages = await self._client.xread(
                    streams,
                    count=10,
                    block=1000,
                )

                if not messages:
                    continue

                for stream_name, stream_messages in messages:
                    for msg_id, msg_data in stream_messages:
                        if stream_name == self._request_stream:
                            last_id = msg_id
                            await self._handle_request(msg_data)
                        elif stream_name == self._response_stream:
                            response_last_id = msg_id
                            await self._handle_response(msg_data)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error consuming messages", error=str(e))
                await asyncio.sleep(1)

    async def _handle_request(self, data: dict[str, Any]) -> None:
        """Handle incoming request."""
        try:
            raw = data.get("data", "{}")
            parsed = json.loads(raw)
            message_type = MessageType(parsed.get("type"))

            handlers = self._handlers.get(message_type, [])
            if not handlers:
                logger.warning("No handler for message type", type=message_type.value)
                return

            # Reconstruct message based on type
            request = TaskRequest.model_validate(parsed)

            for handler in handlers:
                try:
                    await handler(request)
                except Exception as e:
                    logger.error(
                        "Handler error",
                        message_type=message_type.value,
                        error=str(e),
                    )

        except Exception as e:
            logger.error("Failed to handle request", error=str(e))
            # Move to DLQ
            await self._client.xadd(
                self._dlq_stream,
                {"data": json.dumps(data), "error": str(e)},
                maxlen=10000,
            )

    async def _handle_response(self, data: dict[str, Any]) -> None:
        """Handle incoming response."""
        try:
            raw = data.get("data", "{}")
            parsed = json.loads(raw)
            response = TaskResponse.model_validate(parsed)

            # Find pending request
            correlation_id = response.correlation_id
            if correlation_id and correlation_id in self._pending_requests:
                pending = self._pending_requests[correlation_id]
                if not pending.future.done():
                    pending.future.set_result(response)

        except Exception as e:
            logger.error("Failed to handle response", error=str(e))
