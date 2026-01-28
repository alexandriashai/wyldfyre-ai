"""
Project model for organizing conversations and tasks.
"""

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .conversation import Conversation
    from .domain import Domain
    from .task import Task
    from .user import User


class ProjectStatus(enum.Enum):
    """Project status enum."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    COMPLETED = "completed"


class Project(Base, UUIDMixin, TimestampMixin):
    """
    Project model for grouping related conversations and tasks.

    Projects enable partitioned, organized work across multiple site builds
    without context bleeding.
    """

    __tablename__ = "projects"

    # Project info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Agent context - instructions and context for AI agents working on this project
    agent_context: Mapped[str | None] = mapped_column(Text)

    # Project root path - filesystem location of the project's codebase
    root_path: Mapped[str | None] = mapped_column(String(500))

    # Primary URL - the main URL for this project (e.g., https://example.com)
    primary_url: Mapped[str | None] = mapped_column(String(500))

    # Terminal user - system user for scoped terminal access (legacy, use Docker instead)
    terminal_user: Mapped[str | None] = mapped_column(String(100))

    # Docker settings
    docker_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    docker_project_type: Mapped[str | None] = mapped_column(String(50))  # node, php, python, custom
    docker_node_version: Mapped[str | None] = mapped_column(String(20), default="20")
    docker_php_version: Mapped[str | None] = mapped_column(String(20), default="8.3")
    docker_python_version: Mapped[str | None] = mapped_column(String(20), default="3.12")
    docker_memory_limit: Mapped[str | None] = mapped_column(String(20), default="2g")
    docker_cpu_limit: Mapped[str | None] = mapped_column(String(20), default="2.0")
    docker_expose_ports: Mapped[str | None] = mapped_column(Text)  # JSON array
    docker_env_vars: Mapped[str | None] = mapped_column(Text)  # JSON object
    docker_container_status: Mapped[str | None] = mapped_column(String(50))

    # GitHub integration
    github_pat_encrypted: Mapped[str | None] = mapped_column(Text)
    github_repo_url: Mapped[str | None] = mapped_column(String(500))

    # Status
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus),
        default=ProjectStatus.ACTIVE,
        nullable=False,
    )

    # UI customization
    color: Mapped[str | None] = mapped_column(String(7))  # Hex color e.g., #FF5733
    icon: Mapped[str | None] = mapped_column(String(50))  # Icon name e.g., "folder"

    # Quality settings (JSON) - code quality and linting configuration
    quality_settings: Mapped[str | None] = mapped_column(Text)  # JSON object

    # Owner relationship
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    user: Mapped["User"] = relationship("User", back_populates="projects")

    # Child relationships
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="project",
    )
    domains: Mapped[list["Domain"]] = relationship(
        "Domain",
        back_populates="project",
    )

    def __repr__(self) -> str:
        return f"<Project {self.id[:8]} {self.name} {self.status.value}>"
