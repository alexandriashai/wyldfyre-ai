"""
MCP (Model Context Protocol) Client for AI Infrastructure.

Provides integration with MCP servers to extend agent capabilities
with external tools and resources.
"""

import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool as MCPTool

from .logging import get_logger
from .plugins import MCPServerConfig

logger = get_logger(__name__)


@dataclass
class MCPToolResult:
    """Result from an MCP tool call."""
    success: bool
    content: Any
    error: Optional[str] = None


@dataclass
class ConnectedMCPServer:
    """A connected MCP server with its session."""
    config: MCPServerConfig
    session: ClientSession
    tools: list[MCPTool] = field(default_factory=list)


class MCPClient:
    """
    Client for connecting to and interacting with MCP servers.

    Manages connections to multiple MCP servers and provides
    a unified interface for tool discovery and execution.
    """

    def __init__(self):
        self.servers: dict[str, ConnectedMCPServer] = {}
        self.exit_stack = AsyncExitStack()
        self._tools_cache: dict[str, tuple[str, MCPTool]] = {}  # tool_name -> (server_name, tool)

    async def connect_server(self, config: MCPServerConfig) -> bool:
        """
        Connect to an MCP server.

        Args:
            config: Server configuration

        Returns:
            True if connected successfully
        """
        if not config.enabled:
            logger.debug("Skipping disabled MCP server", name=config.name)
            return False

        if config.name in self.servers:
            logger.warning("Server already connected", name=config.name)
            return True

        try:
            # Determine if it's a Python or Node.js server
            is_python = config.command.endswith(".py") or config.command == "python"
            is_node = config.command.endswith(".js") or config.command in ("node", "npx")

            if is_python:
                command = "python"
                args = [config.command] + config.args if config.command != "python" else config.args
            elif is_node:
                command = config.command if config.command in ("node", "npx") else "node"
                args = [config.command] + config.args if config.command not in ("node", "npx") else config.args
            else:
                command = config.command
                args = config.args

            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=config.env if config.env else None,
            )

            # Connect using stdio transport
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            stdio, write = stdio_transport

            # Create session
            session = await self.exit_stack.enter_async_context(
                ClientSession(stdio, write)
            )

            # Initialize the session
            await session.initialize()

            # List available tools
            tools_response = await session.list_tools()
            tools = tools_response.tools

            # Store connection
            self.servers[config.name] = ConnectedMCPServer(
                config=config,
                session=session,
                tools=tools,
            )

            # Cache tools for quick lookup
            for tool in tools:
                self._tools_cache[tool.name] = (config.name, tool)

            logger.info(
                "Connected to MCP server",
                name=config.name,
                tools=[t.name for t in tools],
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to connect to MCP server",
                name=config.name,
                error=str(e),
            )
            return False

    async def connect_servers(self, configs: list[MCPServerConfig]) -> dict[str, bool]:
        """
        Connect to multiple MCP servers.

        Args:
            configs: List of server configurations

        Returns:
            Dict mapping server name to connection success
        """
        results = {}
        for config in configs:
            results[config.name] = await self.connect_server(config)
        return results

    async def disconnect_server(self, name: str) -> bool:
        """Disconnect from an MCP server."""
        if name not in self.servers:
            return False

        server = self.servers.pop(name)

        # Remove tools from cache
        for tool in server.tools:
            self._tools_cache.pop(tool.name, None)

        logger.info("Disconnected from MCP server", name=name)
        return True

    async def disconnect_all(self) -> None:
        """Disconnect from all MCP servers."""
        await self.exit_stack.aclose()
        self.servers.clear()
        self._tools_cache.clear()
        logger.info("Disconnected from all MCP servers")

    def list_tools(self) -> list[dict[str, Any]]:
        """
        List all available tools from connected servers.

        Returns:
            List of tool definitions in Claude-compatible format
        """
        tools = []
        for tool_name, (server_name, tool) in self._tools_cache.items():
            tools.append({
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema,
                "server": server_name,
            })
        return tools

    def get_tools_for_claude(self) -> list[dict[str, Any]]:
        """
        Get tools in format suitable for Claude API.

        Returns:
            List of tool definitions for Claude's tools parameter
        """
        tools = []
        for tool_name, (server_name, tool) in self._tools_cache.items():
            tools.append({
                "name": tool_name,
                "description": tool.description or f"Tool from {server_name}",
                "input_schema": tool.inputSchema,
            })
        return tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> MCPToolResult:
        """
        Call a tool on an MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Tool execution result
        """
        if tool_name not in self._tools_cache:
            return MCPToolResult(
                success=False,
                content=None,
                error=f"Tool not found: {tool_name}",
            )

        server_name, tool = self._tools_cache[tool_name]
        server = self.servers.get(server_name)

        if server is None:
            return MCPToolResult(
                success=False,
                content=None,
                error=f"Server not connected: {server_name}",
            )

        try:
            result = await server.session.call_tool(tool_name, arguments)

            # Extract content from result
            content = []
            for item in result.content:
                if hasattr(item, "text"):
                    content.append(item.text)
                elif hasattr(item, "data"):
                    content.append(item.data)
                else:
                    content.append(str(item))

            return MCPToolResult(
                success=True,
                content="\n".join(content) if content else None,
            )

        except Exception as e:
            logger.error(
                "MCP tool call failed",
                tool=tool_name,
                server=server_name,
                error=str(e),
            )
            return MCPToolResult(
                success=False,
                content=None,
                error=str(e),
            )

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available."""
        return tool_name in self._tools_cache

    def get_server_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all connected servers."""
        return {
            name: {
                "connected": True,
                "tools": [t.name for t in server.tools],
                "tool_count": len(server.tools),
            }
            for name, server in self.servers.items()
        }


# Global MCP client instance
_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    """Get the global MCP client instance."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client


async def init_mcp_servers(configs: list[MCPServerConfig]) -> MCPClient:
    """Initialize MCP client and connect to servers."""
    client = get_mcp_client()
    await client.connect_servers(configs)
    return client
