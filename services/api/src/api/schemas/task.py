"""
Task schemas.
"""

from datetime import datetime

from pydantic import BaseModel

from ai_core import AgentType, TaskStatus


class TaskResponse(BaseModel):
    """Task information response."""

    id: str
    task_type: str
    title: str | None
    description: str | None
    status: TaskStatus
    priority: int

    # Agent info
    agent_type: AgentType | None
    correlation_id: str | None

    # Timing
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None

    # Results
    error_message: str | None

    # Metrics
    token_count_input: int | None
    token_count_output: int | None
    estimated_cost: float | None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """Task list response."""

    tasks: list[TaskResponse]
    total: int
    page: int
    page_size: int
