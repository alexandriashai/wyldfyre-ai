"""
API request/response schemas.
"""

from .auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RegisterRequest,
    UpdatePasswordRequest,
    UpdateProfileRequest,
    UserResponse,
)
from .common import (
    ErrorResponse,
    PaginatedResponse,
    SuccessResponse,
)
from .conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
    ConversationWithMessagesResponse,
    MessageResponse,
    PlanUpdate,
)
from .domain import (
    DomainCreate,
    DomainResponse,
    DomainUpdate,
)
from .project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
    ProjectWithStatsResponse,
)
from .task import (
    TaskResponse,
    TaskListResponse,
)
from .usage import (
    AgentBreakdown,
    BudgetAlertResponse,
    BudgetStatusResponse,
    DailySummaryResponse,
    DailyUsagePoint,
    ModelBreakdown,
    UsageByAgentResponse,
    UsageHistoryResponse,
    UsageListResponse,
    UsageRecordResponse,
)

__all__ = [
    # Auth
    "LoginRequest",
    "LoginResponse",
    "RefreshRequest",
    "RegisterRequest",
    "UpdatePasswordRequest",
    "UpdateProfileRequest",
    "UserResponse",
    # Common
    "ErrorResponse",
    "PaginatedResponse",
    "SuccessResponse",
    # Conversation
    "ConversationCreate",
    "ConversationListResponse",
    "ConversationResponse",
    "ConversationUpdate",
    "ConversationWithMessagesResponse",
    "MessageResponse",
    "PlanUpdate",
    # Domain
    "DomainCreate",
    "DomainResponse",
    "DomainUpdate",
    # Project
    "ProjectCreate",
    "ProjectListResponse",
    "ProjectResponse",
    "ProjectUpdate",
    "ProjectWithStatsResponse",
    # Task
    "TaskResponse",
    "TaskListResponse",
    # Usage
    "AgentBreakdown",
    "BudgetAlertResponse",
    "BudgetStatusResponse",
    "DailySummaryResponse",
    "DailyUsagePoint",
    "ModelBreakdown",
    "UsageByAgentResponse",
    "UsageHistoryResponse",
    "UsageListResponse",
    "UsageRecordResponse",
]
