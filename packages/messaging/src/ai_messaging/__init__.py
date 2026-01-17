"""
AI Messaging Package - Redis-based messaging for AI Infrastructure.

This package provides inter-service communication:
- Redis client wrapper
- Pub/Sub for real-time messaging
- Message bus for request/response patterns
- Message schemas
"""

from .bus import MessageBus
from .client import RedisClient, get_redis_client, redis_client_context
from .messages import (
    AgentHeartbeat,
    AgentStatus,
    AgentStatusMessage,
    AgentType,
    BaseMessage,
    MessageType,
    SystemAlert,
    TaskProgress,
    TaskRequest,
    TaskResponse,
    TaskStatus,
    ToolCall,
    ToolResult,
    UserNotification,
)
from .pubsub import Channels, PubSubManager

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Client
    "RedisClient",
    "get_redis_client",
    "redis_client_context",
    # PubSub
    "PubSubManager",
    "Channels",
    # Message Bus
    "MessageBus",
    # Messages
    "BaseMessage",
    "MessageType",
    "AgentType",
    "TaskStatus",
    "AgentStatus",
    "TaskRequest",
    "TaskResponse",
    "TaskProgress",
    "AgentStatusMessage",
    "AgentHeartbeat",
    "ToolCall",
    "ToolResult",
    "SystemAlert",
    "UserNotification",
]
