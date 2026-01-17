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

from ai_core import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


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
        permission_level: Minimum permission level required
    """

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Awaitable[ToolResult]]
    requires_confirmation: bool = False
    permission_level: int = 0

    def to_claude_schema(self) -> dict[str, Any]:
        """Convert to Claude API tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }


class ToolRegistry:
    """
    Registry for agent tools.

    Manages tool registration, lookup, and execution.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

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

    def list_tools(self, max_permission_level: int | None = None) -> list[Tool]:
        """List all registered tools."""
        tools = list(self._tools.values())
        if max_permission_level is not None:
            tools = [t for t in tools if t.permission_level <= max_permission_level]
        return tools

    def get_claude_schemas(self, max_permission_level: int | None = None) -> list[dict[str, Any]]:
        """Get Claude API schemas for all tools."""
        return [t.to_claude_schema() for t in self.list_tools(max_permission_level)]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """
        Execute a tool by name.

        Args:
            name: Tool name
            arguments: Tool arguments
            context: Execution context (correlation_id, user_id, etc.)

        Returns:
            ToolResult with execution outcome
        """
        tool = self.get(name)
        if not tool:
            return ToolResult.fail(f"Unknown tool: {name}")

        try:
            logger.info("Executing tool", tool=name, args=list(arguments.keys()))

            # Inject context if handler accepts it
            sig = inspect.signature(tool.handler)
            if "context" in sig.parameters:
                result = await tool.handler(**arguments, context=context or {})
            else:
                result = await tool.handler(**arguments)

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
            }
        )
        async def read_file(path: str) -> ToolResult:
            ...
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
