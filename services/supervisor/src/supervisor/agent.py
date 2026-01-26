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
        # Strip leading **/ prefix properly (not char-by-char)
        search_pattern = pattern
        if search_pattern.startswith("**/"):
            search_pattern = search_pattern[3:]

        for path in base.rglob(search_pattern):
            if len(results) >= max_results:
                break
            # Skip hidden directories and common excludes
            if path.is_file() and not any(p.startswith(".") for p in path.parts):
                if not any(excl in str(path) for excl in ["node_modules", "__pycache__", ".git", "venv", ".venv"]):
                    try:
                        size = path.stat().st_size
                    except Exception:
                        size = 0
                    results.append({
                        "path": str(path),
                        "name": path.name,
                        "relative": str(path.relative_to(base)),
                        "size": size,
                    })
    except Exception as e:
        logger.debug("Glob search error", pattern=pattern, error=str(e))
    return results


async def _grep_content(
    pattern: str,
    path: str = "/home/wyld-core",
    max_results: int = 30,
    file_type: str | None = None,
    context_lines: int = 1,
) -> list[dict[str, Any]]:
    """Search for pattern in files with context lines."""
    base = Path(path)
    results: list[dict[str, Any]] = []
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error:
        # If pattern is invalid regex, treat it as literal search
        regex = re.compile(re.escape(pattern), re.IGNORECASE)

    all_extensions = [
        ".py", ".ts", ".tsx", ".js", ".jsx",
        ".yaml", ".yml", ".json", ".toml",
        ".md", ".txt", ".rst",
        ".php", ".html", ".twig",
        ".css", ".scss", ".less",
        ".sh", ".bash",
        ".sql",
        ".cfg", ".ini", ".conf",
        ".env.example", ".dockerfile",
    ]

    # Filter to specific file type if requested
    if file_type:
        type_map = {
            "python": [".py"],
            "py": [".py"],
            "typescript": [".ts", ".tsx"],
            "ts": [".ts", ".tsx"],
            "javascript": [".js", ".jsx"],
            "js": [".js", ".jsx"],
            "php": [".php"],
            "yaml": [".yaml", ".yml"],
            "json": [".json"],
            "css": [".css", ".scss", ".less"],
            "html": [".html", ".twig"],
            "shell": [".sh", ".bash"],
            "sql": [".sql"],
            "config": [".cfg", ".ini", ".conf", ".toml"],
            "markdown": [".md"],
        }
        extensions = type_map.get(file_type.lower(), [f".{file_type}"])
    else:
        extensions = all_extensions

    excludes = ["node_modules", "__pycache__", ".git", "venv", ".venv", "dist", "build"]

    for ext in extensions:
        if len(results) >= max_results:
            break
        for file_path in base.rglob(f"*{ext}"):
            if len(results) >= max_results:
                break
            if any(excl in str(file_path) for excl in excludes):
                continue
            try:
                async with aiofiles.open(file_path, "r", errors="ignore") as f:
                    content = await f.read()
                    lines = content.split("\n")
                    for i, line in enumerate(lines):
                        if regex.search(line):
                            # Gather context lines
                            start = max(0, i - context_lines)
                            end = min(len(lines), i + context_lines + 1)
                            context = "\n".join(
                                f"{'>' if j == i else ' '} {j+1}: {lines[j][:150]}"
                                for j in range(start, end)
                            )
                            results.append({
                                "file": str(file_path),
                                "relative": str(file_path.relative_to(base)) if str(file_path).startswith(str(base)) else str(file_path),
                                "line": i + 1,
                                "content": line.strip()[:200],
                                "context": context,
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

    # Safety: prevent writing to the base directory itself or existing directories
    resolved = Path(path).resolve()
    if resolved.is_dir() or str(resolved) == str(Path(allowed_base).resolve()):
        return f"Error: '{path}' is a directory, not a file. Write to a file path inside it."

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

        # Set web-appropriate permissions for files in web-served directories
        web_dirs = ["/home/wyld-web/", "/var/www/"]
        if any(path.startswith(d) for d in web_dirs):
            import os
            os.chmod(path, 0o644)
            try:
                import shutil
                shutil.chown(path, user="www-data", group="www-data")
            except Exception:
                pass  # May fail in Docker, permissions are still readable

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
    """Load TELOS mission, values, and server baseline for agent context."""
    telos_dir = Path("/home/wyld-core/pai/TELOS")
    context_parts = []

    for filename in ["mission.md", "values.md", "server_baseline.md"]:
        filepath = telos_dir / filename
        if filepath.exists():
            try:
                content = filepath.read_text()
                context_parts.append(content.strip())
            except Exception:
                pass

    if context_parts:
        return "## TELOS Framework (Mission, Values & Server Context)\n\n" + "\n\n---\n\n".join(context_parts)
    return ""


SUPERVISOR_SYSTEM_PROMPT = """You are Wyld, the Supervisor agent for Wyld Fyre AI Infrastructure.

Your primary role is to be the user's conversational AI assistant. You should:
1. Respond directly to conversational messages, questions, and general requests
2. Delegate to specialized agents when there's a specific technical task OR when you need to verify facts
3. Be helpful, friendly, and informative
4. Record important learnings to your PAI memory system for future reference
5. ALWAYS search your memory for relevant learnings before answering infrastructure questions

CRITICAL: NEVER make assumptions about the system architecture or infrastructure. If you're unsure:
1. First, use `search_memory` to check if you've learned about this before
2. If no relevant learnings, delegate to INFRA to check the actual state
3. Only state facts that you have verified or that the user has confirmed

The user (Wyld) is an experienced developer. Don't assume you know their infrastructure better than they do.

## Memory System (PAI)
You have access to a persistent memory system powered by Qdrant vector search.
Store important learnings and retrieve them later via semantic similarity search.

Use these memory tools:
- `store_memory`: Save a learning/insight to the vector store. Include category, tags, and appropriate scope (GLOBAL/PROJECT/DOMAIN).
- `search_memory`: Find relevant past learnings by semantic similarity search. Use project_id/domain_id to scope results.
- `list_memory_collections`: List available memory collections.
- `get_memory_stats`: Get statistics about stored memories.

IMPORTANT: When you or your agents discover something important about the system, infrastructure, or user preferences, use `store_memory` to remember it! Always search with `search_memory` before answering infrastructure questions.

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
11. If you're wrong about something, acknowledge it immediately and store the correct information using store_memory.

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
        """Get the supervisor's system prompt, with project context if available."""
        base_prompt = SUPERVISOR_SYSTEM_PROMPT

        # Append project context if we're handling a project-scoped task
        project_ctx = getattr(self, "_current_project_context", None)
        if project_ctx:
            project_section = "\n\n## CURRENT PROJECT CONTEXT\n"
            project_section += "You are currently working within a specific project. Use this context for all responses:\n"
            if project_ctx.get("project_name"):
                project_section += f"- Project Name: {project_ctx['project_name']}\n"
            if project_ctx.get("root_path"):
                project_section += f"- Project Root Path: {project_ctx['root_path']}\n"
            if project_ctx.get("domain"):
                project_section += f"- Domain: {project_ctx['domain']}\n"
            if project_ctx.get("agent_context"):
                project_section += f"- Additional Context: {project_ctx['agent_context']}\n"
            project_section += "\nWhen the user refers to 'the site', 'the project', or asks you to edit/fix something, "
            project_section += "use the root_path above as the working directory. Do NOT ask which site or project they mean."
            base_prompt += project_section

        return base_prompt

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

    async def _record_and_emit_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        cost: float | None = None,
    ) -> None:
        """
        Record API usage to database AND emit WebSocket event for real-time display.

        This ensures the frontend usage meter updates in real-time.
        """
        from ai_core import get_cost_tracker
        from ai_core.pricing import calculate_cost

        # Calculate cost if not provided
        if cost is None:
            usage_cost = calculate_cost(
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
            )
            cost = float(usage_cost.total_cost)

        # Record to database (async, non-blocking)
        asyncio.create_task(
            get_cost_tracker().record_usage(
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                agent_type=self.agent_type,
                agent_name="wyld",
                user_id=self._state.current_user_id,
                project_id=self._state.current_project_id,
            )
        )

        # Emit WebSocket event for real-time frontend update
        logger.debug(
            "Usage event emission check",
            user_id=self._state.current_user_id,
            conversation_id=self._state.current_conversation_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        )
        if self._state.current_user_id:
            await self._pubsub.publish(
                "agent:responses",
                {
                    "type": "usage_update",
                    "user_id": self._state.current_user_id,
                    "conversation_id": self._state.current_conversation_id,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cached_tokens": cached_tokens,
                    "cost": cost,
                    "model": model,
                },
            )
            logger.info(
                "Usage update event emitted",
                user_id=self._state.current_user_id,
                input_tokens=input_tokens,
                cost=cost,
            )
        else:
            logger.warning(
                "Cannot emit usage event - no user_id in state",
                input_tokens=input_tokens,
                cost=cost,
            )

    async def _recall_relevant_memories(
        self,
        task_description: str,
        project_id: str | None = None,
        domain_id: str | None = None,
        categories: list[str] | None = None,
        limit: int = 8,
    ) -> str:
        """
        Search PAI memory for relevant past learnings to inform current work.

        Searches across multiple dimensions:
        - Task similarity (semantic search on description)
        - Project-scoped learnings (architecture, conventions)
        - Domain-scoped learnings (site preferences, configs)
        - Global best practices

        Returns formatted context string for injection into prompts.
        """
        if not self._memory:
            return ""

        all_learnings: list[dict] = []

        try:
            # Search 1: Direct task relevance
            task_results = await self._memory.search_learnings(
                query=task_description,
                limit=limit,
                agent_type="supervisor",
                permission_level=4,
                project_id=project_id,
                domain_id=domain_id,
            )
            all_learnings.extend(task_results)

            # Search 2: Category-specific learnings if provided
            if categories:
                for cat in categories[:3]:
                    cat_results = await self._memory.search_learnings(
                        query=task_description,
                        category=cat,
                        limit=3,
                        agent_type="supervisor",
                        permission_level=4,
                        project_id=project_id,
                        domain_id=domain_id,
                    )
                    for r in cat_results:
                        if r not in all_learnings:
                            all_learnings.append(r)

            # Search 3: Error/failure learnings to avoid repeating mistakes
            error_results = await self._memory.search_learnings(
                query=f"error problem issue {task_description}",
                category="error_pattern",
                limit=3,
                agent_type="supervisor",
                permission_level=4,
                project_id=project_id,
                domain_id=domain_id,
            )
            for r in error_results:
                if r not in all_learnings:
                    all_learnings.append(r)

        except Exception as e:
            logger.warning("Memory recall failed", error=str(e))
            return ""

        if not all_learnings:
            return ""

        # Deduplicate by content similarity (exact match on first 100 chars)
        seen_content: set[str] = set()
        unique_learnings: list[dict] = []
        for learning in all_learnings:
            content_key = learning.get("content", "")[:100]
            if content_key not in seen_content:
                seen_content.add(content_key)
                unique_learnings.append(learning)

        # Format for prompt injection
        memory_parts: list[str] = []
        for i, learning in enumerate(unique_learnings[:limit], 1):
            content = learning.get("content", "")
            scope = learning.get("scope", "global")
            category = learning.get("category", "general")
            confidence = learning.get("confidence", 0.8)

            # Truncate long learnings
            if len(content) > 300:
                content = content[:300] + "..."

            scope_label = f"[{scope.upper()}]" if scope != "global" else ""
            conf_label = "★" if confidence >= 0.9 else ""
            memory_parts.append(f"{i}. {scope_label}{conf_label} ({category}) {content}")

        return "\n\n## Past Learnings (from PAI Memory)\n" + "\n".join(memory_parts) + "\n\nApply these learnings to improve your work. Avoid past mistakes. Build on what worked before."

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

            # Auto-inject project context into delegated payload
            task_payload = payload or {}
            project_ctx = getattr(supervisor, "_current_project_context", None)
            if project_ctx:
                # Only inject if not already set by the LLM
                if "root_path" not in task_payload and project_ctx.get("root_path"):
                    task_payload["root_path"] = project_ctx["root_path"]
                if "project_name" not in task_payload and project_ctx.get("project_name"):
                    task_payload["project_name"] = project_ctx["project_name"]
                if "domain" not in task_payload and project_ctx.get("domain"):
                    task_payload["domain"] = project_ctx["domain"]

            # Create task request
            request = TaskRequest(
                task_type=task_type,
                payload=task_payload,
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

        # Handle host command execution (delegated from API container)
        if request.task_type == "host_command":
            return await self._handle_host_command(request)

        # Inject project context for project-scoped tasks
        self._current_project_context = None
        payload = request.payload or {}
        if payload.get("root_path") or payload.get("project_name"):
            self._current_project_context = {
                "project_name": payload.get("project_name"),
                "root_path": payload.get("root_path"),
                "domain": payload.get("domain"),
                "agent_context": payload.get("agent_context"),
            }

        try:
            # Use default processing (system prompt now includes project context)
            response = await super().process_task(request)

            # Auto-generate conversation title after first chat message
            if request.task_type == "chat" and response.status == TaskStatus.COMPLETED:
                conversation_id = payload.get("conversation_id")
                if conversation_id:
                    await self._maybe_generate_title(request, conversation_id)

            return response
        finally:
            # Clear project context after task completes
            self._current_project_context = None

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

            # ========== MEMORY RECALL PHASE ==========
            past_learnings = ""
            if self._memory:
                await self.publish_action("recalling", "Checking past learnings...")
                past_learnings = await self._recall_relevant_memories(
                    task_description=description,
                    project_id=project_id,
                    domain_id=project_name,  # Use project name as domain_id for site projects
                    categories=["plan_creation", "plan_completion", "error_pattern", "file_pattern"],
                )
                if past_learnings:
                    logger.info("Retrieved past learnings for plan", learnings_length=len(past_learnings))

            # ========== PLAN PHASE ==========
            await self.publish_action("planning", "Creating implementation plan...")
            steps = await self._generate_plan_from_exploration(
                description, exploration, base_path=root_path, past_learnings=past_learnings
            )

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
                        "todos": s.get("todos", []),
                        "changes": s.get("changes", []),
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
                    # Send structured steps so frontend can render interactive step UI
                    await self._pubsub.publish(
                        "agent:responses",
                        {
                            "type": "step_update",
                            "user_id": user_id,
                            "conversation_id": conversation_id,
                            "plan_id": plan_id,
                            "steps": plan["steps"],
                            "current_step": 0,
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

            # Guard: wait for plan creation to finish if still in progress
            plan_status = plan.get("status", "")
            if plan_status in ("exploring", "drafting"):
                # Plan is still being created - wait up to 60s for it to finish
                logger.info("Plan still being created, waiting...", plan_id=plan_id, status=plan_status)
                for _wait in range(12):  # 12 x 5s = 60s max
                    await asyncio.sleep(5)
                    plan_data = await self._redis.get(plan_key)
                    if not plan_data:
                        break
                    plan = json.loads(plan_data)
                    plan_status = plan.get("status", "")
                    if plan_status not in ("exploring", "drafting"):
                        logger.info("Plan creation finished", plan_id=plan_id, status=plan_status)
                        break
                else:
                    return TaskResponse(
                        task_id=request.id,
                        status=TaskStatus.FAILED,
                        error="Plan creation timed out - still in progress after 60s",
                        agent_type=self.agent_type,
                    )

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

            # Execute each step with step-level scoring (Improvement 2)
            cancelled = False
            step_scores: list[float] = []  # Track scores for course correction
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

                # ========== Improvement 2: Step-Level Scoring ==========
                step_score = await self._score_step_execution(
                    step=step,
                    result={
                        "completed": step.get("status") == "completed",
                        "error": step.get("error"),
                        "files_modified": [],  # Could extract from step_result
                    },
                )
                step_scores.append(step_score)
                step["score"] = step_score
                logger.debug(f"Step {i+1} scored: {step_score:.2f}")

                # Check for course correction on remaining steps
                remaining_steps = steps[i + 1:]
                if remaining_steps and step_score < 0.5:
                    replanned_steps, did_replan = await self._maybe_course_correct(
                        step_scores, remaining_steps, plan
                    )
                    if did_replan:
                        # Replace remaining steps with replanned versions
                        steps[i + 1:] = replanned_steps
                        plan["steps"] = steps
                        logger.info(f"Course corrected: replaced {len(remaining_steps)} steps with {len(replanned_steps)}")

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

            # ========== PAI PLAN COMPLETION FEEDBACK ==========
            if self._memory:
                try:
                    from ai_memory import Learning, LearningScope, PAIPhase

                    plan_title = plan.get("title", plan.get("description", "Untitled plan"))

                    # Calculate plan quality score
                    success_rate = completed_steps / max(len(steps), 1)
                    plan_confidence = max(0.5, min(0.95, success_rate))

                    step_summaries = []
                    failed_steps = []
                    for s in steps:
                        status = s.get("status", "pending")
                        title = s.get("title", "Step")
                        if status == "completed":
                            step_summaries.append(f"✓ {title}")
                        else:
                            step_summaries.append(f"✗ {title}")
                            failed_steps.append(title)

                    # Store plan outcome with quality grading
                    feedback_type = "full_success" if success_rate == 1.0 else "partial_success" if success_rate > 0.5 else "mostly_failed"
                    learning_content = (
                        f"Plan '{plan_title}' completed ({feedback_type}). "
                        f"{completed_steps}/{len(steps)} steps succeeded. "
                        f"Steps: {', '.join(step_summaries)}"
                    )
                    if failed_steps:
                        learning_content += f" Failed: {', '.join(failed_steps)}."

                    learning = Learning(
                        content=learning_content,
                        phase=PAIPhase.LEARN,
                        category="plan_completion",
                        scope=LearningScope.PROJECT,
                        created_by_agent="supervisor",
                        confidence=plan_confidence,
                        project_id=self._state.current_project_id,
                        domain_id=plan.get("project_name") or None,
                        metadata={
                            "plan_id": plan_id,
                            "plan_title": plan_title,
                            "steps_completed": completed_steps,
                            "steps_total": len(steps),
                            "success_rate": success_rate,
                            "feedback_type": feedback_type,
                            "failed_steps": failed_steps,
                            "conversation_id": conversation_id,
                            "completed_at": plan["completed_at"],
                        },
                    )
                    await self._memory.store_learning(learning)

                    # If plan had failures, store error pattern for future avoidance
                    if failed_steps:
                        error_learning = Learning(
                            content=(
                                f"Plan '{plan_title}' had {len(failed_steps)} failed steps: {', '.join(failed_steps)}. "
                                f"Consider breaking these into smaller sub-tasks or providing more specific file instructions."
                            ),
                            phase=PAIPhase.LEARN,
                            category="error_pattern",
                            scope=LearningScope.PROJECT,
                            created_by_agent="supervisor",
                            confidence=0.85,
                            project_id=self._state.current_project_id,
                            domain_id=plan.get("project_name") or None,
                            metadata={
                                "plan_id": plan_id,
                                "failed_steps": failed_steps,
                                "feedback_type": "plan_failure_pattern",
                            },
                        )
                        await self._memory.store_learning(error_learning)

                    logger.info("Plan feedback stored in memory", plan_id=plan_id, confidence=plan_confidence)

                    # ========== Improvement 1: Outcome Feedback Loop ==========
                    # Capture execution outcome and update related learnings
                    await self._capture_execution_outcome(
                        plan_id=plan_id,
                        steps=steps,
                        result={
                            "success": success_rate >= 0.8,
                            "summary": plan_title,
                            "duration_ms": None,  # Could track actual duration
                        },
                    )

                except Exception as mem_err:
                    logger.warning("Failed to store plan feedback in memory", error=str(mem_err))

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
            "description": "Read a file's contents. Only use this for files NOT already shown in the pre-loaded context above. Returns file content with line numbers.",
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
            "description": "Create a new file or completely overwrite an existing file. Creates parent directories automatically. Use this for NEW files. For modifying existing files, prefer edit_file instead.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute file path to write"},
                    "content": {"type": "string", "description": "Complete file content to write"},
                },
                "required": ["path", "content"],
            },
        },
        {
            "name": "edit_file",
            "description": "Find and replace specific text in an existing file. The old_text must match EXACTLY (including whitespace/indentation). Use this for targeted modifications to existing files.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute file path to edit"},
                    "old_text": {"type": "string", "description": "Exact text to find (must match file content precisely, including indentation)"},
                    "new_text": {"type": "string", "description": "Replacement text"},
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
        {
            "name": "glob_files",
            "description": "Find files by name pattern. Returns file paths with sizes. Use patterns like '*.py' (all Python files), 'routes/*.ts' (TypeScript in routes/), 'auth*' (files starting with auth).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern (e.g. '*.py', 'routes/*.ts', 'auth*')"},
                    "base_path": {"type": "string", "description": "Base directory to search from (default: project root)"},
                },
                "required": ["pattern"],
            },
        },
        {
            "name": "grep_files",
            "description": "Search for text/regex pattern in file contents. Returns matching lines with surrounding context. Searches Python, TypeScript, PHP, YAML, JSON, HTML, CSS, SQL, shell, and config files. Use file_type to narrow search.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Search pattern (regex supported, case-insensitive). Examples: 'class Auth', 'def handle_', 'import.*redis'"},
                    "path": {"type": "string", "description": "Directory to search in (default: project root)"},
                    "file_type": {"type": "string", "description": "Limit search to file type: python, typescript, javascript, php, yaml, json, css, html, shell, sql, config, markdown"},
                },
                "required": ["pattern"],
            },
        },
        {
            "name": "run_command",
            "description": "Execute a shell command. Use for: git operations, running tests, builds, package management, linting, type checking. Commands run from the project root. Timeout: 120s.",
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
            "description": "List files and subdirectories at a path. Shows directories (📁) and files (📄) sorted with dirs first. Use to understand project structure.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute directory path to list"},
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

        Includes nudge mechanism to prevent endless searching without writing.
        Pre-loads file contents when files are specified in the step.
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

        # Pre-load file contents for files specified in the step
        preloaded_context = ""
        if files:
            preloaded_parts = []
            for file_path in files[:5]:  # Max 5 files pre-loaded
                try:
                    if Path(file_path).exists():
                        content = await _read_file(file_path, max_lines=200)
                        if content:
                            preloaded_parts.append(f"### {Path(file_path).name}\n**Path:** `{file_path}`\n```\n{content[:3000]}\n```")
                            await self.publish_action("file_read", f"Pre-loading: {Path(file_path).name}")
                except Exception:
                    pass
            if preloaded_parts:
                preloaded_context = "\n\n## Current File Contents (already loaded for you):\n\n" + "\n\n".join(preloaded_parts)

        # ========== PAI MEMORY PRE-LOAD ==========
        # Search for relevant past learnings to inject into the step context
        memory_context = ""
        if self._memory:
            try:
                # Set context for store_insight tool handler
                self._current_plan_title = plan.get("title", "")
                self._current_domain_id = project_name or None

                # Search for learnings relevant to this specific step
                step_query = f"{step_title} {step_description} {plan.get('title', '')}"
                memory_results = await self._memory.search_learnings(
                    query=step_query,
                    limit=5,
                    agent_type="supervisor",
                    permission_level=4,
                    project_id=self._state.current_project_id,
                    domain_id=project_name or None,
                )

                if memory_results:
                    memory_parts = []
                    for r in memory_results:
                        content = r.get("content", "")[:200]
                        scope = r.get("scope", "global")
                        cat = r.get("category", "general")
                        confidence = r.get("confidence", 0.8)
                        marker = "★" if confidence >= 0.9 else "•"
                        memory_parts.append(f"{marker} [{scope}/{cat}] {content}")

                    memory_context = "\n\n## Past Learnings (Apply these to your work)\n" + "\n".join(memory_parts)
                    logger.info("Injected memory context into step", step=step_title, learnings=len(memory_results))
            except Exception as e:
                logger.debug("Memory pre-load failed for step", error=str(e))

        # Detect if this is a frontend/web task and inject design context
        all_text = f"{step_title} {step_description} {plan.get('title', '')} {plan.get('description', '')}".lower()
        all_files = " ".join(files).lower()
        is_frontend_task = (
            any(kw in all_text for kw in ["website", "bootstrap", "frontend", "html", "css", "redesign", "landing page", "web page", "responsive", "navbar", "hero"]) or
            any(ext in all_files for ext in [".html", ".css", ".scss", ".js"])
        )

        frontend_context = ""
        if is_frontend_task:
            frontend_context = """

## Frontend Design Standards (FOLLOW THESE)

### Bootstrap 5 Integration
- Use Bootstrap 5 via CDN in the `<head>`:
  ```
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js" defer></script>
  ```
- Use Bootstrap's grid system: `container`, `row`, `col-*` classes
- Use Bootstrap components: `navbar`, `card`, `btn`, `form-control`, etc.
- Use utility classes: `mt-4`, `py-3`, `text-center`, `d-flex`, etc.

### HTML Quality
- Use semantic elements: `<header>`, `<nav>`, `<main>`, `<section>`, `<article>`, `<footer>`
- Every page needs: proper `<!DOCTYPE html>`, `<meta charset="utf-8">`, `<meta name="viewport" ...>`
- Logical heading hierarchy: h1 → h2 → h3 (one h1 per page)
- All images need `alt` attributes; decorative images use `alt=""`
- Links should have descriptive text (not "click here")

### Modern CSS Patterns
- Use CSS custom properties for theming: `:root { --primary: #6366f1; }`
- Mobile-first responsive design with min-width media queries
- Smooth transitions: `transition: all 0.2s ease-out;`
- Card hover effects: `transform: translateY(-4px); box-shadow: 0 12px 24px rgba(0,0,0,0.1);`
- Button hover: subtle scale `transform: scale(1.02);`
- Gradient backgrounds: `background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);`
- Use `clamp()` for fluid typography: `font-size: clamp(1rem, 2.5vw, 2rem);`

### Responsive Design
- Bootstrap breakpoints: sm(576px), md(768px), lg(992px), xl(1200px), xxl(1400px)
- Navigation should collapse to hamburger toggler at mobile widths
- Images use `img-fluid` class for responsive scaling
- Stack columns on mobile, side-by-side on desktop: `col-12 col-md-6 col-lg-4`
- No horizontal scroll on mobile — avoid fixed pixel widths

### Accessibility Essentials
- Color contrast: text should be ≥4.5:1 contrast ratio
- All interactive elements reachable via keyboard (Tab)
- Focus styles visible: `outline: 2px solid var(--primary); outline-offset: 2px;`
- Skip-to-content link for keyboard users
- `aria-label` on icon-only buttons; `aria-current="page"` on active nav items
- Respect `prefers-reduced-motion`: wrap animations in `@media (prefers-reduced-motion: no-preference) { }`

### Quality Patterns
- Hero sections: full-width gradient bg + centered text + CTA button
- Cards: consistent border-radius, subtle shadow, lift on hover
- Forms: proper labels, inline validation, focus ring styling
- Footer: dark background, organized link groups, muted copyright text
- Loading states: skeleton shimmer animations
- Consistent spacing: use Bootstrap's spacing scale (1-5)
- Professional typography: system font stack or Google Fonts (Inter, Poppins)
"""

        # Build the execution prompt
        file_context = f"\nTarget files: {', '.join(files)}" if files else ""
        project_info = f"\n**Project:** {project_name}" if project_name else ""
        custom_context = f"\n\n## Project Instructions\n{agent_context}" if agent_context else ""

        # Include todos as specific sub-tasks
        todos = step.get("todos", [])
        todos_context = ""
        if todos:
            todos_list = "\n".join([f"  {i+1}. {t}" for i, t in enumerate(todos)])
            todos_context = f"\n\n## Specific Tasks (complete ALL of these):\n{todos_list}"

        # Include changes as file action instructions
        changes = step.get("changes", [])
        changes_context = ""
        if changes:
            changes_list = "\n".join([
                f"  - {'CREATE' if c.get('action') == 'create' else 'MODIFY'}: {c.get('file', '')} — {c.get('summary', '')}"
                for c in changes
            ])
            changes_context = f"\n\n## File Changes Required:\n{changes_list}"

        prompt = f"""{telos}

---

## Task Execution

You are executing a plan step.{project_info}

**Plan:** {plan.get('title', '')} - {plan.get('description', '')}
**Step:** {step_title}
**Description:** {step_description}
**Agent Role:** {step_agent}{file_context}{todos_context}{changes_context}{preloaded_context}{memory_context}{custom_context}{frontend_context}

## Instructions

1. The target file contents are pre-loaded above — use them directly, do NOT re-read files already shown
2. Make the specific changes using write_file (for new files) or edit_file (for modifications)
3. Verify your changes by reading back the modified files
4. All file paths are under the directory {root_path}/ (this is a DIRECTORY even if the name contains dots)
5. Do NOT just describe or recommend changes — actually write them to files
6. If a file needs to be CREATED, use write_file with the full content
7. If a file needs to be MODIFIED, use edit_file with old_text and new_text
8. You MUST use write_file or edit_file at least once — searching alone is not acceptable
9. Write COMPLETE, production-quality code — not placeholders or TODOs
10. Use `recall_learning` if you need to remember how something was done before or what patterns to follow
11. Use `store_insight` when you discover something important: a technique that works, a pattern to reuse, or a mistake to avoid

Execute this step now. Make real file changes, not just descriptions."""

        messages = [{"role": "user", "content": prompt}]
        actions_taken = []
        files_modified = []
        max_iterations = 30
        nudge_sent = False

        # Detect if this is a verify/review step (no write nudge needed)
        step_lower = (step_title + " " + step_description).lower()
        is_verify_step = any(kw in step_lower for kw in ["verify", "review", "check", "validate", "test", "inspect"])

        # Build dynamic tools list — add plugin analysis tools for frontend tasks
        step_tools = list(self.STEP_TOOLS)
        if is_frontend_task:
            step_tools.extend([
                {
                    "name": "check_accessibility",
                    "description": "Run accessibility analysis on HTML/CSS code. Returns issues with severity levels and fix suggestions. Use this after writing HTML files to catch a11y problems.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "HTML or component source code to analyze"},
                        },
                        "required": ["code"],
                    },
                },
                {
                    "name": "check_responsive_design",
                    "description": "Review CSS for responsive design quality. Checks breakpoint coverage, mobile-first approach, fluid units, and modern patterns. Use after writing CSS.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "css": {"type": "string", "description": "CSS code to review"},
                        },
                        "required": ["css"],
                    },
                },
                {
                    "name": "get_animation_suggestions",
                    "description": "Get CSS animation/transition suggestions for a component type. Returns ready-to-use CSS snippets.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "component_type": {"type": "string", "description": "Component type: button, card, modal, input, skeleton, navbar, hero"},
                            "interaction": {"type": "string", "description": "Interaction type: hover, click, focus, enter, exit, loading"},
                        },
                        "required": ["component_type"],
                    },
                },
            ])

        # Always add memory tools — PAI should be available in every step
        step_tools.extend([
            {
                "name": "recall_learning",
                "description": "Search PAI memory for relevant past learnings. Use this when you need context about how something was done before, what patterns to follow, or what mistakes to avoid. Returns semantically similar past experiences.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "What to search for in past learnings (e.g., 'bootstrap navbar patterns', 'responsive grid layout', 'form validation approach')"},
                        "category": {"type": "string", "description": "Optional category filter: plan_creation, plan_completion, error_pattern, file_pattern, quality_insight, user_preference"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "store_insight",
                "description": "Store a new learning/insight in PAI memory for future use. Use this when you discover something important: a pattern that works well, a mistake to avoid, a user preference, or a technique that produced good results.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "The learning/insight to remember (be specific and actionable)"},
                        "category": {"type": "string", "description": "Category: file_pattern, quality_insight, error_pattern, technique, user_preference", "enum": ["file_pattern", "quality_insight", "error_pattern", "technique", "user_preference"]},
                        "scope": {"type": "string", "description": "Scope: global (all projects), project (this project only), domain (this site only)", "enum": ["global", "project", "domain"], "default": "project"},
                    },
                    "required": ["content", "category"],
                },
            },
        ])

        # Track frontend files written this step for auto-analysis
        frontend_files_written = []

        for iteration in range(max_iterations):
            # Check for task cancellation between iterations
            if self.is_task_cancelled():
                return f"Step cancelled after {iteration} iterations. Actions: {'; '.join(actions_taken)}"

            # Nudge: if after 8 iterations no write/edit has happened, remind the agent
            # Skip nudge for verify/review steps which are read-only by nature
            if iteration == 8 and not files_modified and not nudge_sent and not is_verify_step:
                nudge_sent = True
                messages.append({"role": "user", "content": [{"type": "text", "text": "REMINDER: You have used 8 iterations without making any file changes. You MUST use write_file or edit_file NOW to make the required changes. Stop searching and start writing. If you cannot find the right files, create them."}]})

            response = await self._llm.create_message(
                max_tokens=8192,
                tier=ModelTier.BALANCED,
                messages=messages,
                tools=step_tools,
            )

            # Check if LLM wants to use tools
            if response.stop_reason == "tool_use":
                # Process all tool calls in this response
                tool_results = []
                for tool_call in response.tool_calls:
                    tool_name = tool_call.name
                    tool_input = tool_call.arguments

                    # Fire pre-tool plugin hook
                    if self._plugin_integration:
                        try:
                            pre_ctx = await self._plugin_integration.trigger_hook(
                                "pre_tool_use",
                                {"tool_name": tool_name, "tool_args": tool_input, "agent_name": "wyld"},
                            )
                            # Check if hook blocked the tool
                            if pre_ctx.get("blocked"):
                                result = f"Tool blocked by plugin: {pre_ctx.get('reason', 'unknown')}"
                                is_error = True
                                tool_results.append({"type": "tool_result", "tool_use_id": tool_call.id, "content": result, "is_error": True})
                                continue
                        except Exception:
                            pass

                    # Execute the tool
                    result, is_error = await self._run_step_tool(tool_name, tool_input, root_path)
                    actions_taken.append(f"{tool_name}({tool_input.get('path', tool_input.get('pattern', ''))[:50]})")

                    # Fire post-tool plugin hook
                    if self._plugin_integration:
                        try:
                            await self._plugin_integration.trigger_hook(
                                "post_tool_use",
                                {"tool_name": tool_name, "tool_args": tool_input, "result": result[:500], "agent_name": "wyld"},
                            )
                        except Exception:
                            pass

                    # Track file modifications
                    if tool_name in ("write_file", "edit_file") and not is_error:
                        modified_path = tool_input.get("path", "")
                        if modified_path and modified_path not in files_modified:
                            files_modified.append(modified_path)
                        # Track frontend files for auto-analysis
                        if is_frontend_task and modified_path:
                            if any(modified_path.endswith(ext) for ext in (".html", ".htm", ".css", ".scss")):
                                frontend_files_written.append(modified_path)

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

                # Auto-run plugin analysis on frontend files that were just written
                quality_feedback = ""
                if is_frontend_task and frontend_files_written:
                    try:
                        from .plugins_bridge import run_accessibility_check, run_responsive_review
                        feedback_parts = []
                        for fpath in frontend_files_written[-2:]:  # Analyze last 2 files max
                            file_content = await _read_file(fpath, max_lines=300)
                            if not file_content:
                                continue
                            fname = Path(fpath).name
                            if fpath.endswith((".html", ".htm")):
                                a11y = run_accessibility_check(file_content)
                                issues = a11y.get("issues", [])
                                critical = [i for i in issues if i.get("severity") in ("critical", "high")]
                                if critical:
                                    issue_list = "; ".join([i.get("message", "") for i in critical[:3]])
                                    feedback_parts.append(f"⚠️ {fname} accessibility: {issue_list}")
                            elif fpath.endswith((".css", ".scss")):
                                resp = run_responsive_review(file_content)
                                findings = resp.get("findings", [])
                                warnings = [f for f in findings if f.get("type") == "warning"]
                                if warnings:
                                    warn_list = "; ".join([f.get("message", "") for f in warnings[:2]])
                                    feedback_parts.append(f"⚠️ {fname} responsive: {warn_list}")
                        if feedback_parts:
                            quality_feedback = "\n\n[QUALITY CHECK] " + " | ".join(feedback_parts) + "\nFix these issues in your next file writes."
                    except Exception:
                        pass  # Don't break execution if analysis fails
                    frontend_files_written.clear()

                # Add assistant response and tool results to messages
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

                # Append quality feedback to tool results if any
                if quality_feedback:
                    tool_results.append({"type": "text", "text": quality_feedback})
                messages.append({"role": "user", "content": tool_results})
            else:
                # LLM is done - extract final text response
                final_text = response.text_content

                # ========== PAI FEEDBACK LOOP ==========
                # Store quality-graded learnings based on execution outcome
                if self._memory:
                    try:
                        from ai_memory import Learning, LearningScope, PAIPhase
                        iterations_used = iteration + 1

                        # === Quality scoring (higher = better execution) ===
                        quality_score = 1.0
                        if not files_modified:
                            quality_score -= 0.3  # No file changes is concerning
                        if iterations_used > 20:
                            quality_score -= 0.2  # Took too many iterations
                        elif iterations_used > 10:
                            quality_score -= 0.1
                        if nudge_sent:
                            quality_score -= 0.1  # Needed a reminder to write

                        # Confidence derived from quality
                        confidence = max(0.5, min(0.95, 0.7 + (quality_score * 0.25)))

                        # === Store execution outcome learning ===
                        if files_modified:
                            # SUCCESS PATTERN: Store what worked
                            file_exts = list(set(Path(f).suffix for f in files_modified))
                            learning = Learning(
                                content=(
                                    f"Successfully executed '{step_title}' for plan '{plan.get('title', '')}'. "
                                    f"Modified {len(files_modified)} files ({', '.join(file_exts)}). "
                                    f"Completed in {iterations_used} iterations. "
                                    f"Approach: {final_text[:150]}"
                                ),
                                phase=PAIPhase.LEARN,
                                category="technique",
                                scope=LearningScope.PROJECT,
                                created_by_agent="supervisor",
                                confidence=confidence,
                                project_id=self._state.current_project_id,
                                domain_id=project_name or None,
                                metadata={
                                    "plan_title": plan.get("title", ""),
                                    "step_title": step_title,
                                    "files_modified": files_modified,
                                    "file_extensions": file_exts,
                                    "iterations_used": iterations_used,
                                    "quality_score": quality_score,
                                    "actions_count": len(actions_taken),
                                    "feedback_type": "success",
                                },
                            )
                            await self._memory.store_learning(learning)

                            # === Store file-level patterns ===
                            for fpath in files_modified[:3]:
                                ext = Path(fpath).suffix
                                fname = Path(fpath).name
                                file_learning = Learning(
                                    content=f"File pattern: {fname} ({ext}) in project '{project_name}'. Part of: {step_title}.",
                                    phase=PAIPhase.LEARN,
                                    category="file_pattern",
                                    scope=LearningScope.PROJECT,
                                    created_by_agent="supervisor",
                                    confidence=confidence,
                                    project_id=self._state.current_project_id,
                                    domain_id=project_name or None,
                                    metadata={"file_path": fpath, "step_title": step_title},
                                )
                                await self._memory.store_learning(file_learning)
                        else:
                            # NO-CHANGE PATTERN: Store as potential issue
                            learning = Learning(
                                content=(
                                    f"Step '{step_title}' completed without file changes. "
                                    f"This may indicate the step was verification-only or encountered issues. "
                                    f"Actions attempted: {'; '.join(actions_taken[-3:])}"
                                ),
                                phase=PAIPhase.LEARN,
                                category="quality_insight",
                                scope=LearningScope.PROJECT,
                                created_by_agent="supervisor",
                                confidence=0.6,
                                project_id=self._state.current_project_id,
                                domain_id=project_name or None,
                                metadata={
                                    "step_title": step_title,
                                    "iterations_used": iterations_used,
                                    "feedback_type": "no_changes",
                                },
                            )
                            await self._memory.store_learning(learning)

                    except Exception as e:
                        logger.debug("Failed to store step feedback", error=str(e))

                # Build informative output
                if files_modified:
                    modified_list = ", ".join([Path(f).name for f in files_modified])
                    return f"{final_text}\n\n✅ Files modified: {modified_list}"
                else:
                    return f"{final_text}\n\n⚠️ No files were modified in this step."

        # Max iterations reached — store as ERROR PATTERN for future avoidance
        if self._memory:
            try:
                from ai_memory import Learning, LearningScope, PAIPhase
                error_learning = Learning(
                    content=(
                        f"ERROR: Step '{step_title}' hit max iterations ({max_iterations}). "
                        f"{'Files modified: ' + ', '.join(Path(f).name for f in files_modified) if files_modified else 'NO files modified'}. "
                        f"Last actions: {'; '.join(actions_taken[-3:])}. "
                        f"Plan: {plan.get('title', '')}. "
                        f"This step may need to be broken into smaller sub-tasks or given more specific instructions."
                    ),
                    phase=PAIPhase.LEARN,
                    category="error_pattern",
                    scope=LearningScope.PROJECT,
                    created_by_agent="supervisor",
                    confidence=0.9,  # High confidence that this was a problem
                    project_id=self._state.current_project_id,
                    domain_id=project_name or None,
                    metadata={
                        "step_title": step_title,
                        "plan_title": plan.get("title", ""),
                        "max_iterations": max_iterations,
                        "files_modified": files_modified,
                        "actions_taken": actions_taken[-5:],
                        "feedback_type": "max_iterations",
                    },
                )
                await self._memory.store_learning(error_learning)
            except Exception:
                pass

        if files_modified:
            modified_list = ", ".join([Path(f).name for f in files_modified])
            return f"Step reached max iterations ({max_iterations}). Files modified: {modified_list}. Actions: {'; '.join(actions_taken[-5:])}"
        return f"Step reached max iterations ({max_iterations}) with NO file changes. Actions: {'; '.join(actions_taken)}"

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
                    file_type=tool_input.get("file_type"),
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
            elif tool_name == "check_accessibility":
                from .plugins_bridge import run_accessibility_check
                result = run_accessibility_check(tool_input["code"])
                return (json_mod.dumps(result, indent=2), False)
            elif tool_name == "check_responsive_design":
                from .plugins_bridge import run_responsive_review
                result = run_responsive_review(tool_input["css"])
                return (json_mod.dumps(result, indent=2), False)
            elif tool_name == "get_animation_suggestions":
                from .plugins_bridge import run_animation_suggestions
                result = run_animation_suggestions(
                    tool_input["component_type"],
                    tool_input.get("interaction"),
                )
                return (json_mod.dumps(result, indent=2), False)
            elif tool_name == "recall_learning":
                # Search PAI memory for relevant past learnings
                if self._memory:
                    results = await self._memory.search_learnings(
                        query=tool_input["query"],
                        category=tool_input.get("category"),
                        limit=5,
                        agent_type="supervisor",
                        permission_level=4,
                        project_id=self._state.current_project_id,
                        domain_id=getattr(self, "_current_domain_id", None),
                    )
                    if results:
                        formatted = []
                        for r in results:
                            content = r.get("content", "")[:250]
                            scope = r.get("scope", "global")
                            cat = r.get("category", "general")
                            conf = r.get("confidence", 0.8)
                            formatted.append(f"[{scope}|{cat}|conf:{conf:.1f}] {content}")
                        return ("\n\n".join(formatted), False)
                    return ("No relevant past learnings found for this query.", False)
                return ("Memory system not available.", False)
            elif tool_name == "store_insight":
                # Store a new learning in PAI memory
                if self._memory:
                    from ai_memory import Learning, LearningScope, PAIPhase
                    scope_map = {"global": LearningScope.GLOBAL, "project": LearningScope.PROJECT, "domain": LearningScope.DOMAIN}
                    learning = Learning(
                        content=tool_input["content"],
                        phase=PAIPhase.LEARN,
                        category=tool_input["category"],
                        scope=scope_map.get(tool_input.get("scope", "project"), LearningScope.PROJECT),
                        created_by_agent="supervisor",
                        confidence=0.85,
                        project_id=self._state.current_project_id,
                        domain_id=getattr(self, "_current_domain_id", None),
                        metadata={"source": "step_execution", "plan_title": getattr(self, "_current_plan_title", "")},
                    )
                    doc_id = await self._memory.store_learning(learning)
                    return (f"Insight stored successfully (id: {doc_id})", False)
                return ("Memory system not available.", False)
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

        # Deduplication: prevent processing the same modification message twice
        # This handles cases where WebSocket reconnection or frontend re-sends cause duplicates
        import hashlib
        dedup_hash = hashlib.md5(f"{plan_id}:{user_message}".encode()).hexdigest()[:16]
        dedup_key = f"plan_modify_dedup:{plan_id}:{dedup_hash}"
        already_processing = await self._redis.set(dedup_key, "1", ex=120, nx=True)
        if not already_processing:
            # Another instance is already processing this exact modification
            logger.warning(
                "Duplicate plan modification detected, skipping",
                plan_id=plan_id,
                user_message=user_message[:50] if user_message else None,
            )
            return TaskResponse(
                task_id=request.id,
                status=TaskStatus.COMPLETED,
                result={"message": "Duplicate modification skipped"},
                agent_type=self.agent_type,
            )

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

            elif modification_type == "regenerate":
                # User wants to regenerate the plan from scratch (e.g., "try again")
                # Use the ORIGINAL plan description, not the user's retry message
                root_path = request.payload.get("root_path", "/home/wyld-core")
                original_description = plan.get("description", plan.get("title", ""))

                await self.publish_action("exploring", f"Re-exploring for plan regeneration...")

                # Fresh exploration based on original task
                exploration = await self._explore_for_plan(original_description, base_path=root_path)

                # Recall past learnings (especially error patterns from previous attempts)
                past_learnings = ""
                if self._memory:
                    await self.publish_action("recalling", "Learning from previous attempts...")
                    past_learnings = await self._recall_relevant_memories(
                        task_description=original_description,
                        project_id=self._state.current_project_id,
                        domain_id=plan.get("project_name"),
                        categories=["plan_completion", "error_pattern", "technique"],
                    )

                await self.publish_action("planning", "Regenerating plan...")

                # Generate fresh steps with memory context
                new_steps = await self._generate_plan_from_exploration(
                    original_description, exploration, base_path=root_path, past_learnings=past_learnings
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
                            "todos": s.get("todos", []),
                            "changes": s.get("changes", []),
                            "status": "pending",
                            "dependencies": [],
                            "output": None,
                            "error": None,
                            "started_at": None,
                            "completed_at": None,
                        }
                        for i, s in enumerate(new_steps)
                    ]
                    result_message = f"Plan regenerated with {len(steps)} steps"
                    await self.publish_action("plan_modified", result_message)
                else:
                    # Regeneration failed — keep existing steps
                    logger.warning("Plan regeneration produced no steps", plan_id=plan_id)
                    result_message = f"Regeneration attempt produced no steps, keeping {len(steps)} existing steps"
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

                # Recall past learnings for this project/task
                past_learnings = ""
                if self._memory:
                    await self.publish_action("recalling", "Checking past learnings...")
                    past_learnings = await self._recall_relevant_memories(
                        task_description=combined_task,
                        project_id=self._state.current_project_id,
                        domain_id=plan.get("project_name"),
                        categories=["plan_creation", "plan_completion", "error_pattern"],
                    )

                await self.publish_action("planning", "Updating plan with new findings...")

                # Regenerate steps with combined context and memory
                new_steps = await self._generate_plan_from_exploration(
                    combined_task, exploration, base_path=root_path, past_learnings=past_learnings
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
                            "todos": s.get("todos", []),
                            "changes": s.get("changes", []),
                            "status": "pending",
                            "dependencies": [],
                            "output": None,
                            "error": None,
                            "started_at": None,
                            "completed_at": None,
                        }
                        for i, s in enumerate(new_steps)
                    ]
                    result_message = f"Plan updated with {len(steps)} steps after researching: {additional_context[:50]}"
                    await self.publish_action("plan_modified", result_message)
                else:
                    # Regeneration produced no steps — re-read plan from Redis
                    # to avoid overwriting a concurrent update with stale data
                    logger.warning(
                        "Plan regeneration produced no steps, keeping existing plan",
                        plan_id=plan_id,
                        original_steps=original_step_count,
                    )
                    fresh_plan_data = await self._redis.get(plan_key)
                    if fresh_plan_data:
                        plan = json.loads(fresh_plan_data)
                        steps = plan.get("steps", [])
                    result_message = f"Plan regeneration found no changes, keeping {len(steps)} existing steps"
                    await self.publish_action("plan_modified", result_message)

            # Update plan in Redis — with concurrency protection
            # For research_and_update/regenerate: only save if we actually have steps
            # This prevents a failed regeneration from clearing an existing plan
            is_regeneration = modification_type in ("research_and_update", "regenerate")
            if is_regeneration and len(steps) == 0 and original_step_count > 0:
                logger.warning(
                    "Refusing to save empty plan over existing steps",
                    plan_id=plan_id,
                    original_steps=original_step_count,
                )
            else:
                plan["steps"] = steps
                plan["modified_at"] = datetime.now(timezone.utc).isoformat()
                await self._redis.set(plan_key, json.dumps(plan))

            # Send update to frontend
            if self._pubsub and user_id:
                if modification_type in ("research_and_update", "regenerate"):
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
                    # Send structured steps so frontend can render interactive step UI
                    await self._pubsub.publish(
                        "agent:responses",
                        {
                            "type": "step_update",
                            "user_id": user_id,
                            "conversation_id": conversation_id,
                            "plan_id": plan_id,
                            "steps": steps,
                            "current_step": 0,
                            "modification": modification_type,
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

    async def _handle_host_command(self, request: TaskRequest) -> TaskResponse:
        """
        Execute a shell command on the host, delegated from the API container.

        Used by domain_service for nginx/certbot operations that require
        host-level access (the API container runs as non-root without nginx/certbot).

        Publishes the result back to a response channel so the caller can await it.
        """
        import asyncio as _asyncio
        import json

        command_id = request.payload.get("command_id")
        command = request.payload.get("command")

        if not command_id or not command:
            return TaskResponse(
                task_id=request.id,
                status=TaskStatus.FAILED,
                error="Missing command_id or command in payload",
                agent_type=self.agent_type,
            )

        logger.info("Executing host command", command_id=command_id, command=command[:100])

        # Allow only specific command patterns for security
        allowed_prefixes = [
            "bash -c",
            "nginx",
            "certbot",
            "ln -sf /etc/nginx",
            "systemctl reload nginx",
            "systemctl restart nginx",
        ]
        cmd_lower = command.lower().strip()
        # Block obviously dangerous patterns
        dangerous = ["rm -rf /", "mkfs", "dd if=", "shutdown", "reboot", "passwd", "userdel", "chmod -R 777 /"]
        for d in dangerous:
            if d in cmd_lower:
                error_msg = f"Blocked dangerous command pattern: {d}"
                logger.warning("Host command blocked", command_id=command_id, reason=error_msg)
                result = {"returncode": 1, "stdout": "", "stderr": error_msg}
                await self._redis.client.publish(
                    f"host_command:{command_id}:response",
                    json.dumps(result),
                )
                return TaskResponse(
                    task_id=request.id,
                    status=TaskStatus.FAILED,
                    error=error_msg,
                    agent_type=self.agent_type,
                )

        try:
            proc = await _asyncio.create_subprocess_shell(
                command,
                stdout=_asyncio.subprocess.PIPE,
                stderr=_asyncio.subprocess.PIPE,
                cwd="/tmp",
            )
            stdout_bytes, stderr_bytes = await _asyncio.wait_for(
                proc.communicate(), timeout=120
            )

            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            returncode = proc.returncode or 0

            logger.info(
                "Host command completed",
                command_id=command_id,
                returncode=returncode,
                stdout_len=len(stdout),
                stderr_len=len(stderr),
            )

            result = {
                "returncode": returncode,
                "stdout": stdout[:8000],
                "stderr": stderr[:8000],
            }

        except _asyncio.TimeoutError:
            logger.error("Host command timed out", command_id=command_id)
            result = {"returncode": 1, "stdout": "", "stderr": "Command timed out after 120s"}

        except Exception as e:
            logger.error("Host command failed", command_id=command_id, error=str(e))
            result = {"returncode": 1, "stdout": "", "stderr": str(e)}

        # Publish result back to the waiting domain_service
        response_channel = f"host_command:{command_id}:response"
        await self._redis.client.publish(response_channel, json.dumps(result))

        status = TaskStatus.COMPLETED if result["returncode"] == 0 else TaskStatus.FAILED
        return TaskResponse(
            task_id=request.id,
            status=status,
            result=result,
            error=result["stderr"] if result["returncode"] != 0 else None,
            agent_type=self.agent_type,
        )

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

        root_path = plan.get("root_path", "/home/wyld-core")
        prompt = f"""Analyze this user message to determine how they want to modify the plan.

Current Plan: {plan.get('title', 'Untitled')}
Project Root: {root_path}/
Current Steps:
{step_list}

User Message: "{user_message}"

Determine the modification type. Respond with JSON only:

## IMPORTANT: Almost ALL modifications should use "research_and_update"

Use "research_and_update" (DEFAULT for any content change):
{{"type": "research_and_update", "data": {{"context": "the user's requirement restated clearly"}}}}

Use this when the user:
- Adds ANY new requirement or feature (even small ones)
- Wants to change the approach or technology
- Says the plan is missing something
- Asks about or suggests different implementation details
- Provides feedback like "make it better", "more modern", "add X"
- Requests any content that would need file exploration

For skipping steps (ONLY use for explicit "skip step X"):
{{"type": "skip", "data": {{"step_indices": [0]}}}}

For removing steps (ONLY use for explicit "remove step X"):
{{"type": "remove", "data": {{"step_indices": [1]}}}}

For regenerating from scratch (ONLY for "start over", "try again", "redo the whole plan"):
{{"type": "regenerate", "data": {{}}}}

CRITICAL RULES:
- NEVER use "add" type — always use "research_and_update" for adding content
- NEVER use "modify" type — always use "research_and_update" for changing step content
- "research_and_update" ensures the plan gets proper todos, file paths, and detailed changes
- Only use "skip"/"remove"/"regenerate" for their exact purposes described above
- When in doubt, use "research_and_update"

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

        # Scan the project root to give the LLM real directory context
        try:
            dir_entries = await asyncio.to_thread(os.listdir, base_path)
            dir_listing = ", ".join(sorted(dir_entries)[:30])
        except Exception:
            dir_listing = "(unable to list)"

        # Ask Claude for search strategy based on the task
        strategy_prompt = f"""Analyze this development task and determine what to search for in the codebase.
Project root directory: {base_path}/
(This is a DIRECTORY, not a file — even if the name contains dots like "site.example.com")

Files/dirs in project root: {dir_listing}

Task: {task_description}

Respond with a JSON object containing search strategies:
{{"file_patterns": ["*.html", "*.css", "*.js"], "search_terms": ["navbar", "header"], "key_dirs": ["."]}}

- file_patterns: glob patterns for relevant files (max 6). Match what actually exists in the project!
- search_terms: keywords to search for in code (max 5)
- key_dirs: directories likely to contain relevant code (use "." for flat projects)

Only output the JSON object, no other text."""

        try:
            response = await self._llm.create_message(
                max_tokens=500,
                tier=ModelTier.FAST,
                messages=[{"role": "user", "content": strategy_prompt}],
            )

            # Record API usage and emit WebSocket event for real-time display
            await self._record_and_emit_usage(
                model=response.model or self.config.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cached_tokens=response.cached_tokens,
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
        for pattern in strategy.get("file_patterns", [])[:6]:
            await self.publish_action("file_search", f"Searching: {pattern}")
            files = await _glob_files(pattern, base_path=base_path, max_results=15)
            exploration["files"].extend(files[:10])

        # Search for patterns in code
        for term in strategy.get("search_terms", [])[:5]:
            await self.publish_action("file_search", f"Searching for: {term}")
            matches = await _grep_content(term, path=base_path, max_results=10)
            exploration["patterns"].extend(matches[:8])

        # List directory structures for key dirs
        for dir_name in strategy.get("key_dirs", [])[:4]:
            dir_path = Path(base_path) / dir_name
            if dir_path.is_dir():
                await self.publish_action("file_search", f"Listing: {dir_name}/")
                try:
                    entries = sorted(dir_path.iterdir())[:20]
                    dir_listing = []
                    for entry in entries:
                        prefix = "📁" if entry.is_dir() else "📄"
                        dir_listing.append(f"{prefix} {entry.name}")
                    exploration.setdefault("directories", []).append({
                        "path": str(dir_path),
                        "entries": dir_listing,
                    })
                except Exception:
                    pass

        # Read key files discovered
        seen_paths = set()
        files_to_read = exploration["files"][:8]
        for f in files_to_read:
            path = f.get("path", "")
            if path and path not in seen_paths:
                seen_paths.add(path)
                file_name = Path(path).name
                await self.publish_action("file_read", f"Reading: {file_name}")
                content = await _read_file(path, max_lines=150)
                exploration["content"].append({
                    "path": path,
                    "content": content[:4000]
                })

        # Second-pass exploration: ask Claude for follow-up searches based on gaps
        try:
            follow_up_prompt = f"""Given these initial exploration results and the task "{task_description}",
what 2-3 additional specific searches would fill gaps in understanding?
Return JSON: {{"follow_up_patterns": ["*.py"], "follow_up_terms": ["class_name"]}}

Files found: {len(exploration["files"])}
Patterns found: {len(exploration["patterns"])}
Files read: {[Path(c["path"]).name for c in exploration["content"]]}

Only output the JSON object, no other text."""

            follow_up_response = await self._llm.create_message(
                max_tokens=300,
                tier=ModelTier.FAST,
                messages=[{"role": "user", "content": follow_up_prompt}],
            )

            # Record API usage and emit WebSocket event
            await self._record_and_emit_usage(
                model=follow_up_response.model or self.config.model,
                input_tokens=follow_up_response.input_tokens,
                output_tokens=follow_up_response.output_tokens,
                cached_tokens=follow_up_response.cached_tokens,
            )

            fu_text = follow_up_response.text_content or "{}"
            fu_start = fu_text.find("{")
            fu_end = fu_text.rfind("}") + 1
            if fu_start >= 0 and fu_end > fu_start:
                follow_up = json.loads(fu_text[fu_start:fu_end])
            else:
                follow_up = {}

            # Execute follow-up searches
            for pattern in follow_up.get("follow_up_patterns", [])[:3]:
                await self.publish_action("file_search", f"Follow-up: {pattern}")
                files = await _glob_files(pattern, base_path=base_path, max_results=10)
                for f in files[:5]:
                    if f.get("path") not in seen_paths:
                        exploration["files"].append(f)

            for term in follow_up.get("follow_up_terms", [])[:3]:
                await self.publish_action("file_search", f"Follow-up: {term}")
                matches = await _grep_content(term, path=base_path, max_results=8)
                exploration["patterns"].extend(matches[:5])

            # Read any new key files from follow-up
            new_files = [f for f in exploration["files"] if f.get("path") not in seen_paths]
            for f in new_files[:3]:
                path = f.get("path", "")
                if path:
                    seen_paths.add(path)
                    file_name = Path(path).name
                    await self.publish_action("file_read", f"Reading: {file_name}")
                    content = await _read_file(path, max_lines=150)
                    exploration["content"].append({
                        "path": path,
                        "content": content[:4000]
                    })

        except Exception as e:
            logger.debug("Follow-up exploration failed (non-critical)", error=str(e))

        logger.info(
            "Exploration complete",
            files_found=len(exploration["files"]),
            patterns_found=len(exploration["patterns"]),
            files_read=len(exploration["content"]),
        )

        return exploration

    async def _generate_plan_from_exploration(self, task: str, exploration: dict, base_path: str = "/home/wyld-core", past_learnings: str = "") -> list[dict]:
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
            for p in exploration.get("patterns", [])[:12]
        ]) or "No patterns found"

        content_summary = "\n\n".join([
            f"### {Path(c['path']).name}\n```\n{c['content'][:1500]}\n```"
            for c in exploration.get("content", [])[:4]
        ]) or "No file contents available"

        # Load TELOS for value-aligned planning
        telos = _load_telos_context()

        # Detect if task is web/frontend related for specialized planning
        task_lower = task.lower()
        is_web_task = any(kw in task_lower for kw in ["website", "bootstrap", "html", "css", "redesign", "landing", "web page", "frontend", "responsive"])

        web_planning_guide = ""
        if is_web_task:
            web_planning_guide = """
## Web Project Planning Guide

For website tasks, structure steps by PAGE rather than by concept:
- Step 1: Create shared assets (CSS stylesheet, JS, shared partials)
- Step 2: Create/Update the main page (index.html) with full Bootstrap layout
- Step 3: Create/Update each additional page (one step per 2-3 pages max)
- Step 4: Add interactive features (forms, animations, theme toggle)
- Final: Verify all pages render correctly

Each HTML page step should produce a COMPLETE page with full Bootstrap 5 markup — not just fragments. Include `<head>` with meta tags, Bootstrap CDN, `<nav>`, `<main>`, `<footer>` in every page.
"""

        prompt = f"""Create an ACTIONABLE implementation plan. Research is ALREADY DONE — the exploration results below show what exists in the codebase.

{telos}

---

## Task
{task}

## Codebase Root Directory
{base_path}/
(This is a DIRECTORY path — even if the name contains dots like "site.example.com", it is a folder, not a file)

## Files Already Found
{files_summary}

## Code Patterns Already Found
{patterns_summary}

## File Contents Already Read
{content_summary}
{web_planning_guide}{past_learnings}
## CRITICAL RULES

The exploration above IS the research phase. Do NOT create steps that say "investigate", "research", "identify", or "determine". Those are already done.

This is a SINGLE SERVER environment. All infrastructure (nginx, databases, SSL, Docker) is already installed and running. When building websites or apps:
- Build files directly in the project's configured root_path — do NOT set up new servers, cloud services, or deployment pipelines
- Nginx, certbot, Node, Python, PHP are already available — do NOT include installation steps
- Use existing databases (PostgreSQL, Redis) — do NOT provision new database instances
- Reference the Server Baseline above for what's already available

Every step must be a CONCRETE ACTION that modifies or creates a file. Each step will be executed by an agent with read/write file tools.

Respond with a JSON array only:
[{{"title": "Action verb + what", "description": "Specific file changes: what to write/modify and where", "agent": "code|infra|qa", "files": ["{base_path}/path/to/file"], "todos": ["Specific actionable sub-task 1", "Specific actionable sub-task 2"], "changes": [{{"file": "{base_path}/path/to/file", "action": "create|modify", "summary": "Brief description of change"}}]}}]

Rules:
- NEVER use agent type "research" — research is already complete
- Every step MUST specify which files to create or modify with full paths starting with {base_path}
- Titles must start with action verbs: "Create", "Add", "Update", "Configure", "Modify", "Write"
- Descriptions must say exactly WHAT content to write or change, not what to "look for"
- Use "code" for source code changes, "infra" for config/deployment, "qa" for tests
- Include a final "Verify changes" step (agent: "qa")
- 3-6 steps maximum
- Each step MUST include "todos": a list of 3-5 specific, actionable sub-tasks that describe exactly what to do
- Each step MUST include "changes": a list of file change objects with "file" (full path), "action" ("create" or "modify"), and "summary" (brief description)
- Only output the JSON array, no other text."""

        try:
            response = await self._llm.create_message(
                max_tokens=6000,
                tier=ModelTier.BALANCED,
                messages=[{"role": "user", "content": prompt}],
            )

            # Record API usage and emit WebSocket event for real-time display
            await self._record_and_emit_usage(
                model=response.model or self.config.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cached_tokens=response.cached_tokens,
            )

            text = response.text_content or "[]"
            logger.debug(
                "Plan generation LLM response",
                provider=response.provider.value if response.provider else "unknown",
                model=response.model,
                output_tokens=response.output_tokens,
                stop_reason=response.stop_reason,
                text_length=len(text),
                text_preview=text[:300],
            )

            # Handle truncated responses (max_tokens hit)
            if response.stop_reason == "max_tokens" or response.stop_reason == "length":
                logger.warning(
                    "Plan generation truncated by max_tokens",
                    output_tokens=response.output_tokens,
                    text_length=len(text),
                )
                # Try to salvage: find the last complete JSON object in the array
                start = text.find("[")
                if start >= 0:
                    # Find last complete object by looking for "}," or "}" before truncation
                    last_obj_end = text.rfind("}")
                    if last_obj_end > start:
                        salvaged = text[start:last_obj_end + 1] + "]"
                        try:
                            steps = json.loads(salvaged)
                            if steps:
                                logger.info("Salvaged truncated plan", steps_count=len(steps))
                                return steps
                        except json.JSONDecodeError:
                            pass

            # Extract JSON array from response
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                steps = json.loads(text[start:end])
                if not steps:
                    logger.warning(
                        "LLM returned empty steps array, using fallback",
                        model=response.model,
                        text_preview=text[:200],
                    )
                    raise ValueError("LLM returned empty steps array")
                return steps
            else:
                raise ValueError(f"No JSON array found in response (length={len(text)}): {text[:200]}")

        except Exception as e:
            logger.warning("Failed to generate plan from exploration", error=str(e))
            # Return fallback actionable steps based on exploration
            found_files = [f.get("path", "") for f in exploration.get("files", [])[:5] if f.get("path")]

            if found_files:
                # Existing project: read, modify, verify
                return [
                    {
                        "title": "Read and understand relevant files",
                        "description": "Read files found during exploration to understand current state before making changes",
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
            else:
                # New project: create from scratch
                return [
                    {
                        "title": f"Create project structure",
                        "description": f"Create the initial project files and directory structure in {base_path}/",
                        "agent": "code",
                        "files": [f"{base_path}/index.html"],
                        "todos": ["Create the main entry file", "Set up directory structure"],
                    },
                    {
                        "title": f"Implement: {task[:40]}",
                        "description": f"Build the core content and functionality as described: {task[:100]}",
                        "agent": "code",
                        "files": [base_path],
                    },
                    {
                        "title": "Add styling and polish",
                        "description": f"Add CSS styling and any additional assets to complete the project in {base_path}/",
                        "agent": "code",
                        "files": [base_path],
                    },
                    {
                        "title": "Verify project is complete",
                        "description": "Review all created files to ensure the project meets requirements",
                        "agent": "qa",
                        "files": [base_path],
                    },
                ]

    # =========================================================================
    # Improvement 1: Outcome Feedback Loop (Plan-to-Learn Pipeline)
    # =========================================================================

    async def _capture_execution_outcome(
        self,
        plan_id: str,
        steps: list[dict],
        result: dict,
    ) -> None:
        """
        Capture execution outcome and update learnings.

        This creates a closed feedback loop: Plan → Execute → Verify → Score → Store Learning
        """
        from datetime import datetime, timezone

        outcome = {
            "plan_id": plan_id,
            "success": result.get("success", False),
            "steps_completed": len([s for s in steps if s.get("status") == "completed"]),
            "steps_total": len(steps),
            "error_types": [s.get("error_type") for s in steps if s.get("error")],
            "duration_ms": result.get("duration_ms"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Update confidence on related learnings
        if outcome["success"]:
            await self._boost_related_learnings(plan_id, boost=0.1)
        else:
            await self._decay_related_learnings(plan_id, decay=0.15)

        # Store as new learning if pattern is novel
        if await self._is_novel_pattern(outcome):
            if self._memory:
                from ai_memory import Learning, LearningScope, PAIPhase

                learning = Learning(
                    content=f"Plan pattern {'succeeded' if outcome['success'] else 'failed'}: {result.get('summary', '')}",
                    phase=PAIPhase.LEARN,
                    category="execution_outcome",
                    scope=LearningScope.PROJECT,
                    project_id=self._state.current_project_id,
                    created_by_agent="supervisor",
                    confidence=0.8 if outcome["success"] else 0.6,
                    metadata=outcome,
                )
                await self._memory.store_learning(learning)
                logger.debug(f"Stored execution outcome for plan {plan_id}")

    async def _boost_related_learnings(self, plan_id: str, boost: float = 0.1) -> None:
        """Boost utility score of learnings related to a successful plan."""
        if not self._memory:
            return

        try:
            # Search for learnings related to this plan
            related = await self._memory.search_learnings(
                query=f"plan_id:{plan_id}",
                limit=10,
                agent_type="supervisor",
                permission_level=4,
            )

            for learning_dict in related:
                learning_id = learning_dict.get("id")
                if learning_id:
                    await self._memory.boost_learning(learning_id, boost)

            logger.debug(f"Boosted {len(related)} learnings for plan {plan_id}")
        except Exception as e:
            logger.debug(f"Failed to boost learnings: {e}")

    async def _decay_related_learnings(self, plan_id: str, decay: float = 0.15) -> None:
        """Decay utility score of learnings related to a failed plan."""
        if not self._memory:
            return

        try:
            # Search for learnings related to this plan
            related = await self._memory.search_learnings(
                query=f"plan_id:{plan_id}",
                limit=10,
                agent_type="supervisor",
                permission_level=4,
            )

            for learning_dict in related:
                learning_id = learning_dict.get("id")
                if learning_id:
                    await self._memory.decay_learning(learning_id, decay)

            logger.debug(f"Decayed {len(related)} learnings for plan {plan_id}")
        except Exception as e:
            logger.debug(f"Failed to decay learnings: {e}")

    async def _is_novel_pattern(self, outcome: dict) -> bool:
        """Check if this execution pattern is novel enough to store."""
        if not self._memory:
            return True

        try:
            # Search for similar outcomes
            query = f"plan pattern {outcome.get('steps_completed')}/{outcome.get('steps_total')} steps"
            similar = await self._memory.search_learnings(
                query=query,
                category="execution_outcome",
                limit=3,
                agent_type="supervisor",
                permission_level=4,
            )

            # If no similar patterns, it's novel
            if not similar:
                return True

            # Check if this is significantly different
            for s in similar:
                s_meta = s.get("metadata", {})
                if (
                    s_meta.get("steps_completed") == outcome.get("steps_completed")
                    and s_meta.get("steps_total") == outcome.get("steps_total")
                    and s_meta.get("success") == outcome.get("success")
                ):
                    return False  # Very similar pattern exists

            return True
        except Exception:
            return True  # On error, assume novel

    # =========================================================================
    # Improvement 2: Process Reward Model (Step-Level Scoring)
    # =========================================================================

    async def _score_step_execution(
        self,
        step: dict,
        result: dict,
        expected_duration_ms: int = 5000,
    ) -> float:
        """
        Score individual step execution 0-1.

        Factors:
        - Completion score
        - Efficiency score (time vs expected)
        - Error-free score
        - Output quality score (optional LLM assessment)
        """
        scores = []

        # 1. Completion score (40% weight)
        completed = 1.0 if result.get("completed", step.get("status") == "completed") else 0.0
        scores.append(completed * 0.4)

        # 2. Efficiency score (20% weight)
        actual_ms = result.get("duration_ms", expected_duration_ms)
        if actual_ms > 0:
            efficiency = min(1.0, expected_duration_ms / max(actual_ms, 1))
        else:
            efficiency = 1.0
        scores.append(efficiency * 0.2)

        # 3. Error-free score (30% weight)
        error_free = 0.0 if result.get("error") or step.get("error") else 1.0
        scores.append(error_free * 0.3)

        # 4. File modification score (10% weight)
        # Steps that modify files are generally more productive
        files_modified = len(result.get("files_modified", []))
        file_score = min(1.0, files_modified / 3) if files_modified else 0.5
        scores.append(file_score * 0.1)

        return sum(scores)

    async def _maybe_course_correct(
        self,
        step_scores: list[float],
        remaining_steps: list[dict],
        plan: dict,
    ) -> tuple[list[dict], bool]:
        """
        Check if course correction needed based on step scores.

        Returns:
            Tuple of (potentially replanned steps, whether replanning occurred)
        """
        if len(step_scores) < 3:
            return remaining_steps, False

        # Calculate recent average score
        recent_avg = sum(step_scores[-3:]) / 3

        if recent_avg < 0.5:
            logger.warning(f"Low step scores ({recent_avg:.2f}), considering re-plan")

            # Only replan if there are significant remaining steps
            if len(remaining_steps) >= 2:
                try:
                    replanned = await self._replan_remaining(remaining_steps, step_scores, plan)
                    if replanned:
                        logger.info(f"Re-planned {len(remaining_steps)} remaining steps")
                        return replanned, True
                except Exception as e:
                    logger.warning(f"Re-planning failed: {e}")

        return remaining_steps, False

    async def _replan_remaining(
        self,
        remaining_steps: list[dict],
        step_scores: list[float],
        plan: dict,
    ) -> list[dict] | None:
        """
        Re-plan remaining steps based on execution feedback.

        This generates alternative steps when the current approach isn't working.
        """
        if not remaining_steps:
            return None

        # Gather context about what's failing
        failing_context = []
        for i, score in enumerate(step_scores[-3:]):
            if score < 0.5:
                failing_context.append(f"Step scored {score:.2f}")

        # Get original goal
        goal = plan.get("description", plan.get("title", ""))

        # Generate new plan prompt
        prompt = f"""The current plan is struggling. Recent step scores: {step_scores[-3:]}.

Original goal: {goal}

Remaining steps that need to be re-planned:
{[s.get('title') for s in remaining_steps]}

Generate simpler, more focused steps to achieve the remaining work. Break complex steps into smaller, more concrete actions.

Return a JSON array of new steps, each with: title, description, agent (code/qa/infra), files (array of paths)."""

        try:
            response = await self._llm.create_message(
                max_tokens=2000,
                tier=ModelTier.BALANCED,
                messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            )

            import json
            text = response.text_content
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                new_steps = json.loads(text[start:end])
                # Add IDs and order to new steps
                from uuid import uuid4
                base_order = plan.get("current_step", 0) + 1
                for i, step in enumerate(new_steps):
                    step["id"] = str(uuid4())
                    step["order"] = base_order + i
                    step["status"] = "pending"
                    step["replanned"] = True
                return new_steps
        except Exception as e:
            logger.debug(f"Failed to replan: {e}")

        return None

    # =========================================================================
    # Improvement 6: Plan Quality Prediction and Alternative Exploration
    # =========================================================================

    async def _generate_plans_with_exploration(
        self,
        goal: str,
        context: dict,
        exploration: dict,
        num_candidates: int = 3,
    ) -> dict:
        """
        Generate and evaluate multiple plan candidates.

        Uses Tree-of-Thoughts at plan level: generate diverse candidates,
        score them, and select the best approach.

        Returns:
            Dict with best plan and metadata about exploration
        """
        # Generate diverse candidates
        candidates = await self._generate_candidate_plans(goal, context, exploration, num_candidates)

        if not candidates:
            # Fallback to single plan
            return {
                "plan": await self._generate_plan_from_exploration(goal, exploration),
                "predicted_quality": 0.5,
                "alternatives_considered": 0,
            }

        # Score each candidate
        scored_candidates = []
        for plan_steps in candidates:
            score = await self._predict_plan_quality(plan_steps, context)
            scored_candidates.append((plan_steps, score))

        # Sort by predicted quality
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        best_plan, best_score = scored_candidates[0]

        # If best score is low, try refinement
        if best_score < 0.6 and len(scored_candidates) > 1:
            try:
                refined = await self._refine_plan(best_plan, scored_candidates[1:])
                refined_score = await self._predict_plan_quality(refined, context)
                if refined_score > best_score:
                    best_plan, best_score = refined, refined_score
            except Exception as e:
                logger.debug(f"Plan refinement failed: {e}")

        return {
            "plan": best_plan,
            "predicted_quality": best_score,
            "alternatives_considered": len(candidates),
            "exploration_metadata": {
                "scores": [s for _, s in scored_candidates],
                "refinement_applied": best_score > scored_candidates[0][1] if scored_candidates else False,
            },
        }

    async def _predict_plan_quality(
        self,
        plan_steps: list[dict],
        context: dict,
    ) -> float:
        """
        Predict plan success probability 0-1.

        Scoring factors:
        1. Historical success rate for similar goals
        2. Complexity score (simpler is better)
        3. Step clarity score
        4. Context alignment score
        """
        scores = []

        # 1. Historical success rate for similar goals (30% weight)
        if self._memory:
            try:
                goal = context.get("goal", "")
                similar_outcomes = await self._memory.search_learnings(
                    query=goal,
                    category="execution_outcome",
                    limit=10,
                    agent_type="supervisor",
                    permission_level=4,
                )
                if similar_outcomes:
                    success_count = sum(
                        1 for l in similar_outcomes
                        if l.get("metadata", {}).get("success")
                    )
                    success_rate = success_count / len(similar_outcomes)
                    scores.append(success_rate * 0.3)
                else:
                    scores.append(0.5 * 0.3)  # Neutral if no history
            except Exception:
                scores.append(0.5 * 0.3)
        else:
            scores.append(0.5 * 0.3)

        # 2. Complexity score (25% weight) - simpler is better
        step_count = len(plan_steps)
        substep_count = sum(len(s.get("todos", [])) for s in plan_steps)
        total_complexity = step_count + substep_count * 0.5

        # Ideal complexity is 3-5 steps
        if 3 <= total_complexity <= 5:
            complexity_score = 1.0
        elif total_complexity < 3:
            complexity_score = 0.7  # Too simple might miss things
        elif total_complexity <= 8:
            complexity_score = 0.8
        else:
            complexity_score = max(0.3, 1.0 - (total_complexity - 8) * 0.1)
        scores.append(complexity_score * 0.25)

        # 3. Step clarity score (25% weight)
        clarity_scores = []
        for step in plan_steps:
            step_clarity = 0.0
            # Has title
            if step.get("title"):
                step_clarity += 0.3
            # Has description
            if step.get("description") and len(step["description"]) > 20:
                step_clarity += 0.4
            # Has specific files
            if step.get("files"):
                step_clarity += 0.3
            clarity_scores.append(step_clarity)

        avg_clarity = sum(clarity_scores) / len(clarity_scores) if clarity_scores else 0.5
        scores.append(avg_clarity * 0.25)

        # 4. Context alignment score (20% weight)
        alignment_score = 0.5
        if context.get("root_path"):
            # Check if steps reference the correct path
            path_refs = sum(
                1 for s in plan_steps
                if context["root_path"] in str(s.get("files", []))
                or context["root_path"] in str(s.get("description", ""))
            )
            alignment_score = min(1.0, path_refs / max(len(plan_steps), 1))
        scores.append(alignment_score * 0.2)

        return sum(scores)

    async def _generate_candidate_plans(
        self,
        goal: str,
        context: dict,
        exploration: dict,
        num_candidates: int,
    ) -> list[list[dict]]:
        """Generate diverse plan candidates using different strategies."""
        candidates = []

        # Strategy 1: Direct LLM planning (always include)
        try:
            direct_plan = await self._generate_plan_from_exploration(
                goal, exploration, base_path=context.get("root_path", "/home/wyld-core")
            )
            if direct_plan:
                candidates.append(direct_plan)
        except Exception:
            pass

        # Strategy 2: Historical pattern matching
        if self._memory and len(candidates) < num_candidates:
            try:
                similar_successes = await self._memory.search_learnings(
                    query=goal,
                    category="plan_completion",
                    limit=5,
                    agent_type="supervisor",
                    permission_level=4,
                )
                # Filter for successful completions
                for success in similar_successes:
                    if success.get("metadata", {}).get("success_rate", 0) > 0.8:
                        pattern_plan = await self._adapt_historical_pattern(success, goal, context)
                        if pattern_plan:
                            candidates.append(pattern_plan)
                            break
            except Exception:
                pass

        # Strategy 3: Decomposition approach (for complex goals)
        if self._is_complex_goal(goal) and len(candidates) < num_candidates:
            try:
                decomposed = await self._generate_decomposed_plan(goal, context, exploration)
                if decomposed:
                    candidates.append(decomposed)
            except Exception:
                pass

        return candidates

    def _is_complex_goal(self, goal: str) -> bool:
        """Determine if a goal is complex enough to warrant decomposition."""
        complexity_indicators = [
            " and ", " with ", " including ", " also ",
            "multiple", "several", "all", "complete",
            "refactor", "migrate", "redesign",
        ]
        goal_lower = goal.lower()
        indicator_count = sum(1 for ind in complexity_indicators if ind in goal_lower)
        word_count = len(goal.split())

        return indicator_count >= 2 or word_count > 20

    async def _adapt_historical_pattern(
        self,
        historical: dict,
        goal: str,
        context: dict,
    ) -> list[dict] | None:
        """Adapt a historical successful pattern to the current goal."""
        meta = historical.get("metadata", {})
        historical_steps = meta.get("step_titles", [])

        if not historical_steps:
            return None

        # Create adapted steps
        adapted = []
        for title in historical_steps:
            adapted.append({
                "title": title,
                "description": f"Adapted from successful pattern. Apply to: {goal[:50]}",
                "agent": "code",
                "files": [],
                "adapted_from": historical.get("id"),
            })

        return adapted

    async def _generate_decomposed_plan(
        self,
        goal: str,
        context: dict,
        exploration: dict,
    ) -> list[dict] | None:
        """Generate a plan by first decomposing the goal into sub-goals."""
        prompt = f"""Break down this complex goal into 2-4 independent sub-goals:

Goal: {goal}

Context: Working in {context.get('root_path', '/home/wyld-core')}
Files found: {[f.get('relative') for f in exploration.get('files', [])[:5]]}

For each sub-goal, provide:
1. A focused title (what to accomplish)
2. Brief description
3. Which files might be involved

Return a JSON array of sub-goals, each with: title, description, files (array)."""

        try:
            response = await self._llm.create_message(
                max_tokens=1500,
                tier=ModelTier.FAST,
                messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            )

            import json
            text = response.text_content
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                sub_goals = json.loads(text[start:end])
                # Convert sub-goals to plan steps
                return [
                    {
                        "title": sg.get("title", f"Sub-task {i+1}"),
                        "description": sg.get("description", ""),
                        "agent": "code",
                        "files": sg.get("files", []),
                        "decomposed": True,
                    }
                    for i, sg in enumerate(sub_goals)
                ]
        except Exception as e:
            logger.debug(f"Goal decomposition failed: {e}")

        return None

    async def _refine_plan(
        self,
        best_plan: list[dict],
        alternatives: list[tuple[list[dict], float]],
    ) -> list[dict]:
        """Refine the best plan by incorporating insights from alternatives."""
        # Collect unique elements from alternatives
        alternative_steps = set()
        for alt_plan, _ in alternatives:
            for step in alt_plan:
                alternative_steps.add(step.get("title", ""))

        # Check if alternatives suggest missing steps
        best_titles = {s.get("title", "") for s in best_plan}
        missing_suggestions = alternative_steps - best_titles

        # If alternatives suggest significantly different approaches, consider merging
        if len(missing_suggestions) >= 2:
            # Add one verification/validation step based on alternatives
            best_plan.append({
                "title": "Verify implementation completeness",
                "description": f"Review changes against original requirements. Alternative approaches suggested: {list(missing_suggestions)[:2]}",
                "agent": "qa",
                "files": [],
                "refinement_added": True,
            })

        return best_plan

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

        all_changes = []

        for step in plan.get("steps", []):
            icon = status_icons.get(step.get("status", "pending"), "⬜")
            agent_info = f" ({step.get('agent')})" if step.get("agent") else ""
            lines.append(f"{step.get('order', '?')}. {icon} **{step.get('title', 'Untitled')}**{agent_info}")
            if step.get("description"):
                lines.append(f"   {step.get('description')}")
            lines.append("")

            # Show todos as checklist
            if step.get("todos"):
                lines.append("   **To-do:**")
                for todo in step["todos"]:
                    lines.append(f"   - [ ] {todo}")
                lines.append("")

            # Show file changes per step
            if step.get("changes"):
                lines.append("   **Files:**")
                for change in step["changes"]:
                    action_icon = "🆕" if change.get("action") == "create" else "✏️"
                    file_path = change.get("file", "")
                    # Show relative path for readability
                    display_path = file_path.replace("/home/wyld-core/", "")
                    lines.append(f"   - {action_icon} `{display_path}`")
                    all_changes.append(change)
                lines.append("")

        # Add summary of all files to be changed
        if all_changes:
            seen_files = set()
            unique_changes = []
            for change in all_changes:
                file_path = change.get("file", "")
                if file_path not in seen_files:
                    seen_files.add(file_path)
                    unique_changes.append(change)

            lines.extend(["---", "", "### 📁 All files to be changed:", ""])
            for change in unique_changes:
                action_icon = "🆕" if change.get("action") == "create" else "✏️"
                file_path = change.get("file", "")
                display_path = file_path.replace("/home/wyld-core/", "")
                summary = change.get("summary", "")
                summary_text = f" — {summary}" if summary else ""
                lines.append(f"- {action_icon} `{display_path}`{summary_text}")
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
    # NOTE: Use "agent_learnings" to match API routes and memory tools
    qdrant_store = None
    try:
        qdrant_store = QdrantStore(
            collection_name="agent_learnings",
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
