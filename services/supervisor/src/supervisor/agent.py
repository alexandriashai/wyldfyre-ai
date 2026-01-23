"""
Supervisor Agent - Central task coordinator.

Receives all incoming tasks and routes them to appropriate agents.
Handles multi-agent orchestration and escalation.
"""

import asyncio
import os
import re
from pathlib import Path
from typing import Any

import aiofiles

from ai_core import (
    AgentStatus,
    AgentType,
    ElevationReason,
    ModelTier,
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


# ============================================================
# Exploration Helper Functions for Plan Mode
# ============================================================

async def _glob_files(pattern: str, base_path: str = "/home/wyld-core", max_results: int = 50) -> list[dict[str, str]]:
    """Find files matching glob pattern."""
    base = Path(base_path)
    results: list[dict[str, str]] = []
    try:
        # Handle both "**/*.py" and "*.py" patterns
        search_pattern = pattern.lstrip("**/")
        for path in base.rglob(search_pattern):
            if len(results) >= max_results:
                break
            # Skip hidden directories and common excludes
            if path.is_file() and not any(p.startswith(".") for p in path.parts):
                if not any(excl in str(path) for excl in ["node_modules", "__pycache__", ".git", "venv"]):
                    results.append({
                        "path": str(path),
                        "name": path.name,
                        "relative": str(path.relative_to(base))
                    })
    except Exception as e:
        logger.debug("Glob search error", pattern=pattern, error=str(e))
    return results


async def _grep_content(pattern: str, path: str = "/home/wyld-core", max_results: int = 30) -> list[dict[str, Any]]:
    """Search for pattern in files."""
    base = Path(path)
    results: list[dict[str, Any]] = []
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error:
        # If pattern is invalid regex, treat it as literal search
        regex = re.compile(re.escape(pattern), re.IGNORECASE)

    extensions = [".py", ".ts", ".tsx", ".js", ".jsx", ".yaml", ".yml", ".json", ".md"]

    for ext in extensions:
        if len(results) >= max_results:
            break
        for file_path in base.rglob(f"*{ext}"):
            if len(results) >= max_results:
                break
            # Skip common excludes
            if any(excl in str(file_path) for excl in ["node_modules", "__pycache__", ".git", "venv"]):
                continue
            try:
                async with aiofiles.open(file_path, "r", errors="ignore") as f:
                    content = await f.read()
                    for i, line in enumerate(content.split("\n"), 1):
                        if regex.search(line):
                            results.append({
                                "file": str(file_path),
                                "line": i,
                                "content": line.strip()[:200]
                            })
                            if len(results) >= max_results:
                                break
            except Exception:
                continue
    return results


async def _read_file(path: str, max_lines: int = 200) -> str:
    """Read file contents."""
    try:
        async with aiofiles.open(path, "r", errors="ignore") as f:
            lines = await f.readlines()
            return "".join(lines[:max_lines])
    except Exception as e:
        return f"Error reading file: {e}"


# Safety: paths that should never be written to
WRITE_BLOCKED_PATTERNS = [
    ".env", "credentials", "secret", ".git/", "node_modules/",
    "__pycache__/", ".venv/", "id_rsa", ".pem", ".key",
]


async def _write_file(path: str, content: str, allowed_base: str = "/home/wyld-core") -> str:
    """
    Write content to a file with safety checks.

    Enforces:
    - No writing to sensitive paths (.env, credentials, keys)
    - Only writes within allowed_base path
    - Creates parent directories if needed
    """
    # Safety: must be within allowed base
    if not path.startswith(allowed_base):
        return f"Error: Cannot write outside {allowed_base}"

    # Safety: block sensitive paths
    path_lower = path.lower()
    for blocked in WRITE_BLOCKED_PATTERNS:
        if blocked in path_lower:
            return f"Error: Cannot write to protected path containing '{blocked}'"

    try:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "w") as f:
            await f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


async def _edit_file(path: str, old_text: str, new_text: str, allowed_base: str = "/home/wyld-core") -> str:
    """
    Replace specific text in a file (safer than full overwrite).

    Enforces same safety checks as _write_file.
    """
    if not path.startswith(allowed_base):
        return f"Error: Cannot edit outside {allowed_base}"

    path_lower = path.lower()
    for blocked in WRITE_BLOCKED_PATTERNS:
        if blocked in path_lower:
            return f"Error: Cannot edit protected path containing '{blocked}'"

    try:
        async with aiofiles.open(path, "r") as f:
            content = await f.read()

        if old_text not in content:
            return f"Error: old_text not found in {path}"

        count = content.count(old_text)
        new_content = content.replace(old_text, new_text, 1)

        async with aiofiles.open(path, "w") as f:
            await f.write(new_content)

        return f"Replaced text in {path} (1 of {count} occurrences)"
    except Exception as e:
        return f"Error editing file: {e}"


async def _run_command(command: str, cwd: str = "/home/wyld-core", timeout: int = 120) -> str:
    """
    Execute a shell command and return its output.

    Safety: blocks dangerous commands but allows git, npm, docker, builds, etc.
    """
    import asyncio as _asyncio

    # Block dangerous commands
    dangerous = ["rm -rf /", "mkfs", "dd if=", ":(){", "fork bomb", "shutdown", "reboot"]
    cmd_lower = command.lower()
    for d in dangerous:
        if d in cmd_lower:
            return f"Error: Blocked dangerous command pattern: {d}"

    try:
        proc = await _asyncio.create_subprocess_shell(
            command,
            stdout=_asyncio.subprocess.PIPE,
            stderr=_asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await _asyncio.wait_for(proc.communicate(), timeout=timeout)

        output = ""
        if stdout:
            output += stdout.decode("utf-8", errors="replace")
        if stderr:
            output += ("\n[stderr]\n" + stderr.decode("utf-8", errors="replace")) if output else stderr.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            output = f"[exit code {proc.returncode}]\n{output}"

        return output[:8000] if output else f"Command completed (exit code {proc.returncode})"
    except _asyncio.TimeoutError:
        return f"Error: Command timed out after {timeout}s"
    except Exception as e:
        return f"Error running command: {e}"


async def _list_directory(path: str) -> str:
    """List files and directories at a path."""
    from pathlib import Path as _Path

    target = _Path(path)
    if not target.exists():
        return f"Error: Path does not exist: {path}"
    if not target.is_dir():
        return f"Error: Not a directory: {path}"

    try:
        entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        lines = []
        for entry in entries[:100]:  # Limit to 100 entries
            if entry.name.startswith(".") and entry.name not in (".env", ".gitignore"):
                continue
            prefix = "📁 " if entry.is_dir() else "📄 "
            lines.append(f"{prefix}{entry.name}")
        return "\n".join(lines) if lines else "(empty directory)"
    except Exception as e:
        return f"Error listing directory: {e}"


def _load_telos_context() -> str:
    """Load TELOS mission and values for agent context."""
    telos_dir = Path("/home/wyld-core/pai/TELOS")
    context_parts = []

    for filename in ["mission.md", "values.md"]:
        filepath = telos_dir / filename
        if filepath.exists():
            try:
                content = filepath.read_text()
                context_parts.append(content.strip())
            except Exception:
                pass

    if context_parts:
        return "## TELOS Framework (Mission & Values)\n\n" + "\n\n---\n\n".join(context_parts)
    return ""


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
        self.register_tool(self._create_restart_agent_tool())

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
                channel = f"agent:{agent_type}:tasks"
                subscriber_count = await supervisor._pubsub.publish(
                    channel,
                    request.model_dump_json(),
                )

                # If no subscribers, the target agent isn't running
                if subscriber_count == 0:
                    logger.warning(
                        "No subscribers for agent channel",
                        target_agent=agent_type,
                        channel=channel,
                    )
                    return ToolResult.fail(
                        f"Agent '{agent_type}' is not running. "
                        f"Use restart_agent to start it, or handle this task directly."
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

    def _create_restart_agent_tool(self) -> Tool:
        """Create the restart_agent tool."""
        supervisor = self

        AGENT_MODULES = {
            "code": "code_agent",
            "data": "data_agent",
            "infra": "infra_agent",
            "research": "research_agent",
            "qa": "qa_agent",
        }

        @tool(
            name="restart_agent",
            description="Start or restart a stopped agent. Use this when delegation fails because an agent is not running.",
            parameters={
                "type": "object",
                "properties": {
                    "agent_type": {
                        "type": "string",
                        "enum": ["code", "data", "infra", "research", "qa"],
                        "description": "The type of agent to restart",
                    },
                },
                "required": ["agent_type"],
            },
        )
        async def restart_agent(agent_type: str) -> ToolResult:
            import subprocess
            import signal

            module_name = AGENT_MODULES.get(agent_type)
            if not module_name:
                return ToolResult.fail(f"Unknown agent type: {agent_type}")

            agent_src_path = f"/home/wyld-core/services/agents/{module_name}/src"
            python_path = ":".join([
                agent_src_path,
                "/home/wyld-core/packages/core/src",
                "/home/wyld-core/packages/messaging/src",
                "/home/wyld-core/packages/memory/src",
                "/home/wyld-core/packages/agents/src",
            ])

            await supervisor.publish_action(
                "tool_call",
                f"Starting {agent_type} agent..."
            )

            # Kill existing process if running
            try:
                result = subprocess.run(
                    ["pgrep", "-f", f"python3 -m {module_name}"],
                    capture_output=True, text=True,
                )
                if result.stdout.strip():
                    for pid in result.stdout.strip().split("\n"):
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                        except (ProcessLookupError, ValueError):
                            pass
                    await asyncio.sleep(2)
            except Exception:
                pass

            # Build environment from current process env
            import os
            env = os.environ.copy()
            env["PYTHONPATH"] = python_path
            env["REDIS_HOST"] = "localhost"
            env["QDRANT_HOST"] = "localhost"
            env["POSTGRES_HOST"] = "localhost"

            # Start the agent
            log_path = f"/var/log/ai-{agent_type}-agent.log"
            try:
                log_file = open(log_path, "w")
                proc = subprocess.Popen(
                    ["python3", "-m", module_name],
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    cwd="/home/wyld-core",
                    start_new_session=True,
                )

                # Wait briefly to check if it started
                await asyncio.sleep(3)

                if proc.poll() is not None:
                    log_file.close()
                    with open(log_path, "r") as f:
                        error_output = f.read()[-500:]
                    return ToolResult.fail(
                        f"Agent {agent_type} failed to start: {error_output}"
                    )

                logger.info(
                    "Agent started",
                    agent_type=agent_type,
                    pid=proc.pid,
                )

                return ToolResult.ok({
                    "status": "started",
                    "agent_type": agent_type,
                    "pid": proc.pid,
                    "log_file": log_path,
                })

            except Exception as e:
                return ToolResult.fail(f"Failed to start agent {agent_type}: {e}")

        return restart_agent._tool

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

        Override to handle special task types like create_plan and execute_plan.
        """
        # Handle plan creation specially
        if request.task_type == "create_plan":
            return await self._handle_create_plan(request)

        # Handle plan execution
        if request.task_type == "execute_plan":
            return await self._handle_execute_plan(request)

        # Handle plan modification
        if request.task_type == "modify_plan":
            return await self._handle_modify_plan(request)

        # Otherwise use default processing
        response = await super().process_task(request)

        # Auto-generate conversation title after first chat message
        if request.task_type == "chat" and response.status == TaskStatus.COMPLETED:
            conversation_id = request.payload.get("conversation_id")
            if conversation_id:
                await self._maybe_generate_title(request, conversation_id)

        return response

    async def _maybe_generate_title(self, request: TaskRequest, conversation_id: str) -> None:
        """
        Generate a conversation title from the first user message.

        Only generates if the conversation title is still a default name.
        """
        try:
            # Check current title in Redis
            conv_key = f"conversation:{conversation_id}"
            current_title = await self._redis.hget(conv_key, "title")

            # Only generate if title is default
            default_titles = {"New Chat", "Chat with Wyld", "New Conversation", None, ""}
            if current_title and current_title not in default_titles:
                return

            # Check message count — only do this for the first message
            msg_count = await self._redis.hget(conv_key, "message_count")
            if msg_count and int(msg_count) > 2:
                return

            # Get the user message content
            user_message = request.payload.get("content", "")
            if not user_message or len(user_message) < 3:
                return

            # Generate title using LLM (fast, small call)
            response = await self._llm.create_message(
                max_tokens=30,
                tier=ModelTier.FAST,
                messages=[{
                    "role": "user",
                    "content": f"Generate a short title (3-6 words, no quotes) for a conversation that starts with this message:\n\n{user_message[:200]}"
                }],
            )

            title = response.text_content.strip().strip('"\'') if response.text_content else None
            if not title or len(title) < 2:
                return

            # Truncate to reasonable length
            title = title[:60]

            # Update in Redis
            await self._redis.hset(conv_key, "title", title)

            # Update in database
            try:
                from database import db_session_context
                from database.models import Conversation
                from sqlalchemy import update

                async with db_session_context() as session:
                    await session.execute(
                        update(Conversation)
                        .where(Conversation.id == conversation_id)
                        .values(title=title)
                    )
                    await session.commit()
            except Exception as db_err:
                logger.debug("Failed to update title in DB", error=str(db_err))

            # Notify frontend
            user_id = request.user_id or request.payload.get("user_id")
            if self._pubsub and user_id:
                await self._pubsub.publish(
                    "agent:responses",
                    {
                        "type": "conversation_renamed",
                        "user_id": user_id,
                        "conversation_id": conversation_id,
                        "title": title,
                    },
                )

            logger.info("Generated conversation title", conversation_id=conversation_id[:8], title=title)

        except Exception as e:
            # Non-critical — don't fail the task if title generation fails
            logger.debug("Title generation failed", error=str(e))

    async def _handle_create_plan(self, request: TaskRequest) -> TaskResponse:
        """
        Handle plan creation with Explore → Plan phases.

        This first explores the codebase to gather context, then generates
        intelligent plan steps based on actual files and patterns found.
        """
        import json
        from datetime import datetime, timezone

        plan_id = request.payload.get("plan_id")
        description = request.payload.get("description", "")
        conversation_id = request.payload.get("conversation_id")
        user_id = request.user_id or request.payload.get("user_id")
        project_id = request.payload.get("project_id") or request.metadata.get("project_id")
        root_path = request.payload.get("root_path") or "/home/wyld-core"
        agent_context = request.payload.get("agent_context") or ""
        project_name = request.payload.get("project_name") or ""

        # Set state context for publish_action to work
        self._state.current_user_id = user_id
        self._state.current_conversation_id = conversation_id
        self._state.current_project_id = project_id

        logger.info(
            "Creating plan with exploration",
            plan_id=plan_id,
            description=description[:50],
            root_path=root_path,
            project_name=project_name,
        )

        try:
            # ========== EXPLORE PHASE ==========
            logger.info(
                "Publishing explore action",
                user_id=user_id,
                conversation_id=conversation_id,
                state_user_id=self._state.current_user_id,
            )
            await self.publish_action("exploring", f"Exploring {project_name or 'codebase'}...")
            exploration = await self._explore_for_plan(description, base_path=root_path)

            # ========== PLAN PHASE ==========
            await self.publish_action("planning", "Creating implementation plan...")
            steps = await self._generate_plan_from_exploration(description, exploration, base_path=root_path)

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
                        "files": s.get("files", []),
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
                plan["root_path"] = root_path
                plan["agent_context"] = agent_context
                plan["project_name"] = project_name

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
                            "plan_status": "PENDING",  # Frontend expects uppercase
                            "plan": plan,
                            "agent": "wyld",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )

                logger.info("Plan created successfully", plan_id=plan_id, steps=len(steps))
                await self.publish_action("complete", f"Plan created with {len(steps)} steps")

                # Store plan creation in memory (PLAN phase)
                if self._memory:
                    try:
                        from ai_memory import Learning, LearningScope, PAIPhase

                        step_titles = [s.get("title", f"Step {i+1}") for i, s in enumerate(steps)]
                        learning = Learning(
                            content=f"Created plan: {description[:100]}\nSteps: {', '.join(step_titles)}",
                            phase=PAIPhase.PLAN,
                            category="plan_creation",
                            scope=LearningScope.PROJECT,
                            created_by_agent="supervisor",
                            metadata={
                                "plan_id": plan_id,
                                "description": description[:200],
                                "steps_count": len(steps),
                                "conversation_id": conversation_id,
                                "project_name": project_name,
                            },
                        )
                        await self._memory.store_learning(learning)
                    except Exception as mem_err:
                        logger.warning("Failed to store plan creation in memory", error=str(mem_err))

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

        except Exception as e:
            logger.error("Plan creation failed", error=str(e))
            return TaskResponse(
                task_id=request.id,
                status=TaskStatus.FAILED,
                error=str(e),
                agent_type=self.agent_type,
            )
        finally:
            # Clear state context
            self._state.current_user_id = None
            self._state.current_conversation_id = None
            self._state.current_project_id = None

    async def _handle_execute_plan(self, request: TaskRequest) -> TaskResponse:
        """
        Execute an approved plan by working through its steps.

        Each step is executed in order, with real-time status updates
        sent to the frontend to show progress.
        """
        import json
        import asyncio
        from datetime import datetime, timezone

        plan_id = request.payload.get("plan_id")
        conversation_id = request.payload.get("conversation_id")
        user_id = request.user_id or request.payload.get("user_id")
        # root_path from request payload (set by WebSocket handler)
        request_root_path = request.payload.get("root_path")

        # Set state context for publish_action to work
        self._state.current_user_id = user_id
        self._state.current_conversation_id = conversation_id

        logger.info(
            "Executing plan",
            plan_id=plan_id,
            conversation_id=conversation_id,
        )

        try:
            # Load plan from Redis
            plan_key = f"plan:{plan_id}"
            plan_data = await self._redis.get(plan_key)

            if not plan_data:
                return TaskResponse(
                    task_id=request.id,
                    status=TaskStatus.FAILED,
                    error=f"Plan {plan_id} not found",
                    agent_type=self.agent_type,
                )

            plan = json.loads(plan_data)
            steps = plan.get("steps", [])

            # Resolve root_path: request > plan > default
            root_path = request_root_path or plan.get("root_path") or "/home/wyld-core"
            plan["root_path"] = root_path  # Ensure it's in plan for step execution
            logger.info("Plan execution root_path", root_path=root_path)

            if not steps:
                return TaskResponse(
                    task_id=request.id,
                    status=TaskStatus.FAILED,
                    error="Plan has no steps",
                    agent_type=self.agent_type,
                )

            # Update plan status to executing
            plan["status"] = "executing"
            await self._redis.set(plan_key, json.dumps(plan))

            # Send initial execution status
            await self.publish_action("executing", f"Starting plan execution: {plan.get('title', 'Plan')}")

            # Send step_update to frontend with all steps
            if self._pubsub and user_id:
                await self._pubsub.publish(
                    "agent:responses",
                    {
                        "type": "step_update",
                        "user_id": user_id,
                        "conversation_id": conversation_id,
                        "plan_id": plan_id,
                        "steps": steps,
                        "current_step": 0,
                        "agent": "wyld",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            # Execute each step
            cancelled = False
            for i, step in enumerate(steps):
                # Check for task cancellation before each step
                if self.is_task_cancelled():
                    cancelled = True
                    logger.info("Plan execution cancelled by user", plan_id=plan_id)
                    await self.publish_action("cancelled", "Plan execution stopped by user")
                    break

                # Skip already completed or skipped steps (e.g., after modification)
                if step.get("status") in ("completed", "skipped"):
                    continue

                step_id = step.get("id")
                step_title = step.get("title", f"Step {i + 1}")
                step_description = step.get("description", "")

                # Update step status to in_progress
                step["status"] = "in_progress"
                step["started_at"] = datetime.now(timezone.utc).isoformat()
                plan["current_step"] = i
                await self._redis.set(plan_key, json.dumps(plan))

                # Send step update
                await self.publish_action("step_progress", f"Working on: {step_title}")
                if self._pubsub and user_id:
                    await self._pubsub.publish(
                        "agent:responses",
                        {
                            "type": "step_update",
                            "user_id": user_id,
                            "conversation_id": conversation_id,
                            "plan_id": plan_id,
                            "steps": steps,
                            "current_step": i,
                            "agent": "wyld",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )

                # Execute the step using Claude
                try:
                    # Check for cancellation again before executing
                    if self.is_task_cancelled():
                        cancelled = True
                        step["status"] = "pending"  # Reset to pending
                        step.pop("started_at", None)
                        break

                    step_result = await self._execute_plan_step(step, plan)
                    step["status"] = "completed"
                    step["completed_at"] = datetime.now(timezone.utc).isoformat()
                    step["output"] = step_result
                except Exception as e:
                    step["status"] = "failed"
                    step["error"] = str(e)
                    step["completed_at"] = datetime.now(timezone.utc).isoformat()
                    logger.error("Step execution failed", step_id=step_id, error=str(e))

                # Update plan in Redis
                await self._redis.set(plan_key, json.dumps(plan))

                # Send step completion update
                if self._pubsub and user_id:
                    await self._pubsub.publish(
                        "agent:responses",
                        {
                            "type": "step_update",
                            "user_id": user_id,
                            "conversation_id": conversation_id,
                            "plan_id": plan_id,
                            "steps": steps,
                            "current_step": i,
                            "agent": "wyld",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )

                # Small delay to allow task control messages to be processed
                await asyncio.sleep(0.1)

            # Mark plan as completed or cancelled
            completed_steps = sum(1 for s in steps if s.get("status") == "completed")

            if cancelled:
                plan["status"] = "paused"  # Mark as paused so it can be resumed
                await self._redis.set(plan_key, json.dumps(plan))

                # Send cancelled status update
                if self._pubsub and user_id:
                    await self._pubsub.publish(
                        "agent:responses",
                        {
                            "type": "plan_update",
                            "user_id": user_id,
                            "conversation_id": conversation_id,
                            "plan_id": plan_id,
                            "plan_content": f"⏸️ Plan paused. {completed_steps}/{len(steps)} steps completed.\n\nType 'resume' to continue or modify the plan.",
                            "plan_status": "APPROVED",  # Keep approved so it can be resumed
                            "agent": "wyld",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )

                return TaskResponse(
                    task_id=request.id,
                    status=TaskStatus.COMPLETED,
                    result={
                        "plan_id": plan_id,
                        "cancelled": True,
                        "steps_completed": completed_steps,
                        "steps_total": len(steps),
                    },
                    agent_type=self.agent_type,
                )

            plan["status"] = "completed"
            plan["completed_at"] = datetime.now(timezone.utc).isoformat()
            await self._redis.set(plan_key, json.dumps(plan))

            # Send completion message
            await self.publish_action("complete", f"Plan completed: {completed_steps}/{len(steps)} steps")

            # Store completed plan in PAI memory (LEARN phase)
            if self._memory:
                try:
                    from ai_memory import Learning, LearningScope, PAIPhase

                    plan_title = plan.get("title", plan.get("description", "Untitled plan"))
                    step_summaries = []
                    for s in steps:
                        status_icon = "✓" if s.get("status") == "completed" else "✗"
                        step_summaries.append(f"{status_icon} {s.get('title', 'Step')}")

                    learning_content = (
                        f"Completed plan: {plan_title}\n"
                        f"Steps ({completed_steps}/{len(steps)} completed):\n"
                        + "\n".join(step_summaries)
                    )

                    learning = Learning(
                        content=learning_content,
                        phase=PAIPhase.LEARN,
                        category="plan_completion",
                        scope=LearningScope.PROJECT,
                        created_by_agent="supervisor",
                        metadata={
                            "plan_id": plan_id,
                            "plan_title": plan_title,
                            "steps_completed": completed_steps,
                            "steps_total": len(steps),
                            "conversation_id": conversation_id,
                            "completed_at": plan["completed_at"],
                        },
                    )
                    await self._memory.store_learning(learning)
                    logger.info("Plan stored in memory", plan_id=plan_id, phase="LEARN")
                except Exception as mem_err:
                    logger.warning("Failed to store plan in memory", error=str(mem_err))

            # Send final plan_update to clear plan panel
            if self._pubsub and user_id:
                await self._pubsub.publish(
                    "agent:responses",
                    {
                        "type": "plan_update",
                        "user_id": user_id,
                        "conversation_id": conversation_id,
                        "plan_id": plan_id,
                        "plan_content": f"✅ Plan completed! {completed_steps}/{len(steps)} steps finished.",
                        "plan_status": "COMPLETED",
                        "agent": "wyld",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            return TaskResponse(
                task_id=request.id,
                status=TaskStatus.COMPLETED,
                result={
                    "plan_id": plan_id,
                    "steps_completed": completed_steps,
                    "steps_total": len(steps),
                },
                agent_type=self.agent_type,
            )

        except Exception as e:
            logger.error("Plan execution failed", error=str(e))
            return TaskResponse(
                task_id=request.id,
                status=TaskStatus.FAILED,
                error=str(e),
                agent_type=self.agent_type,
            )
        finally:
            # Clear state context
            self._state.current_user_id = None
            self._state.current_conversation_id = None

    # Tool definitions for plan step execution
    STEP_TOOLS = [
        {
            "name": "read_file",
            "description": "Read the contents of a file. Use this to understand existing code before making changes.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute file path to read"},
                    "max_lines": {"type": "integer", "description": "Max lines to read (default 200)", "default": 200},
                },
                "required": ["path"],
            },
        },
        {
            "name": "write_file",
            "description": "Write content to a file. Creates parent directories if needed. Use for new files or full rewrites.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute file path to write"},
                    "content": {"type": "string", "description": "Full file content to write"},
                },
                "required": ["path", "content"],
            },
        },
        {
            "name": "edit_file",
            "description": "Replace specific text in a file. Safer than write_file for targeted changes.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute file path to edit"},
                    "old_text": {"type": "string", "description": "Exact text to find and replace"},
                    "new_text": {"type": "string", "description": "Replacement text"},
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
        {
            "name": "glob_files",
            "description": "Find files matching a glob pattern within the project.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern (e.g. '*.py', 'docs/*.md')"},
                    "base_path": {"type": "string", "description": "Base directory (default /home/wyld-core)", "default": "/home/wyld-core"},
                },
                "required": ["pattern"],
            },
        },
        {
            "name": "grep_files",
            "description": "Search for a text pattern across project files.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Search pattern (regex supported)"},
                    "path": {"type": "string", "description": "Directory to search (default /home/wyld-core)", "default": "/home/wyld-core"},
                },
                "required": ["pattern"],
            },
        },
        {
            "name": "run_command",
            "description": "Execute a shell command. Use for git operations, builds, tests, package management, and other CLI tasks. Commands run from the project root directory.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "cwd": {"type": "string", "description": "Working directory (default: project root)"},
                },
                "required": ["command"],
            },
        },
        {
            "name": "list_directory",
            "description": "List files and directories at a given path.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list"},
                },
                "required": ["path"],
            },
        },
    ]

    async def _execute_plan_step(self, step: dict, plan: dict) -> str:
        """
        Execute a single plan step using Claude with file tools.

        Uses a tool-use loop so Claude can:
        1. Explore the codebase (read, glob, grep)
        2. Make actual file changes (write, edit)
        3. Verify its work

        TELOS values are injected into context to guide decisions.
        """
        import json as json_mod

        step_title = step.get("title", "Step")
        step_description = step.get("description", "")
        step_agent = step.get("agent", "code")
        files = step.get("files", [])

        # Get project root from plan
        root_path = plan.get("root_path", "/home/wyld-core")
        project_name = plan.get("project_name", "")
        agent_context = plan.get("agent_context", "")

        # Load TELOS context
        telos = _load_telos_context()

        # Build the execution prompt
        file_context = f"\nRelevant files: {', '.join(files)}" if files else ""
        project_info = f"\n**Project:** {project_name}" if project_name else ""
        custom_context = f"\n\n## Project Instructions\n{agent_context}" if agent_context else ""
        prompt = f"""{telos}

---

## Task Execution

You are executing a plan step.{project_info}

**Plan:** {plan.get('title', '')} - {plan.get('description', '')}
**Step:** {step_title}
**Description:** {step_description}
**Agent Role:** {step_agent}{file_context}{custom_context}

## Instructions

1. Use the tools to explore relevant files first (read_file, glob_files, grep_files)
2. Make the actual changes using write_file or edit_file
3. Verify your changes by reading back the modified files
4. All file paths are under {root_path}

## Values Alignment
- Verify before acting: Read existing files before modifying
- Transparency: Explain what you're changing and why
- Security first: Never write credentials or sensitive data
- Continuous improvement: Store learnings from this step

Execute this step now. Make real file changes, not just descriptions."""

        messages = [{"role": "user", "content": prompt}]
        actions_taken = []
        max_iterations = 12  # Prevent infinite loops

        for iteration in range(max_iterations):
            # Check for task cancellation between iterations
            if self.is_task_cancelled():
                return f"Step cancelled after {iteration} iterations. Actions: {'; '.join(actions_taken)}"

            response = await self._llm.create_message(
                model="auto",
                max_tokens=4096,
                messages=messages,
                tools=self.STEP_TOOLS,
            )

            # Check if LLM wants to use tools
            if response.stop_reason == "tool_use":
                # Process all tool calls in this response
                tool_results = []
                for tool_call in response.tool_calls:
                    tool_name = tool_call.name
                    tool_input = tool_call.arguments

                    # Execute the tool
                    result, is_error = await self._run_step_tool(tool_name, tool_input, root_path)
                    actions_taken.append(f"{tool_name}({tool_input.get('path', tool_input.get('pattern', ''))[:50]})")

                    # Publish action for real-time UI updates
                    action_label = {
                        "read_file": "file_read",
                        "write_file": "file_write",
                        "edit_file": "file_edit",
                        "glob_files": "file_search",
                        "grep_files": "file_search",
                    }.get(tool_name, "executing")

                    short_path = tool_input.get("path", tool_input.get("pattern", ""))
                    if "/" in short_path:
                        short_path = short_path.split("/")[-1]
                    await self.publish_action(action_label, f"{tool_name}: {short_path}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": result[:8000],  # Truncate large results
                        "is_error": is_error,
                    })

                # Add assistant response and tool results to messages
                # Store in normalized dict format
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
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})
            else:
                # LLM is done - extract final text response
                final_text = response.text_content

                # Store learning from this step execution
                if self._memory and actions_taken:
                    try:
                        from ai_memory import Learning, LearningScope, PAIPhase
                        learning = Learning(
                            content=f"Plan step '{step_title}': {final_text[:200]}",
                            phase=PAIPhase.EXECUTE,
                            category="plan_execution",
                            scope=LearningScope.PROJECT,
                            created_by_agent="supervisor",
                            metadata={
                                "plan_title": plan.get("title", ""),
                                "step_title": step_title,
                                "actions": actions_taken[:10],
                                "files_modified": [a.split("(")[1].rstrip(")") for a in actions_taken if "write_file" in a or "edit_file" in a],
                            },
                        )
                        await self._memory.store_learning(learning)
                    except Exception as e:
                        logger.debug("Failed to store step learning", error=str(e))

                return final_text or f"Step completed with {len(actions_taken)} actions"

        return f"Step reached max iterations ({max_iterations}). Actions: {'; '.join(actions_taken)}"

    async def _run_step_tool(self, tool_name: str, tool_input: dict, root_path: str = "/home/wyld-core") -> tuple[str, bool]:
        """
        Execute a tool call from the plan step execution loop.

        Returns:
            Tuple of (result_string, is_error)
        """
        import json as json_mod

        try:
            if tool_name == "read_file":
                result = await _read_file(
                    tool_input["path"],
                    max_lines=tool_input.get("max_lines", 200),
                )
                return (result, False)
            elif tool_name == "write_file":
                result = await _write_file(
                    tool_input["path"],
                    tool_input["content"],
                    allowed_base=root_path,
                )
                return (result, False)
            elif tool_name == "edit_file":
                result = await _edit_file(
                    tool_input["path"],
                    tool_input["old_text"],
                    tool_input["new_text"],
                    allowed_base=root_path,
                )
                return (result, False)
            elif tool_name == "glob_files":
                results = await _glob_files(
                    tool_input["pattern"],
                    base_path=tool_input.get("base_path", root_path),
                    max_results=20,
                )
                return (json_mod.dumps(results, indent=2), False)
            elif tool_name == "grep_files":
                results = await _grep_content(
                    tool_input["pattern"],
                    path=tool_input.get("path", root_path),
                    max_results=15,
                )
                return (json_mod.dumps(results, indent=2), False)
            elif tool_name == "run_command":
                result = await _run_command(
                    tool_input["command"],
                    cwd=tool_input.get("cwd", root_path),
                    timeout=120,
                )
                return (result, False)
            elif tool_name == "list_directory":
                result = await _list_directory(tool_input["path"])
                return (result, False)
            else:
                return (f"Unknown tool: {tool_name}", True)
        except Exception as e:
            return (f"Tool error ({tool_name}): {e}", True)

    async def _handle_modify_plan(self, request: TaskRequest) -> TaskResponse:
        """
        Handle plan modification requests from user chat messages.

        Supports:
        - Adding new steps
        - Skipping steps
        - Modifying step descriptions
        - Reordering steps
        """
        import json
        from datetime import datetime, timezone
        from uuid import uuid4

        plan_id = request.payload.get("plan_id")
        conversation_id = request.payload.get("conversation_id")
        user_id = request.user_id or request.payload.get("user_id")
        user_message = request.payload.get("message", "")
        modification_type = request.payload.get("modification_type")
        modification_data = request.payload.get("modification_data", {})

        # Set state context
        self._state.current_user_id = user_id
        self._state.current_conversation_id = conversation_id

        logger.info(
            "Modifying plan",
            plan_id=plan_id,
            modification_type=modification_type,
            user_message=user_message[:50] if user_message else None,
        )

        try:
            # Load plan from Redis
            plan_key = f"plan:{plan_id}"
            plan_data = await self._redis.get(plan_key)

            if not plan_data:
                return TaskResponse(
                    task_id=request.id,
                    status=TaskStatus.FAILED,
                    error=f"Plan {plan_id} not found",
                    agent_type=self.agent_type,
                )

            plan = json.loads(plan_data)
            steps = plan.get("steps", [])
            original_step_count = len(steps)

            # If no explicit modification type, use Claude to parse intent
            if not modification_type and user_message:
                modification_type, modification_data = await self._parse_modification_intent(
                    user_message, steps, plan
                )

            if not modification_type:
                # Couldn't parse as a modification — let the user know
                if self._pubsub and user_id:
                    await self._pubsub.publish(
                        "agent:responses",
                        {
                            "type": "message",
                            "user_id": user_id,
                            "conversation_id": conversation_id,
                            "content": (
                                "I have a plan ready for your review. You can:\n"
                                "- **Describe changes** you'd like (e.g., \"also add error handling\" or \"use Redis instead\")\n"
                                "- **`/plan approve`** to start execution\n"
                                "- **`/plan reject`** to discard the plan"
                            ),
                            "agent": "wyld",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                return TaskResponse(
                    task_id=request.id,
                    status=TaskStatus.COMPLETED,
                    result={"message": "Not a plan modification, guidance sent"},
                    agent_type=self.agent_type,
                )

            # Apply the modification
            result_message = ""

            if modification_type == "add":
                # Add new step(s)
                new_steps = modification_data.get("steps", [])
                insert_after = modification_data.get("insert_after")  # step index or None for end

                for new_step_data in new_steps:
                    new_step = {
                        "id": str(uuid4()),
                        "order": len(steps) + 1,
                        "title": new_step_data.get("title", "New Step"),
                        "description": new_step_data.get("description", ""),
                        "status": "pending",
                        "agent": new_step_data.get("agent"),
                        "files": new_step_data.get("files", []),
                    }

                    if insert_after is not None and insert_after < len(steps):
                        steps.insert(insert_after + 1, new_step)
                    else:
                        steps.append(new_step)

                # Reorder step numbers
                for i, step in enumerate(steps):
                    step["order"] = i + 1

                result_message = f"Added {len(new_steps)} new step(s) to the plan"
                await self.publish_action("plan_modified", result_message)

            elif modification_type == "skip":
                # Skip specific step(s)
                step_indices = modification_data.get("step_indices", [])
                skipped = 0

                for idx in step_indices:
                    if 0 <= idx < len(steps):
                        if steps[idx]["status"] == "pending":
                            steps[idx]["status"] = "skipped"
                            steps[idx]["completed_at"] = datetime.now(timezone.utc).isoformat()
                            skipped += 1

                result_message = f"Skipped {skipped} step(s)"
                await self.publish_action("plan_modified", result_message)

            elif modification_type == "modify":
                # Modify step description/title
                step_index = modification_data.get("step_index")
                new_title = modification_data.get("title")
                new_description = modification_data.get("description")

                if step_index is not None and 0 <= step_index < len(steps):
                    if new_title:
                        steps[step_index]["title"] = new_title
                    if new_description:
                        steps[step_index]["description"] = new_description

                    result_message = f"Modified step {step_index + 1}: {steps[step_index]['title']}"
                    await self.publish_action("plan_modified", result_message)

            elif modification_type == "reorder":
                # Reorder steps
                new_order = modification_data.get("new_order", [])  # list of step indices

                if new_order and len(new_order) == len(steps):
                    reordered = [steps[i] for i in new_order if 0 <= i < len(steps)]
                    if len(reordered) == len(steps):
                        steps = reordered
                        for i, step in enumerate(steps):
                            step["order"] = i + 1

                        result_message = "Reordered plan steps"
                        await self.publish_action("plan_modified", result_message)

            elif modification_type == "remove":
                # Remove step(s) - only pending ones
                step_indices = sorted(modification_data.get("step_indices", []), reverse=True)
                removed = 0

                for idx in step_indices:
                    if 0 <= idx < len(steps) and steps[idx]["status"] == "pending":
                        steps.pop(idx)
                        removed += 1

                # Reorder step numbers
                for i, step in enumerate(steps):
                    step["order"] = i + 1

                result_message = f"Removed {removed} step(s) from the plan"
                await self.publish_action("plan_modified", result_message)

            elif modification_type == "research_and_update":
                # User asked for something that requires more codebase exploration.
                # Re-explore and regenerate the plan incorporating the new requirement.
                root_path = request.payload.get("root_path", "/home/wyld-core")
                additional_context = modification_data.get("context", user_message)

                # Combine original plan description with new requirement
                original_description = plan.get("description", plan.get("title", ""))
                combined_task = f"{original_description}\n\nAdditional requirement: {additional_context}"

                await self.publish_action("exploring", f"Researching: {additional_context[:60]}...")

                # Do exploration focused on the new requirement
                exploration = await self._explore_for_plan(additional_context, base_path=root_path)

                # Also include context from original exploration if available
                # by reading key files from existing steps
                existing_files = []
                for s in steps:
                    existing_files.extend(s.get("files", []))

                await self.publish_action("planning", "Updating plan with new findings...")

                # Regenerate steps with combined context
                new_steps = await self._generate_plan_from_exploration(
                    combined_task, exploration, base_path=root_path
                )

                if new_steps:
                    steps = [
                        {
                            "id": str(uuid4()),
                            "order": i + 1,
                            "title": s.get("title", f"Step {i + 1}"),
                            "description": s.get("description", ""),
                            "agent": s.get("agent"),
                            "files": s.get("files", []),
                            "status": "pending",
                        }
                        for i, s in enumerate(new_steps)
                    ]

                result_message = f"Plan updated with {len(steps)} steps after researching: {additional_context[:50]}"
                await self.publish_action("plan_modified", result_message)

            # Update plan in Redis
            plan["steps"] = steps
            await self._redis.set(plan_key, json.dumps(plan))

            # Send update to frontend
            if self._pubsub and user_id:
                if modification_type == "research_and_update":
                    # Full plan regeneration — send plan_update with new content
                    await self._pubsub.publish(
                        "agent:responses",
                        {
                            "type": "plan_update",
                            "user_id": user_id,
                            "conversation_id": conversation_id,
                            "plan_id": plan_id,
                            "plan_content": self._format_plan_for_display(plan),
                            "plan_status": "PENDING",
                            "plan": plan,
                            "agent": "wyld",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                else:
                    # Structural change — send step_update
                    await self._pubsub.publish(
                        "agent:responses",
                        {
                            "type": "step_update",
                            "user_id": user_id,
                            "conversation_id": conversation_id,
                            "plan_id": plan_id,
                            "steps": steps,
                            "current_step": plan.get("current_step", 0),
                            "modification": modification_type,
                            "agent": "wyld",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )

                # Also send a chat message about the modification
                await self._pubsub.publish(
                    "agent:responses",
                    {
                        "type": "message",
                        "user_id": user_id,
                        "conversation_id": conversation_id,
                        "content": f"✏️ Plan updated: {result_message}",
                        "agent": "wyld",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            return TaskResponse(
                task_id=request.id,
                status=TaskStatus.COMPLETED,
                result={
                    "plan_id": plan_id,
                    "modification_type": modification_type,
                    "message": result_message,
                    "steps_before": original_step_count,
                    "steps_after": len(steps),
                },
                agent_type=self.agent_type,
            )

        except Exception as e:
            logger.error("Plan modification failed", error=str(e))
            return TaskResponse(
                task_id=request.id,
                status=TaskStatus.FAILED,
                error=str(e),
                agent_type=self.agent_type,
            )
        finally:
            self._state.current_user_id = None
            self._state.current_conversation_id = None

    async def _parse_modification_intent(
        self, user_message: str, steps: list, plan: dict
    ) -> tuple[str | None, dict]:
        """
        Use Claude to parse the user's modification intent from their message.

        Returns (modification_type, modification_data) tuple.
        """
        import json

        # Build step list for context
        step_list = "\n".join([
            f"{i+1}. [{s['status']}] {s['title']}: {s.get('description', '')[:50]}"
            for i, s in enumerate(steps)
        ])

        prompt = f"""Analyze this user message to determine how they want to modify the plan.

Current Plan: {plan.get('title', 'Untitled')}
Current Steps:
{step_list}

User Message: "{user_message}"

Determine the modification type and data. Respond with JSON only:

For NEW FEATURES or requirements that need codebase research (e.g., "also add authentication",
"use PostgreSQL instead", "include API rate limiting", "what about error handling?"):
{{"type": "research_and_update", "data": {{"context": "the user's requirement in clear terms"}}}}

Use "research_and_update" when the user:
- Asks to add substantial new functionality
- Wants to change the technical approach
- Mentions something that requires understanding the codebase
- Asks a question about the plan that implies they want changes
- Requests the plan cover additional areas

For simple step additions (when you know exactly what to add):
{{"type": "add", "data": {{"steps": [{{"title": "...", "description": "...", "agent": "code|qa"}}], "insert_after": null}}}}

For skipping steps:
{{"type": "skip", "data": {{"step_indices": [0, 2]}}}}

For modifying a step's title/description:
{{"type": "modify", "data": {{"step_index": 0, "title": "new title", "description": "new description"}}}}

For reordering (provide new order as indices):
{{"type": "reorder", "data": {{"new_order": [2, 0, 1, 3]}}}}

For removing steps:
{{"type": "remove", "data": {{"step_indices": [1]}}}}

IMPORTANT: Default to "research_and_update" when in doubt. It is better to research
and regenerate than to add a vague step without understanding the codebase.

JSON response:"""

        try:
            response = await self._llm.create_message(
                max_tokens=500,
                tier=ModelTier.FAST,
                messages=[{"role": "user", "content": prompt}],
            )

            text = response.text_content or "{}"

            # Extract JSON from response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(text[start:end])
                return result.get("type"), result.get("data", {})

        except Exception as e:
            logger.error("Failed to parse modification intent", error=str(e))

        return None, {}

    async def _explore_for_plan(self, task_description: str, base_path: str = "/home/wyld-core") -> dict:
        """
        Explore codebase to gather context for planning.

        Uses Claude to determine search strategy, then executes file searches
        and reads key files to build understanding of the codebase.
        """
        import json

        # Ask Claude for search strategy based on the task
        strategy_prompt = f"""Analyze this development task and determine what to search for in the codebase.
Project root: {base_path}

Task: {task_description}

Respond with a JSON object containing search strategies:
{{"file_patterns": ["*.py", "auth*.ts"], "search_terms": ["login", "user"], "key_dirs": ["services", "models"]}}

- file_patterns: glob patterns for relevant files (max 4)
- search_terms: keywords to search for in code (max 3)
- key_dirs: directories likely to contain relevant code

Key project directories: services/, packages/, agents/, config/, docs/, database/, web/, pai/

Only output the JSON object, no other text."""

        try:
            response = await self._llm.create_message(
                max_tokens=500,
                tier=ModelTier.FAST,
                messages=[{"role": "user", "content": strategy_prompt}],
            )

            # Record API usage for cost tracking
            from ai_core import get_cost_tracker
            asyncio.create_task(
                get_cost_tracker().record_usage(
                    model=response.model or self.config.model,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    cached_tokens=response.cached_tokens,
                    agent_type=self.agent_type,
                    agent_name="wyld",
                    user_id=self._state.current_user_id,
                    project_id=self._state.current_project_id,
                )
            )

            text = response.text_content or "{}"
            # Extract JSON from response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                strategy = json.loads(text[start:end])
            else:
                strategy = {}
        except Exception as e:
            logger.debug("Failed to get search strategy", error=str(e))
            # Fallback: extract keywords from task description
            words = task_description.lower().split()
            keywords = [w for w in words if len(w) > 3 and w not in ["with", "that", "this", "from", "have"]][:2]
            strategy = {
                "file_patterns": ["*.py", "*.ts"],
                "search_terms": keywords or ["main"],
            }

        exploration: dict[str, list[Any]] = {"files": [], "patterns": [], "content": []}

        # Find files matching patterns
        for pattern in strategy.get("file_patterns", [])[:4]:
            await self.publish_action("file_search", f"Searching: {pattern}")
            files = await _glob_files(pattern, base_path=base_path, max_results=15)
            exploration["files"].extend(files[:10])

        # Search for patterns in code
        for term in strategy.get("search_terms", [])[:3]:
            await self.publish_action("file_search", f"Searching for: {term}")
            matches = await _grep_content(term, path=base_path, max_results=10)
            exploration["patterns"].extend(matches[:8])

        # Read key files discovered
        seen_paths = set()
        files_to_read = exploration["files"][:4]
        for f in files_to_read:
            path = f.get("path", "")
            if path and path not in seen_paths:
                seen_paths.add(path)
                file_name = Path(path).name
                await self.publish_action("file_read", f"Reading: {file_name}")
                content = await _read_file(path, max_lines=60)
                exploration["content"].append({
                    "path": path,
                    "content": content[:2000]
                })

        logger.info(
            "Exploration complete",
            files_found=len(exploration["files"]),
            patterns_found=len(exploration["patterns"]),
            files_read=len(exploration["content"]),
        )

        return exploration

    async def _generate_plan_from_exploration(self, task: str, exploration: dict, base_path: str = "/home/wyld-core") -> list[dict]:
        """
        Generate plan steps from exploration results.

        Uses Claude to create intelligent, context-aware plan steps
        based on actual files and patterns found in the codebase.
        """
        import json

        # Format exploration results for the prompt
        files_summary = "\n".join([
            f"- {f.get('relative', f.get('path', 'unknown'))}"
            for f in exploration.get("files", [])[:12]
        ]) or "No files found"

        patterns_summary = "\n".join([
            f"- {Path(p.get('file', '')).name}:{p.get('line', '?')}: {p.get('content', '')[:60]}..."
            for p in exploration.get("patterns", [])[:8]
        ]) or "No patterns found"

        content_summary = "\n\n".join([
            f"### {Path(c['path']).name}\n```\n{c['content'][:800]}\n```"
            for c in exploration.get("content", [])[:2]
        ]) or "No file contents available"

        # Load TELOS for value-aligned planning
        telos = _load_telos_context()

        prompt = f"""Create an ACTIONABLE implementation plan. Research is ALREADY DONE — the exploration results below show what exists in the codebase.

{telos}

---

## Task
{task}

## Codebase Root
{base_path}

## Files Already Found
{files_summary}

## Code Patterns Already Found
{patterns_summary}

## File Contents Already Read
{content_summary}

## CRITICAL RULES

The exploration above IS the research phase. Do NOT create steps that say "investigate", "research", "identify", or "determine". Those are already done.

Every step must be a CONCRETE ACTION that modifies or creates a file. Each step will be executed by an agent with read/write file tools.

Respond with a JSON array only:
[{{"title": "Action verb + what", "description": "Specific file changes: what to write/modify and where", "agent": "code|infra|qa", "files": ["{base_path}/path/to/file"]}}]

Rules:
- NEVER use agent type "research" — research is already complete
- Every step MUST specify which files to create or modify with full paths starting with {base_path}
- Titles must start with action verbs: "Create", "Add", "Update", "Configure", "Modify", "Write"
- Descriptions must say exactly WHAT content to write or change, not what to "look for"
- Use "code" for source code changes, "infra" for config/deployment, "qa" for tests
- Include a final "Verify changes" step (agent: "qa")
- 3-6 steps maximum
- Only output the JSON array, no other text."""

        try:
            response = await self._llm.create_message(
                max_tokens=1500,
                tier=ModelTier.BALANCED,
                messages=[{"role": "user", "content": prompt}],
            )

            # Record API usage for cost tracking
            from ai_core import get_cost_tracker
            asyncio.create_task(
                get_cost_tracker().record_usage(
                    model=response.model or self.config.model,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    cached_tokens=response.cached_tokens,
                    agent_type=self.agent_type,
                    agent_name="wyld",
                    user_id=self._state.current_user_id,
                    project_id=self._state.current_project_id,
                )
            )

            text = response.text_content or "[]"
            # Extract JSON array from response
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                steps = json.loads(text[start:end])
                return steps
            else:
                raise ValueError("No JSON array found in response")

        except Exception as e:
            logger.warning("Failed to generate plan from exploration", error=str(e))
            # Return fallback actionable steps based on exploration
            found_files = [f.get("path", "") for f in exploration.get("files", [])[:5] if f.get("path")]
            return [
                {
                    "title": f"Read and understand relevant files",
                    "description": f"Read files found during exploration to understand current state before making changes",
                    "agent": "code",
                    "files": found_files[:3],
                },
                {
                    "title": f"Implement: {task[:40]}",
                    "description": f"Make the required modifications to implement the task",
                    "agent": "code",
                    "files": found_files,
                },
                {
                    "title": "Verify changes are correct",
                    "description": "Read back modified files and confirm changes are accurate",
                    "agent": "qa",
                    "files": found_files[:3],
                },
            ]

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
    # Use localhost for host-based supervisor (not running in Docker)
    # The .env uses POSTGRES_HOST=postgres for Docker, but we need localhost
    db_url = settings.database.url_with_password.replace(
        f"@{settings.database.host}:",
        "@localhost:"
    )
    logger.info("Database URL configured for host access", host="localhost")
    db_engine = create_async_engine(
        db_url,
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
    # Override host to localhost for host-based supervisor
    from ai_core import RedisSettings
    redis_settings = RedisSettings(
        host="localhost",
        port=settings.redis.port,
        password=settings.redis.password,
        db=settings.redis.db,
        max_connections=settings.redis.max_connections,
    )
    redis_client = RedisClient(redis_settings)
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
