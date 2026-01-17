"""
Base Agent Package - Foundation for all AI Infrastructure agents.

Provides:
- BaseAgent class with tool execution
- Tool registry and decorator
- Claude API integration
- Memory and messaging integration
"""

from .agent import BaseAgent
from .tools import Tool, ToolRegistry, ToolResult, tool

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "BaseAgent",
    "Tool",
    "ToolRegistry",
    "ToolResult",
    "tool",
]
