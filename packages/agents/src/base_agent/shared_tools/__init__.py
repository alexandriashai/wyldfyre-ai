"""
Shared tools available to all agents.

These tools enable:
- Memory operations (vector search, storing learnings)
- Agent collaboration (notifications, task scheduling)
- Common utilities
"""

from .memory_tools import (
    search_memory,
    store_memory,
    list_memory_collections,
    get_memory_stats,
    delete_memory,
)


def get_memory_tools():
    """Get all memory tool functions for registration."""
    return [
        search_memory,
        store_memory,
        list_memory_collections,
        get_memory_stats,
        delete_memory,
    ]

from .collaboration_tools import (
    notify_user,
    request_agent_help,
    broadcast_status,
)

from .system_tools import (
    get_system_info,
    check_service_health,
    shell_execute,
    process_list,
    process_kill,
    service_manage,
    resource_monitor,
    system_info,
)

from .subagent_tools import (
    spawn_subagent,
)

from .aider_tool import aider_code

from .browser_shared import (
    browser_status,
    screenshot_url,
    page_content_fetch,
    visual_diff,
    get_browser_shared_tools,
)

__all__ = [
    # Memory tools
    "search_memory",
    "store_memory",
    "list_memory_collections",
    "get_memory_stats",
    "delete_memory",
    "get_memory_tools",
    # Collaboration tools
    "notify_user",
    "request_agent_help",
    "broadcast_status",
    # System tools
    "get_system_info",
    "check_service_health",
    "shell_execute",
    "process_list",
    "process_kill",
    "service_manage",
    "resource_monitor",
    "system_info",
    # Subagent tools
    "spawn_subagent",
    # Aider code editing
    "aider_code",
    # Browser shared tools
    "browser_status",
    "screenshot_url",
    "page_content_fetch",
    "visual_diff",
    "get_browser_shared_tools",
]
