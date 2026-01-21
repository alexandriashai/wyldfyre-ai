"""
API Usage schemas.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from ai_core import AgentType


class ModelBreakdown(BaseModel):
    """Cost breakdown by model."""

    model: str
    cost: float
    percentage: float


class AgentBreakdown(BaseModel):
    """Cost breakdown by agent type."""

    agent_type: str
    cost: float
    percentage: float


class DailySummaryResponse(BaseModel):
    """Daily usage summary response."""

    total_cost: float
    total_input_tokens: int
    total_output_tokens: int
    total_cached_tokens: int
    request_count: int
    period_start: datetime
    period_end: datetime
    breakdown_by_model: list[ModelBreakdown]
    breakdown_by_agent: list[AgentBreakdown]


class UsageByAgentResponse(BaseModel):
    """Usage breakdown by agent type response."""

    period_days: int
    total_cost: float
    breakdown: list[AgentBreakdown]


class DailyUsagePoint(BaseModel):
    """Single day usage point for charting."""

    date: str  # ISO date string
    cost: float
    tokens: int
    requests: int


class UsageHistoryResponse(BaseModel):
    """Usage history for charting."""

    period_days: int
    total_cost: float
    total_tokens: int
    total_requests: int
    daily_data: list[DailyUsagePoint]


class BudgetAlertResponse(BaseModel):
    """Budget alert status response."""

    id: str
    name: str
    description: str | None
    threshold_amount: float
    period: str
    current_spend: float
    percentage_used: float
    is_exceeded: bool
    is_active: bool
    last_triggered_at: datetime | None
    trigger_count: int

    class Config:
        from_attributes = True


class BudgetStatusResponse(BaseModel):
    """Overall budget status response."""

    daily_spend: float
    daily_limit: float
    daily_percentage: float
    hourly_rate: float
    projected_daily: float
    alerts: list[BudgetAlertResponse]


class UsageRecordResponse(BaseModel):
    """Individual usage record response."""

    id: str
    provider: str
    model: str
    usage_type: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_total: float
    agent_type: str | None
    agent_name: str | None
    task_id: str | None
    correlation_id: str | None
    latency_ms: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class UsageListResponse(BaseModel):
    """Paginated usage records response."""

    records: list[UsageRecordResponse]
    total: int
    page: int
    page_size: int
