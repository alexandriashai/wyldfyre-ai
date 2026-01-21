"""
AI Database Package - Database models for AI Infrastructure.

This package provides SQLAlchemy models for:
- User authentication and authorization
- Task tracking
- Domain management
"""

from ai_core import AgentType, DomainStatus, TaskStatus

from .base import Base, TimestampMixin, UUIDMixin, generate_uuid
from .domain import Domain
from .project import Project, ProjectStatus
from .task import Task
from .user import User

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Base
    "Base",
    "TimestampMixin",
    "UUIDMixin",
    "generate_uuid",
    # Enums (re-exported from ai_core for convenience)
    "TaskStatus",
    "AgentType",
    "DomainStatus",
    "ProjectStatus",
    # Models
    "User",
    "Task",
    "Domain",
    "Project",
]
