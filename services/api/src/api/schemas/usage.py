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
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None


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


# Provider Usage Reconciliation Schemas


class ProviderUsageRecord(BaseModel):
    """Provider-reported usage record."""

    id: str
    provider: str
    report_date: datetime
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: float
    workspace_id: str | None

    class Config:
        from_attributes = True


class ProviderUsageResponse(BaseModel):
    """Provider-reported usage response."""

    records: list[ProviderUsageRecord]
    total: int
    period_start: datetime
    period_end: datetime


class ModelReconciliation(BaseModel):
    """Reconciliation data for a single model."""

    model: str
    local_cost: float
    provider_cost: float
    difference: float
    difference_percentage: float
    local_input_tokens: int
    local_output_tokens: int
    provider_input_tokens: int
    provider_output_tokens: int


class ReconciliationResponse(BaseModel):
    """Local vs provider cost reconciliation response."""

    period_start: datetime
    period_end: datetime
    local_total: float
    provider_total: float
    total_difference: float
    total_difference_percentage: float
    by_model: list[ModelReconciliation]


class ProviderSyncStatus(BaseModel):
    """Sync status for a single provider."""

    configured: bool
    last_sync: dict | None = None


class SyncStatusResponse(BaseModel):
    """Sync configuration and status response."""

    anthropic: ProviderSyncStatus
    openai: ProviderSyncStatus


class SyncResult(BaseModel):
    """Result of a sync operation for a provider."""

    configured: bool
    success: bool | None = None
    records_synced: int | None = None
    duration_seconds: float | None = None
    error: str | None = None


class SyncResponse(BaseModel):
    """Response from manual sync trigger."""

    anthropic: SyncResult
    openai: SyncResult
    message: str
