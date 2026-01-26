"""
Exploration and planning tools for spawning specialized subagents.

These tools provide Claude Code-style Explore and Plan capabilities
as tools within existing agents, leveraging the subagent pattern.
"""

import json
from typing import Any

from ai_core import get_logger

from ..specialized_subagents import (
    EXPLORE_TOOLS,
    PLAN_TOOLS,
    THOROUGHNESS_MAP,
    ExploreSubagent,
    PlanSubagent,
    create_filtered_registry,
)
from ..tools import ToolResult, tool

logger = get_logger(__name__)


@tool(
    name="spawn_explore_agent",
    description="""Spawn a fast exploration subagent to search and understand code.

Use for:
- Finding files by patterns (glob, grep)
- Searching code for keywords, symbols, or patterns
- Understanding codebase structure and organization
- Tracing dependencies between files and modules
- Locating function/class definitions and references

Returns structured findings with file paths and line numbers.

Examples:
- "Find where authentication is handled"
- "Search for all API endpoint definitions"
- "Find usages of the UserService class"
- "Map the directory structure of src/components"

This is a READ-ONLY operation that will not modify any files.""",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to explore - pattern, symbol, or question about the code",
            },
            "path": {
                "type": "string",
                "description": "Root path to start exploration (default: workspace root)",
            },
            "thoroughness": {
                "type": "string",
                "enum": ["quick", "medium", "thorough"],
                "description": "Exploration depth: quick=3 iterations, medium=7, thorough=12. Use 'quick' for simple pattern searches, 'medium' for understanding code flow, 'thorough' for comprehensive analysis.",
                "default": "medium",
            },
        },
        "required": ["query"],
    },
    permission_level=0,  # Read-only
    side_effects=False,  # Safe to run in parallel
)
async def spawn_explore_agent(
    query: str,
    path: str | None = None,
    thoroughness: str = "medium",
    _agent: Any = None,
) -> ToolResult:
    """Spawn an explore subagent to search and understand code."""
    try:
        if not _agent:
            return ToolResult.fail("No parent agent context available")

        # Validate thoroughness
        if thoroughness not in THOROUGHNESS_MAP:
            thoroughness = "medium"

        max_iterations = THOROUGHNESS_MAP[thoroughness]

        # Get parent's LLM and create filtered tool registry
        llm = _agent._llm
        source_registry = _agent._tool_registry
        filtered_registry = create_filtered_registry(source_registry, EXPLORE_TOOLS)

        parent_type = _agent.agent_type.value if hasattr(_agent, "agent_type") else "unknown"

        # Create action callback to forward to parent
        async def action_callback(action_type: str, description: str) -> None:
            if hasattr(_agent, "publish_action"):
                await _agent.publish_action(action_type, description)

        # Build the exploration task with path context
        task = f"Explore: {query}"
        if path:
            task = f"{task}\n\nStart from path: {path}"

        # Publish start action
        if hasattr(_agent, "publish_action"):
            await _agent.publish_action(
                "delegating",
                f"Spawning explore agent ({thoroughness}): {query[:50]}..."
            )

        # Create and execute explore subagent
        subagent = ExploreSubagent(
            llm=llm,
            tool_registry=filtered_registry,
            task=task,
            max_iterations=max_iterations,
            model_tier="balanced",
            parent_agent_type=parent_type,
            action_callback=action_callback,
        )

        result = await subagent.execute()

        # Format the response
        output = {
            "success": result.success,
            "response": result.response,
            "iterations": result.iterations,
            "tool_calls_made": result.tool_calls_made,
            "thoroughness": thoroughness,
            "usage": {
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
                "cached_tokens": result.usage.cached_tokens,
                "total_cost": str(result.usage.total_cost),
                "model": result.usage.model,
            },
        }

        # Try to parse JSON from response if present
        try:
            # Look for JSON in the response
            response_text = result.response or ""
            if "{" in response_text and "}" in response_text:
                # Extract JSON portion
                start = response_text.index("{")
                end = response_text.rindex("}") + 1
                json_str = response_text[start:end]
                parsed = json.loads(json_str)
                output["structured_findings"] = parsed
        except (json.JSONDecodeError, ValueError):
            pass  # Response wasn't JSON, that's fine

        if result.error:
            output["error"] = result.error

        if result.success:
            return ToolResult.ok(
                output,
                subagent_type="explore",
                subagent_iterations=result.iterations,
                tools_used=len(result.tool_calls_made),
                cost=str(result.usage.total_cost),
            )
        else:
            return ToolResult.fail(
                f"Explore agent failed: {result.error or 'Unknown error'}. "
                f"Partial response: {result.response[:200] if result.response else 'None'}"
            )

    except Exception as e:
        logger.error("Explore agent spawn failed", query=query[:100], error=str(e))
        return ToolResult.fail(f"Failed to spawn explore agent: {e}")


@tool(
    name="spawn_plan_agent",
    description="""Spawn an architecture/planning subagent to design implementation.

Use for:
- Designing new features with proper architecture
- Planning refactors with impact analysis
- Creating implementation roadmaps
- Analyzing architectural trade-offs
- Identifying all files that need changes

Returns a structured plan with files to modify, implementation steps, and considerations.

Examples:
- "Plan adding a notification system"
- "Design the architecture for user authentication"
- "Plan refactoring the API layer to use async"
- "Create a roadmap for migrating to TypeScript"

This is a READ-ONLY operation that analyzes code but will not modify any files.""",
    parameters={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "What to plan - feature, refactor, or architectural change",
            },
            "context": {
                "type": "string",
                "description": "Additional context about requirements, constraints, or preferences",
            },
        },
        "required": ["task"],
    },
    permission_level=0,  # Read-only (planning doesn't modify)
    side_effects=False,  # Safe to run in parallel
)
async def spawn_plan_agent(
    task: str,
    context: str | None = None,
    _agent: Any = None,
) -> ToolResult:
    """Spawn a plan subagent to design implementation approach."""
    try:
        if not _agent:
            return ToolResult.fail("No parent agent context available")

        # Get parent's LLM and create filtered tool registry
        llm = _agent._llm
        source_registry = _agent._tool_registry
        filtered_registry = create_filtered_registry(source_registry, PLAN_TOOLS)

        parent_type = _agent.agent_type.value if hasattr(_agent, "agent_type") else "unknown"

        # Create action callback to forward to parent
        async def action_callback(action_type: str, description: str) -> None:
            if hasattr(_agent, "publish_action"):
                await _agent.publish_action(action_type, description)

        # Publish start action
        if hasattr(_agent, "publish_action"):
            await _agent.publish_action(
                "delegating",
                f"Spawning plan agent: {task[:50]}..."
            )

        # Create and execute plan subagent
        subagent = PlanSubagent(
            llm=llm,
            tool_registry=filtered_registry,
            task=task,
            context=context,
            max_iterations=10,
            model_tier="balanced",
            parent_agent_type=parent_type,
            action_callback=action_callback,
        )

        result = await subagent.execute()

        # Format the response
        output = {
            "success": result.success,
            "response": result.response,
            "iterations": result.iterations,
            "tool_calls_made": result.tool_calls_made,
            "usage": {
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
                "cached_tokens": result.usage.cached_tokens,
                "total_cost": str(result.usage.total_cost),
                "model": result.usage.model,
            },
        }

        # Try to parse JSON from response if present
        try:
            response_text = result.response or ""
            if "{" in response_text and "}" in response_text:
                start = response_text.index("{")
                end = response_text.rindex("}") + 1
                json_str = response_text[start:end]
                parsed = json.loads(json_str)
                output["plan"] = parsed
        except (json.JSONDecodeError, ValueError):
            pass  # Response wasn't JSON, that's fine

        if result.error:
            output["error"] = result.error

        if result.success:
            return ToolResult.ok(
                output,
                subagent_type="plan",
                subagent_iterations=result.iterations,
                tools_used=len(result.tool_calls_made),
                cost=str(result.usage.total_cost),
            )
        else:
            return ToolResult.fail(
                f"Plan agent failed: {result.error or 'Unknown error'}. "
                f"Partial response: {result.response[:200] if result.response else 'None'}"
            )

    except Exception as e:
        logger.error("Plan agent spawn failed", task=task[:100], error=str(e))
        return ToolResult.fail(f"Failed to spawn plan agent: {e}")
