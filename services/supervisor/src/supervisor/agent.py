"""
Supervisor Agent - Central task coordinator.

Receives all incoming tasks and routes them to appropriate agents.
Handles multi-agent orchestration and escalation.
"""

import asyncio
from typing import Any

from ai_core import AgentStatus, AgentType, get_logger
from ai_memory import PAIMemory
from ai_messaging import (
    MessageType,
    PubSubManager,
    RedisClient,
    TaskRequest,
    TaskResponse,
    TaskStatus,
)
from base_agent import BaseAgent, Tool, ToolResult, tool

from .router import RoutingDecision, RoutingStrategy, TaskRouter

logger = get_logger(__name__)

SUPERVISOR_SYSTEM_PROMPT = """You are the Supervisor agent for AI Infrastructure, a multi-agent AI system.

Your role is to:
1. Analyze incoming task requests
2. Route tasks to the appropriate specialized agent(s)
3. Orchestrate multi-agent workflows
4. Handle escalation and error recovery

Available agents:
- CODE: Git operations, file operations, code analysis, testing
- DATA: SQL queries, data analysis, ETL operations, backups
- INFRA: Docker management, Nginx configuration, SSL, domain management
- RESEARCH: Web search, documentation lookup, information synthesis
- QA: Testing, code review, security scanning, validation

Guidelines:
- Route simple tasks directly to the appropriate agent
- For complex tasks, break them into subtasks and coordinate
- If unsure, ask the Research agent for context first
- Escalate issues that require human intervention
- Track task progress and handle failures gracefully

When routing, consider:
- Task type and keywords
- Required permissions
- Agent availability
- Task dependencies
"""


class SupervisorAgent(BaseAgent):
    """
    Supervisor agent for task routing and orchestration.

    Responsibilities:
    - Receive all incoming task requests
    - Analyze and route tasks to appropriate agents
    - Coordinate multi-agent workflows
    - Handle escalation and fallback
    """

    def __init__(
        self,
        redis_client: RedisClient,
        memory: PAIMemory | None = None,
    ):
        from base_agent.agent import AgentConfig

        config = AgentConfig(
            name="supervisor",
            agent_type=AgentType.SUPERVISOR,
            permission_level=3,  # Highest permission level
            system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        )

        super().__init__(config, redis_client, memory)

        self._router = TaskRouter()
        self._agent_status: dict[AgentType, AgentStatus] = {}
        self._pending_responses: dict[str, asyncio.Future] = {}

    def get_system_prompt(self) -> str:
        """Get the supervisor's system prompt."""
        return SUPERVISOR_SYSTEM_PROMPT

    def register_tools(self) -> None:
        """Register supervisor-specific tools."""
        self.register_tool(self._create_route_task_tool())
        self.register_tool(self._create_delegate_task_tool())
        self.register_tool(self._create_check_agent_status_tool())
        self.register_tool(self._create_escalate_tool())

    def _create_route_task_tool(self) -> Tool:
        """Create the route_task tool."""

        @tool(
            name="analyze_and_route",
            description="Analyze a task and determine which agent should handle it",
            parameters={
                "type": "object",
                "properties": {
                    "task_type": {
                        "type": "string",
                        "description": "The type of task to route",
                    },
                    "task_description": {
                        "type": "string",
                        "description": "Description of the task",
                    },
                },
                "required": ["task_type", "task_description"],
            },
        )
        async def analyze_and_route(
            task_type: str,
            task_description: str,
        ) -> ToolResult:
            decision = self._router.analyze_task(
                task_type,
                payload={"description": task_description},
            )

            return ToolResult.ok({
                "strategy": decision.strategy.value,
                "primary_agent": decision.primary_agent.value,
                "secondary_agents": [a.value for a in decision.secondary_agents],
                "reasoning": decision.reasoning,
                "confidence": decision.confidence,
            })

        return analyze_and_route._tool

    def _create_delegate_task_tool(self) -> Tool:
        """Create the delegate_task tool."""

        @tool(
            name="delegate_task",
            description="Delegate a task to a specific agent",
            parameters={
                "type": "object",
                "properties": {
                    "agent_type": {
                        "type": "string",
                        "enum": ["code", "data", "infra", "research", "qa"],
                        "description": "The agent to delegate to",
                    },
                    "task_type": {
                        "type": "string",
                        "description": "Type of task",
                    },
                    "payload": {
                        "type": "object",
                        "description": "Task payload",
                    },
                    "wait_for_response": {
                        "type": "boolean",
                        "description": "Whether to wait for the agent's response",
                        "default": True,
                    },
                },
                "required": ["agent_type", "task_type"],
            },
        )
        async def delegate_task(
            agent_type: str,
            task_type: str,
            payload: dict | None = None,
            wait_for_response: bool = True,
            context: dict | None = None,
        ) -> ToolResult:
            target_agent = AgentType(agent_type)

            # Create task request
            request = TaskRequest(
                task_type=task_type,
                payload=payload or {},
                target_agent=target_agent,
                correlation_id=context.get("task_id") if context else None,
            )

            # Publish to agent's task queue
            if self._pubsub:
                await self._pubsub.publish(
                    f"agent:{agent_type}:tasks",
                    request.model_dump_json(),
                )

            if not wait_for_response:
                return ToolResult.ok({
                    "status": "delegated",
                    "task_id": request.id,
                    "target_agent": agent_type,
                })

            # Wait for response
            try:
                response = await self._wait_for_response(request.id, timeout=300)
                return ToolResult.ok({
                    "status": response.status.value,
                    "result": response.result,
                    "error": response.error,
                    "duration_ms": response.duration_ms,
                })
            except asyncio.TimeoutError:
                return ToolResult.fail(
                    f"Timeout waiting for response from {agent_type}"
                )

        return delegate_task._tool

    def _create_check_agent_status_tool(self) -> Tool:
        """Create the check_agent_status tool."""

        @tool(
            name="check_agent_status",
            description="Check the status of an agent",
            parameters={
                "type": "object",
                "properties": {
                    "agent_type": {
                        "type": "string",
                        "enum": ["code", "data", "infra", "research", "qa"],
                        "description": "The agent to check",
                    },
                },
                "required": ["agent_type"],
            },
        )
        async def check_agent_status(agent_type: str) -> ToolResult:
            target = AgentType(agent_type)
            status = self._agent_status.get(target, AgentStatus.OFFLINE)

            return ToolResult.ok({
                "agent": agent_type,
                "status": status.value,
                "available": status == AgentStatus.IDLE,
            })

        return check_agent_status._tool

    def _create_escalate_tool(self) -> Tool:
        """Create the escalate tool."""

        @tool(
            name="escalate",
            description="Escalate an issue that requires human intervention",
            parameters={
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why escalation is needed",
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Severity level",
                    },
                    "context": {
                        "type": "object",
                        "description": "Additional context",
                    },
                },
                "required": ["reason", "severity"],
            },
        )
        async def escalate(
            reason: str,
            severity: str,
            context: dict | None = None,
        ) -> ToolResult:
            logger.warning(
                "Task escalated",
                reason=reason,
                severity=severity,
                context=context,
            )

            # Publish escalation event
            if self._pubsub:
                await self._pubsub.publish(
                    "system:escalations",
                    {
                        "reason": reason,
                        "severity": severity,
                        "context": context,
                    },
                )

            return ToolResult.ok({
                "status": "escalated",
                "severity": severity,
                "message": "Issue has been escalated for human review",
            })

        return escalate._tool

    async def start(self) -> None:
        """Start the supervisor agent."""
        await super().start()

        # Subscribe to agent status updates
        if self._pubsub:
            await self._pubsub.subscribe(
                "agent:status",
                self._handle_agent_status,
            )

            # Subscribe to all task responses
            await self._pubsub.subscribe(
                "task:*:response",
                self._handle_task_response,
                pattern=True,
            )

        logger.info("Supervisor agent ready")

    async def _handle_agent_status(self, message: str) -> None:
        """Handle agent status updates."""
        try:
            from ai_messaging import AgentStatusMessage

            status_msg = AgentStatusMessage.model_validate_json(message)
            self._agent_status[status_msg.agent_type] = status_msg.status

            logger.debug(
                "Agent status updated",
                agent=status_msg.agent_type.value,
                status=status_msg.status.value,
            )
        except Exception as e:
            logger.error("Failed to handle agent status", error=str(e))

    async def _handle_task_response(self, message: str) -> None:
        """Handle task responses from agents."""
        try:
            response = TaskResponse.model_validate_json(message)
            task_id = response.task_id

            if task_id in self._pending_responses:
                future = self._pending_responses.pop(task_id)
                if not future.done():
                    future.set_result(response)

        except Exception as e:
            logger.error("Failed to handle task response", error=str(e))

    async def _wait_for_response(
        self,
        task_id: str,
        timeout: float = 300,
    ) -> TaskResponse:
        """Wait for a task response."""
        future: asyncio.Future[TaskResponse] = asyncio.Future()
        self._pending_responses[task_id] = future

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending_responses.pop(task_id, None)

    async def route_and_execute(self, request: TaskRequest) -> TaskResponse:
        """
        Route a task request and execute it.

        This is the main entry point for all incoming tasks.
        """
        # Analyze routing
        decision = self._router.analyze_task(
            request.task_type,
            payload=request.payload,
            metadata=request.metadata,
        )

        logger.info(
            "Routing task",
            task_id=request.id,
            task_type=request.task_type,
            strategy=decision.strategy.value,
            primary_agent=decision.primary_agent.value,
        )

        if decision.strategy == RoutingStrategy.SINGLE:
            # Simple delegation
            return await self._delegate_single(request, decision)

        elif decision.strategy == RoutingStrategy.SEQUENTIAL:
            # Sequential execution
            return await self._delegate_sequential(request, decision)

        elif decision.strategy == RoutingStrategy.PARALLEL:
            # Parallel execution
            return await self._delegate_parallel(request, decision)

        else:
            # Let Claude decide
            return await self.process_task(request)

    async def _delegate_single(
        self,
        request: TaskRequest,
        decision: RoutingDecision,
    ) -> TaskResponse:
        """Delegate to a single agent."""
        # Modify request with target agent
        request.target_agent = decision.primary_agent

        # Publish to agent queue
        if self._pubsub:
            await self._pubsub.publish(
                f"agent:{decision.primary_agent.value}:tasks",
                request.model_dump_json(),
            )

        # Wait for response
        try:
            return await self._wait_for_response(request.id)
        except asyncio.TimeoutError:
            return TaskResponse(
                task_id=request.id,
                status=TaskStatus.FAILED,
                error=f"Timeout waiting for {decision.primary_agent.value}",
                agent_type=self.agent_type,
            )

    async def _delegate_sequential(
        self,
        request: TaskRequest,
        decision: RoutingDecision,
    ) -> TaskResponse:
        """Execute tasks sequentially across multiple agents."""
        all_agents = [decision.primary_agent] + decision.secondary_agents
        results = []
        current_payload = request.payload.copy()

        for agent in all_agents:
            sub_request = TaskRequest(
                task_type=request.task_type,
                payload=current_payload,
                target_agent=agent,
                correlation_id=request.id,
            )

            if self._pubsub:
                await self._pubsub.publish(
                    f"agent:{agent.value}:tasks",
                    sub_request.model_dump_json(),
                )

            try:
                response = await self._wait_for_response(sub_request.id)
                results.append({
                    "agent": agent.value,
                    "status": response.status.value,
                    "result": response.result,
                })

                # Pass result to next agent
                if response.result:
                    current_payload["previous_result"] = response.result

                if response.status == TaskStatus.FAILED:
                    break

            except asyncio.TimeoutError:
                results.append({
                    "agent": agent.value,
                    "status": "timeout",
                    "error": "Timeout waiting for response",
                })
                break

        # Aggregate results
        final_status = TaskStatus.COMPLETED
        if any(r.get("status") in ("failed", "timeout") for r in results):
            final_status = TaskStatus.FAILED

        return TaskResponse(
            task_id=request.id,
            status=final_status,
            result={"sequential_results": results},
            agent_type=self.agent_type,
        )

    async def _delegate_parallel(
        self,
        request: TaskRequest,
        decision: RoutingDecision,
    ) -> TaskResponse:
        """Execute tasks in parallel across multiple agents."""
        all_agents = [decision.primary_agent] + decision.secondary_agents

        # Create tasks for all agents
        tasks = []
        for agent in all_agents:
            sub_request = TaskRequest(
                task_type=request.task_type,
                payload=request.payload,
                target_agent=agent,
                correlation_id=request.id,
            )

            if self._pubsub:
                await self._pubsub.publish(
                    f"agent:{agent.value}:tasks",
                    sub_request.model_dump_json(),
                )

            tasks.append(self._wait_for_response(sub_request.id))

        # Wait for all
        try:
            responses = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=300,
            )
        except asyncio.TimeoutError:
            responses = []

        # Aggregate results
        results = []
        for agent, response in zip(all_agents, responses):
            if isinstance(response, Exception):
                results.append({
                    "agent": agent.value,
                    "status": "error",
                    "error": str(response),
                })
            else:
                results.append({
                    "agent": agent.value,
                    "status": response.status.value,
                    "result": response.result,
                })

        final_status = TaskStatus.COMPLETED
        if any(r.get("status") in ("failed", "error") for r in results):
            final_status = TaskStatus.FAILED

        return TaskResponse(
            task_id=request.id,
            status=final_status,
            result={"parallel_results": results},
            agent_type=self.agent_type,
        )
