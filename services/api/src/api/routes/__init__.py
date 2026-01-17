"""
API route modules.
"""

from .agents import router as agents_router
from .auth import router as auth_router
from .chat import router as chat_router
from .conversations import router as conversations_router
from .domains import router as domains_router
from .files import router as files_router
from .health import router as health_router
from .memory import router as memory_router
from .tasks import router as tasks_router

__all__ = [
    "agents_router",
    "auth_router",
    "chat_router",
    "conversations_router",
    "domains_router",
    "files_router",
    "health_router",
    "memory_router",
    "tasks_router",
]
