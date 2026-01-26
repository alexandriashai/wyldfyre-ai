"""
Lightweight subagent for focused subtasks.

Subagents share the parent's LLM client and tool registry but maintain
independent conversation history. They are limited to a max number of
iterations and return a structured result to the parent agent.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from ai_core import LLMClient, calculate_cost, get_logger

from .tools import ToolRegistry, ToolResult

logger = get_logger(__name__)

# Hard cap on subagent iterations to prevent runaway loops
MAX_SUBAGENT_ITERATIONS = 15

# Model tier mapping
MODEL_TIERS = {
    "fast": "fast",
    "balanced": "auto",
    "powerful": "powerful",
}

# Type alias for action callback
ActionCallback = Callable[[str, str], Awaitable[None]]


@dataclass
class SubagentUsage:
    """Token usage and cost tracking for subagent execution."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    total_cost: Decimal = field(default_factory=lambda: Decimal("0"))
    model: str | None = None


@dataclass
class SubagentResult:
    """Result from a subagent execution."""

    success: bool
    response: str
    iterations: int
    tool_calls_made: list[str] = field(default_factory=list)
    error: str | None = None
    usage: SubagentUsage = field(default_factory=SubagentUsage)


class Subagent:
    """
    Lightweight agent instance for focused subtasks.

    Shares parent's LLM client and tool registry but maintains
    independent conversation history. Limited to MAX_SUBAGENT_ITERATIONS.
    """

    def __init__(
        self,
        llm: LLMClient,
        tool_registry: ToolRegistry,
        task: str,
        max_iterations: int = 10,
        model_tier: str = "balanced",
        parent_agent_type: str = "unknown",
        action_callback: ActionCallback | None = None,
        subagent_type: str = "subagent",
    ) -> None:
        self._llm = llm
        self._tool_registry = tool_registry
        self._task = task
        self._max_iterations = min(max_iterations, MAX_SUBAGENT_ITERATIONS)
        self._model_tier = MODEL_TIERS.get(model_tier, "auto")
        self._parent_agent_type = parent_agent_type
        self._action_callback = action_callback
        self._subagent_type = subagent_type
        self._conversation: list[dict[str, Any]] = []
        self._tool_calls_made: list[str] = []

    async def _publish_action(self, action_type: str, description: str) -> None:
        """Publish an action to the parent agent for real-time display."""
        if self._action_callback:
            try:
                await self._action_callback(action_type, description)
            except Exception as e:
                logger.debug("Failed to publish subagent action", error=str(e))

    def _summarize_args(self, arguments: dict[str, Any], max_len: int = 60) -> str:
        """Summarize tool arguments for display."""
        if not arguments:
            return ""
        # Convert to a brief string representation
        parts = []
        for k, v in list(arguments.items())[:3]:  # Max 3 args
            v_str = str(v)
            if len(v_str) > 30:
                v_str = v_str[:27] + "..."
            parts.append(f"{k}={v_str}")
        result = ", ".join(parts)
        if len(result) > max_len:
            result = result[:max_len - 3] + "..."
        return result

    def _get_system_prompt(self) -> str:
        """Generate focused system prompt for the subtask."""
        return (
            f"You are a focused subagent spawned by {self._parent_agent_type}. "
            f"Your sole task is: {self._task}\n\n"
            "Guidelines:\n"
            "- Stay focused on the specific task assigned\n"
            "- Use available tools to gather information or make changes\n"
            "- Be concise in your final response\n"
            "- Report errors clearly if you cannot complete the task\n"
            "- Do not ask clarifying questions - work with what you have\n"
        )

    async def execute(self) -> SubagentResult:
        """
        Execute the subtask with the agentic loop.

        Returns:
            SubagentResult with success status, response, and metadata
        """
        # Publish start action
        task_preview = self._task[:60] + "..." if len(self._task) > 60 else self._task
        await self._publish_action(
            "subagent_start",
            f"{self._subagent_type}: Starting - {task_preview}"
        )

        # Initialize with the task as user message
        self._conversation.append({
            "role": "user",
            "content": self._task,
        })

        # Get available tool schemas
        tools = self._tool_registry.get_claude_schemas()

        # Initialize usage tracking
        total_input_tokens = 0
        total_output_tokens = 0
        total_cached_tokens = 0
        total_cost = Decimal("0")
        model_used = None

        iterations = 0
        while iterations < self._max_iterations:
            iterations += 1

            try:
                response = await self._llm.create_message(
                    model=self._model_tier,
                    max_tokens=4096,
                    system=self._get_system_prompt(),
                    messages=self._conversation,
                    tools=tools if tools else None,
                )

                # Track usage from this call
                total_input_tokens += response.input_tokens
                total_output_tokens += response.output_tokens
                total_cached_tokens += response.cached_tokens or 0
                model_used = response.model or model_used

                # Calculate cost for this call
                usage_cost = calculate_cost(
                    model=response.model or "claude-sonnet-4-20250514",
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    cached_tokens=response.cached_tokens,
                )
                total_cost += usage_cost.total_cost

            except Exception as e:
                logger.error("Subagent LLM call failed", error=str(e))
                await self._publish_action(
                    "subagent_error",
                    f"{self._subagent_type}: LLM call failed"
                )
                return SubagentResult(
                    success=False,
                    response="",
                    iterations=iterations,
                    tool_calls_made=self._tool_calls_made,
                    error=f"LLM call failed: {e}",
                    usage=SubagentUsage(
                        input_tokens=total_input_tokens,
                        output_tokens=total_output_tokens,
                        cached_tokens=total_cached_tokens,
                        total_cost=total_cost,
                        model=model_used,
                    ),
                )

            # Check if done
            if response.stop_reason == "end_turn":
                # Publish completion with cost info
                cost_str = f"${float(total_cost):.4f}" if total_cost > 0 else ""
                await self._publish_action(
                    "subagent_complete",
                    f"{self._subagent_type}: Complete ({iterations} iter, {total_input_tokens + total_output_tokens:,} tok{', ' + cost_str if cost_str else ''})"
                )
                return SubagentResult(
                    success=True,
                    response=response.text_content or "",
                    iterations=iterations,
                    tool_calls_made=self._tool_calls_made,
                    usage=SubagentUsage(
                        input_tokens=total_input_tokens,
                        output_tokens=total_output_tokens,
                        cached_tokens=total_cached_tokens,
                        total_cost=total_cost,
                        model=model_used,
                    ),
                )

            elif response.stop_reason == "tool_use":
                # Execute tools
                tool_results = []

                for tool_call in response.tool_calls:
                    self._tool_calls_made.append(tool_call.name)

                    # Publish tool call action
                    args_summary = self._summarize_args(tool_call.arguments)
                    await self._publish_action(
                        "subagent_tool_call",
                        f"{self._subagent_type}: {tool_call.name}({args_summary})"
                    )

                    result = await self._tool_registry.execute(
                        tool_call.name,
                        tool_call.arguments,
                        context={
                            "task_id": f"subagent_{id(self)}",
                            "_agent_type": self._parent_agent_type,
                        },
                    )

                    # Publish tool result action
                    status_icon = "✓" if result.success else "✗"
                    await self._publish_action(
                        "subagent_tool_result",
                        f"{self._subagent_type}: {tool_call.name} → {status_icon}"
                    )

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": str(result.output) if result.success else (result.error or "Tool execution failed"),
                        "is_error": not result.success,
                    })

                # Add assistant response and tool results to history
                assistant_content = []
                if response.text_content:
                    assistant_content.append({"type": "text", "text": response.text_content})
                for tc in response.tool_calls:
                    assistant_content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })

                self._conversation.append({"role": "assistant", "content": assistant_content})
                self._conversation.append({"role": "user", "content": tool_results})

            else:
                # Unexpected stop reason
                logger.warning("Subagent unexpected stop", stop_reason=response.stop_reason)
                break

        # Max iterations reached
        cost_str = f"${float(total_cost):.4f}" if total_cost > 0 else ""
        await self._publish_action(
            "subagent_complete",
            f"{self._subagent_type}: Max iterations ({iterations}) reached ({total_input_tokens + total_output_tokens:,} tok{', ' + cost_str if cost_str else ''})"
        )
        return SubagentResult(
            success=False,
            response="Subtask incomplete - maximum iterations reached",
            iterations=iterations,
            tool_calls_made=self._tool_calls_made,
            error="max_iterations",
            usage=SubagentUsage(
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                cached_tokens=total_cached_tokens,
                total_cost=total_cost,
                model=model_used,
            ),
        )
