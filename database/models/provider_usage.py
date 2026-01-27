"""
Provider Usage models for storing provider-reported usage and cost data.

Stores actual billing data from Anthropic and OpenAI Usage APIs
for reconciliation with local estimates.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Index, Integer, Numeric, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin
from .api_usage import APIProvider


class SyncType(str, PyEnum):
    """Type of sync operation."""

    FULL = "full"
    INCREMENTAL = "incremental"
    MANUAL = "manual"


class ProviderUsage(Base, UUIDMixin, TimestampMixin):
    """
    Provider-reported usage data.

    Stores actual usage data fetched from Anthropic/OpenAI Usage APIs
    for reconciliation with local cost estimates.
    """

    __tablename__ = "provider_usage"

    # Provider info
    provider: Mapped[APIProvider] = mapped_column(
        Enum(APIProvider),
        nullable=False,
        index=True,
    )

    # Report date (the date the usage is for)
    report_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Model (e.g., "claude-3-5-sonnet-20241022", "gpt-4o")
    model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Token counts from provider
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Cost reported by provider (actual billed amount in USD)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=8),
        nullable=False,
        default=Decimal("0"),
    )

    # Optional workspace/project association
    workspace_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Raw API response for debugging/auditing
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Composite indexes for common queries
    __table_args__ = (
        # Daily aggregation queries by provider
        Index("ix_provider_usage_provider_date", "provider", "report_date"),
        # Model-specific queries
        Index("ix_provider_usage_model_date", "model", "report_date"),
        # Unique constraint to prevent duplicates
        Index(
            "ix_provider_usage_unique",
            "provider",
            "report_date",
            "model",
            "workspace_id",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ProviderUsage {self.id[:8]} "
            f"{self.provider.value}/{self.model} "
            f"date={self.report_date.date()} "
            f"cost=${float(self.cost_usd):.6f}>"
        )

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens + self.cached_tokens


class UsageSyncLog(Base, UUIDMixin, TimestampMixin):
    """
    Tracks sync operations with provider Usage APIs.

    Records when syncs occurred, their success/failure status,
    and any error messages for debugging.
    """

    __tablename__ = "usage_sync_log"

    # Provider being synced
    provider: Mapped[APIProvider] = mapped_column(
        Enum(APIProvider),
        nullable=False,
        index=True,
    )

    # Sync type
    sync_type: Mapped[SyncType] = mapped_column(
        Enum(SyncType),
        nullable=False,
        default=SyncType.INCREMENTAL,
    )

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Result
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    records_synced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Date range synced
    sync_start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    sync_end_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        # Recent syncs by provider
        Index("ix_usage_sync_log_provider_date", "provider", "started_at"),
    )

    def __repr__(self) -> str:
        status = "OK" if self.success else "FAILED"
        return (
            f"<UsageSyncLog {self.id[:8]} "
            f"{self.provider.value} {self.sync_type.value} "
            f"{status} records={self.records_synced}>"
        )

    @property
    def duration_seconds(self) -> float | None:
        """Duration of the sync in seconds."""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
