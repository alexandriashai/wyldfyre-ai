"""
Plugin System for AI Infrastructure.

Provides a manifest-based plugin architecture similar to Claude Code plugins.
Supports:
- Tool registration from plugins
- Hook system for event handling
- MCP server integration
- Hot-reload capability
"""

import importlib.util
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from .logging import get_logger

logger = get_logger(__name__)


class PluginStatus(str, Enum):
    """Plugin lifecycle status."""
    DISCOVERED = "discovered"
    LOADING = "loading"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"


class HookEvent(str, Enum):
    """Supported hook events."""
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    TASK_ERROR = "task_error"
    AGENT_ERROR = "agent_error"
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"
    # New hook for user prompt processing (Phase 2 Enhancement)
    USER_PROMPT_SUBMIT = "user_prompt_submit"


@dataclass
class PluginTool:
    """A tool provided by a plugin."""
    name: str
    description: str
    handler: str  # module:function path
    parameters: dict[str, Any]
    permission_level: int = 0
    _callable: Optional[Callable[..., Any]] = field(default=None, repr=False)


@dataclass
class PluginHook:
    """A hook provided by a plugin."""
    event: HookEvent
    handler: str  # module:function path
    priority: int = 50  # 0-100, higher = runs first
    _callable: Optional[Callable[..., Any]] = field(default=None, repr=False)


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class Plugin:
    """A loaded plugin."""
    name: str
    version: str
    description: str
    author: str
    path: Path
    status: PluginStatus = PluginStatus.DISCOVERED

    # Components
    tools: list[PluginTool] = field(default_factory=list)
    hooks: list[PluginHook] = field(default_factory=list)
    mcp_servers: list[MCPServerConfig] = field(default_factory=list)

    # Metadata
    requires: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    agents: list[str] = field(default_factory=list)  # Which agents can use this plugin

    # Runtime
    loaded_at: Optional[datetime] = None
    error: Optional[str] = None


class PluginRegistry:
    """
    Central registry for all plugins.

    Handles discovery, loading, and management of plugins.
    """

    def __init__(self, plugins_dir: str | Path = "plugins"):
        self.plugins_dir = Path(plugins_dir)
        self.plugins: dict[str, Plugin] = {}
        self.tools: dict[str, PluginTool] = {}
        self.hooks: dict[HookEvent, list[PluginHook]] = {event: [] for event in HookEvent}
        self.mcp_servers: dict[str, MCPServerConfig] = {}

    def discover_plugins(self) -> list[str]:
        """
        Discover all plugins in the plugins directory.

        Returns:
            List of discovered plugin names
        """
        discovered: list[str] = []

        if not self.plugins_dir.exists():
            logger.warning("Plugins directory does not exist", path=str(self.plugins_dir))
            return discovered

        for plugin_path in self.plugins_dir.iterdir():
            if not plugin_path.is_dir():
                continue

            manifest_path = plugin_path / "manifest.yaml"
            if not manifest_path.exists():
                # Also check for plugin.json (Claude Code style)
                manifest_path = plugin_path / ".claude-plugin" / "plugin.json"
                if not manifest_path.exists():
                    continue

            try:
                plugin = self._load_manifest(plugin_path, manifest_path)
                self.plugins[plugin.name] = plugin
                discovered.append(plugin.name)
                logger.info("Discovered plugin", name=plugin.name, version=plugin.version)
            except Exception as e:
                logger.error("Failed to load plugin manifest", path=str(plugin_path), error=str(e))

        return discovered

    def _load_manifest(self, plugin_path: Path, manifest_path: Path) -> Plugin:
        """Load a plugin manifest file."""
        with open(manifest_path) as f:
            if manifest_path.suffix == ".json":
                import json
                data = json.load(f)
            else:
                data = yaml.safe_load(f)

        # Parse tools
        tools = []
        for tool_data in data.get("tools", []):
            tools.append(PluginTool(
                name=tool_data["name"],
                description=tool_data.get("description", ""),
                handler=tool_data["handler"],
                parameters=tool_data.get("parameters", {}),
                permission_level=tool_data.get("permission_level", 0),
            ))

        # Parse hooks
        hooks = []
        for hook_data in data.get("hooks", []):
            try:
                event = HookEvent(hook_data["event"])
                hooks.append(PluginHook(
                    event=event,
                    handler=hook_data["handler"],
                    priority=hook_data.get("priority", 50),
                ))
            except ValueError:
                logger.warning("Unknown hook event", hook_event=hook_data.get("event"))

        # Parse MCP servers
        mcp_servers = []
        for mcp_data in data.get("mcp_servers", []):
            mcp_servers.append(MCPServerConfig(
                name=mcp_data["name"],
                command=mcp_data["command"],
                args=mcp_data.get("args", []),
                env=mcp_data.get("env", {}),
                enabled=mcp_data.get("enabled", True),
            ))

        return Plugin(
            name=data["name"],
            version=data.get("version", "0.0.0"),
            description=data.get("description", ""),
            author=data.get("author", "Unknown"),
            path=plugin_path,
            tools=tools,
            hooks=hooks,
            mcp_servers=mcp_servers,
            requires=data.get("requires", []),
            permissions=data.get("permissions", []),
            config=data.get("config", {}),
            agents=data.get("agents", ["*"]),  # Default to all agents
        )

    def load_plugin(self, name: str) -> bool:
        """
        Load a plugin and register its components.

        Args:
            name: Plugin name to load

        Returns:
            True if loaded successfully
        """
        if name not in self.plugins:
            logger.error("Plugin not found", name=name)
            return False

        plugin = self.plugins[name]
        plugin.status = PluginStatus.LOADING

        try:
            # Load tool handlers
            for tool in plugin.tools:
                tool._callable = self._load_handler(plugin.path, tool.handler)
                self.tools[tool.name] = tool
                logger.debug("Registered tool", plugin=name, tool=tool.name)

            # Load hook handlers
            for hook in plugin.hooks:
                hook._callable = self._load_handler(plugin.path, hook.handler)
                self.hooks[hook.event].append(hook)
                # Sort by priority (higher first)
                self.hooks[hook.event].sort(key=lambda h: h.priority, reverse=True)
                logger.debug("Registered hook", plugin=name, hook_event=hook.event.value)

            # Register MCP servers
            for mcp in plugin.mcp_servers:
                self.mcp_servers[mcp.name] = mcp
                logger.debug("Registered MCP server", plugin=name, server=mcp.name)

            plugin.status = PluginStatus.ACTIVE
            plugin.loaded_at = datetime.now(timezone.utc)
            logger.info("Plugin loaded successfully", name=name)
            return True

        except Exception as e:
            plugin.status = PluginStatus.ERROR
            plugin.error = str(e)
            logger.error("Failed to load plugin", name=name, error=str(e))
            return False

    def _load_handler(self, plugin_path: Path, handler_path: str) -> Callable[..., Any]:
        """
        Load a handler function from a module path.

        Args:
            plugin_path: Base path of the plugin
            handler_path: Handler in format "module:function" or "module.submodule:function"
        """
        module_path, func_name = handler_path.rsplit(":", 1)

        # Convert module path to file path
        # Handle both "tools" (direct) and "tools.submodule" (nested)
        parts = module_path.split(".")
        module_file = plugin_path

        for part in parts:
            module_file = module_file / part

        # Try different file patterns
        if module_file.with_suffix(".py").exists():
            module_file = module_file.with_suffix(".py")
        elif (module_file / "__init__.py").exists():
            module_file = module_file / "__init__.py"
        elif module_file.exists() and module_file.is_dir():
            # It's a package
            module_file = module_file / "__init__.py"
        else:
            # Fallback: try as direct .py file in plugin root
            alt_file = plugin_path / f"{module_path}.py"
            if alt_file.exists():
                module_file = alt_file
            else:
                raise ImportError(f"Module not found: {module_path} (tried {module_file})")

        # Create a unique module name to avoid conflicts
        unique_module_name = f"plugins.{plugin_path.name}.{module_path}"

        # Load the module
        spec = importlib.util.spec_from_file_location(unique_module_name, module_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module: {module_path} from {module_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[unique_module_name] = module
        spec.loader.exec_module(module)

        # Get the function
        func = getattr(module, func_name, None)
        if func is None:
            raise ImportError(f"Function not found: {func_name} in {module_path}")

        return func

    def load_all(self) -> dict[str, bool]:
        """
        Load all discovered plugins.

        Returns:
            Dict mapping plugin name to load success
        """
        results = {}
        for name in self.plugins:
            results[name] = self.load_plugin(name)
        return results

    def unload_plugin(self, name: str) -> bool:
        """Unload a plugin and unregister its components."""
        if name not in self.plugins:
            return False

        plugin = self.plugins[name]

        # Remove tools
        for tool in plugin.tools:
            self.tools.pop(tool.name, None)

        # Remove hooks
        for hook in plugin.hooks:
            if hook in self.hooks[hook.event]:
                self.hooks[hook.event].remove(hook)

        # Remove MCP servers
        for mcp in plugin.mcp_servers:
            self.mcp_servers.pop(mcp.name, None)

        plugin.status = PluginStatus.DISABLED
        logger.info("Plugin unloaded", name=name)
        return True

    def reload_plugin(self, name: str) -> bool:
        """Reload a plugin (hot-reload)."""
        self.unload_plugin(name)

        # Re-discover to pick up manifest changes
        manifest_path = self.plugins[name].path / "manifest.yaml"
        if manifest_path.exists():
            try:
                self.plugins[name] = self._load_manifest(self.plugins[name].path, manifest_path)
            except Exception as e:
                logger.error("Failed to reload manifest", name=name, error=str(e))
                return False

        return self.load_plugin(name)

    async def trigger_hook(
        self,
        event: HookEvent,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Trigger all hooks for an event.

        Args:
            event: The hook event to trigger
            context: Context data to pass to hooks

        Returns:
            Modified context after all hooks have run
        """
        import asyncio

        for hook in self.hooks[event]:
            if hook._callable is None:
                continue

            try:
                # Hooks receive context and return modified context
                if asyncio.iscoroutinefunction(hook._callable):
                    result = await hook._callable(context)
                else:
                    result = hook._callable(context)

                # If hook returns a dict, use it as the new context
                # This preserves all keys including those the hook didn't modify
                if isinstance(result, dict):
                    context = result

            except Exception as e:
                logger.error(
                    "Hook execution failed",
                    hook_event=event.value,
                    handler=hook.handler,
                    error=str(e),
                )
                # Continue with other hooks even if one fails

        return context

    def get_tools_for_agent(self, agent_name: str) -> list[PluginTool]:
        """Get all tools available to a specific agent."""
        available = []
        for plugin in self.plugins.values():
            if plugin.status != PluginStatus.ACTIVE:
                continue
            if "*" in plugin.agents or agent_name in plugin.agents:
                available.extend(plugin.tools)
        return available

    def get_plugin_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all plugins."""
        return {
            name: {
                "status": plugin.status.value,
                "version": plugin.version,
                "tools": len(plugin.tools),
                "hooks": len(plugin.hooks),
                "mcp_servers": len(plugin.mcp_servers),
                "loaded_at": plugin.loaded_at.isoformat() if plugin.loaded_at else None,
                "error": plugin.error,
            }
            for name, plugin in self.plugins.items()
        }


# Global plugin registry
_plugin_registry: Optional[PluginRegistry] = None


def get_plugin_registry(plugins_dir: str | Path = "plugins") -> PluginRegistry:
    """Get the global plugin registry."""
    global _plugin_registry
    if _plugin_registry is None:
        _plugin_registry = PluginRegistry(plugins_dir)
    return _plugin_registry


def init_plugins(plugins_dir: str | Path = "plugins") -> PluginRegistry:
    """Initialize and load all plugins."""
    registry = get_plugin_registry(plugins_dir)
    registry.discover_plugins()
    registry.load_all()
    return registry
