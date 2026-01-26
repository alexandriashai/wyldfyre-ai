"""
API route modules.
"""

from .agents import router as agents_router
from .auth import router as auth_router
from .chat import router as chat_router
from .conversations import router as conversations_router
from .domains import router as domains_router
from .files import router as files_router
from .grafana_proxy import router as grafana_router
from .integrations import router as integrations_router
from .health import router as health_router
from .memory import router as memory_router
from .notifications import router as notifications_router
from .projects import router as projects_router
from .settings import router as settings_router
from .tasks import router as tasks_router
from .usage import router as usage_router
from .workspace import router as workspace_router
from .containers import router as containers_router
from .github import router as github_router
from .plans import router as plans_router

__all__ = [
    "agents_router",
    "auth_router",
    "chat_router",
    "conversations_router",
    "domains_router",
    "files_router",
    "grafana_router",
    "health_router",
    "integrations_router",
    "memory_router",
    "notifications_router",
    "projects_router",
    "settings_router",
    "tasks_router",
    "usage_router",
    "workspace_router",
    "containers_router",
    "github_router",
    "plans_router",
]
