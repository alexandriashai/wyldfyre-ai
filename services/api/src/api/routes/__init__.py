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
from .health import router as health_router
from .memory import router as memory_router
from .settings import router as settings_router
from .tasks import router as tasks_router

__all__ = [
    "agents_router",
    "auth_router",
    "chat_router",
    "conversations_router",
    "domains_router",
    "files_router",
    "grafana_router",
    "health_router",
    "memory_router",
    "settings_router",
    "tasks_router",
]
