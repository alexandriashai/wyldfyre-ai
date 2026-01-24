"""
Collaboration tools for agent-to-agent communication.

These tools enable:
- Notifying users of important events
- Requesting help from other agents
- Broadcasting status updates
"""

from datetime import datetime, timezone
from typing import Any

from ai_core import get_logger, get_settings
from ai_messaging import PubSubManager, RedisClient

from ..tools import ToolResult, tool

logger = get_logger(__name__)


async def _get_pubsub() -> tuple[PubSubManager, RedisClient]:
    """Get a connected PubSub manager and its underlying Redis client.

    Returns both so the caller can properly close the Redis connection.
    """
    settings = get_settings()
    redis = RedisClient(settings.redis)
    await redis.connect()
    return PubSubManager(redis), redis


@tool(
    name="notify_user",
    description="""Send a notification to the user via WebSocket.
    Use this for important updates, warnings, or completion messages that should appear in the UI.""",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Notification title",
            },
            "message": {
                "type": "string",
                "description": "Notification message content",
            },
            "notification_type": {
                "type": "string",
                "enum": ["info", "success", "warning", "error"],
                "description": "Type of notification",
                "default": "info",
            },
            "user_id": {
                "type": "string",
                "description": "Target user ID (required for delivery)",
            },
        },
        "required": ["title", "message", "user_id"],
    },
)
async def notify_user(
    title: str,
    message: str,
    user_id: str,
    notification_type: str = "info",
) -> ToolResult:
    """Send notification to user."""
    redis = None
    try:
        pubsub, redis = await _get_pubsub()

        await pubsub.publish(
            channel="agent:responses",
            message={
                "type": "notification",
                "user_id": user_id,
                "title": title,
                "message": message,
                "notification_type": notification_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return ToolResult.ok({
            "message": "Notification sent",
            "title": title,
            "user_id": user_id,
        })

    except Exception as e:
        logger.error("Notify user failed", error=str(e))
        return ToolResult.fail(f"Notify user failed: {e}")
    finally:
        if redis:
            await redis.close()


@tool(
    name="request_agent_help",
    description="""Request help from another specialized agent.
    Use this when a task requires expertise from a different agent type.
    The request will be routed through the supervisor.""",
    parameters={
        "type": "object",
        "properties": {
            "target_agent": {
                "type": "string",
                "enum": ["code", "data", "infra", "research", "qa"],
                "description": "The agent to request help from",
            },
            "task_description": {
                "type": "string",
                "description": "Description of what help is needed",
            },
            "task_context": {
                "type": "object",
                "description": "Additional context to pass to the target agent",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "normal", "high", "urgent"],
                "description": "Request priority",
                "default": "normal",
            },
        },
        "required": ["target_agent", "task_description"],
    },
)
async def request_agent_help(
    target_agent: str,
    task_description: str,
    task_context: dict[str, Any] | None = None,
    priority: str = "normal",
) -> ToolResult:
    """Request help from another agent."""
    redis = None
    try:
        pubsub, redis = await _get_pubsub()

        priority_map = {"low": 3, "normal": 5, "high": 7, "urgent": 9}

        await pubsub.publish(
            channel="agent:supervisor:tasks",
            message={
                "type": "task_request",
                "task_type": "agent_collaboration",
                "payload": {
                    "target_agent": target_agent,
                    "task_description": task_description,
                    "context": task_context or {},
                    "requesting_agent": "unknown",  # Will be filled by caller
                },
                "priority": priority_map.get(priority, 5),
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "collaboration_request": True,
                },
            },
        )

        return ToolResult.ok({
            "message": f"Help request sent to {target_agent} agent",
            "target_agent": target_agent,
            "task_description": task_description,
            "priority": priority,
        })

    except Exception as e:
        logger.error("Request agent help failed", error=str(e))
        return ToolResult.fail(f"Request agent help failed: {e}")
    finally:
        if redis:
            await redis.close()


@tool(
    name="broadcast_status",
    description="""Broadcast a status update to all listeners (other agents and the UI).
    Use this to communicate progress, state changes, or important milestones.""",
    parameters={
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "Status message",
            },
            "agent": {
                "type": "string",
                "description": "Agent name broadcasting the status",
            },
            "phase": {
                "type": "string",
                "enum": ["starting", "working", "waiting", "completing", "error"],
                "description": "Current phase of work",
            },
            "progress": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Progress percentage (0-100)",
            },
            "details": {
                "type": "object",
                "description": "Additional status details",
            },
        },
        "required": ["status", "agent"],
    },
)
async def broadcast_status(
    status: str,
    agent: str,
    phase: str | None = None,
    progress: int | None = None,
    details: dict[str, Any] | None = None,
) -> ToolResult:
    """Broadcast status update."""
    redis = None
    try:
        pubsub, redis = await _get_pubsub()

        message = {
            "type": "status",
            "agent": agent,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if phase:
            message["phase"] = phase
        if progress is not None:
            message["progress"] = progress
        if details:
            message["details"] = details

        await pubsub.publish(
            channel="agent:status",
            message=message,
        )

        return ToolResult.ok({
            "message": "Status broadcast sent",
            "agent": agent,
            "status": status,
        })

    except Exception as e:
        logger.error("Broadcast status failed", error=str(e))
        return ToolResult.fail(f"Broadcast status failed: {e}")
    finally:
        if redis:
            await redis.close()
