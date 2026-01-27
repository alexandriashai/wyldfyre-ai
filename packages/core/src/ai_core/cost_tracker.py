"""
Cost Tracker Service - Records and monitors API usage costs.

Provides:
- Recording API usage to database
- Updating Prometheus metrics
- Aggregated usage statistics
- Budget monitoring and alerts
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from .enums import AgentType
from .logging import get_logger
from .metrics import claude_api_cost_dollars
from .pricing import Provider, UsageCost, calculate_cost, get_model_provider

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


@dataclass
class UsageSummary:
    """Summary of API usage for a period."""

    total_cost: Decimal
    total_input_tokens: int
    total_output_tokens: int
    total_cached_tokens: int
    request_count: int
    period_start: datetime
    period_end: datetime
    breakdown_by_model: dict[str, Decimal]
    breakdown_by_agent: dict[str, Decimal]


@dataclass
class DailyUsage:
    """Daily usage statistics."""

    date: datetime
    total_cost: Decimal
    total_tokens: int
    request_count: int


class CostTracker:
    """
    Service for tracking API usage costs.

    Records usage to PostgreSQL and updates Prometheus metrics
    in a single atomic operation.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._session_factory: Any = None

    def set_session_factory(self, session_factory: Any) -> None:
        """Set the database session factory for persistence."""
        self._session_factory = session_factory

    async def record_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        agent_type: AgentType | None = None,
        agent_name: str | None = None,
        task_id: str | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
        correlation_id: str | None = None,
        request_id: str | None = None,
        latency_ms: int | None = None,
        session: "AsyncSession | None" = None,
    ) -> UsageCost:
        """
        Record API usage with cost calculation.

        Args:
            model: Model identifier (e.g., "claude-opus-4-5")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cached_tokens: Number of cached input tokens
            agent_type: Type of agent making the request
            agent_name: Name of the agent instance
            task_id: Associated task ID
            user_id: Associated user ID
            project_id: Associated project ID for per-project cost tracking
            correlation_id: Request correlation ID
            request_id: API request ID from provider
            latency_ms: Response latency in milliseconds
            session: Optional database session (creates one if not provided)

        Returns:
            UsageCost with calculated costs
        """
        # Calculate cost
        usage_cost = calculate_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
        )

        # Update Prometheus metrics
        agent_label = agent_type.value if agent_type else "unknown"
        claude_api_cost_dollars.labels(
            agent_type=agent_label,
            model=model,
        ).inc(float(usage_cost.total_cost))

        # Persist to database if session factory is configured
        if self._session_factory is not None or session is not None:
            await self._persist_usage(
                usage_cost=usage_cost,
                agent_type=agent_type,
                agent_name=agent_name,
                task_id=task_id,
                user_id=user_id,
                project_id=project_id,
                correlation_id=correlation_id,
                request_id=request_id,
                latency_ms=latency_ms,
                session=session,
            )

        logger.debug(
            "Recorded API usage",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=float(usage_cost.total_cost),
            agent=agent_label,
        )

        return usage_cost

    async def _persist_usage(
        self,
        usage_cost: UsageCost,
        agent_type: AgentType | None,
        agent_name: str | None,
        task_id: str | None,
        user_id: str | None,
        project_id: str | None,
        correlation_id: str | None,
        request_id: str | None,
        latency_ms: int | None,
        session: "AsyncSession | None" = None,
    ) -> None:
        """Persist usage record to database."""
        # Import here to avoid circular imports
        from database.models import APIProvider, APIUsage, UsageType

        # Map provider enum
        provider_map = {
            Provider.ANTHROPIC: APIProvider.ANTHROPIC,
            Provider.OPENAI: APIProvider.OPENAI,
        }

        async def _do_insert(db_session: "AsyncSession") -> None:
            # Verify task_id exists before using it (foreign key constraint)
            validated_task_id = None
            if task_id:
                from sqlalchemy import select, text
                result = await db_session.execute(
                    text("SELECT 1 FROM tasks WHERE id = :tid LIMIT 1"),
                    {"tid": task_id}
                )
                if result.scalar() is not None:
                    validated_task_id = task_id

            usage_record = APIUsage(
                provider=provider_map.get(usage_cost.provider, APIProvider.ANTHROPIC),
                model=usage_cost.model,
                usage_type=UsageType.CHAT,
                input_tokens=usage_cost.input_tokens,
                output_tokens=usage_cost.output_tokens,
                cached_tokens=usage_cost.cached_tokens,
                cost_input=usage_cost.input_cost,
                cost_output=usage_cost.output_cost,
                cost_cached=usage_cost.cached_cost,
                cost_total=usage_cost.total_cost,
                agent_type=agent_type,
                agent_name=agent_name,
                task_id=validated_task_id,
                user_id=user_id,
                project_id=project_id,
                correlation_id=correlation_id,
                request_id=request_id,
                latency_ms=latency_ms,
            )
            db_session.add(usage_record)
            await db_session.commit()

        try:
            if session is not None:
                await _do_insert(session)
            elif self._session_factory is not None:
                async with self._session_factory() as db_session:
                    await _do_insert(db_session)
        except Exception as e:
            logger.error("Failed to persist API usage", error=str(e))
            # Don't raise - we don't want to fail the main operation

    async def record_embedding_usage(
        self,
        model: str,
        input_tokens: int,
        agent_type: AgentType | None = None,
        task_id: str | None = None,
        user_id: str | None = None,
        session: "AsyncSession | None" = None,
    ) -> UsageCost:
        """
        Record embedding API usage (output tokens are always 0).

        Args:
            model: Embedding model (e.g., "text-embedding-3-small")
            input_tokens: Number of input tokens
            agent_type: Type of agent making the request
            task_id: Associated task ID
            user_id: Associated user ID
            session: Optional database session

        Returns:
            UsageCost with calculated costs
        """
        usage_cost = calculate_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=0,
        )

        # Persist to database
        if self._session_factory is not None or session is not None:
            from database.models import APIProvider, APIUsage, UsageType

            provider_map = {
                Provider.ANTHROPIC: APIProvider.ANTHROPIC,
                Provider.OPENAI: APIProvider.OPENAI,
            }

            async def _do_insert(db_session: "AsyncSession") -> None:
                # Verify task_id exists before using it (foreign key constraint)
                validated_task_id = None
                if task_id:
                    from sqlalchemy import text
                    result = await db_session.execute(
                        text("SELECT 1 FROM tasks WHERE id = :tid LIMIT 1"),
                        {"tid": task_id}
                    )
                    if result.scalar() is not None:
                        validated_task_id = task_id

                usage_record = APIUsage(
                    provider=provider_map.get(usage_cost.provider, APIProvider.OPENAI),
                    model=model,
                    usage_type=UsageType.EMBEDDING,
                    input_tokens=input_tokens,
                    output_tokens=0,
                    cached_tokens=0,
                    cost_input=usage_cost.input_cost,
                    cost_output=Decimal("0"),
                    cost_cached=Decimal("0"),
                    cost_total=usage_cost.total_cost,
                    agent_type=agent_type,
                    task_id=validated_task_id,
                    user_id=user_id,
                )
                db_session.add(usage_record)
                await db_session.commit()

            try:
                if session is not None:
                    await _do_insert(session)
                elif self._session_factory is not None:
                    async with self._session_factory() as db_session:
                        await _do_insert(db_session)
            except Exception as e:
                logger.error("Failed to persist embedding usage", error=str(e))

        logger.debug(
            "Recorded embedding usage",
            model=model,
            tokens=input_tokens,
            cost=float(usage_cost.total_cost),
        )

        return usage_cost

    async def get_daily_summary(
        self,
        date: datetime | None = None,
        session: "AsyncSession | None" = None,
    ) -> UsageSummary | None:
        """
        Get usage summary for a specific day.

        Args:
            date: Date to get summary for (defaults to today)
            session: Database session

        Returns:
            UsageSummary or None if no data
        """
        if self._session_factory is None and session is None:
            logger.warning("No database session available for daily summary")
            return None

        from sqlalchemy import func, select

        from database.models import APIUsage

        if date is None:
            date = datetime.now(timezone.utc)

        # Start and end of day
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        async def _get_summary(db_session: "AsyncSession") -> UsageSummary | None:
            # Main aggregation query
            stmt = select(
                func.sum(APIUsage.cost_total).label("total_cost"),
                func.sum(APIUsage.input_tokens).label("total_input"),
                func.sum(APIUsage.output_tokens).label("total_output"),
                func.sum(APIUsage.cached_tokens).label("total_cached"),
                func.count(APIUsage.id).label("request_count"),
            ).where(
                APIUsage.created_at >= day_start,
                APIUsage.created_at < day_end,
            )

            result = await db_session.execute(stmt)
            row = result.first()

            if row is None or row.request_count == 0:
                return None

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
            )
            model_result = await db_session.execute(model_stmt)
            breakdown_by_model = {r.model: r.cost for r in model_result}

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
            )
            agent_result = await db_session.execute(agent_stmt)
            breakdown_by_agent = {
                (r.agent_type.value if r.agent_type else "unknown"): r.cost
                for r in agent_result
            }

            return UsageSummary(
                total_cost=row.total_cost or Decimal("0"),
                total_input_tokens=row.total_input or 0,
                total_output_tokens=row.total_output or 0,
                total_cached_tokens=row.total_cached or 0,
                request_count=row.request_count,
                period_start=day_start,
                period_end=day_end,
                breakdown_by_model=breakdown_by_model,
                breakdown_by_agent=breakdown_by_agent,
            )

        try:
            if session is not None:
                return await _get_summary(session)
            elif self._session_factory is not None:
                async with self._session_factory() as db_session:
                    return await _get_summary(db_session)
        except Exception as e:
            logger.error("Failed to get daily summary", error=str(e))
            return None
        return None

    async def get_usage_by_agent(
        self,
        days: int = 30,
        session: "AsyncSession | None" = None,
    ) -> dict[str, Decimal]:
        """
        Get total usage breakdown by agent type.

        Args:
            days: Number of days to include
            session: Database session

        Returns:
            Dict mapping agent type to total cost
        """
        if self._session_factory is None and session is None:
            return {}

        from sqlalchemy import func, select

        from database.models import APIUsage

        since = datetime.now(timezone.utc) - timedelta(days=days)

        async def _get_breakdown(db_session: "AsyncSession") -> dict[str, Decimal]:
            stmt = (
                select(
                    APIUsage.agent_type,
                    func.sum(APIUsage.cost_total).label("total_cost"),
                )
                .where(APIUsage.created_at >= since)
                .group_by(APIUsage.agent_type)
            )

            result = await db_session.execute(stmt)
            return {
                (r.agent_type.value if r.agent_type else "unknown"): r.total_cost
                for r in result
            }

        try:
            if session is not None:
                return await _get_breakdown(session)
            elif self._session_factory is not None:
                async with self._session_factory() as db_session:
                    return await _get_breakdown(db_session)
        except Exception as e:
            logger.error("Failed to get usage by agent", error=str(e))
            return {}
        return {}

    async def get_usage_history(
        self,
        days: int = 30,
        session: "AsyncSession | None" = None,
    ) -> list[DailyUsage]:
        """
        Get daily usage history for charting.

        Args:
            days: Number of days of history
            session: Database session

        Returns:
            List of DailyUsage records
        """
        if self._session_factory is None and session is None:
            return []

        from sqlalchemy import cast, func, select
        from sqlalchemy.types import Date

        from database.models import APIUsage

        since = datetime.now(timezone.utc) - timedelta(days=days)

        async def _get_history(db_session: "AsyncSession") -> list[DailyUsage]:
            stmt = (
                select(
                    cast(APIUsage.created_at, Date).label("date"),
                    func.sum(APIUsage.cost_total).label("total_cost"),
                    func.sum(
                        APIUsage.input_tokens
                        + APIUsage.output_tokens
                        + APIUsage.cached_tokens
                    ).label("total_tokens"),
                    func.count(APIUsage.id).label("request_count"),
                )
                .where(APIUsage.created_at >= since)
                .group_by(cast(APIUsage.created_at, Date))
                .order_by(cast(APIUsage.created_at, Date))
            )

            result = await db_session.execute(stmt)
            return [
                DailyUsage(
                    date=r.date,
                    total_cost=r.total_cost,
                    total_tokens=r.total_tokens,
                    request_count=r.request_count,
                )
                for r in result
            ]

        try:
            if session is not None:
                return await _get_history(session)
            elif self._session_factory is not None:
                async with self._session_factory() as db_session:
                    return await _get_history(db_session)
        except Exception as e:
            logger.error("Failed to get usage history", error=str(e))
            return []
        return []


# Global singleton instance
_cost_tracker: CostTracker | None = None


def get_cost_tracker() -> CostTracker:
    """Get the global cost tracker instance."""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker


def configure_cost_tracker(session_factory: Any) -> CostTracker:
    """Configure the cost tracker with a database session factory."""
    tracker = get_cost_tracker()
    tracker.set_session_factory(session_factory)
    return tracker
