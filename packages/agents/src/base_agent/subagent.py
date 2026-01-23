"""
Lightweight subagent for focused subtasks.

Subagents share the parent's LLM client and tool registry but maintain
independent conversation history. They are limited to a max number of
iterations and return a structured result to the parent agent.
"""

from dataclasses import dataclass, field
from typing import Any

from ai_core import LLMClient, get_logger

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


@dataclass
class SubagentResult:
    """Result from a subagent execution."""

    success: bool
    response: str
    iterations: int
    tool_calls_made: list[str] = field(default_factory=list)
    error: str | None = None


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
    ) -> None:
        self._llm = llm
        self._tool_registry = tool_registry
        self._task = task
        self._max_iterations = min(max_iterations, MAX_SUBAGENT_ITERATIONS)
        self._model_tier = MODEL_TIERS.get(model_tier, "auto")
        self._parent_agent_type = parent_agent_type
        self._conversation: list[dict[str, Any]] = []
        self._tool_calls_made: list[str] = []

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
        # Initialize with the task as user message
        self._conversation.append({
            "role": "user",
            "content": self._task,
        })

        # Get available tool schemas
        tools = self._tool_registry.get_claude_schemas()

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
            except Exception as e:
                logger.error("Subagent LLM call failed", error=str(e))
                return SubagentResult(
                    success=False,
                    response="",
                    iterations=iterations,
                    tool_calls_made=self._tool_calls_made,
                    error=f"LLM call failed: {e}",
                )

            # Check if done
            if response.stop_reason == "end_turn":
                return SubagentResult(
                    success=True,
                    response=response.text_content or "",
                    iterations=iterations,
                    tool_calls_made=self._tool_calls_made,
                )

            elif response.stop_reason == "tool_use":
                # Execute tools
                tool_results = []

                for tool_call in response.tool_calls:
                    self._tool_calls_made.append(tool_call.name)

                    result = await self._tool_registry.execute(
                        tool_call.name,
                        tool_call.arguments,
                        context={
                            "task_id": f"subagent_{id(self)}",
                            "_agent_type": self._parent_agent_type,
                        },
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
        return SubagentResult(
            success=False,
            response="Subtask incomplete - maximum iterations reached",
            iterations=iterations,
            tool_calls_made=self._tool_calls_made,
            error="max_iterations",
        )
