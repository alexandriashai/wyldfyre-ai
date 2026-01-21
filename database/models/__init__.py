"""
Database models for AI Infrastructure.
"""

from ai_core import AgentType, DomainStatus, TaskStatus

from .base import Base, TimestampMixin, UUIDMixin, generate_uuid
from .api_usage import APIProvider, APIUsage, BudgetAlert, UsageType
from .domain import Domain
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
    # Models
    "User",
    "Task",
    "Domain",
    "APIUsage",
    "BudgetAlert",
]
