"""
Project schemas.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from ai_db import ProjectStatus


class ProjectCreate(BaseModel):
    """Create project request."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    icon: str | None = Field(None, max_length=50)


class ProjectUpdate(BaseModel):
    """Update project request."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    status: ProjectStatus | None = None
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    icon: str | None = Field(None, max_length=50)


class ProjectResponse(BaseModel):
    """Project information response."""

    id: str
    name: str
    description: str | None
    status: ProjectStatus
    color: str | None
    icon: str | None
    user_id: str

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectWithStatsResponse(ProjectResponse):
    """Project with statistics response."""

    conversation_count: int = 0
    task_count: int = 0
    total_cost: float = 0.0


class ProjectListResponse(BaseModel):
    """Project list response."""

    projects: list[ProjectResponse]
    total: int
    page: int
    page_size: int
