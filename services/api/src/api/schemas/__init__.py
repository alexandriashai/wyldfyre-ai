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
from .domain import (
    DomainCreate,
    DomainResponse,
    DomainUpdate,
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
    # Domain
    "DomainCreate",
    "DomainResponse",
    "DomainUpdate",
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
