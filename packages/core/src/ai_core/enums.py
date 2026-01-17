"""
Shared enumerations for AI Infrastructure.

These enums are used across multiple packages to ensure consistency.
"""

from enum import Enum


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentType(str, Enum):
    """Types of agents in the system."""
    SUPERVISOR = "supervisor"
    CODE = "code"
    DATA = "data"
    INFRA = "infra"
    RESEARCH = "research"
    QA = "qa"


class AgentStatus(str, Enum):
    """Agent operational status."""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


class MessageType(str, Enum):
    """Types of messages in the system."""
    # Task messages
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    TASK_PROGRESS = "task_progress"
    TASK_ERROR = "task_error"
    TASK_CANCELLED = "task_cancelled"

    # Agent messages
    AGENT_STATUS = "agent_status"
    AGENT_HEARTBEAT = "agent_heartbeat"
    AGENT_TOOL_CALL = "agent_tool_call"
    AGENT_TOOL_RESULT = "agent_tool_result"

    # System messages
    SYSTEM_ALERT = "system_alert"
    SYSTEM_SHUTDOWN = "system_shutdown"

    # User messages
    USER_NOTIFICATION = "user_notification"
    USER_CHAT = "user_chat"


class DomainStatus(str, Enum):
    """Domain provisioning status."""
    PENDING = "pending"
    DNS_CONFIGURED = "dns_configured"
    SSL_PENDING = "ssl_pending"
    ACTIVE = "active"
    ERROR = "error"
    SUSPENDED = "suspended"
