"""
Supervisor Agent - Central task coordinator.

Receives all incoming tasks and routes them to appropriate agents.
Handles multi-agent orchestration and escalation.
"""

import asyncio
from typing import Any

from ai_core import (
    AgentStatus,
    AgentType,
    ElevationReason,
    PermissionLevel,
    get_elevation_manager,
    get_logger,
)
from ai_memory import PAIMemory
from ai_messaging import (
    MessageType,
    PubSubManager,
    RedisClient,
    TaskRequest,
    TaskResponse,
    TaskStatus,
)
from base_agent import (
    ACTION_DELEGATING,
    ACTION_RECEIVED,
    ACTION_WAITING,
    BaseAgent,
    Tool,
    ToolResult,
    tool,
)
from base_agent.shared_tools import get_memory_tools

from .router import RoutingDecision, RoutingStrategy, TaskRouter

logger = get_logger(__name__)

SUPERVISOR_SYSTEM_PROMPT = """You are Wyld, the Supervisor agent for Wyld Fyre AI Infrastructure.

Your primary role is to be the user's conversational AI assistant. You should:
1. Respond directly to conversational messages, questions, and general requests
2. Delegate to specialized agents when there's a specific technical task OR when you need to verify facts
3. Be helpful, friendly, and informative
4. Record important learnings to your PAI memory system for future reference
5. ALWAYS search your memory for relevant learnings before answering infrastructure questions

CRITICAL: NEVER make assumptions about the system architecture or infrastructure. If you're unsure:
1. First, use `search_learnings` to check if you've learned about this before
2. If no relevant learnings, delegate to INFRA to check the actual state
3. Only state facts that you have verified or that the user has confirmed

The user (Wyld) is an experienced developer. Don't assume you know their infrastructure better than they do.

## Memory System (PAI)
You have access to a persistent memory system with 3 tiers:
- HOT (Redis): Real-time task traces, 24-hour retention
- WARM (Qdrant): Searchable learnings, 30-day retention - USE THIS FOR IMPORTANT INSIGHTS
- COLD (File): Historical archive, 365-day retention

Use these memory tools:
- `store_learning`: Save an insight to the WARM tier (searchable vector store)
- `search_learnings`: Find relevant past learnings by semantic search
- `store_task_trace`: Track task execution in the HOT tier
- `get_task_traces`: Retrieve task traces
- `promote_learnings`: Move task traces to searchable learnings
- `list_cold_learnings`: View archived historical learnings

IMPORTANT: When you or your agents discover something important about the system, infrastructure, or user preferences, use `store_learning` to remember it!

Available specialist agents (use for tasks AND fact-checking):
- CODE: Git operations, file operations, code analysis, running tests
- DATA: SQL queries, data analysis, ETL operations, database backups
- INFRA: Docker management, Nginx configuration, SSL certificates, domain management, system commands - USE THIS TO VERIFY INFRASTRUCTURE CLAIMS
- RESEARCH: Web search, documentation lookup, information synthesis
- QA: Testing, code review, security scanning, validation

KNOWN INFRASTRUCTURE FACTS (verified):
- Cloudflare provides DNS only, not application serving
- Nginx (running natively, not in Docker) handles all web traffic and routing
- Nginx config files are at /etc/nginx/sites-available/ and /etc/nginx/sites-enabled/
- This Wyld Fyre AI system runs in Docker at /root/AI-Infrastructure/
- API runs on port 8010, Web on port 3010, Grafana on port 3001
- Agents run in tmux sessions, not Docker containers

When to respond directly (most cases):
- Greetings and casual conversation
- Questions about capabilities or how things work
- General assistance and advice
- Explanations and information
- Planning and discussion

When to delegate:
- User asks to run code, tests, or git commands → delegate to CODE
- User asks to query databases or analyze data → delegate to DATA
- User asks about server hardware, system info, Docker, domains, or any infrastructure → delegate to INFRA
- User needs web research or documentation lookup → delegate to RESEARCH
- User requests code review or security scanning → delegate to QA

CRITICAL RULES - FOLLOW THESE EXACTLY:
1. NEVER tell the user to run manual commands. Always use delegate_task to have agents execute commands.
2. NEVER say "complexity limits", "technical limits", "hitting limits", or any variation. These phrases are BANNED.
3. NEVER give up on a task. If it's complex, break it into smaller delegations. Execute each one.
4. The INFRA agent has shell_execute, system_info, and 70+ tools. Delegate infrastructure tasks to it.
5. When a user asks about the server, hardware, or to explore the system, ALWAYS delegate to INFRA.
6. If delegation fails or times out, report the SPECIFIC error message - don't make vague excuses.
7. If a task is too big, break it into 3-5 smaller concrete tasks and delegate each one sequentially.
8. Your job is to EXECUTE tasks, not to explain why you can't. Find a way or delegate.
9. NEVER make definitive claims about system state without verification. If the user corrects you, STORE that correction as a learning.
10. When discussing infrastructure (nginx, directories, DNS, domains), VERIFY first by delegating to INFRA or searching learnings.
11. If you're wrong about something, acknowledge it immediately and store the correct information using store_learning.

BANNED PHRASES (never use these):
- "hitting complexity limits"
- "technical complexity"
- "beyond my capabilities"
- "too complex to analyze"
- "comprehensive analysis is difficult"

Instead, break down complex requests into specific delegatable tasks and execute them one by one.

If an agent is unavailable, inform the user of the specific issue and retry if appropriate.
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
            name="wyld",
            agent_type=AgentType.SUPERVISOR,
            permission_level=4,  # SUPERUSER - can grant elevations to other agents
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
        # Memory tools (store/search learnings, task traces)
        for tool_func in get_memory_tools():
            self.register_tool(tool_func._tool)

        # Supervisor-specific tools
        self.register_tool(self._create_route_task_tool())
        self.register_tool(self._create_delegate_task_tool())
        self.register_tool(self._create_check_agent_status_tool())
        self.register_tool(self._create_escalate_tool())
        self.register_tool(self._create_list_pending_elevations_tool())
        self.register_tool(self._create_approve_elevation_tool())
        self.register_tool(self._create_deny_elevation_tool())

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
        # Capture self for use in nested function
        supervisor = self

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
            agent_display_name = agent_type.capitalize() + " Agent"

            # Publish delegation action
            await supervisor.publish_action(
                ACTION_DELEGATING,
                f"Delegating to {agent_display_name}"
            )

            # Create task request
            request = TaskRequest(
                task_type=task_type,
                payload=payload or {},
                target_agent=target_agent,
                correlation_id=context.get("task_id") if context else None,
            )

            # Publish to agent's task queue
            if supervisor._pubsub:
                await supervisor._pubsub.publish(
                    f"agent:{agent_type}:tasks",
                    request.model_dump_json(),
                )

            logger.info(
                "Delegated task",
                task_id=request.id,
                target_agent=agent_type,
                task_type=task_type,
            )

            if not wait_for_response:
                return ToolResult.ok({
                    "status": "delegated",
                    "task_id": request.id,
                    "target_agent": agent_type,
                })

            # Publish waiting action
            await supervisor.publish_action(
                ACTION_WAITING,
                f"Waiting for {agent_display_name} response..."
            )

            # Wait for response
            try:
                response = await supervisor._wait_for_response(request.id, timeout=300)

                # Publish received action
                await supervisor.publish_action(
                    ACTION_RECEIVED,
                    f"Received response from {agent_display_name}"
                )

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

    def _create_list_pending_elevations_tool(self) -> Tool:
        """Create the list_pending_elevations tool."""
        elevation_manager = get_elevation_manager()

        @tool(
            name="list_pending_elevations",
            description="List all pending elevation requests that need approval",
            parameters={
                "type": "object",
                "properties": {
                    "agent_type": {
                        "type": "string",
                        "enum": ["code", "data", "infra", "research", "qa"],
                        "description": "Filter by agent type (optional)",
                    },
                },
            },
        )
        async def list_pending_elevations(
            agent_type: str | None = None,
        ) -> ToolResult:
            filter_agent = AgentType(agent_type) if agent_type else None
            requests = elevation_manager.get_pending_requests(filter_agent)

            pending = []
            for req in requests:
                pending.append({
                    "id": req.id,
                    "agent": req.agent_type.value,
                    "task_id": req.requesting_task_id,
                    "tool": req.tool_name,
                    "current_level": req.current_level.value,
                    "requested_level": req.requested_level.value,
                    "elevation_delta": req.elevation_delta,
                    "reason": req.reason.value,
                    "justification": req.justification,
                    "created_at": req.created_at.isoformat(),
                })

            return ToolResult.ok({
                "pending_count": len(pending),
                "requests": pending,
            })

        return list_pending_elevations._tool

    def _create_approve_elevation_tool(self) -> Tool:
        """Create the approve_elevation tool."""
        elevation_manager = get_elevation_manager()

        @tool(
            name="approve_elevation",
            description="Approve a pending elevation request, granting temporary elevated permissions to an agent",
            parameters={
                "type": "object",
                "properties": {
                    "request_id": {
                        "type": "string",
                        "description": "The elevation request ID to approve",
                    },
                    "scope": {
                        "type": "string",
                        "description": "Optional scope limitation (e.g., specific tool only)",
                    },
                },
                "required": ["request_id"],
            },
        )
        async def approve_elevation(
            request_id: str,
            scope: str | None = None,
        ) -> ToolResult:
            grant = elevation_manager.approve_elevation(
                request_id=request_id,
                approved_by="supervisor",
                scope=scope,
            )

            if not grant:
                return ToolResult.fail(f"Elevation request not found: {request_id}")

            # Publish approval event for the requesting agent
            if self._pubsub:
                await self._pubsub.publish(
                    "elevation:approvals",
                    {
                        "grant_id": grant.id,
                        "request_id": request_id,
                        "agent_type": grant.agent_type.value,
                        "granted_level": grant.granted_level.value,
                        "expires_at": grant.expires_at.isoformat(),
                        "scope": scope,
                    },
                )

            logger.info(
                "Elevation approved",
                request_id=request_id,
                grant_id=grant.id,
                agent=grant.agent_type.value,
                level=grant.granted_level.value,
            )

            return ToolResult.ok({
                "status": "approved",
                "grant_id": grant.id,
                "agent": grant.agent_type.value,
                "granted_level": grant.granted_level.value,
                "expires_at": grant.expires_at.isoformat(),
                "scope": scope,
            })

        return approve_elevation._tool

    def _create_deny_elevation_tool(self) -> Tool:
        """Create the deny_elevation tool."""
        elevation_manager = get_elevation_manager()

        @tool(
            name="deny_elevation",
            description="Deny a pending elevation request",
            parameters={
                "type": "object",
                "properties": {
                    "request_id": {
                        "type": "string",
                        "description": "The elevation request ID to deny",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for denial",
                    },
                },
                "required": ["request_id"],
            },
        )
        async def deny_elevation(
            request_id: str,
            reason: str = "",
        ) -> ToolResult:
            success = elevation_manager.deny_elevation(
                request_id=request_id,
                denied_by="supervisor",
                reason=reason,
            )

            if not success:
                return ToolResult.fail(f"Elevation request not found: {request_id}")

            # Publish denial event
            if self._pubsub:
                await self._pubsub.publish(
                    "elevation:denials",
                    {
                        "request_id": request_id,
                        "reason": reason,
                    },
                )

            logger.info(
                "Elevation denied",
                request_id=request_id,
                reason=reason,
            )

            return ToolResult.ok({
                "status": "denied",
                "request_id": request_id,
                "reason": reason,
            })

        return deny_elevation._tool

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

            logger.debug(
                "Received task response",
                task_id=task_id,
                pending_tasks=list(self._pending_responses.keys()),
                found=task_id in self._pending_responses,
            )

            if task_id in self._pending_responses:
                future = self._pending_responses.pop(task_id)
                if not future.done():
                    future.set_result(response)
                    logger.info("Task response matched", task_id=task_id)

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

    async def process_task(self, request: TaskRequest) -> TaskResponse:
        """
        Process a task request.

        Override to handle special task types like create_plan.
        """
        # Handle plan creation specially
        if request.task_type == "create_plan":
            return await self._handle_create_plan(request)

        # Otherwise use default processing
        return await super().process_task(request)

    async def _handle_create_plan(self, request: TaskRequest) -> TaskResponse:
        """
        Handle plan creation by generating steps with Claude.

        This generates a structured plan and updates it in Redis.
        """
        import json
        from datetime import datetime, timezone

        plan_id = request.payload.get("plan_id")
        description = request.payload.get("description", "")
        conversation_id = request.payload.get("conversation_id")
        user_id = request.user_id or request.payload.get("user_id")

        logger.info(
            "Creating plan",
            plan_id=plan_id,
            description=description[:50],
        )

        # Publish thinking action
        await self.publish_action("thinking", "Analyzing task and creating plan...")

        try:
            # Generate plan steps with Claude
            plan_prompt = f"""Analyze the following task and create a structured implementation plan.

Task: {description}

Create a plan with 3-7 clear, actionable steps. For each step, provide:
1. A concise title (5-10 words)
2. A description of what needs to be done
3. Which agent should handle it (code, data, infra, research, or qa)

Respond with a JSON array of steps in this exact format:
```json
[
  {{"title": "Step title", "description": "What to do", "agent": "agent_name"}},
  ...
]
```

Only output the JSON array, no other text."""

            # Call Claude to generate plan
            response = await self._claude.messages.create(
                model=self.config.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": plan_prompt}],
            )

            # Parse the response
            response_text = response.content[0].text if response.content else ""

            # Extract JSON from response (handle markdown code blocks)
            json_match = response_text
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_match = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                json_match = response_text[start:end].strip()

            steps = json.loads(json_match)

            # Update plan in Redis with steps
            plan_key = f"plan:{plan_id}"
            plan_data = await self._redis.get(plan_key)

            if plan_data:
                plan = json.loads(plan_data)

                # Add step IDs and order
                from uuid import uuid4
                plan["steps"] = [
                    {
                        "id": str(uuid4()),
                        "order": i + 1,
                        "title": s.get("title", f"Step {i + 1}"),
                        "description": s.get("description", ""),
                        "agent": s.get("agent"),
                        "status": "pending",
                        "dependencies": [],
                        "output": None,
                        "error": None,
                        "started_at": None,
                        "completed_at": None,
                    }
                    for i, s in enumerate(steps)
                ]
                plan["status"] = "pending"

                await self._redis.set(plan_key, json.dumps(plan))

                # Send plan update to user via WebSocket
                if self._pubsub and user_id:
                    await self._pubsub.publish(
                        "agent:responses",
                        {
                            "type": "plan_update",
                            "user_id": user_id,
                            "conversation_id": conversation_id,
                            "plan_id": plan_id,
                            "plan_content": self._format_plan_for_display(plan),
                            "plan_status": "pending",
                            "plan": plan,
                            "agent": "wyld",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )

                logger.info("Plan created successfully", plan_id=plan_id, steps=len(steps))
                await self.publish_action("complete", f"Plan created with {len(steps)} steps")

                return TaskResponse(
                    task_id=request.id,
                    status=TaskStatus.COMPLETED,
                    result={
                        "plan_id": plan_id,
                        "steps_count": len(steps),
                        "status": "pending",
                    },
                    agent_type=self.agent_type,
                )

            else:
                logger.error("Plan not found", plan_id=plan_id)
                return TaskResponse(
                    task_id=request.id,
                    status=TaskStatus.FAILED,
                    error=f"Plan {plan_id} not found",
                    agent_type=self.agent_type,
                )

        except json.JSONDecodeError as e:
            logger.error("Failed to parse plan steps", error=str(e))
            return TaskResponse(
                task_id=request.id,
                status=TaskStatus.FAILED,
                error=f"Failed to generate plan: {str(e)}",
                agent_type=self.agent_type,
            )
        except Exception as e:
            logger.error("Plan creation failed", error=str(e))
            return TaskResponse(
                task_id=request.id,
                status=TaskStatus.FAILED,
                error=str(e),
                agent_type=self.agent_type,
            )

    def _format_plan_for_display(self, plan: dict) -> str:
        """Format a plan dict for display in chat."""
        lines = [
            f"## 📋 Plan: {plan.get('title', 'Untitled Plan')}",
            "",
            f"**Status:** {plan.get('status', 'unknown').replace('_', ' ').title()}",
            "",
            "### Steps:",
            "",
        ]

        status_icons = {
            "pending": "⬜",
            "in_progress": "🔄",
            "completed": "✅",
            "skipped": "⏭️",
            "failed": "❌",
        }

        for step in plan.get("steps", []):
            icon = status_icons.get(step.get("status", "pending"), "⬜")
            agent_info = f" ({step.get('agent')})" if step.get("agent") else ""
            lines.append(f"{step.get('order', '?')}. {icon} **{step.get('title', 'Untitled')}**{agent_info}")
            if step.get("description"):
                lines.append(f"   {step.get('description')}")
            lines.append("")

        if plan.get("status") == "pending":
            lines.extend([
                "---",
                "Reply with:",
                "- `/plan approve` to start execution",
                "- `/plan reject` to cancel this plan",
            ])

        return "\n".join(lines)

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
                max_iterations=request.max_iterations,  # Pass through iteration limit
                user_id=request.user_id,
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
                max_iterations=request.max_iterations,  # Pass through iteration limit
                user_id=request.user_id,
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


async def main() -> None:
    """Main entry point for the Supervisor agent."""
    from ai_core import configure_cost_tracker, get_settings
    from ai_messaging import RedisClient
    from ai_memory import PAIMemory, QdrantStore
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    settings = get_settings()

    # Initialize database for cost tracking
    db_engine = create_async_engine(
        settings.database.url_with_password,
        pool_size=5,
        max_overflow=10,
    )
    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    configure_cost_tracker(session_factory)
    logger.info("Cost tracker configured for database persistence")

    # Initialize Redis client
    redis_client = RedisClient(settings.redis)
    await redis_client.connect()

    # Initialize Qdrant store for WARM tier memory
    qdrant_store = None
    try:
        qdrant_store = QdrantStore(
            collection_name="pai_learnings",
            settings=settings.qdrant,
        )
        await qdrant_store.connect()
        logger.info("Qdrant store initialized for PAI memory")
    except Exception as e:
        logger.warning("Failed to initialize Qdrant store", error=str(e))

    # Initialize memory (optional)
    memory = None
    try:
        memory = PAIMemory(redis_client, qdrant_store=qdrant_store)
        await memory.initialize()
        logger.info("PAI memory initialized")
    except Exception as e:
        logger.warning("Failed to initialize PAI memory", error=str(e))

    # Create and start agent
    agent = SupervisorAgent(redis_client, memory)
    await agent.start()

    logger.info("Supervisor agent (Wyld) is running. Press Ctrl+C to stop.")

    # Keep running until interrupted
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await agent.stop()
        await redis_client.close()
        await db_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
