"""Template Agent Implementation.

Copy this file and customize for your agent.
"""

from ai_agents import BaseAgent, Tool, ToolResult
from ai_core import get_logger

logger = get_logger(__name__)


class TemplateAgent(BaseAgent):
    """Template agent - copy and customize.

    This agent demonstrates the basic structure. Replace with your
    specific functionality.
    """

    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent.

        Customize this to define your agent's personality and capabilities.
        """
        return """You are a specialized agent for [describe purpose].

Your capabilities:
- [Capability 1]
- [Capability 2]

Guidelines:
- Always validate inputs before processing
- Log important operations for audit trails
- Handle errors gracefully and report clearly
"""

    def get_tools(self) -> list[Tool]:
        """Return the list of tools available to this agent.

        Add your custom tools here.
        """
        return [
            Tool(
                name="example_tool",
                description="An example tool that demonstrates the structure",
                parameters={
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "string",
                            "description": "The input to process"
                        },
                        "options": {
                            "type": "object",
                            "description": "Optional settings",
                            "properties": {
                                "verbose": {"type": "boolean", "default": False}
                            }
                        }
                    },
                    "required": ["input"]
                },
                handler=self._example_tool_handler
            ),
            # Add more tools here
        ]

    async def _example_tool_handler(
        self,
        input: str,
        options: dict | None = None
    ) -> ToolResult:
        """Handle example_tool calls.

        Args:
            input: The input to process
            options: Optional settings

        Returns:
            ToolResult with success status and data
        """
        logger.info("example_tool_called", input=input, options=options)

        try:
            # Your tool logic here
            result = f"Processed: {input}"

            if options and options.get("verbose"):
                result += " (verbose mode)"

            return ToolResult(
                success=True,
                data={"result": result}
            )

        except Exception as e:
            logger.error("example_tool_failed", error=str(e))
            return ToolResult(
                success=False,
                error=f"Tool failed: {str(e)}"
            )

    async def on_startup(self) -> None:
        """Called when the agent starts.

        Override to perform initialization.
        """
        logger.info("template_agent_starting")
        await super().on_startup()

    async def on_shutdown(self) -> None:
        """Called when the agent stops.

        Override to perform cleanup.
        """
        logger.info("template_agent_stopping")
        await super().on_shutdown()
