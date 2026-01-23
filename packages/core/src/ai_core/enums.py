"""
Shared enumerations for AI Infrastructure.

These enums are used across multiple packages to ensure consistency.
"""

from enum import Enum


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"  # Alias for backwards compatibility
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
    PROVISIONING = "provisioning"  # Domain is being provisioned
    DNS_CONFIGURED = "dns_configured"
    SSL_PENDING = "ssl_pending"
    ACTIVE = "active"
    ERROR = "error"
    SUSPENDED = "suspended"


class PermissionLevel(int, Enum):
    """
    Agent permission levels (0-4).

    Higher levels can access all tools from lower levels.
    """

    READ_ONLY = 0  # View status, query info
    READ_WRITE = 1  # Create/modify files in workspace
    EXECUTE = 2  # Run commands, scripts, processes
    ADMIN = 3  # System configs, packages, services
    SUPERUSER = 4  # Full system access, permissions, elevation grants


class CapabilityCategory(str, Enum):
    """
    Categories of tool capabilities.

    Used to group related permissions and enable fine-grained access control.
    """

    SYSTEM = "system"  # Shell, processes, packages, services
    FILE = "file"  # File read/write/delete/permissions
    NETWORK = "network"  # HTTP, DNS, ports, connectivity
    DATABASE = "database"  # SQL, Redis, Qdrant operations
    DOCKER = "docker"  # Container management
    GIT = "git"  # Version control operations
    SECURITY = "security"  # Authentication, secrets, scanning
    MONITORING = "monitoring"  # Metrics, logs, alerts
    CODE = "code"  # Code analysis, testing, refactoring
    DATA = "data"  # Data processing, ETL, backups
    WEB = "web"  # Web scraping, API calls, research


class ElevationReason(str, Enum):
    """
    Reasons for requesting permission elevation.

    Used for audit logging and approval workflows.
    """

    TOOL_REQUIREMENT = "tool_requirement"  # Tool requires higher level
    TASK_ESCALATION = "task_escalation"  # Task complexity requires more access
    USER_REQUEST = "user_request"  # User explicitly requested action
    EMERGENCY = "emergency"  # Critical issue requires immediate action
    SUPERVISOR_DELEGATION = "supervisor_delegation"  # Supervisor authorized action
