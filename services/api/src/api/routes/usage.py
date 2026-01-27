"""
Usage analytics routes for token and cost tracking.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import AgentType, get_cost_tracker, get_logger

from ..database import get_db_session
from ..dependencies import CurrentUserDep
from ..schemas.usage import (
    AgentBreakdown,
    BudgetAlertResponse,
    BudgetStatusResponse,
    DailySummaryResponse,
    DailyUsagePoint,
    ModelBreakdown,
    ModelReconciliation,
    ProviderSyncStatus,
    ProviderUsageRecord,
    ProviderUsageResponse,
    ReconciliationResponse,
    SyncResponse,
    SyncResult,
    SyncStatusResponse,
    UsageByAgentResponse,
    UsageHistoryResponse,
    UsageListResponse,
    UsageRecordResponse,
)
from ..services.usage_sync_service import get_usage_sync_service

logger = get_logger(__name__)

router = APIRouter(prefix="/usage", tags=["Usage Analytics"])


@router.get("/daily", response_model=DailySummaryResponse)
async def get_daily_summary(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    date: datetime | None = Query(None, description="Date for summary (defaults to today)"),
) -> DailySummaryResponse:
    """
    Get usage summary for a specific day.

    Returns token counts, costs, and breakdowns by model and agent.
    """
    from database.models import APIUsage

    if date is None:
        date = datetime.now(timezone.utc)

    # Start and end of day
    day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    # Main aggregation query
    stmt = select(
        func.coalesce(func.sum(APIUsage.cost_total), 0).label("total_cost"),
        func.coalesce(func.sum(APIUsage.input_tokens), 0).label("total_input"),
        func.coalesce(func.sum(APIUsage.output_tokens), 0).label("total_output"),
        func.coalesce(func.sum(APIUsage.cached_tokens), 0).label("total_cached"),
        func.count(APIUsage.id).label("request_count"),
    ).where(
        APIUsage.created_at >= day_start,
        APIUsage.created_at < day_end,
    )

    result = await db.execute(stmt)
    row = result.first()

    total_cost = float(row.total_cost) if row else 0.0

    # Model breakdown
    model_stmt = (
        select(
            APIUsage.model,
            func.sum(APIUsage.cost_total).label("cost"),
        )
        .where(
            APIUsage.created_at >= day_start,
            APIUsage.created_at < day_end,
        )
        .group_by(APIUsage.model)
        .order_by(func.sum(APIUsage.cost_total).desc())
    )
    model_result = await db.execute(model_stmt)
    breakdown_by_model = [
        ModelBreakdown(
            model=r.model,
            cost=float(r.cost),
            percentage=float(r.cost) / total_cost * 100 if total_cost > 0 else 0,
        )
        for r in model_result
    ]

    # Agent breakdown
    agent_stmt = (
        select(
            APIUsage.agent_type,
            func.sum(APIUsage.cost_total).label("cost"),
        )
        .where(
            APIUsage.created_at >= day_start,
            APIUsage.created_at < day_end,
        )
        .group_by(APIUsage.agent_type)
        .order_by(func.sum(APIUsage.cost_total).desc())
    )
    agent_result = await db.execute(agent_stmt)
    breakdown_by_agent = [
        AgentBreakdown(
            agent_type=r.agent_type.value if r.agent_type else "unknown",
            cost=float(r.cost),
            percentage=float(r.cost) / total_cost * 100 if total_cost > 0 else 0,
        )
        for r in agent_result
    ]

    return DailySummaryResponse(
        total_cost=total_cost,
        total_input_tokens=row.total_input if row else 0,
        total_output_tokens=row.total_output if row else 0,
        total_cached_tokens=row.total_cached if row else 0,
        request_count=row.request_count if row else 0,
        period_start=day_start,
        period_end=day_end,
        breakdown_by_model=breakdown_by_model,
        breakdown_by_agent=breakdown_by_agent,
    )


@router.get("/by-agent", response_model=UsageByAgentResponse)
async def get_usage_by_agent(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
) -> UsageByAgentResponse:
    """
    Get usage breakdown by agent type for the specified period.
    """
    from database.models import APIUsage

    since = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = (
        select(
            APIUsage.agent_type,
            func.sum(APIUsage.cost_total).label("total_cost"),
        )
        .where(APIUsage.created_at >= since)
        .group_by(APIUsage.agent_type)
        .order_by(func.sum(APIUsage.cost_total).desc())
    )

    result = await db.execute(stmt)
    rows = list(result.all())

    total_cost = sum(float(r.total_cost) for r in rows)

    breakdown = [
        AgentBreakdown(
            agent_type=r.agent_type.value if r.agent_type else "unknown",
            cost=float(r.total_cost),
            percentage=float(r.total_cost) / total_cost * 100 if total_cost > 0 else 0,
        )
        for r in rows
    ]

    return UsageByAgentResponse(
        period_days=days,
        total_cost=total_cost,
        breakdown=breakdown,
    )


@router.get("/history", response_model=UsageHistoryResponse)
async def get_usage_history(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
) -> UsageHistoryResponse:
    """
    Get daily usage history for charting.
    """
    from sqlalchemy import cast
    from sqlalchemy.types import Date

    from database.models import APIUsage

    since = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = (
        select(
            cast(APIUsage.created_at, Date).label("date"),
            func.sum(APIUsage.cost_total).label("total_cost"),
            func.sum(
                APIUsage.input_tokens + APIUsage.output_tokens + APIUsage.cached_tokens
            ).label("total_tokens"),
            func.sum(APIUsage.input_tokens).label("input_tokens"),
            func.sum(APIUsage.output_tokens).label("output_tokens"),
            func.sum(APIUsage.cached_tokens).label("cached_tokens"),
            func.count(APIUsage.id).label("request_count"),
        )
        .where(APIUsage.created_at >= since)
        .group_by(cast(APIUsage.created_at, Date))
        .order_by(cast(APIUsage.created_at, Date))
    )

    result = await db.execute(stmt)
    rows = list(result.all())

    daily_data = [
        DailyUsagePoint(
            date=r.date.isoformat(),
            cost=float(r.total_cost),
            tokens=r.total_tokens,
            requests=r.request_count,
            input_tokens=r.input_tokens or 0,
            output_tokens=r.output_tokens or 0,
            cached_tokens=r.cached_tokens or 0,
        )
        for r in rows
    ]

    total_cost = sum(d.cost for d in daily_data)
    total_tokens = sum(d.tokens for d in daily_data)
    total_requests = sum(d.requests for d in daily_data)

    return UsageHistoryResponse(
        period_days=days,
        total_cost=total_cost,
        total_tokens=total_tokens,
        total_requests=total_requests,
        daily_data=daily_data,
    )


@router.get("/budget", response_model=BudgetStatusResponse)
async def get_budget_status(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> BudgetStatusResponse:
    """
    Get current budget status and alerts.
    """
    from database.models import APIUsage, BudgetAlert

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    hour_ago = now - timedelta(hours=1)

    # Get today's spend
    daily_stmt = select(
        func.coalesce(func.sum(APIUsage.cost_total), 0).label("total")
    ).where(APIUsage.created_at >= today_start)
    daily_result = await db.execute(daily_stmt)
    daily_spend = float(daily_result.scalar_one())

    # Get hourly rate
    hourly_stmt = select(
        func.coalesce(func.sum(APIUsage.cost_total), 0).label("total")
    ).where(APIUsage.created_at >= hour_ago)
    hourly_result = await db.execute(hourly_stmt)
    hourly_rate = float(hourly_result.scalar_one())

    # Calculate projected daily spend
    hours_passed = (now - today_start).total_seconds() / 3600
    if hours_passed > 0:
        projected_daily = (daily_spend / hours_passed) * 24
    else:
        projected_daily = 0.0

    # Get active budget alerts
    alerts_stmt = select(BudgetAlert).where(BudgetAlert.is_active == True)
    alerts_result = await db.execute(alerts_stmt)
    alerts = list(alerts_result.scalars().all())

    # Find daily limit from alerts (or use default)
    daily_limit = 100.0  # Default
    for alert in alerts:
        if alert.period == "daily" and alert.name == "Daily Critical":
            daily_limit = float(alert.threshold_amount)
            break

    # Update current spend on alerts
    alert_responses = []
    for alert in alerts:
        # Update current spend based on period
        if alert.period == "daily":
            alert.current_spend = daily_spend
        elif alert.period == "hourly":
            alert.current_spend = hourly_rate

        alert_responses.append(
            BudgetAlertResponse(
                id=alert.id,
                name=alert.name,
                description=alert.description,
                threshold_amount=float(alert.threshold_amount),
                period=alert.period,
                current_spend=float(alert.current_spend),
                percentage_used=alert.percentage_used,
                is_exceeded=alert.is_exceeded,
                is_active=alert.is_active,
                last_triggered_at=alert.last_triggered_at,
                trigger_count=alert.trigger_count,
            )
        )

    return BudgetStatusResponse(
        daily_spend=daily_spend,
        daily_limit=daily_limit,
        daily_percentage=daily_spend / daily_limit * 100 if daily_limit > 0 else 0,
        hourly_rate=hourly_rate,
        projected_daily=projected_daily,
        alerts=alert_responses,
    )


@router.get("/records", response_model=UsageListResponse)
async def list_usage_records(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    agent_type: AgentType | None = Query(None),
    model: str | None = Query(None),
) -> UsageListResponse:
    """
    List individual usage records with pagination and filtering.
    """
    from database.models import APIUsage

    # Build query
    query = select(APIUsage)

    if agent_type:
        query = query.where(APIUsage.agent_type == agent_type)
    if model:
        query = query.where(APIUsage.model == model)

    # Get total count
    count_query = select(func.count(APIUsage.id))
    if agent_type:
        count_query = count_query.where(APIUsage.agent_type == agent_type)
    if model:
        count_query = count_query.where(APIUsage.model == model)

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Apply pagination
    query = (
        query.order_by(APIUsage.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    records = list(result.scalars().all())

    return UsageListResponse(
        records=[
            UsageRecordResponse(
                id=r.id,
                provider=r.provider.value,
                model=r.model,
                usage_type=r.usage_type.value,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                cached_tokens=r.cached_tokens,
                cost_total=float(r.cost_total),
                agent_type=r.agent_type.value if r.agent_type else None,
                agent_name=r.agent_name,
                task_id=r.task_id,
                correlation_id=r.correlation_id,
                latency_ms=r.latency_ms,
                created_at=r.created_at,
            )
            for r in records
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ============================================================================
# Provider Usage Reconciliation Endpoints
# ============================================================================


@router.get("/provider-reported", response_model=ProviderUsageResponse)
async def get_provider_reported_usage(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
) -> ProviderUsageResponse:
    """
    Get provider-reported usage data from Anthropic/OpenAI.

    Returns actual billing data fetched from provider APIs.
    """
    from database.models import ProviderUsage

    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=days)
    period_end = now

    stmt = (
        select(ProviderUsage)
        .where(
            ProviderUsage.report_date >= period_start,
            ProviderUsage.report_date <= period_end,
        )
        .order_by(ProviderUsage.report_date.desc())
    )

    result = await db.execute(stmt)
    records = list(result.scalars().all())

    return ProviderUsageResponse(
        records=[
            ProviderUsageRecord(
                id=r.id,
                provider=r.provider.value,
                report_date=r.report_date,
                model=r.model,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                cached_tokens=r.cached_tokens,
                cost_usd=float(r.cost_usd),
                workspace_id=r.workspace_id,
            )
            for r in records
        ],
        total=len(records),
        period_start=period_start,
        period_end=period_end,
    )


@router.get("/reconciliation", response_model=ReconciliationResponse)
async def get_usage_reconciliation(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
) -> ReconciliationResponse:
    """
    Compare local cost estimates with provider-reported costs.

    Returns a breakdown by model showing differences between
    local tracking and actual provider billing.
    """
    from database.models import APIUsage, ProviderUsage

    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=days)
    period_end = now

    # Get local usage aggregated by model
    local_stmt = (
        select(
            APIUsage.model,
            func.sum(APIUsage.cost_total).label("total_cost"),
            func.sum(APIUsage.input_tokens).label("input_tokens"),
            func.sum(APIUsage.output_tokens).label("output_tokens"),
        )
        .where(
            APIUsage.created_at >= period_start,
            APIUsage.created_at <= period_end,
        )
        .group_by(APIUsage.model)
    )
    local_result = await db.execute(local_stmt)
    local_by_model = {
        r.model: {
            "cost": float(r.total_cost or 0),
            "input_tokens": r.input_tokens or 0,
            "output_tokens": r.output_tokens or 0,
        }
        for r in local_result
    }

    # Get provider usage aggregated by model
    provider_stmt = (
        select(
            ProviderUsage.model,
            func.sum(ProviderUsage.cost_usd).label("total_cost"),
            func.sum(ProviderUsage.input_tokens).label("input_tokens"),
            func.sum(ProviderUsage.output_tokens).label("output_tokens"),
        )
        .where(
            ProviderUsage.report_date >= period_start,
            ProviderUsage.report_date <= period_end,
        )
        .group_by(ProviderUsage.model)
    )
    provider_result = await db.execute(provider_stmt)
    provider_by_model = {
        r.model: {
            "cost": float(r.total_cost or 0),
            "input_tokens": r.input_tokens or 0,
            "output_tokens": r.output_tokens or 0,
        }
        for r in provider_result
    }

    # Combine models from both sources
    all_models = set(local_by_model.keys()) | set(provider_by_model.keys())

    reconciliation_data = []
    local_total = 0.0
    provider_total = 0.0

    for model in sorted(all_models):
        local = local_by_model.get(model, {"cost": 0, "input_tokens": 0, "output_tokens": 0})
        provider = provider_by_model.get(model, {"cost": 0, "input_tokens": 0, "output_tokens": 0})

        local_cost = local["cost"]
        provider_cost = provider["cost"]
        difference = local_cost - provider_cost
        diff_pct = (difference / provider_cost * 100) if provider_cost > 0 else 0.0

        local_total += local_cost
        provider_total += provider_cost

        reconciliation_data.append(
            ModelReconciliation(
                model=model,
                local_cost=local_cost,
                provider_cost=provider_cost,
                difference=difference,
                difference_percentage=diff_pct,
                local_input_tokens=local["input_tokens"],
                local_output_tokens=local["output_tokens"],
                provider_input_tokens=provider["input_tokens"],
                provider_output_tokens=provider["output_tokens"],
            )
        )

    total_difference = local_total - provider_total
    total_diff_pct = (total_difference / provider_total * 100) if provider_total > 0 else 0.0

    return ReconciliationResponse(
        period_start=period_start,
        period_end=period_end,
        local_total=local_total,
        provider_total=provider_total,
        total_difference=total_difference,
        total_difference_percentage=total_diff_pct,
        by_model=reconciliation_data,
    )


@router.get("/sync-status", response_model=SyncStatusResponse)
async def get_sync_status(
    current_user: CurrentUserDep,
) -> SyncStatusResponse:
    """
    Get sync configuration and status for all providers.

    Shows whether each provider's admin API is configured
    and when the last successful sync occurred.
    """
    sync_service = get_usage_sync_service()
    status = await sync_service.get_sync_status()

    return SyncStatusResponse(
        anthropic=ProviderSyncStatus(
            configured=status["anthropic"]["configured"],
            last_sync=status["anthropic"]["last_sync"],
        ),
        openai=ProviderSyncStatus(
            configured=status["openai"]["configured"],
            last_sync=status["openai"]["last_sync"],
        ),
    )


@router.post("/sync", response_model=SyncResponse)
async def trigger_manual_sync(
    current_user: CurrentUserDep,
    days: int = Query(7, ge=1, le=30, description="Number of days to sync"),
) -> SyncResponse:
    """
    Trigger a manual sync with provider Usage APIs.

    Fetches usage data for the specified number of days
    and stores it in the database for reconciliation.
    """
    from database.models import SyncType

    sync_service = get_usage_sync_service()
    results = await sync_service.sync_all_providers(
        lookback_days=days,
        sync_type=SyncType.MANUAL,
    )

    return SyncResponse(
        anthropic=SyncResult(
            configured=results["anthropic"].get("configured", False),
            success=results["anthropic"].get("success"),
            records_synced=results["anthropic"].get("records_synced"),
            duration_seconds=results["anthropic"].get("duration_seconds"),
            error=results["anthropic"].get("error"),
        ),
        openai=SyncResult(
            configured=results["openai"].get("configured", False),
            success=results["openai"].get("success"),
            records_synced=results["openai"].get("records_synced"),
            duration_seconds=results["openai"].get("duration_seconds"),
            error=results["openai"].get("error"),
        ),
        message="Sync completed",
    )
