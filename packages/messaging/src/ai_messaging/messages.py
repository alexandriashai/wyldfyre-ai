"""
Message schemas for inter-service communication.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


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


class AgentType(str, Enum):
    """Types of agents in the system."""
    SUPERVISOR = "supervisor"
    CODE = "code"
    DATA = "data"
    INFRA = "infra"
    RESEARCH = "research"
    QA = "qa"


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentStatus(str, Enum):
    """Agent operational status."""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


class BaseMessage(BaseModel):
    """Base message with common fields."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: MessageType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: str | None = None
    source: str | None = None


class TaskRequest(BaseMessage):
    """Request to execute a task."""
    type: MessageType = MessageType.TASK_REQUEST
    task_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    target_agent: AgentType | None = None
    priority: int = Field(default=5, ge=1, le=10)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseMessage):
    """Response from task execution."""
    type: MessageType = MessageType.TASK_RESPONSE
    task_id: str
    status: TaskStatus
    result: dict[str, Any] | None = None
    error: str | None = None
    agent_type: AgentType
    duration_ms: int | None = None


class TaskProgress(BaseMessage):
    """Progress update for a task."""
    type: MessageType = MessageType.TASK_PROGRESS
    task_id: str
    progress_percent: int = Field(ge=0, le=100)
    message: str | None = None
    agent_type: AgentType


class AgentStatusMessage(BaseMessage):
    """Agent status update."""
    type: MessageType = MessageType.AGENT_STATUS
    agent_type: AgentType
    status: AgentStatus
    current_task_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentHeartbeat(BaseMessage):
    """Agent heartbeat message."""
    type: MessageType = MessageType.AGENT_HEARTBEAT
    agent_type: AgentType
    status: AgentStatus
    uptime_seconds: int
    tasks_completed: int = 0
    memory_usage_mb: float | None = None
    cpu_percent: float | None = None


class ToolCall(BaseMessage):
    """Tool call by an agent."""
    type: MessageType = MessageType.AGENT_TOOL_CALL
    agent_type: AgentType
    task_id: str
    tool_name: str
    tool_input: dict[str, Any]


class ToolResult(BaseMessage):
    """Result of a tool call."""
    type: MessageType = MessageType.AGENT_TOOL_RESULT
    agent_type: AgentType
    task_id: str
    tool_name: str
    success: bool
    output: Any | None = None
    error: str | None = None
    duration_ms: int


class SystemAlert(BaseMessage):
    """System-level alert."""
    type: MessageType = MessageType.SYSTEM_ALERT
    severity: str  # info, warning, error, critical
    title: str
    message: str
    component: str | None = None


class UserNotification(BaseMessage):
    """Notification for a user."""
    type: MessageType = MessageType.USER_NOTIFICATION
    user_id: str
    title: str
    message: str
    notification_type: str  # info, success, warning, error
    action_url: str | None = None
