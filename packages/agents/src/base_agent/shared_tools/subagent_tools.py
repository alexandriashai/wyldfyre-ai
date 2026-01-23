"""
Subagent spawning tool for dynamic task delegation.

Allows agents to spawn lightweight subagent instances for focused subtasks.
The subagent shares the parent's LLM client and tool registry but maintains
independent conversation history.
"""

import json
from typing import Any

from ai_core import get_logger

from ..subagent import Subagent, SubagentResult
from ..tools import ToolResult, tool

logger = get_logger(__name__)


@tool(
    name="spawn_subagent",
    description="""Spawn a lightweight subagent to handle a focused subtask.
    The subagent has access to the same tools but independent conversation history.
    Use this for research, exploration, or analysis subtasks that benefit from
    a clean context. Max 15 iterations per subagent.

    Returns the subagent's final response and execution metadata.""",
    parameters={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Clear description of the subtask for the subagent to complete",
            },
            "max_iterations": {
                "type": "integer",
                "description": "Maximum iterations for the subagent (default: 10, max: 15)",
                "default": 10,
            },
            "model_tier": {
                "type": "string",
                "enum": ["fast", "balanced", "powerful"],
                "description": "Model tier to use (fast=cheap/quick, balanced=default, powerful=complex tasks)",
                "default": "balanced",
            },
        },
        "required": ["task"],
    },
    permission_level=1,
    side_effects=True,
)
async def spawn_subagent(
    task: str,
    max_iterations: int = 10,
    model_tier: str = "balanced",
    _agent: Any = None,
) -> ToolResult:
    """Spawn and execute a subagent for a focused subtask."""
    try:
        if not _agent:
            return ToolResult.fail("No parent agent context available")

        # Get parent's LLM and tool registry
        llm = _agent._llm
        tool_registry = _agent._tool_registry
        parent_type = _agent.agent_type.value if hasattr(_agent, "agent_type") else "unknown"

        # Publish delegating action
        if hasattr(_agent, "publish_action"):
            await _agent.publish_action(
                "delegating",
                f"Spawning subagent for: {task[:80]}..."
            )

        # Create and execute subagent
        subagent = Subagent(
            llm=llm,
            tool_registry=tool_registry,
            task=task,
            max_iterations=max_iterations,
            model_tier=model_tier,
            parent_agent_type=parent_type,
        )

        result = await subagent.execute()

        # Format the response
        output = {
            "success": result.success,
            "response": result.response,
            "iterations": result.iterations,
            "tool_calls_made": result.tool_calls_made,
        }

        if result.error:
            output["error"] = result.error

        if result.success:
            return ToolResult.ok(
                output,
                subagent_iterations=result.iterations,
                tools_used=len(result.tool_calls_made),
            )
        else:
            return ToolResult.fail(
                f"Subagent failed: {result.error or 'Unknown error'}. "
                f"Partial response: {result.response[:200]}"
            )

    except Exception as e:
        logger.error("Subagent spawn failed", task=task[:100], error=str(e))
        return ToolResult.fail(f"Failed to spawn subagent: {e}")
