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
    primary_url: str | None = Field(None, max_length=500)
    terminal_user: str | None = Field(None, max_length=100)
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    icon: str | None = Field(None, max_length=50)

    # Docker settings
    docker_enabled: bool = False
    docker_project_type: str | None = Field(None, max_length=50)
    docker_node_version: str | None = Field(None, max_length=20)
    docker_php_version: str | None = Field(None, max_length=20)
    docker_python_version: str | None = Field(None, max_length=20)
    docker_memory_limit: str | None = Field(None, max_length=20)
    docker_cpu_limit: str | None = Field(None, max_length=20)
    docker_expose_ports: str | None = None
    docker_env_vars: str | None = None


class ProjectUpdate(BaseModel):
    """Update project request."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    agent_context: str | None = None
    root_path: str | None = Field(None, max_length=500)
    primary_url: str | None = Field(None, max_length=500)
    terminal_user: str | None = Field(None, max_length=100)
    status: ProjectStatus | None = None
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    icon: str | None = Field(None, max_length=50)

    # Docker settings
    docker_enabled: bool | None = None
    docker_project_type: str | None = Field(None, max_length=50)
    docker_node_version: str | None = Field(None, max_length=20)
    docker_php_version: str | None = Field(None, max_length=20)
    docker_python_version: str | None = Field(None, max_length=20)
    docker_memory_limit: str | None = Field(None, max_length=20)
    docker_cpu_limit: str | None = Field(None, max_length=20)
    docker_expose_ports: str | None = None
    docker_env_vars: str | None = None


class ProjectResponse(BaseModel):
    """Project information response."""

    id: str
    name: str
    description: str | None
    agent_context: str | None
    root_path: str | None
    primary_url: str | None
    terminal_user: str | None
    status: ProjectStatus
    color: str | None
    icon: str | None
    user_id: str

    # Docker settings
    docker_enabled: bool = False
    docker_project_type: str | None = None
    docker_node_version: str | None = None
    docker_php_version: str | None = None
    docker_python_version: str | None = None
    docker_memory_limit: str | None = None
    docker_cpu_limit: str | None = None
    docker_expose_ports: str | None = None
    docker_env_vars: str | None = None
    docker_container_status: str | None = None

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
    primary_url: str | None
    domains: list[ProjectDomainInfo] = []

    # Docker context for agents
    docker_enabled: bool = False
    docker_project_type: str | None = None
    docker_container_status: str | None = None

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
