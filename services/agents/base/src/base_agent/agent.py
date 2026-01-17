"""
Base agent class for AI Infrastructure.

Provides the foundation for all specialized agents with:
- Claude API integration
- Tool execution
- Memory integration
- Message handling
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from anthropic import AsyncAnthropic

from ai_core import (
    AgentStatus,
    AgentType,
    agent_active_tasks,
    agent_errors_total,
    agent_task_duration_seconds,
    agent_tasks_total,
    agent_tool_calls_total,
    claude_api_tokens_total,
    get_logger,
    get_settings,
)
from ai_memory import PAIMemory, PAIPhase
from ai_messaging import (
    AgentHeartbeat,
    AgentStatusMessage,
    MessageType,
    PubSubManager,
    RedisClient,
    TaskProgress,
    TaskRequest,
    TaskResponse,
    TaskStatus,
    ToolCall,
    ToolResult as ToolResultMessage,
)

from .tools import Tool, ToolRegistry, ToolResult

logger = get_logger(__name__)


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str
    agent_type: AgentType
    permission_level: int = 1
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    max_tool_iterations: int = 10
    heartbeat_interval: int = 30
    system_prompt: str = ""


@dataclass
class ConversationMessage:
    """A message in the conversation history."""

    role: str  # "user", "assistant", or "tool_result"
    content: Any


@dataclass
class AgentState:
    """Runtime state of an agent."""

    status: AgentStatus = AgentStatus.IDLE
    current_task_id: str | None = None
    tasks_completed: int = 0
    start_time: float = field(default_factory=time.time)
    conversation_history: list[ConversationMessage] = field(default_factory=list)


class BaseAgent(ABC):
    """
    Base class for all AI Infrastructure agents.

    Subclasses must implement:
    - get_system_prompt(): Return the agent's system prompt
    - register_tools(): Register agent-specific tools

    Optional overrides:
    - on_task_start(): Called when a task starts
    - on_task_complete(): Called when a task completes
    - on_task_error(): Called when a task fails
    """

    def __init__(
        self,
        config: AgentConfig,
        redis_client: RedisClient,
        memory: PAIMemory | None = None,
    ):
        self.config = config
        self._redis = redis_client
        self._memory = memory
        self._tool_registry = ToolRegistry()
        self._state = AgentState()
        self._pubsub: PubSubManager | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False

        # Initialize Claude client
        settings = get_settings()
        self._claude = AsyncAnthropic(
            api_key=settings.api.anthropic_api_key.get_secret_value()
        )

        # Register tools
        self.register_tools()

    @property
    def name(self) -> str:
        """Get agent name."""
        return self.config.name

    @property
    def agent_type(self) -> AgentType:
        """Get agent type."""
        return self.config.agent_type

    @property
    def status(self) -> AgentStatus:
        """Get current status."""
        return self._state.status

    @property
    def tools(self) -> list[Tool]:
        """Get registered tools."""
        return self._tool_registry.list_tools()

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Get the agent's system prompt.

        Returns:
            System prompt string for Claude
        """
        pass

    @abstractmethod
    def register_tools(self) -> None:
        """
        Register agent-specific tools.

        Called during initialization to populate the tool registry.
        """
        pass

    def register_tool(self, tool: Tool) -> None:
        """Register a tool with this agent."""
        self._tool_registry.register(tool)

    async def start(self) -> None:
        """Start the agent."""
        logger.info("Starting agent", agent=self.name, type=self.agent_type.value)

        # Initialize pub/sub
        self._pubsub = PubSubManager(self._redis)
        await self._pubsub.start()

        # Subscribe to task requests
        await self._pubsub.subscribe(
            f"agent:{self.agent_type.value}:tasks",
            self._handle_task_message,
        )

        # Start heartbeat
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Publish status
        await self._publish_status(AgentStatus.IDLE)

        logger.info("Agent started", agent=self.name)

    async def stop(self) -> None:
        """Stop the agent."""
        logger.info("Stopping agent", agent=self.name)

        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            await self._pubsub.stop()

        await self._publish_status(AgentStatus.OFFLINE)
        logger.info("Agent stopped", agent=self.name)

    async def process_task(self, request: TaskRequest) -> TaskResponse:
        """
        Process a task request.

        Args:
            request: The task request to process

        Returns:
            TaskResponse with results
        """
        task_id = request.id
        start_time = time.time()

        logger.info(
            "Processing task",
            task_id=task_id,
            task_type=request.task_type,
            agent=self.name,
        )

        # Update state
        self._state.status = AgentStatus.BUSY
        self._state.current_task_id = task_id
        agent_active_tasks.labels(agent_type=self.agent_type.value).inc()

        try:
            # Call hook
            await self.on_task_start(request)

            # Store task start in memory
            if self._memory:
                await self._memory.store_task_trace(
                    task_id=task_id,
                    phase=PAIPhase.OBSERVE,
                    data={
                        "task_type": request.task_type,
                        "agent_type": self.agent_type.value,
                    },
                )

            # Build initial message
            user_message = self._build_task_message(request)

            # Reset conversation for new task
            self._state.conversation_history = []

            # Execute with Claude
            result = await self._execute_with_claude(task_id, user_message)

            # Record success
            duration_ms = int((time.time() - start_time) * 1000)
            agent_tasks_total.labels(
                agent_type=self.agent_type.value,
                task_type=request.task_type,
                status="success",
            ).inc()
            agent_task_duration_seconds.labels(
                agent_type=self.agent_type.value,
                task_type=request.task_type,
            ).observe(duration_ms / 1000)

            # Call hook
            await self.on_task_complete(request, result)

            # Store completion in memory
            if self._memory:
                await self._memory.store_task_trace(
                    task_id=task_id,
                    phase=PAIPhase.VERIFY,
                    data={"success": True, "duration_ms": duration_ms},
                )

            self._state.tasks_completed += 1

            return TaskResponse(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                result=result,
                agent_type=self.agent_type,
                duration_ms=duration_ms,
                correlation_id=request.correlation_id,
            )

        except Exception as e:
            logger.error("Task failed", task_id=task_id, error=str(e))

            agent_tasks_total.labels(
                agent_type=self.agent_type.value,
                task_type=request.task_type,
                status="error",
            ).inc()
            agent_errors_total.labels(
                agent_type=self.agent_type.value,
                error_type=type(e).__name__,
            ).inc()

            # Call error hook
            await self.on_task_error(request, e)

            return TaskResponse(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                agent_type=self.agent_type,
                duration_ms=int((time.time() - start_time) * 1000),
                correlation_id=request.correlation_id,
            )

        finally:
            self._state.status = AgentStatus.IDLE
            self._state.current_task_id = None
            agent_active_tasks.labels(agent_type=self.agent_type.value).dec()

    def _build_task_message(self, request: TaskRequest) -> str:
        """Build the initial user message for a task."""
        parts = [f"Task Type: {request.task_type}"]

        if request.payload:
            parts.append(f"\nPayload: {request.payload}")

        if request.metadata:
            parts.append(f"\nMetadata: {request.metadata}")

        return "\n".join(parts)

    async def _execute_with_claude(
        self,
        task_id: str,
        user_message: str,
    ) -> dict[str, Any]:
        """
        Execute task using Claude with tool use.

        Implements the agentic loop:
        1. Send message to Claude
        2. If Claude wants to use tools, execute them
        3. Send results back to Claude
        4. Repeat until Claude provides final response
        """
        # Add user message to history
        self._state.conversation_history.append(
            ConversationMessage(role="user", content=user_message)
        )

        # Get tool schemas
        tools = self._tool_registry.get_claude_schemas(self.config.permission_level)

        iterations = 0
        while iterations < self.config.max_tool_iterations:
            iterations += 1

            # Build messages for API
            messages = self._build_api_messages()

            # Call Claude
            response = await self._claude.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=self.get_system_prompt(),
                messages=messages,
                tools=tools if tools else None,
            )

            # Track token usage
            claude_api_tokens_total.labels(
                agent_type=self.agent_type.value,
                model=self.config.model,
                direction="input",
            ).inc(response.usage.input_tokens)
            claude_api_tokens_total.labels(
                agent_type=self.agent_type.value,
                model=self.config.model,
                direction="output",
            ).inc(response.usage.output_tokens)

            # Check stop reason
            if response.stop_reason == "end_turn":
                # Extract final response
                text_content = ""
                for block in response.content:
                    if block.type == "text":
                        text_content += block.text

                return {
                    "response": text_content,
                    "iterations": iterations,
                }

            elif response.stop_reason == "tool_use":
                # Execute tools
                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        tool_use_id = block.id

                        # Track tool call
                        agent_tool_calls_total.labels(
                            agent_type=self.agent_type.value,
                            tool_name=tool_name,
                        ).inc()

                        # Publish tool call event
                        if self._pubsub:
                            await self._pubsub.publish(
                                "agent:tool_calls",
                                ToolCall(
                                    agent_type=self.agent_type,
                                    task_id=task_id,
                                    tool_name=tool_name,
                                    tool_input=tool_input,
                                ).model_dump_json(),
                            )

                        # Execute tool
                        result = await self._tool_registry.execute(
                            tool_name,
                            tool_input,
                            context={"task_id": task_id},
                        )

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": str(result.output) if result.success else result.error,
                            "is_error": not result.success,
                        })

                        # Publish tool result event
                        if self._pubsub:
                            await self._pubsub.publish(
                                "agent:tool_results",
                                ToolResultMessage(
                                    agent_type=self.agent_type,
                                    task_id=task_id,
                                    tool_name=tool_name,
                                    success=result.success,
                                    output=result.output,
                                    error=result.error,
                                    duration_ms=0,
                                ).model_dump_json(),
                            )

                # Add assistant response and tool results to history
                self._state.conversation_history.append(
                    ConversationMessage(role="assistant", content=response.content)
                )
                self._state.conversation_history.append(
                    ConversationMessage(role="user", content=tool_results)
                )

            else:
                # Unexpected stop reason
                logger.warning(
                    "Unexpected stop reason",
                    stop_reason=response.stop_reason,
                )
                break

        # Max iterations reached
        return {
            "response": "Task incomplete - maximum iterations reached",
            "iterations": iterations,
            "warning": "max_iterations",
        }

    def _build_api_messages(self) -> list[dict[str, Any]]:
        """Build messages list for Claude API."""
        messages = []

        for msg in self._state.conversation_history:
            if msg.role == "user":
                if isinstance(msg.content, list):
                    # Tool results
                    messages.append({"role": "user", "content": msg.content})
                else:
                    messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                # Convert content blocks
                content = []
                for block in msg.content:
                    if block.type == "text":
                        content.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                messages.append({"role": "assistant", "content": content})

        return messages

    async def _handle_task_message(self, message: str) -> None:
        """Handle incoming task message from pub/sub."""
        try:
            request = TaskRequest.model_validate_json(message)

            # Check if targeted to this agent
            if request.target_agent and request.target_agent != self.agent_type:
                return

            # Process task
            response = await self.process_task(request)

            # Publish response
            if self._pubsub:
                await self._pubsub.publish(
                    f"task:{request.id}:response",
                    response.model_dump_json(),
                )

        except Exception as e:
            logger.error("Failed to handle task message", error=str(e))

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat messages."""
        while self._running:
            try:
                await self._send_heartbeat()
                await asyncio.sleep(self.config.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Heartbeat failed", error=str(e))

    async def _send_heartbeat(self) -> None:
        """Send a heartbeat message."""
        if not self._pubsub:
            return

        uptime = int(time.time() - self._state.start_time)

        heartbeat = AgentHeartbeat(
            agent_type=self.agent_type,
            status=self._state.status,
            uptime_seconds=uptime,
            tasks_completed=self._state.tasks_completed,
        )

        await self._pubsub.publish(
            "agent:heartbeats",
            heartbeat.model_dump_json(),
        )

    async def _publish_status(self, status: AgentStatus) -> None:
        """Publish agent status update."""
        self._state.status = status

        if not self._pubsub:
            return

        status_msg = AgentStatusMessage(
            agent_type=self.agent_type,
            status=status,
            current_task_id=self._state.current_task_id,
        )

        await self._pubsub.publish(
            "agent:status",
            status_msg.model_dump_json(),
        )

    async def _publish_progress(
        self,
        task_id: str,
        progress: int,
        message: str | None = None,
    ) -> None:
        """Publish task progress update."""
        if not self._pubsub:
            return

        progress_msg = TaskProgress(
            task_id=task_id,
            progress_percent=progress,
            message=message,
            agent_type=self.agent_type,
        )

        await self._pubsub.publish(
            f"task:{task_id}:progress",
            progress_msg.model_dump_json(),
        )

    # Hooks for subclasses
    async def on_task_start(self, request: TaskRequest) -> None:
        """Called when a task starts. Override in subclasses."""
        pass

    async def on_task_complete(
        self, request: TaskRequest, result: dict[str, Any]
    ) -> None:
        """Called when a task completes. Override in subclasses."""
        pass

    async def on_task_error(self, request: TaskRequest, error: Exception) -> None:
        """Called when a task fails. Override in subclasses."""
        pass
