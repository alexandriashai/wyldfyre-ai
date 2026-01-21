"""
Tool system for AI agents.

Provides a registry and execution framework for agent tools,
compatible with Claude's tool use API.
"""

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from pydantic import BaseModel, Field

from ai_core import (
    CapabilityCategory,
    ElevationReason,
    PermissionContext,
    PermissionLevel,
    get_elevation_manager,
    get_logger,
    get_security_validator,
)

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

# Tools that always require explicit confirmation, regardless of permission level
CRITICAL_TOOLS = frozenset([
    "docker_compose_down",
    "docker_system_prune",
    "delete_file",
    "directory_delete",
    "file_chown",
    "package_remove",
    "process_kill",
])


class ToolResult(BaseModel):
    """Result from tool execution."""

    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def ok(cls, output: Any, **metadata: Any) -> "ToolResult":
        """Create successful result."""
        return cls(success=True, output=output, metadata=metadata)

    @classmethod
    def fail(cls, error: str, **metadata: Any) -> "ToolResult":
        """Create failed result."""
        return cls(success=False, error=error, metadata=metadata)


@dataclass
class Tool:
    """
    Represents a tool that can be used by an agent.

    Attributes:
        name: Unique tool identifier
        description: Human-readable description
        parameters: JSON Schema for tool parameters
        handler: Async function to execute the tool
        requires_confirmation: Whether to require user confirmation
        permission_level: Minimum permission level required (0-4)
        capability_category: Category of capability (system, file, network, etc.)
        allows_elevation: Whether this tool can be accessed via elevation
        max_elevation_level: Maximum level this tool can be elevated to
    """

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Awaitable[ToolResult]]
    requires_confirmation: bool = False
    permission_level: int = 0
    capability_category: CapabilityCategory | None = None
    allows_elevation: bool = True
    max_elevation_level: int | None = None

    def __post_init__(self) -> None:
        """Set default max elevation level if not specified."""
        if self.max_elevation_level is None:
            self.max_elevation_level = self.permission_level

    @property
    def is_critical(self) -> bool:
        """Check if this tool is in the critical tools list."""
        return self.name in CRITICAL_TOOLS

    def to_claude_schema(self) -> dict[str, Any]:
        """Convert to Claude API tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def to_permission_info(self) -> dict[str, Any]:
        """Get permission-related information for debugging."""
        return {
            "name": self.name,
            "permission_level": self.permission_level,
            "capability_category": self.capability_category.value if self.capability_category else None,
            "allows_elevation": self.allows_elevation,
            "max_elevation_level": self.max_elevation_level,
            "requires_confirmation": self.requires_confirmation,
            "is_critical": self.is_critical,
        }


class ToolRegistry:
    """
    Registry for agent tools.

    Manages tool registration, lookup, and execution with permission checking.
    """

    def __init__(self, permission_context: PermissionContext | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self._permission_context = permission_context
        self._elevation_manager = get_elevation_manager()

    def set_permission_context(self, context: PermissionContext) -> None:
        """Set the permission context for this registry."""
        self._permission_context = context

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        if tool.name in self._tools:
            logger.warning("Overwriting existing tool", tool=tool.name)
        self._tools[tool.name] = tool
        logger.debug("Registered tool", tool=tool.name)

    def unregister(self, name: str) -> bool:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(
        self,
        max_permission_level: int | None = None,
        capability_filter: CapabilityCategory | None = None,
        include_elevatable: bool = False,
    ) -> list[Tool]:
        """
        List registered tools with optional filtering.

        Args:
            max_permission_level: Filter by maximum permission level
            capability_filter: Filter by capability category
            include_elevatable: Include tools that can be accessed via elevation

        Returns:
            List of matching tools
        """
        tools = list(self._tools.values())

        if max_permission_level is not None:
            if include_elevatable and self._permission_context:
                # Include tools that can be accessed via elevation
                ceiling = self._permission_context.allowed_elevation_to
                max_level = ceiling.value if ceiling else max_permission_level + 1
                tools = [
                    t for t in tools
                    if t.permission_level <= max_permission_level
                    or (t.allows_elevation and t.permission_level <= max_level)
                ]
            else:
                tools = [t for t in tools if t.permission_level <= max_permission_level]

        if capability_filter:
            tools = [
                t for t in tools
                if t.capability_category == capability_filter
            ]

        return tools

    def get_claude_schemas(
        self,
        max_permission_level: int | None = None,
        include_elevatable: bool = True,
    ) -> list[dict[str, Any]]:
        """Get Claude API schemas for all accessible tools."""
        return [
            t.to_claude_schema()
            for t in self.list_tools(max_permission_level, include_elevatable=include_elevatable)
        ]

    def check_permission(
        self,
        tool: Tool,
        task_id: str | None = None,
    ) -> tuple[bool, str | None]:
        """
        Check if the current context has permission to execute a tool.

        Args:
            tool: The tool to check
            task_id: Current task ID for elevation tracking

        Returns:
            Tuple of (allowed, elevation_grant_id or error_message)
        """
        if not self._permission_context:
            # No permission context - allow all (backward compatibility)
            return True, None

        required_level = PermissionLevel(tool.permission_level)
        current_level = self._permission_context.current_level

        # Check capability access
        if tool.capability_category:
            if self._permission_context.allowed_capabilities:
                if tool.capability_category not in self._permission_context.allowed_capabilities:
                    return False, f"Capability not allowed: {tool.capability_category.value}"

        # Check permission level
        if current_level >= required_level:
            return True, None

        # Check if elevation is possible
        if not tool.allows_elevation:
            return False, f"Tool {tool.name} does not allow elevation"

        # Try auto-elevation
        auto_approved, result = self._elevation_manager.request_elevation(
            context=self._permission_context,
            target_level=required_level,
            tool_name=tool.name,
            task_id=task_id or "unknown",
            reason=ElevationReason.TOOL_REQUIREMENT,
            justification=f"Tool {tool.name} requires level {required_level.value}",
        )

        if auto_approved and result:
            # Update active elevation in context
            self._permission_context.active_elevation = result
            return True, result.id

        if result:
            # Needs supervisor approval
            return False, f"Elevation request pending: {result.id}"

        return False, f"Permission denied: requires level {required_level.value}"

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """
        Execute a tool by name with permission checking.

        Args:
            name: Tool name
            arguments: Tool arguments
            context: Execution context (task_id, user_id, etc.)

        Returns:
            ToolResult with execution outcome
        """
        tool = self.get(name)
        if not tool:
            return ToolResult.fail(f"Unknown tool: {name}")

        # Check permissions
        task_id = context.get("task_id") if context else None
        allowed, info = self.check_permission(tool, task_id)

        if not allowed:
            logger.warning(
                "Permission denied for tool",
                tool=name,
                reason=info,
            )
            return ToolResult.fail(f"Permission denied: {info}")

        # Log if elevation was used
        if info:
            logger.info(
                "Tool executed with elevation",
                tool=name,
                elevation_grant_id=info,
            )

        # Security validation - check for dangerous operations
        agent_name = context.get("agent_name") if context else None
        security_validator = get_security_validator()
        security_result = security_validator.validate_tool_input(name, arguments, agent_name)

        if security_result.blocked:
            logger.warning(
                "Security blocked tool execution",
                tool=name,
                rule=security_result.rule_name,
                message=security_result.message,
                threat_level=security_result.threat_level.value,
                agent=agent_name,
            )
            return ToolResult.fail(f"Security blocked: {security_result.message}")

        try:
            logger.info(
                "Executing tool",
                tool=name,
                args=list(arguments.keys()),
                permission_level=tool.permission_level,
                capability=tool.capability_category.value if tool.capability_category else None,
            )

            # Inject special parameters if handler accepts them
            sig = inspect.signature(tool.handler)
            ctx = context or {}

            # Build kwargs for the handler
            kwargs = dict(arguments)

            # Inject context parameters that the handler can accept
            if "context" in sig.parameters:
                kwargs["context"] = ctx
            if "_memory" in sig.parameters and "_memory" in ctx:
                kwargs["_memory"] = ctx["_memory"]
            if "_agent_type" in sig.parameters and "_agent_type" in ctx:
                kwargs["_agent_type"] = ctx["_agent_type"]
            if "_task_id" in sig.parameters and "_task_id" in ctx:
                kwargs["_task_id"] = ctx["_task_id"]

            result = await tool.handler(**kwargs)

            logger.info(
                "Tool execution complete",
                tool=name,
                success=result.success,
            )
            return result

        except Exception as e:
            logger.error("Tool execution failed", tool=name, error=str(e))
            return ToolResult.fail(str(e))


def tool(
    name: str,
    description: str,
    parameters: dict[str, Any] | None = None,
    requires_confirmation: bool = False,
    permission_level: int = 0,
    capability_category: CapabilityCategory | None = None,
    allows_elevation: bool = True,
    max_elevation_level: int | None = None,
) -> Callable[[Callable[P, Awaitable[ToolResult]]], Callable[P, Awaitable[ToolResult]]]:
    """
    Decorator to create a tool from an async function.

    Usage:
        @tool(
            name="read_file",
            description="Read contents of a file",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"}
                },
                "required": ["path"]
            },
            capability_category=CapabilityCategory.FILE,
        )
        async def read_file(path: str) -> ToolResult:
            ...

    Args:
        name: Unique tool identifier
        description: Human-readable description
        parameters: JSON Schema for tool parameters (auto-generated if None)
        requires_confirmation: Whether to require user confirmation
        permission_level: Minimum permission level required (0-4)
        capability_category: Category of capability for access control
        allows_elevation: Whether this tool can be accessed via elevation
        max_elevation_level: Maximum level this tool can be elevated to
    """

    def decorator(
        func: Callable[P, Awaitable[ToolResult]]
    ) -> Callable[P, Awaitable[ToolResult]]:
        # Generate parameters from function signature if not provided
        tool_params = parameters
        if tool_params is None:
            tool_params = _generate_parameters_from_signature(func)

        # Store tool metadata on function
        func._tool = Tool(
            name=name,
            description=description,
            parameters=tool_params,
            handler=func,
            requires_confirmation=requires_confirmation,
            permission_level=permission_level,
            capability_category=capability_category,
            allows_elevation=allows_elevation,
            max_elevation_level=max_elevation_level,
        )

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> ToolResult:
            return await func(*args, **kwargs)

        wrapper._tool = func._tool
        return wrapper

    return decorator


def _generate_parameters_from_signature(func: Callable[..., Any]) -> dict[str, Any]:
    """Generate JSON Schema parameters from function signature."""
    sig = inspect.signature(func)
    properties = {}
    required = []

    type_mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "context"):
            continue

        # Get type annotation
        param_type = "string"  # default
        if param.annotation != inspect.Parameter.empty:
            origin = getattr(param.annotation, "__origin__", param.annotation)
            param_type = type_mapping.get(origin, "string")

        properties[param_name] = {"type": param_type}

        # Check if required (no default value)
        if param.default == inspect.Parameter.empty:
            required.append(param_name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


# Global registry
_global_registry = ToolRegistry()


def get_global_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return _global_registry


def register_tool(tool: Tool) -> None:
    """Register a tool in the global registry."""
    _global_registry.register(tool)


def collect_tools_from_module(module: Any) -> list[Tool]:
    """Collect all tools decorated with @tool from a module."""
    tools = []
    for name in dir(module):
        obj = getattr(module, name)
        if hasattr(obj, "_tool"):
            tools.append(obj._tool)
    return tools
