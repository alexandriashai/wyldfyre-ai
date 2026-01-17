"""
AI Infrastructure API.

FastAPI backend for the multi-agent AI system.
"""

from .main import app, create_app

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "app",
    "create_app",
]
