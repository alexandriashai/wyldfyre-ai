"""
Task model for tracking agent task executions.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .user import User

import enum


class TaskStatus(str, enum.Enum):
    """Task execution status."""
    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentType(str, enum.Enum):
    """Types of agents."""
    SUPERVISOR = "supervisor"
    CODE = "code"
    DATA = "data"
    INFRA = "infra"
    RESEARCH = "research"
    QA = "qa"


class Task(Base, UUIDMixin, TimestampMixin):
    """Task execution model."""

    __tablename__ = "tasks"

    # Task info
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)

    # Status
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus),
        default=TaskStatus.PENDING,
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(Integer, default=5)

    # Agent info
    agent_type: Mapped[AgentType | None] = mapped_column(Enum(AgentType))
    correlation_id: Mapped[str | None] = mapped_column(String(36), index=True)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    # Input/Output (JSON as text)
    input_data: Mapped[str | None] = mapped_column(Text)
    output_data: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    # Metrics
    token_count_input: Mapped[int | None] = mapped_column(Integer)
    token_count_output: Mapped[int | None] = mapped_column(Integer)
    estimated_cost: Mapped[float | None] = mapped_column(Float)

    # User relationship
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        index=True,
    )
    user: Mapped["User | None"] = relationship("User", back_populates="tasks")

    # Parent task for subtasks
    parent_task_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tasks.id"),
        index=True,
    )
    subtasks: Mapped[list["Task"]] = relationship("Task", back_populates="parent_task")
    parent_task: Mapped["Task | None"] = relationship(
        "Task",
        back_populates="subtasks",
        remote_side="Task.id",
    )

    def __repr__(self) -> str:
        return f"<Task {self.id[:8]} {self.task_type} {self.status.value}>"
