"""
Project schemas.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from database.models import ProjectStatus


class ProjectCreate(BaseModel):
    """Create project request."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    agent_context: str | None = None
    root_path: str | None = Field(None, max_length=500)
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    icon: str | None = Field(None, max_length=50)


class ProjectUpdate(BaseModel):
    """Update project request."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    agent_context: str | None = None
    root_path: str | None = Field(None, max_length=500)
    status: ProjectStatus | None = None
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    icon: str | None = Field(None, max_length=50)


class ProjectResponse(BaseModel):
    """Project information response."""

    id: str
    name: str
    description: str | None
    agent_context: str | None
    root_path: str | None
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
    domain_count: int = 0
    total_cost: float = 0.0


class ProjectListResponse(BaseModel):
    """Project list response."""

    projects: list[ProjectResponse]
    total: int
    page: int
    page_size: int


class ProjectDomainInfo(BaseModel):
    """Domain info for project context."""

    domain_name: str
    web_root: str | None
    proxy_target: str | None
    is_primary: bool
    status: str


class ProjectContextResponse(BaseModel):
    """Full project context for agent injection."""

    id: str
    name: str
    description: str | None
    agent_context: str | None
    root_path: str | None
    domains: list[ProjectDomainInfo] = []

    class Config:
        from_attributes = True


class ProjectSpendByModel(BaseModel):
    """Spend breakdown by model."""

    model: str
    cost: float
    tokens: int
    requests: int


class ProjectSpendByAgent(BaseModel):
    """Spend breakdown by agent."""

    agent_type: str
    cost: float
    tokens: int
    requests: int


class ProjectSpendResponse(BaseModel):
    """Detailed project spending response."""

    project_id: str
    project_name: str
    total_cost: float
    total_tokens: int
    total_requests: int
    by_model: list[ProjectSpendByModel] = []
    by_agent: list[ProjectSpendByAgent] = []
