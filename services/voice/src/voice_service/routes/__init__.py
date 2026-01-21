"""
Voice service route modules.
"""

from .health import router as health_router
from .synthesize import router as synthesize_router
from .transcribe import router as transcribe_router

__all__ = [
    "health_router",
    "synthesize_router",
    "transcribe_router",
]
