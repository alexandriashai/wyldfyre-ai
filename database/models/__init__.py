"""
Database models for AI Infrastructure.
"""

from ai_core import AgentType, DomainStatus, TaskStatus

from .base import Base, TimestampMixin, UUIDMixin, generate_uuid
from .api_usage import APIProvider, APIUsage, BudgetAlert, UsageType
from .provider_usage import ProviderUsage, SyncType, UsageSyncLog
from .conversation import Conversation, ConversationStatus, PlanStatus
from .conversation_tag import ConversationTag
from .credential import BrowserSession, StoredCredential
from .domain import Domain
from .message import Message
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
    # Provider Usage enums
    "SyncType",
    # Project & Conversation enums
    "ProjectStatus",
    "ConversationStatus",
    "PlanStatus",
    # Models
    "ConversationTag",
    "User",
    "Task",
    "Domain",
    "Message",
    "APIUsage",
    "BudgetAlert",
    "ProviderUsage",
    "UsageSyncLog",
    "Project",
    "Conversation",
    "StoredCredential",
    "BrowserSession",
]
