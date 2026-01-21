"""
Database models for AI Infrastructure.
"""

from ai_core import AgentType, DomainStatus, TaskStatus

from .base import Base, TimestampMixin, UUIDMixin, generate_uuid
from .api_usage import APIProvider, APIUsage, BudgetAlert, UsageType
from .conversation import Conversation, ConversationStatus, PlanStatus
from .credential import BrowserSession, StoredCredential
from .domain import Domain
from .project import Project, ProjectStatus
from .task import Task
from .user import User

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    "UUIDMixin",
    "generate_uuid",
    # Enums (re-exported from ai_core for convenience)
    "TaskStatus",
    "AgentType",
    "DomainStatus",
    # API Usage enums
    "APIProvider",
    "UsageType",
    # Project & Conversation enums
    "ProjectStatus",
    "ConversationStatus",
    "PlanStatus",
    # Models
    "User",
    "Task",
    "Domain",
    "APIUsage",
    "BudgetAlert",
    "Project",
    "Conversation",
    "StoredCredential",
    "BrowserSession",
]
