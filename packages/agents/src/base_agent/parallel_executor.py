"""
Parallel tool execution for agent tool calls.

Partitions tool calls into parallelizable (no side effects) and sequential
(side effects) groups, executing the parallel batch concurrently via asyncio.gather().
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from ai_core import get_logger

from .tools import ToolRegistry, ToolResult

logger = get_logger(__name__)


@dataclass
class ToolCallRequest:
    """A pending tool call to execute."""

    name: str
    arguments: dict[str, Any]
    tool_use_id: str


@dataclass
class ToolCallResult:
    """Result of a tool call execution."""

    tool_use_id: str
    tool_name: str
    result: ToolResult


class ParallelToolExecutor:
    """
    Executes tool calls with parallel/sequential partitioning.

    Tools marked with side_effects=False are safe to run concurrently.
    Tools with side_effects=True run sequentially after the parallel batch.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def partition(
        self, calls: list[ToolCallRequest]
    ) -> tuple[list[ToolCallRequest], list[ToolCallRequest]]:
        """
        Partition tool calls into parallel and sequential groups.

        Returns:
            (parallel_calls, sequential_calls)
        """
        parallel = []
        sequential = []

        for call in calls:
            tool = self._registry.get(call.name)
            if tool and not tool.side_effects:
                parallel.append(call)
            else:
                sequential.append(call)

        return parallel, sequential

    async def execute_parallel(
        self,
        calls: list[ToolCallRequest],
        context: dict[str, Any] | None = None,
    ) -> list[ToolCallResult]:
        """
        Execute multiple tool calls concurrently.

        Args:
            calls: List of tool calls to execute in parallel
            context: Execution context passed to each tool

        Returns:
            List of results in the same order as input calls
        """
        if not calls:
            return []

        async def _run_one(call: ToolCallRequest) -> ToolCallResult:
            result = await self._registry.execute(
                call.name,
                call.arguments,
                context=context,
            )
            return ToolCallResult(
                tool_use_id=call.tool_use_id,
                tool_name=call.name,
                result=result,
            )

        results = await asyncio.gather(*[_run_one(c) for c in calls])
        return list(results)

    async def execute_sequential(
        self,
        calls: list[ToolCallRequest],
        context: dict[str, Any] | None = None,
    ) -> list[ToolCallResult]:
        """
        Execute tool calls sequentially.

        Args:
            calls: List of tool calls to execute one by one
            context: Execution context passed to each tool

        Returns:
            List of results in order
        """
        results = []
        for call in calls:
            result = await self._registry.execute(
                call.name,
                call.arguments,
                context=context,
            )
            results.append(ToolCallResult(
                tool_use_id=call.tool_use_id,
                tool_name=call.name,
                result=result,
            ))
        return results

    def can_parallelize(self, calls: list[ToolCallRequest]) -> bool:
        """Check if any calls in the batch can be parallelized."""
        for call in calls:
            tool = self._registry.get(call.name)
            if tool and not tool.side_effects:
                return True
        return False
