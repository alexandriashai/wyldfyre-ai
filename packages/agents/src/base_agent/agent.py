"""
Base agent class for AI Infrastructure.

Provides the foundation for all specialized agents with:
- Claude API integration
- Tool execution
- Memory integration
- Message handling
"""

import asyncio
import importlib.util
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any



# Load PAI hooks dynamically
def _load_pai_hook(hook_name: str):
    """Dynamically load PAI hook module."""
    hook_path = Path("/home/wyld-core/pai/hooks") / f"{hook_name}.py"
    if hook_path.exists():
        try:
            spec = importlib.util.spec_from_file_location(hook_name, hook_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except Exception as e:
            from ai_core import get_logger
            get_logger(__name__).warning(f"Failed to load PAI hook {hook_name}: {e}")
    return None

from ai_core import (
    AgentStatus,
    AgentType,
    CapabilityCategory,
    HookEvent,
    LLMClient,
    PermissionContext,
    PermissionLevel,
    agent_active_tasks,
    agent_errors_total,
    agent_last_heartbeat_timestamp,
    agent_task_duration_seconds,
    agent_tasks_total,
    agent_tool_calls_total,
    calculate_cost,
    claude_api_tokens_total,
    get_cost_tracker,
    get_logger,
    get_plugin_integration,
    get_settings,
    init_agent_plugins,
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

from .context_summarizer import ContextSummarizer
from .parallel_executor import ParallelToolExecutor, ToolCallRequest, ToolCallResult
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


class TaskControlState(Enum):
    """Task control states."""
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


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
    # Task control
    task_control: TaskControlState = TaskControlState.RUNNING
    # Pending messages queue (for interrupts while agent is working)
    pending_messages: list[dict] = field(default_factory=list)
    # Pause event for suspending execution
    pause_event: asyncio.Event = field(default_factory=asyncio.Event)

    def __post_init__(self):
        # Ensure pause event starts in "not paused" state (set = not paused)
        self.pause_event.set()


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
        self._plan_exploring = False  # Read-only mode during plan exploration

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

        # Initialize parallel tool executor
        self._parallel_executor = ParallelToolExecutor(self._tool_registry)

        # Initialize LLM client (supports Anthropic + OpenAI fallback)
        self._llm = LLMClient()

        # Initialize context summarizer for long conversations
        self._context_summarizer = ContextSummarizer(self._llm)

        # Register shared tools (available to all agents)
        self._register_shared_tools()

        # Register agent-specific tools
        self.register_tools()

        # Initialize plugin system
        self._plugin_integration = init_agent_plugins(config.name)
        logger.debug(
            "Plugin integration initialized",
            agent=self.config.name,
            plugins_loaded=len(self._plugin_integration.get_active_plugins()),
        )

    def _register_shared_tools(self) -> None:
        """
        Register shared tools available to all agents.

        These include memory, collaboration, subagent, and system tools.
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
            # Subagent tools
            spawn_subagent,
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
        self._tool_registry.register(search_memory._tool)  # type: ignore[attr-defined]
        self._tool_registry.register(store_memory._tool)  # type: ignore[attr-defined]
        self._tool_registry.register(list_memory_collections._tool)  # type: ignore[attr-defined]
        self._tool_registry.register(get_memory_stats._tool)  # type: ignore[attr-defined]
        self._tool_registry.register(delete_memory._tool)  # type: ignore[attr-defined]

        # Register collaboration tools
        self._tool_registry.register(notify_user._tool)  # type: ignore[attr-defined]
        self._tool_registry.register(request_agent_help._tool)  # type: ignore[attr-defined]
        self._tool_registry.register(broadcast_status._tool)  # type: ignore[attr-defined]

        # Register subagent tools
        self._tool_registry.register(spawn_subagent._tool)  # type: ignore[attr-defined]

        # Register system tools (read-only monitoring)
        self._tool_registry.register(get_system_info._tool)  # type: ignore[attr-defined]
        self._tool_registry.register(check_service_health._tool)  # type: ignore[attr-defined]
        self._tool_registry.register(resource_monitor._tool)  # type: ignore[attr-defined]

        # Register system tools (execution - permission level 2+)
        self._tool_registry.register(shell_execute._tool)  # type: ignore[attr-defined]
        self._tool_registry.register(process_list._tool)  # type: ignore[attr-defined]
        self._tool_registry.register(process_kill._tool)  # type: ignore[attr-defined]
        self._tool_registry.register(service_manage._tool)  # type: ignore[attr-defined]

        logger.debug(
            "Registered shared tools",
            agent=self.config.name,
            tool_count=17,
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

    def set_plan_exploring(self, exploring: bool) -> None:
        """Set whether the agent is in plan exploration mode (read-only tools only)."""
        self._plan_exploring = exploring

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

        # Subscribe to task control commands (pause/resume/cancel)
        await self._pubsub.subscribe(
            "agent:task_control",
            self._handle_task_control_message,
        )

        # Subscribe to pending messages (user adds messages while agent is busy)
        await self._pubsub.subscribe(
            "agent:pending_messages",
            self._handle_pending_message,
        )

        # Start heartbeat
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Publish status
        await self._publish_status(AgentStatus.IDLE)

        logger.info("Agent started", agent=self.name)
        await self.log_to_redis("info", f"Agent {self.name} started and ready")

    async def stop(self, graceful_timeout: float = 30.0) -> None:
        """
        Stop the agent gracefully.

        Waits for current task to complete before shutting down.
        This prevents data loss and ensures clean state.

        Args:
            graceful_timeout: Max seconds to wait for current task (default: 30)
        """
        logger.info("Stopping agent", agent=self.name, graceful=True)

        self._running = False

        # Wait for current task to complete (with timeout)
        if self._state.current_task_id:
            logger.info(
                "Waiting for current task to complete",
                agent=self.name,
                task_id=self._state.current_task_id,
            )
            try:
                # Wait up to graceful_timeout for task to complete
                start = time.time()
                while self._state.current_task_id and (time.time() - start) < graceful_timeout:
                    await asyncio.sleep(0.5)

                if self._state.current_task_id:
                    logger.warning(
                        "Task did not complete within shutdown timeout",
                        agent=self.name,
                        task_id=self._state.current_task_id,
                        timeout=graceful_timeout,
                    )
            except Exception as e:
                logger.warning("Error waiting for task completion", error=str(e))

        # Stop heartbeat
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Flush any pending memory writes
        if self._memory:
            try:
                logger.debug("Flushing memory writes", agent=self.name)
                await self._memory.flush()
            except Exception as e:
                logger.warning("Error flushing memory", error=str(e))

        # Unsubscribe and stop pubsub
        if self._pubsub:
            try:
                # Unsubscribe from task channel before stopping
                await self._pubsub.unsubscribe(f"agent:{self.agent_type.value}:tasks")
            except Exception as e:
                logger.warning("Error unsubscribing", error=str(e))
            await self._pubsub.stop()

        await self._publish_status(AgentStatus.OFFLINE)
        logger.info("Agent stopped gracefully", agent=self.name)

    # === Task Control Methods ===

    async def pause_task(self) -> bool:
        """
        Pause the current running task.

        Returns:
            True if task was paused, False if no task running
        """
        if not self._state.current_task_id:
            return False

        if self._state.task_control == TaskControlState.RUNNING:
            self._state.task_control = TaskControlState.PAUSED
            self._state.pause_event.clear()  # Block execution
            await self.publish_action("paused", "Task paused by user")
            logger.info(
                "Task paused",
                task_id=self._state.current_task_id,
                agent=self.name,
            )
            return True
        return False

    async def resume_task(self) -> bool:
        """
        Resume a paused task.

        Returns:
            True if task was resumed, False if not paused
        """
        if self._state.task_control == TaskControlState.PAUSED:
            self._state.task_control = TaskControlState.RUNNING
            self._state.pause_event.set()  # Unblock execution
            await self.publish_action("resumed", "Task resumed")
            logger.info(
                "Task resumed",
                task_id=self._state.current_task_id,
                agent=self.name,
            )
            return True
        return False

    async def cancel_task(self) -> bool:
        """
        Cancel the current running task.

        Returns:
            True if task was cancelled, False if no task running
        """
        if not self._state.current_task_id:
            return False

        self._state.task_control = TaskControlState.CANCELLED
        self._state.pause_event.set()  # Unblock if paused
        await self.publish_action("cancelled", "Task cancelled by user")
        logger.info(
            "Task cancelled",
            task_id=self._state.current_task_id,
            agent=self.name,
        )
        return True

    def add_pending_message(self, message: dict) -> None:
        """
        Add a message to be processed after current operation.

        This allows users to send additional context while the agent is working.

        Args:
            message: Message dict with 'content' and optional metadata
        """
        self._state.pending_messages.append({
            "content": message.get("content", ""),
            "timestamp": time.time(),
            "type": message.get("type", "user_interrupt"),
        })
        logger.debug(
            "Pending message added",
            agent=self.name,
            queue_size=len(self._state.pending_messages),
        )

    def get_pending_messages(self) -> list[dict]:
        """
        Get and clear pending messages.

        Returns:
            List of pending messages
        """
        messages = self._state.pending_messages.copy()
        self._state.pending_messages.clear()
        return messages

    async def _check_task_control(self) -> bool:
        """
        Check task control state and handle pause/cancel.

        Call this periodically during long operations.

        Returns:
            True if should continue, False if cancelled
        """
        # Wait if paused
        if self._state.task_control == TaskControlState.PAUSED:
            await self._state.pause_event.wait()

        # Check if cancelled
        if self._state.task_control == TaskControlState.CANCELLED:
            return False

        return True

    def is_task_cancelled(self) -> bool:
        """Check if current task is cancelled."""
        return self._state.task_control == TaskControlState.CANCELLED

    def is_task_paused(self) -> bool:
        """Check if current task is paused."""
        return self._state.task_control == TaskControlState.PAUSED

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
        await self.log_to_redis("info", f"Processing task {task_id[:8]}... ({request.task_type})")

        # Update state
        self._state.status = AgentStatus.BUSY
        self._state.current_task_id = task_id
        self._state.task_control = TaskControlState.RUNNING
        self._state.pause_event.set()  # Ensure not paused
        agent_active_tasks.labels(agent_type=self.agent_type.value).inc()

        # Set context for action publishing
        user_id = request.user_id or request.payload.get("user_id")
        conversation_id = request.payload.get("conversation_id")
        self._state.current_user_id = user_id
        self._state.current_conversation_id = conversation_id

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

        # === Execute pre_task hook ===
        pre_hook = _load_pai_hook("pre_task")
        hook_context = {}
        if pre_hook and hasattr(pre_hook, "pre_task_hook") and self._memory:
            try:
                hook_context = await pre_hook.pre_task_hook(
                    agent_type=self.agent_type.value,
                    task_type=request.task_type,
                    task_input=request.payload,
                    memory=self._memory,
                    permission_level=self._permission_context.base_level.value if self._permission_context else 1,
                )
                # Inject relevant learnings into task context
                if hook_context.get("relevant_learnings"):
                    if not hasattr(request, "_pai_context"):
                        request._pai_context = {}
                    request._pai_context["learnings"] = hook_context["relevant_learnings"]
                    request._pai_context["correlation_id"] = hook_context.get("correlation_id")
            except Exception as e:
                logger.warning(f"Pre-task hook failed: {e}")

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

            # === THINK phase: Analysis and reasoning ===
            if self._memory:
                relevant_learnings = getattr(request, "_pai_context", {}).get("learnings", [])
                await self._memory.store_task_trace(
                    task_id=task_id,
                    phase=PAIPhase.THINK,
                    data={
                        "agent_type": self.agent_type.value,
                        "task_type": request.task_type,
                        "relevant_learnings_count": len(relevant_learnings),
                        "message_length": len(user_message),
                    },
                )

            # === PLAN phase: Tool selection and strategy ===
            if self._memory:
                available_tools = self._tool_registry.get_claude_schemas(self.config.permission_level)
                await self._memory.store_task_trace(
                    task_id=task_id,
                    phase=PAIPhase.PLAN,
                    data={
                        "agent_type": self.agent_type.value,
                        "available_tools_count": len(available_tools) if available_tools else 0,
                        "max_iterations": request.max_iterations or self.config.max_tool_iterations,
                    },
                )

            # Execute with Claude (with optional iteration limit override)
            result = await self._execute_with_claude(
                task_id,
                user_message,
                max_iterations=request.max_iterations,
                pai_learnings=getattr(request, "_pai_context", {}).get("learnings", []) or None,
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

            # === Execute post_task hook ===
            post_hook = _load_pai_hook("post_task")
            if post_hook and hasattr(post_hook, "post_task_hook") and self._memory:
                try:
                    correlation_id = hook_context.get("correlation_id", task_id)
                    await post_hook.post_task_hook(
                        agent_type=self.agent_type.value,
                        task_type=request.task_type,
                        task_result=result,
                        correlation_id=correlation_id,
                        memory=self._memory,
                        success=True,
                        permission_level=self._permission_context.base_level.value if self._permission_context else 1,
                    )
                except Exception as e:
                    logger.warning(f"Post-task hook failed: {e}")

            self._state.tasks_completed += 1

            # Publish task completion action
            await self.publish_action(ACTION_COMPLETE, "Task completed successfully")
            await self.log_to_redis("info", f"Task {task_id[:8]}... completed in {duration_ms:.0f}ms")

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
            await self.log_to_redis("error", f"Task {task_id[:8]}... failed: {str(e)[:100]}")

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

            # === Store error in PAI memory ===
            if self._memory:
                try:
                    from ai_memory import Learning

                    # Store error trace
                    error_trace = {
                        "phase": PAIPhase.VERIFY.value,
                        "task_id": task_id,
                        "agent_type": self.agent_type.value,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "traceback": traceback.format_exc(),
                        "context": {
                            "task_type": request.task_type,
                            "task_description": str(request.payload)[:200] if request.payload else "",
                        },
                    }
                    await self._memory.store_task_trace(
                        task_id=task_id,
                        phase=PAIPhase.VERIFY,
                        data=error_trace,
                    )

                    # Store as learning for future reference
                    error_learning = Learning(
                        content=f"Error in {request.task_type}: {type(e).__name__} - {str(e)}",
                        phase=PAIPhase.VERIFY,
                        category="error",
                        task_id=task_id,
                        agent_type=self.agent_type.value,
                        confidence=0.95,
                        metadata={"error_type": type(e).__name__},
                        created_by_agent=self.agent_type.value,
                        permission_level=self._permission_context.base_level.value if self._permission_context else 1,
                    )
                    await self._memory.store_learning(error_learning, agent_type=self.agent_type.value)

                    # Execute post_task hook for failed tasks
                    post_hook = _load_pai_hook("post_task")
                    if post_hook and hasattr(post_hook, "post_task_hook"):
                        try:
                            correlation_id = hook_context.get("correlation_id", task_id)
                            await post_hook.post_task_hook(
                                agent_type=self.agent_type.value,
                                task_type=request.task_type,
                                task_result={"error": str(e), "error_type": type(e).__name__},
                                correlation_id=correlation_id,
                                memory=self._memory,
                                success=False,
                                permission_level=self._permission_context.base_level.value if self._permission_context else 1,
                            )
                        except Exception as hook_err:
                            logger.warning(f"Post-task hook failed for error case: {hook_err}")

                except Exception as mem_error:
                    logger.warning(f"Failed to store error in PAI memory: {mem_error}")

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

            if message_ids:
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
            else:
                # Fallback: load from PostgreSQL if Redis is empty
                try:
                    from api.database import db_session_context
                    from database.models import Message
                    from sqlalchemy import select

                    async with db_session_context() as session:
                        result = await session.execute(
                            select(Message)
                            .where(Message.conversation_id == conversation_id)
                            .order_by(Message.created_at.desc())
                            .limit(20)
                        )
                        db_messages = list(reversed(result.scalars().all()))

                        for msg in db_messages:
                            if msg.content:
                                self._state.conversation_history.append(
                                    ConversationMessage(role=msg.role, content=msg.content)
                                )

                    if self._state.conversation_history:
                        logger.debug(
                            "Loaded conversation context from DB fallback",
                            conversation_id=conversation_id,
                            message_count=len(self._state.conversation_history),
                        )
                except Exception as db_err:
                    logger.debug("DB fallback for conversation context failed", error=str(db_err))

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
        pai_learnings: list | None = None,
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
            pai_learnings: Relevant learnings from PAI memory to inject into context
        """
        # Determine iteration limit (task override > config default)
        iteration_limit = max_iterations or self.config.max_tool_iterations

        # Cost accumulators for usage reporting
        from decimal import Decimal
        total_cost = Decimal("0")
        total_input_tokens = 0
        total_output_tokens = 0

        # Inject PAI learnings into user message if available
        if pai_learnings:
            learnings_text = "\n".join(
                f"- {l.get('content', str(l)) if isinstance(l, dict) else str(l)}"
                for l in pai_learnings[:5]
            )
            user_message = (
                f"[Relevant learnings from previous tasks]\n{learnings_text}\n\n"
                f"[Current task]\n{user_message}"
            )

        # Add user message to history
        self._state.conversation_history.append(
            ConversationMessage(role="user", content=user_message)
        )

        # Get tool schemas (read-only during plan exploration phase)
        plan_read_only = getattr(self, "_plan_exploring", False)
        tools = self._tool_registry.get_claude_schemas(
            self.config.permission_level,
            read_only=plan_read_only,
        )

        iterations = 0
        while iterations < iteration_limit:
            iterations += 1

            # === Task Control Check ===
            if not await self._check_task_control():
                # Task was cancelled
                return {
                    "response": "Task was cancelled by user.",
                    "iterations": iterations,
                    "cancelled": True,
                    "usage": {
                        "total_cost": str(total_cost),
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                    },
                }

            # === Process Pending Messages ===
            pending = self.get_pending_messages()
            if pending:
                # Add pending messages as additional context
                for msg in pending:
                    await self.publish_action(
                        "user_message",
                        f"User added: {msg['content'][:50]}..."
                    )
                    self._state.conversation_history.append(
                        ConversationMessage(
                            role="user",
                            content=f"[Additional context from user]: {msg['content']}"
                        )
                    )

            # Build messages for API (async for context summarization)
            messages = await self._build_api_messages()

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

            # Calculate cost for display
            usage_cost = calculate_cost(
                model=response.model or self.config.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cached_tokens=response.cached_tokens,
            )

            # Accumulate usage for response
            total_cost += usage_cost.total_cost
            total_input_tokens += response.input_tokens
            total_output_tokens += response.output_tokens

            # Record to database and Prometheus (async, non-blocking)
            asyncio.create_task(
                get_cost_tracker().record_usage(
                    model=response.model or self.config.model,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    cached_tokens=response.cached_tokens,
                    agent_type=self.agent_type,
                    agent_name=self.config.name,
                    task_id=task_id,
                    correlation_id=getattr(self, "_correlation_id", None),
                )
            )

            # Publish API response action
            total_tokens = response.input_tokens + response.output_tokens
            await self.publish_action(
                ACTION_API_RESPONSE,
                f"Received response ({total_tokens:,} tokens, ${float(usage_cost.total_cost):.6f}, {response.provider.value})"
            )

            # Check stop reason
            if response.stop_reason == "end_turn":
                return {
                    "response": response.text_content,
                    "iterations": iterations,
                    "usage": {
                        "total_cost": str(total_cost),
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                    },
                }

            elif response.stop_reason == "tool_use":
                # Execute tools with parallel/sequential partitioning
                tool_results = []
                tool_step = 0
                tools_success = 0
                tools_failed = 0

                # Partition into parallel (no side effects) and sequential groups
                all_calls = [
                    ToolCallRequest(
                        name=tc.name,
                        arguments=tc.arguments,
                        tool_use_id=tc.id,
                    )
                    for tc in response.tool_calls
                ]
                parallel_calls, sequential_calls = self._parallel_executor.partition(all_calls)

                # Helper to process a single tool call result
                async def _process_tool_result(
                    tool_name: str,
                    tool_input: dict,
                    tool_use_id: str,
                    result: ToolResult,
                ) -> dict:
                    nonlocal tools_success, tools_failed

                    if result.success:
                        tools_success += 1
                    else:
                        tools_failed += 1

                    agent_tool_calls_total.labels(
                        agent_type=self.agent_type.value,
                        tool_name=tool_name,
                        status="success" if result.success else "error",
                    ).inc()

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

                    return {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": str(result.output) if result.success else (result.error or "Tool execution failed"),
                        "is_error": not result.success,
                    }

                # Helper to execute a single tool with hooks
                async def _execute_single_tool(call: ToolCallRequest) -> tuple[str, dict, str, ToolResult]:
                    nonlocal tool_step
                    tool_step += 1

                    # Direct security validation before any execution
                    from ai_core.security import validate_tool as security_validate_tool
                    allowed, sec_msg = security_validate_tool(
                        call.name, call.arguments, agent_name=self.config.name
                    )
                    if not allowed:
                        logger.warning(
                            "Tool blocked by security validator",
                            tool=call.name,
                            reason=sec_msg,
                            agent=self.config.name,
                        )
                        return call.name, call.arguments, call.tool_use_id, ToolResult(
                            success=False,
                            error=f"Blocked by security: {sec_msg}",
                            output=None,
                        )

                    if self._memory:
                        await self._memory.store_task_trace(
                            task_id=task_id,
                            phase=PAIPhase.BUILD,
                            data={
                                "agent_type": self.agent_type.value,
                                "tool_name": call.name,
                                "step": tool_step,
                                "iteration": iterations,
                            },
                        )

                    await self.publish_action(
                        ACTION_TOOL_CALL,
                        f"Calling {call.name}..."
                    )

                    if self._pubsub:
                        await self._pubsub.publish(
                            "agent:tool_calls",
                            ToolCall(
                                agent_type=self.agent_type,
                                task_id=task_id,
                                tool_name=call.name,
                                tool_input=call.arguments,
                            ).model_dump_json(),
                        )

                    pre_hook_result = await self._trigger_pre_tool_hook(
                        call.name, call.arguments, task_id
                    )

                    if pre_hook_result.get("security_blocked"):
                        logger.warning(
                            "Tool blocked by security plugin",
                            tool=call.name,
                            reason=pre_hook_result.get("block_reason"),
                        )
                        result = ToolResult(
                            success=False,
                            error=f"Blocked by security: {pre_hook_result.get('block_reason', 'Security violation')}",
                            output=None,
                        )
                    else:
                        result = await self._tool_registry.execute(
                            call.name,
                            call.arguments,
                            context={
                                "task_id": task_id,
                                "_memory": self._memory,
                                "_agent_type": self.agent_type.value,
                                "_task_id": task_id,
                                "_agent": self,
                            },
                        )

                        await self._trigger_post_tool_hook(
                            call.name, call.arguments, result, task_id
                        )

                    return call.name, call.arguments, call.tool_use_id, result

                # Execute parallel batch first (read-only tools)
                if parallel_calls:
                    await self.publish_action(
                        ACTION_TOOL_CALL,
                        f"Executing {len(parallel_calls)} read-only tools in parallel..."
                    )

                    parallel_tasks = [_execute_single_tool(c) for c in parallel_calls]
                    parallel_results = await asyncio.gather(*parallel_tasks)

                    for tool_name, tool_input, tool_use_id, result in parallel_results:
                        tr = await _process_tool_result(tool_name, tool_input, tool_use_id, result)
                        tool_results.append(tr)

                # Execute sequential tools (with side effects)
                for call in sequential_calls:
                    tool_name, tool_input, tool_use_id, result = await _execute_single_tool(call)
                    tr = await _process_tool_result(tool_name, tool_input, tool_use_id, result)
                    tool_results.append(tr)

                # === EXECUTE phase: Tool execution summary ===
                if self._memory:
                    await self._memory.store_task_trace(
                        task_id=task_id,
                        phase=PAIPhase.EXECUTE,
                        data={
                            "agent_type": self.agent_type.value,
                            "iteration": iterations,
                            "tools_executed": tool_step,
                            "tools_success": tools_success,
                            "tools_failed": tools_failed,
                            "success_rate": tools_success / tool_step if tool_step > 0 else 1.0,
                        },
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
            "usage": {
                "total_cost": str(total_cost),
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            },
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

    async def _build_api_messages(self) -> list[dict[str, Any]]:
        """Build messages list for Claude API.

        Uses context summarization when history exceeds threshold.
        Falls back to truncation for safety.
        Ensures tool_use/tool_result pairs are never split.
        """
        messages = []

        # Limit conversation history to prevent context overflow
        history = self._state.conversation_history

        # Try context summarization first (threshold: 24 messages)
        if self._context_summarizer.should_summarize(len(history)):
            summary, recent_history = await self._context_summarizer.summarize_history(history)

            if summary:
                # Inject summary as initial user/assistant exchange
                messages.append({
                    "role": "user",
                    "content": "[Previous conversation summary follows]",
                })
                messages.append({
                    "role": "assistant",
                    "content": f"[Conversation Summary]\n{summary}\n\n[Continuing from here with full context above]",
                })
                history = recent_history
                logger.debug(
                    "Applied context summarization",
                    original_length=len(self._state.conversation_history),
                    recent_kept=len(recent_history),
                )
            else:
                # Summarization returned empty, fall back to truncation
                max_history = 32
                if len(history) > max_history:
                    safe_start = self._find_safe_truncation_point(
                        history,
                        max_history,
                    )
                    history = history[safe_start:]
                    logger.debug(
                        "Truncated conversation history (summarization empty)",
                        original_length=len(self._state.conversation_history),
                        truncated_length=len(history),
                        safe_start_index=safe_start,
                    )
        else:
            # Under threshold, still apply hard truncation if somehow exceeded
            max_history = 32
            if len(history) > max_history:
                safe_start = self._find_safe_truncation_point(
                    history,
                    max_history,
                )
                history = history[safe_start:]

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
                            # Already a dict (normalized format)
                            content.append(block)
                        else:
                            # Anthropic SDK object (legacy, shouldn't happen with new code)
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

                    # Extract usage from result if available
                    usage = response.result.get("usage") if response.result else None

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
                            "usage": usage,
                        },
                    )

        except Exception as e:
            logger.error("Failed to handle task message", error=str(e))

    async def _handle_task_control_message(self, message: str) -> None:
        """
        Handle task control command (pause/resume/cancel).

        Args:
            message: JSON message with action, user_id, conversation_id
        """
        try:
            import json
            data = json.loads(message)
            action = data.get("action")
            user_id = data.get("user_id")
            conversation_id = data.get("conversation_id")

            # Only handle if this is the agent working on the conversation
            if self._state.current_conversation_id != conversation_id:
                return

            if action == "pause":
                await self.pause_task()
            elif action == "resume":
                await self.resume_task()
            elif action == "cancel":
                await self.cancel_task()

            logger.info(
                "Task control handled",
                action=action,
                task_id=self._state.current_task_id,
                agent=self.name,
            )

        except Exception as e:
            logger.error("Failed to handle task control message", error=str(e))

    async def _handle_pending_message(self, message: str) -> None:
        """
        Handle pending message from user while agent is busy.

        Args:
            message: JSON message with content, user_id, conversation_id
        """
        try:
            import json
            data = json.loads(message)
            content = data.get("content")
            user_id = data.get("user_id")
            conversation_id = data.get("conversation_id")

            # Only handle if this is the agent working on the conversation
            if self._state.current_conversation_id != conversation_id:
                return

            # Add to pending messages queue
            self.add_pending_message({
                "content": content,
                "user_id": user_id,
                "conversation_id": conversation_id,
            })

            logger.info(
                "Pending message queued",
                agent=self.name,
                content_length=len(content) if content else 0,
            )

        except Exception as e:
            logger.error("Failed to handle pending message", error=str(e))

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

        # Update Prometheus gauge for heartbeat monitoring
        agent_last_heartbeat_timestamp.labels(
            agent_name=self.config.name,
            agent_type=self.agent_type.value,
        ).set_to_current_time()

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

    async def log_to_redis(self, level: str, message: str) -> None:
        """
        Write a log entry to Redis for display in the UI.

        Args:
            level: Log level (debug, info, warning, error)
            message: Log message text
        """
        from datetime import datetime, timezone
        import json

        log_key = f"agent:logs:{self.config.name}"
        log_entry = json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
        })

        # Push to Redis list (newest first), keep last 500 entries
        await self._redis.lpush(log_key, log_entry)
        await self._redis.ltrim(log_key, 0, 499)

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

    # Hooks for subclasses
    async def on_task_start(self, request: TaskRequest) -> None:
        """Called when a task starts. Override in subclasses."""
        # Trigger plugin hooks
        if self._plugin_integration:
            await self._plugin_integration.trigger_hook(
                HookEvent.TASK_START,
                {
                    "task_id": request.id,
                    "task_type": request.task_type,
                    "agent_type": self.agent_type.value,
                    "agent_name": self.config.name,
                    "payload": request.payload,
                },
            )

    async def on_task_complete(
        self, request: TaskRequest, result: dict[str, Any]
    ) -> None:
        """Called when a task completes. Override in subclasses."""
        # Trigger plugin hooks
        if self._plugin_integration:
            await self._plugin_integration.trigger_hook(
                HookEvent.TASK_COMPLETE,
                {
                    "task_id": request.id,
                    "task_type": request.task_type,
                    "agent_type": self.agent_type.value,
                    "agent_name": self.config.name,
                    "result": result,
                    "changes": result.get("changes", []),
                },
            )

    async def on_task_error(self, request: TaskRequest, error: Exception) -> None:
        """Called when a task fails. Override in subclasses."""
        # Trigger plugin hooks
        if self._plugin_integration:
            await self._plugin_integration.trigger_hook(
                HookEvent.TASK_ERROR,
                {
                    "task_id": request.id,
                    "task_type": request.task_type,
                    "agent_type": self.agent_type.value,
                    "agent_name": self.config.name,
                    "error": str(error),
                    "error_type": type(error).__name__,
                },
            )

    async def _trigger_pre_tool_hook(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        task_id: str,
    ) -> dict[str, Any]:
        """Trigger pre-tool-use plugin hooks."""
        if not self._plugin_integration:
            return {"blocked": False}

        context = await self._plugin_integration.trigger_hook(
            HookEvent.PRE_TOOL_USE,
            {
                "tool_name": tool_name,
                "tool_args": tool_input,
                "task_id": task_id,
                "agent_type": self.agent_type.value,
                "agent_name": self.config.name,
            },
        )
        return context

    async def _trigger_post_tool_hook(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        result: Any,
        task_id: str,
    ) -> None:
        """Trigger post-tool-use plugin hooks."""
        if not self._plugin_integration:
            return

        await self._plugin_integration.trigger_hook(
            HookEvent.POST_TOOL_USE,
            {
                "tool_name": tool_name,
                "tool_args": tool_input,
                "result": result,
                "task_id": task_id,
                "agent_type": self.agent_type.value,
                "agent_name": self.config.name,
            },
        )
