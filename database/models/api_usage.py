"""
API Usage model for tracking token consumption and costs.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_core import AgentType

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .project import Project
    from .task import Task
    from .user import User


class APIProvider(str, PyEnum):
    """AI API providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class UsageType(str, PyEnum):
    """Type of API usage."""

    CHAT = "chat"  # Standard chat/completion
    EMBEDDING = "embedding"  # Text embedding generation
    TOOL_USE = "tool_use"  # Tool/function calling


class APIUsage(Base, UUIDMixin, TimestampMixin):
    """
    API Usage tracking model.

    Records every API call with token counts and costs for:
    - Real-time cost monitoring via Prometheus
    - Historical analysis and reporting
    - Budget tracking and alerts
    """

    __tablename__ = "api_usage"

    # Provider and model info
    provider: Mapped[APIProvider] = mapped_column(
        Enum(APIProvider),
        nullable=False,
        index=True,
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Usage type
    usage_type: Mapped[UsageType] = mapped_column(
        Enum(UsageType),
        default=UsageType.CHAT,
        nullable=False,
    )

    # Token counts
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Cost (stored as Numeric for precision)
    cost_input: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=8),
        nullable=False,
        default=Decimal("0"),
    )
    cost_output: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=8),
        nullable=False,
        default=Decimal("0"),
    )
    cost_cached: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=8),
        nullable=False,
        default=Decimal("0"),
    )
    cost_total: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=8),
        nullable=False,
        default=Decimal("0"),
        index=True,
    )

    # Agent info (for per-agent tracking)
    agent_type: Mapped[AgentType | None] = mapped_column(Enum(AgentType), index=True)
    agent_name: Mapped[str | None] = mapped_column(String(100))

    # Correlation to other entities
    task_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        index=True,
    )
    task: Mapped["Task | None"] = relationship("Task")

    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    user: Mapped["User | None"] = relationship("User")

    # Project association for per-project cost tracking
    project_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="SET NULL"),
        index=True,
    )
    project: Mapped["Project | None"] = relationship("Project")

    correlation_id: Mapped[str | None] = mapped_column(String(36), index=True)

    # Request metadata
    request_id: Mapped[str | None] = mapped_column(String(100))  # API request ID
    latency_ms: Mapped[int | None] = mapped_column(Integer)  # Response time

    # Composite indexes for common queries
    __table_args__ = (
        # Daily aggregation queries
        Index("ix_api_usage_created_date", "created_at"),
        # Per-agent daily queries
        Index("ix_api_usage_agent_date", "agent_type", "created_at"),
        # Per-user queries
        Index("ix_api_usage_user_date", "user_id", "created_at"),
        # Model-specific analysis
        Index("ix_api_usage_model_date", "model", "created_at"),
        # Per-project queries
        Index("ix_api_usage_project_date", "project_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<APIUsage {self.id[:8]} "
            f"{self.provider.value}/{self.model} "
            f"tokens={self.input_tokens}+{self.output_tokens} "
            f"cost=${float(self.cost_total):.6f}>"
        )

    @property
    def total_tokens(self) -> int:
        """Total tokens used in this request."""
        return self.input_tokens + self.output_tokens + self.cached_tokens


class BudgetAlert(Base, UUIDMixin, TimestampMixin):
    """
    Budget alert configuration and tracking.

    Allows setting spending thresholds and tracking when they're exceeded.
    """

    __tablename__ = "budget_alerts"

    # Alert configuration
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))

    # Threshold settings
    threshold_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
    )
    period: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="daily",  # daily, weekly, monthly
    )

    # Current state
    current_spend: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        default=Decimal("0"),
    )
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trigger_count: Mapped[int] = mapped_column(Integer, default=0)

    # Alert settings
    is_active: Mapped[bool] = mapped_column(default=True)
    notify_slack: Mapped[bool] = mapped_column(default=True)
    notify_email: Mapped[bool] = mapped_column(default=False)

    # Optional scoping
    agent_type: Mapped[AgentType | None] = mapped_column(Enum(AgentType))
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    def __repr__(self) -> str:
        return (
            f"<BudgetAlert {self.name} "
            f"threshold=${float(self.threshold_amount):.2f}/{self.period} "
            f"current=${float(self.current_spend):.2f}>"
        )

    @property
    def is_exceeded(self) -> bool:
        """Check if current spend exceeds threshold."""
        return self.current_spend >= self.threshold_amount

    @property
    def percentage_used(self) -> float:
        """Calculate percentage of budget used."""
        if self.threshold_amount == 0:
            return 0.0
        return float(self.current_spend) / float(self.threshold_amount) * 100
