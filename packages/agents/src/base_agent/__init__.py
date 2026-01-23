"""
Base Agent Package - Foundation for all AI Infrastructure agents.

Provides:
- BaseAgent class with tool execution
- Tool registry and decorator
- Claude API integration
- Memory and messaging integration
"""

from .agent import (
    ACTION_API_CALL,
    ACTION_API_RESPONSE,
    ACTION_COMPLETE,
    ACTION_DELEGATING,
    ACTION_ERROR,
    ACTION_FILE_READ,
    ACTION_FILE_SEARCH,
    ACTION_FILE_WRITE,
    ACTION_MEMORY_SEARCH,
    ACTION_MEMORY_STORE,
    ACTION_RECEIVED,
    ACTION_THINKING,
    ACTION_TOOL_CALL,
    ACTION_TOOL_ERROR,
    ACTION_TOOL_RESULT,
    ACTION_WAITING,
    BaseAgent,
)
from .context_summarizer import ContextSummarizer
from .parallel_executor import ParallelToolExecutor, ToolCallRequest, ToolCallResult
from .subagent import Subagent, SubagentResult
from .tools import CRITICAL_TOOLS, Tool, ToolRegistry, ToolResult, tool

# Re-export permission types for convenience
from ai_core import CapabilityCategory, PermissionContext, PermissionLevel

# Re-export shared tools for all agents
from .shared_tools import (
    # Memory tools
    search_memory,
    store_memory,
    list_memory_collections,
    get_memory_stats,
    delete_memory,
    # Collaboration tools
    notify_user,
    request_agent_help,
    broadcast_status,
    # Subagent tools
    spawn_subagent,
    # System tools
    get_system_info,
    check_service_health,
    shell_execute,
    process_list,
    process_kill,
    service_manage,
    resource_monitor,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Action constants
    "ACTION_API_CALL",
    "ACTION_API_RESPONSE",
    "ACTION_COMPLETE",
    "ACTION_DELEGATING",
    "ACTION_ERROR",
    "ACTION_FILE_READ",
    "ACTION_FILE_SEARCH",
    "ACTION_FILE_WRITE",
    "ACTION_MEMORY_SEARCH",
    "ACTION_MEMORY_STORE",
    "ACTION_RECEIVED",
    "ACTION_THINKING",
    "ACTION_TOOL_CALL",
    "ACTION_TOOL_ERROR",
    "ACTION_TOOL_RESULT",
    "ACTION_WAITING",
    # Classes
    "BaseAgent",
    "CapabilityCategory",
    "ContextSummarizer",
    "CRITICAL_TOOLS",
    "ParallelToolExecutor",
    "PermissionContext",
    "PermissionLevel",
    "Subagent",
    "SubagentResult",
    "Tool",
    "ToolCallRequest",
    "ToolCallResult",
    "ToolRegistry",
    "ToolResult",
    "tool",
    # Shared tools - Memory
    "search_memory",
    "store_memory",
    "list_memory_collections",
    "get_memory_stats",
    "delete_memory",
    # Shared tools - Collaboration
    "notify_user",
    "request_agent_help",
    "broadcast_status",
    # Shared tools - Subagent
    "spawn_subagent",
    # Shared tools - System
    "get_system_info",
    "check_service_health",
    "shell_execute",
    "process_list",
    "process_kill",
    "service_manage",
    "resource_monitor",
]
