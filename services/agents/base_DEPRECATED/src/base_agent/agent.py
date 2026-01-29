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

from ai_core import (
    AgentStatus,
    AgentType,
    CapabilityCategory,
    LLMClient,
    PermissionContext,
    PermissionLevel,
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

# Action type constants for real-time action publishing
ACTION_THINKING = "thinking"
ACTION_TOOL_CALL = "tool_call"
ACTION_TOOL_RESULT = "tool_result"
ACTION_TOOL_ERROR = "tool_error"
ACTION_FILE_READ = "file_read"
ACTION_FILE_WRITE = "file_write"
ACTION_FILE_SEARCH = "file_search"
ACTION_DELEGATING = "delegating"
ACTION_WAITING = "waiting"
ACTION_RECEIVED = "received"
ACTION_API_CALL = "api_call"
ACTION_API_RESPONSE = "api_response"
ACTION_MEMORY_SEARCH = "memory_search"
ACTION_MEMORY_STORE = "memory_store"
ACTION_COMPLETE = "complete"
ACTION_ERROR = "error"

from .tools import Tool, ToolRegistry, ToolResult

logger = get_logger(__name__)


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str
    agent_type: AgentType
    permission_level: int = 1
    allowed_capabilities: list[CapabilityCategory] | None = None
    allowed_elevation_to: int | None = None
    model: str = "claude-opus-4-5"
    max_tokens: int = 8192  # Increased from 4096 for complex responses
    max_tool_iterations: int = 50  # Increased from 10 for comprehensive analysis
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
    # Context for action publishing
    current_user_id: str | None = None
    current_conversation_id: str | None = None
    current_project_id: str | None = None
    # Task control state
    _cancelled: bool = False


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
        self._state = AgentState()
        self._pubsub: PubSubManager | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False

        # Create permission context for this agent
        self._permission_context = PermissionContext(
            agent_type=config.agent_type,
            base_level=PermissionLevel(config.permission_level),
            allowed_capabilities=set(config.allowed_capabilities or []),
            allowed_elevation_to=PermissionLevel(config.allowed_elevation_to)
            if config.allowed_elevation_to is not None
            else None,
        )

        # Initialize tool registry with permission context
        self._tool_registry = ToolRegistry(self._permission_context)

        # Initialize LLM client (supports Anthropic + OpenAI fallback)
        self._llm = LLMClient()

        # Register shared tools (available to all agents)
        self._register_shared_tools()

        # Register agent-specific tools
        self.register_tools()

    def _register_shared_tools(self) -> None:
        """
        Register shared tools available to all agents.

        These include memory, collaboration, and system tools.
        Agents can override this to exclude specific shared tools.
        """
        from .shared_tools import (
            # Memory tools
            search_memory,
            store_memory,
            list_memory_collections,
            get_memory_stats,
            delete_memory,
            # Collaboration tools
            notify_user,
            request_agent_help,
            broadcast_status,
            # System tools
            get_system_info,
            check_service_health,
            resource_monitor,
            shell_execute,
            process_list,
            process_kill,
            service_manage,
        )

        # Register memory tools (access Tool object via _tool attribute from decorator)
        self._tool_registry.register(search_memory._tool)
        self._tool_registry.register(store_memory._tool)
        self._tool_registry.register(list_memory_collections._tool)
        self._tool_registry.register(get_memory_stats._tool)
        self._tool_registry.register(delete_memory._tool)

        # Register collaboration tools
        self._tool_registry.register(notify_user._tool)
        self._tool_registry.register(request_agent_help._tool)
        self._tool_registry.register(broadcast_status._tool)

        # Register system tools (read-only monitoring)
        self._tool_registry.register(get_system_info._tool)
        self._tool_registry.register(check_service_health._tool)
        self._tool_registry.register(resource_monitor._tool)

        # Register system tools (execution - permission level 2+)
        self._tool_registry.register(shell_execute._tool)
        self._tool_registry.register(process_list._tool)
        self._tool_registry.register(process_kill._tool)
        self._tool_registry.register(service_manage._tool)

        logger.debug(
            "Registered shared tools",
            agent=self.config.name,
            tool_count=16,
        )

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

    @property
    def permission_context(self) -> PermissionContext:
        """Get the agent's permission context."""
        return self._permission_context

    @property
    def permission_level(self) -> PermissionLevel:
        """Get the agent's current effective permission level."""
        return self._permission_context.current_level

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

        # Subscribe to task control messages (cancel, pause, resume)
        await self._pubsub.subscribe(
            "agent:task_control",
            self._handle_task_control,
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

        # Reset cancellation flag for new task
        self._reset_cancellation()

        # Set context for action publishing
        user_id = request.user_id or request.payload.get("user_id")
        conversation_id = request.payload.get("conversation_id")
        project_id = request.payload.get("project_id")
        self._state.current_user_id = user_id
        self._state.current_conversation_id = conversation_id
        self._state.current_project_id = project_id

        # Send status update to WebSocket clients
        if user_id and self._pubsub:
            await self._pubsub.publish(
                "agent:responses",
                {
                    "type": "status",
                    "user_id": user_id,
                    "agent": self.agent_type.value,
                    "status": "busy",
                    "task": f"Processing {request.task_type}...",
                },
            )

        # Publish initial thinking action
        await self.publish_action(ACTION_THINKING, "Analyzing request...")

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

            # For chat tasks, load conversation history for context
            if request.task_type == "chat" and request.payload.get("conversation_id"):
                await self._load_conversation_context(request.payload["conversation_id"])
            else:
                # Reset conversation for non-chat tasks
                self._state.conversation_history = []

            # Execute with Claude (with optional iteration limit override)
            result = await self._execute_with_claude(
                task_id, user_message, max_iterations=request.max_iterations
            )

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

            # Publish task completion action
            await self.publish_action(ACTION_COMPLETE, "Task completed successfully")

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

            # Publish error action
            await self.publish_action(ACTION_ERROR, f"Task failed: {str(e)[:100]}")

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
            # Clear context
            self._state.current_user_id = None
            self._state.current_conversation_id = None
            agent_active_tasks.labels(agent_type=self.agent_type.value).dec()

            # Send idle status update to WebSocket clients
            if user_id and self._pubsub:
                await self._pubsub.publish(
                    "agent:responses",
                    {
                        "type": "status",
                        "user_id": user_id,
                        "agent": self.agent_type.value,
                        "status": "idle",
                        "task": None,
                    },
                )

    async def _load_conversation_context(self, conversation_id: str) -> None:
        """Load previous messages from a conversation for context."""
        self._state.conversation_history = []

        if not self._redis:
            return

        try:
            # Get message IDs from conversation (stored newest first via lpush)
            messages_key = f"conversation:{conversation_id}:messages"
            message_ids = await self._redis.lrange(messages_key, 0, 19)  # Last 20 messages

            if not message_ids:
                return

            # Reverse to get chronological order (oldest first)
            message_ids = list(reversed(message_ids))

            # Load each message
            for msg_id in message_ids:
                msg_key = f"message:{msg_id}"
                msg_data = await self._redis.hgetall(msg_key)

                if msg_data:
                    role = msg_data.get("role", "user")
                    content = msg_data.get("content", "")

                    if content:
                        self._state.conversation_history.append(
                            ConversationMessage(role=role, content=content)
                        )

            logger.debug(
                "Loaded conversation context",
                conversation_id=conversation_id,
                message_count=len(self._state.conversation_history),
            )

        except Exception as e:
            logger.warning("Failed to load conversation context", error=str(e))
            self._state.conversation_history = []

    def _build_task_message(self, request: TaskRequest) -> str:
        """Build the initial user message for a task."""
        # For chat tasks, just return the user's message content
        if request.task_type == "chat" and request.payload.get("content"):
            return request.payload["content"]

        # For other tasks, include full context
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
        max_iterations: int | None = None,
    ) -> dict[str, Any]:
        """
        Execute task using Claude with tool use.

        Implements the agentic loop:
        1. Send message to Claude
        2. If Claude wants to use tools, execute them
        3. Send results back to Claude
        4. Repeat until Claude provides final response

        Args:
            task_id: Unique task identifier
            user_message: The message to process
            max_iterations: Override for max tool iterations (uses config default if None)
        """
        # Determine iteration limit (task override > config default)
        iteration_limit = max_iterations or self.config.max_tool_iterations

        # Add user message to history
        self._state.conversation_history.append(
            ConversationMessage(role="user", content=user_message)
        )

        # Get tool schemas
        tools = self._tool_registry.get_claude_schemas(self.config.permission_level)

        iterations = 0
        while iterations < iteration_limit:
            iterations += 1

            # Check for task cancellation
            if self.is_task_cancelled():
                logger.info("Task cancelled by user", task_id=task_id, iterations=iterations)
                return {
                    "response": "Task cancelled by user.",
                    "iterations": iterations,
                    "cancelled": True,
                }

            # Build messages for API
            messages = self._build_api_messages()

            # Publish API call action
            await self.publish_action(ACTION_API_CALL, "Calling LLM API...")

            # Call LLM (handles provider fallback automatically)
            # model="auto" selects tier based on tools/max_tokens/system prompt
            response = await self._llm.create_message(
                model="auto",
                max_tokens=self.config.max_tokens,
                system=self.get_system_prompt(),
                messages=messages,
                tools=tools if tools else None,
            )

            # Track token usage
            claude_api_tokens_total.labels(
                agent_type=self.agent_type.value,
                token_type="input",
            ).inc(response.input_tokens)
            claude_api_tokens_total.labels(
                agent_type=self.agent_type.value,
                token_type="output",
            ).inc(response.output_tokens)

            # Publish API response action
            total_tokens = response.input_tokens + response.output_tokens
            await self.publish_action(
                ACTION_API_RESPONSE,
                f"Received response ({total_tokens:,} tokens, {response.provider.value})"
            )

            # Check stop reason
            if response.stop_reason == "end_turn":
                return {
                    "response": response.text_content,
                    "iterations": iterations,
                }

            elif response.stop_reason == "tool_use":
                # Execute tools
                tool_results = []

                for tool_call in response.tool_calls:
                    tool_name = tool_call.name
                    tool_input = tool_call.arguments
                    tool_use_id = tool_call.id

                    # Publish tool call action to frontend
                    await self.publish_action(
                        ACTION_TOOL_CALL,
                        f"Calling {tool_name}..."
                    )

                    # Publish tool call event to internal channel
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

                    # Execute tool with context (memory, agent type, task id, project id)
                    result = await self._tool_registry.execute(
                        tool_name,
                        tool_input,
                        context={
                            "task_id": task_id,
                            "_memory": self._memory,
                            "_agent_type": self.agent_type.value,
                            "_task_id": task_id,
                            "_project_id": self._state.current_project_id,
                            "_agent": self,  # Pass agent for action publishing
                        },
                    )

                    # Track tool call with status
                    agent_tool_calls_total.labels(
                        agent_type=self.agent_type.value,
                        tool_name=tool_name,
                        status="success" if result.success else "error",
                    ).inc()

                    # Publish tool result action to frontend
                    if result.success:
                        await self.publish_action(
                            ACTION_TOOL_RESULT,
                            f"{tool_name} completed successfully"
                        )
                    else:
                        error_msg = result.error or "Unknown error"
                        await self.publish_action(
                            ACTION_TOOL_ERROR,
                            f"{tool_name} failed: {error_msg[:50]}"
                        )

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": str(result.output) if result.success else (result.error or "Tool execution failed"),
                        "is_error": not result.success,
                    })

                    # Publish tool result event to internal channel
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
                # Store in normalized dict format (Anthropic-compatible)
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
                self._state.conversation_history.append(
                    ConversationMessage(role="assistant", content=assistant_content)
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

    def _has_tool_use(self, msg: ConversationMessage) -> bool:
        """Check if a message contains tool_use blocks."""
        if msg.role != "assistant":
            return False
        if isinstance(msg.content, str):
            return False
        return any(
            (isinstance(block, dict) and block.get("type") == "tool_use")
            or getattr(block, "type", None) == "tool_use"
            for block in msg.content
        )

    def _is_tool_result(self, msg: ConversationMessage) -> bool:
        """Check if a message is a tool_result."""
        if msg.role != "user":
            return False
        if not isinstance(msg.content, list):
            return False
        return any(
            isinstance(block, dict) and block.get("type") == "tool_result"
            for block in msg.content
        )

    def _find_safe_truncation_point(
        self,
        history: list[ConversationMessage],
        target_length: int,
    ) -> int:
        """Find a safe point to start the history slice.

        Returns an index where starting won't break tool_use/tool_result pairs.
        A safe start point is where:
        1. The message at that index is NOT a tool_result (would be orphaned)
        2. OR we're at the beginning
        """
        # Start from where we'd ideally want to truncate
        ideal_start = max(0, len(history) - target_length)

        # Search forward from ideal_start to find a safe boundary
        # We need to find a point where:
        # - Current message is NOT a tool_result (orphaned from its tool_use)
        for i in range(ideal_start, len(history)):
            msg = history[i]

            # If this is a tool_result, we can't start here (orphaned)
            if self._is_tool_result(msg):
                continue

            # If this is a user message (not tool_result) or assistant message, it's safe
            return i

        # If we couldn't find a safe point, start from beginning
        return 0

    def _build_api_messages(self) -> list[dict[str, Any]]:
        """Build messages list for Claude API.

        Truncates conversation history if too long to prevent context overflow.
        Ensures tool_use/tool_result pairs are never split.
        """
        messages = []

        # Limit conversation history to prevent context overflow
        history = self._state.conversation_history
        max_history = 32

        if len(history) > max_history:
            # Find safe truncation point that doesn't break tool pairs
            safe_start = self._find_safe_truncation_point(
                history,
                max_history,
            )

            # Use history from safe_start to end (don't keep first 2 separately)
            history = history[safe_start:]
            logger.debug(
                "Truncated conversation history",
                original_length=len(self._state.conversation_history),
                truncated_length=len(history),
                safe_start_index=safe_start,
            )

        for msg in history:
            if msg.role == "user":
                if isinstance(msg.content, list):
                    # Tool results
                    messages.append({"role": "user", "content": msg.content})
                else:
                    messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                # Handle both string content (from loaded history) and content blocks
                if isinstance(msg.content, str):
                    # Plain string from loaded conversation history
                    messages.append({"role": "assistant", "content": msg.content})
                else:
                    # Content blocks (already in normalized dict format)
                    content = []
                    for block in msg.content:
                        if isinstance(block, dict):
                            content.append(block)
                        else:
                            block_type = getattr(block, "type", None)
                            if block_type == "text":
                                content.append({"type": "text", "text": block.text})
                            elif block_type == "tool_use":
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

            # Publish response to task-specific channel (for inter-agent communication)
            if self._pubsub:
                await self._pubsub.publish(
                    f"task:{request.id}:response",
                    response.model_dump_json(),
                )

                # Also publish to agent:responses for WebSocket routing
                # ONLY if this is a direct user chat request (not a delegated task)
                # Delegated tasks should only respond via task:{id}:response channel
                # User requests have user_id at the top level; delegated tasks only have it in payload
                is_direct_user_request = (
                    request.task_type == "chat"
                    and request.payload.get("conversation_id")
                    and request.user_id  # Direct user requests have user_id at top level
                )

                user_id = request.user_id or request.payload.get("user_id")
                if user_id and is_direct_user_request:
                    from datetime import datetime, timezone

                    conversation_id = request.payload.get("conversation_id")
                    message_id = request.payload.get("message_id")

                    # Get response content from result
                    content = ""
                    if response.result:
                        # Claude response is stored in "response" key
                        content = response.result.get("response", "")

                    await self._pubsub.publish(
                        "agent:responses",
                        {
                            "type": "response" if response.status.value == "completed" else "error",
                            "user_id": user_id,
                            "conversation_id": conversation_id,
                            "message_id": message_id,
                            "content": content if response.status.value == "completed" else response.error,
                            "agent": self.agent_type.value,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "error": response.error,
                        },
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

        from datetime import datetime, timezone
        import json

        uptime = int(time.time() - self._state.start_time)
        now = datetime.now(timezone.utc)

        heartbeat = AgentHeartbeat(
            agent_type=self.agent_type,
            status=self._state.status,
            uptime_seconds=uptime,
            tasks_completed=self._state.tasks_completed,
        )

        # Publish to pub/sub channel
        await self._pubsub.publish(
            "agent:heartbeats",
            heartbeat.model_dump_json(),
        )

        # Store heartbeat in Redis key for API to read
        # The API checks agent:heartbeat:{agent_name} keys
        heartbeat_key = f"agent:heartbeat:{self.config.name}"
        heartbeat_data = json.dumps({
            "timestamp": now.isoformat(),
            "status": self._state.status.value,
            "current_task": self._state.current_task_id,
            "uptime_seconds": uptime,
            "tasks_completed": self._state.tasks_completed,
            "metrics": {},
        })

        # Store with 60 second TTL (agents send every 30 seconds)
        await self._redis.set(heartbeat_key, heartbeat_data, ex=60)

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

    async def publish_action(
        self,
        action: str,
        description: str,
        user_id: str | None = None,
        conversation_id: str | None = None,
    ) -> None:
        """
        Publish real-time action to frontend.

        This enables Claude Code-style action communication where users can see
        exactly what the agent is doing: "Reading file X", "Calling tool Y", etc.

        Args:
            action: Action type (e.g., "thinking", "tool_call", "file_read")
            description: Human-readable description of what's happening
            user_id: Optional user ID (uses current context if not provided)
            conversation_id: Optional conversation ID (uses current context if not provided)
        """
        if not self._pubsub:
            return

        from datetime import datetime, timezone

        # Use provided IDs or fall back to current context
        resolved_user_id = user_id or self._state.current_user_id
        resolved_conversation_id = conversation_id or self._state.current_conversation_id

        # Don't publish if we don't have a user to send to
        if not resolved_user_id:
            return

        await self._pubsub.publish(
            channel="agent:responses",
            message={
                "type": "action",
                "action": action,
                "description": description,
                "agent": self.agent_type.value,
                "user_id": resolved_user_id,
                "conversation_id": resolved_conversation_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    # Task cancellation support
    def is_task_cancelled(self) -> bool:
        """Check if the current task has been cancelled by the user."""
        return self._state._cancelled

    def _reset_cancellation(self) -> None:
        """Reset the cancellation flag for a new task."""
        self._state._cancelled = False

    async def _handle_task_control(self, message: str) -> None:
        """Handle task control messages (cancel, pause, resume)."""
        import json
        try:
            data = json.loads(message)
            action = data.get("action")
            target_conversation_id = data.get("conversation_id")

            # Only process if it's for our current conversation
            if target_conversation_id == self._state.current_conversation_id:
                if action == "cancel":
                    self._state._cancelled = True
                    logger.info(
                        "Task cancellation requested",
                        agent=self.name,
                        conversation_id=target_conversation_id,
                    )
        except Exception as e:
            logger.warning("Failed to handle task control message", error=str(e))

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
