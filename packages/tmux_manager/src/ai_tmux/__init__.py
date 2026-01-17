"""
AI Tmux Manager Package - Process orchestration for AI Infrastructure.

This package provides tmux-based process management for agents:
- Session and window management
- Agent process lifecycle
- Output capture and monitoring
"""

from .manager import (
    AgentConfig,
    AgentProcess,
    AgentState,
    DEFAULT_AGENTS,
    TmuxManager,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "TmuxManager",
    "AgentConfig",
    "AgentProcess",
    "AgentState",
    "DEFAULT_AGENTS",
]
