"""
Plugin Integration Module.

Provides integration between the plugin system and agents.
Handles plugin loading, tool registration, and hook triggering.
"""

import asyncio
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

from .logging import get_logger
from .plugins import (
    HookEvent,
    Plugin,
    PluginRegistry,
    PluginStatus,
    PluginTool,
    get_plugin_registry,
    init_plugins,
)

if TYPE_CHECKING:
    from base_agent import BaseAgent, Tool

logger = get_logger(__name__)


class PluginIntegration:
    """
    Integrates plugin system with agents.

    Provides:
    - Plugin loading for specific agents
    - Tool conversion from plugin format to agent format
    - Hook triggering and context management
    """

    def __init__(
        self,
        agent_name: str,
        plugins_dir: str | Path = "/home/wyld-core/plugins",
    ):
        self.agent_name = agent_name
        self.plugins_dir = Path(plugins_dir)
        self._registry: PluginRegistry | None = None
        self._initialized = False

    def initialize(self) -> bool:
        """
        Initialize the plugin system and load plugins.

        Returns:
            True if initialized successfully
        """
        if self._initialized:
            return True

        try:
            self._registry = get_plugin_registry(self.plugins_dir)
            discovered = self._registry.discover_plugins()

            if discovered:
                results = self._registry.load_all()
                loaded = sum(1 for v in results.values() if v)
                logger.info(
                    "Plugins initialized",
                    agent=self.agent_name,
                    discovered=len(discovered),
                    loaded=loaded,
                )

            self._initialized = True
            return True

        except Exception as e:
            logger.error("Failed to initialize plugins", error=str(e))
            return False

    @property
    def registry(self) -> PluginRegistry | None:
        """Get the plugin registry."""
        return self._registry

    def get_plugin_tools(self) -> list[PluginTool]:
        """
        Get all plugin tools available to this agent.

        Returns:
            List of PluginTool objects
        """
        if not self._registry:
            return []

        return self._registry.get_tools_for_agent(self.agent_name)

    def convert_plugin_tool_to_agent_tool(
        self,
        plugin_tool: PluginTool,
    ) -> dict[str, Any]:
        """
        Convert a PluginTool to the format expected by BaseAgent.

        Args:
            plugin_tool: The plugin tool to convert

        Returns:
            Tool configuration dict for agent registration
        """
        return {
            "name": plugin_tool.name,
            "description": plugin_tool.description,
            "parameters": plugin_tool.parameters,
            "handler": plugin_tool._callable,
            "permission_level": plugin_tool.permission_level,
            "source": "plugin",
        }

    def get_tools_for_claude(self) -> list[dict[str, Any]]:
        """
        Get plugin tools in Claude API format.

        Returns:
            List of tool definitions for Claude API
        """
        tools = []
        for plugin_tool in self.get_plugin_tools():
            tool = {
                "name": plugin_tool.name,
                "description": plugin_tool.description,
                "input_schema": plugin_tool.parameters,
            }
            tools.append(tool)
        return tools

    async def execute_plugin_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute a plugin tool.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            context: Additional context

        Returns:
            Tool execution result
        """
        if not self._registry:
            return {"success": False, "error": "Plugin system not initialized"}

        tool = self._registry.tools.get(tool_name)
        if not tool:
            return {"success": False, "error": f"Tool not found: {tool_name}"}

        if not tool._callable:
            return {"success": False, "error": f"Tool handler not loaded: {tool_name}"}

        try:
            # Execute the tool
            if asyncio.iscoroutinefunction(tool._callable):
                result = await tool._callable(**arguments)
            else:
                result = tool._callable(**arguments)

            return result if isinstance(result, dict) else {"success": True, "result": result}

        except Exception as e:
            logger.error("Plugin tool execution failed", tool=tool_name, error=str(e))
            return {"success": False, "error": str(e)}

    async def trigger_hook(
        self,
        event: HookEvent | str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Trigger plugin hooks for an event.

        Args:
            event: The hook event to trigger
            context: Context data to pass to hooks

        Returns:
            Modified context after all hooks have run
        """
        if not self._registry:
            return context

        # Convert string to HookEvent if needed
        if isinstance(event, str):
            try:
                event = HookEvent(event)
            except ValueError:
                logger.warning("Unknown hook event", hook_event=event)
                return context

        return await self._registry.trigger_hook(event, context)

    def get_active_plugins(self) -> list[dict[str, Any]]:
        """
        Get information about active plugins.

        Returns:
            List of plugin info dicts
        """
        if not self._registry:
            return []

        plugins = []
        for name, plugin in self._registry.plugins.items():
            if plugin.status == PluginStatus.ACTIVE:
                plugins.append({
                    "name": name,
                    "version": plugin.version,
                    "description": plugin.description,
                    "tools": [t.name for t in plugin.tools],
                    "hooks": [h.event.value for h in plugin.hooks],
                })
        return plugins


# Global integration instances per agent
_integrations: dict[str, PluginIntegration] = {}


def get_plugin_integration(
    agent_name: str,
    plugins_dir: str | Path = "/home/wyld-core/plugins",
) -> PluginIntegration:
    """
    Get or create a plugin integration for an agent.

    Args:
        agent_name: Name of the agent
        plugins_dir: Directory containing plugins

    Returns:
        PluginIntegration instance
    """
    if agent_name not in _integrations:
        _integrations[agent_name] = PluginIntegration(agent_name, plugins_dir)
    return _integrations[agent_name]


def init_agent_plugins(
    agent_name: str,
    plugins_dir: str | Path = "/home/wyld-core/plugins",
) -> PluginIntegration:
    """
    Initialize plugins for an agent.

    Args:
        agent_name: Name of the agent
        plugins_dir: Directory containing plugins

    Returns:
        Initialized PluginIntegration instance
    """
    integration = get_plugin_integration(agent_name, plugins_dir)
    integration.initialize()
    return integration
