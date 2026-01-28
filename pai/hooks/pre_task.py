"""
Pre-task hook - Executed before each agent task.

Enhanced with parallel retrieval for OBSERVE phase context.

Responsibilities:
- Load relevant context from memory (parallel queries)
- Extract domain-specific learnings
- Retrieve known issues for similar tasks
- Detect project technology stack (database, framework, etc.)
- Set up correlation tracking
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any

from ai_memory import PAIPhase
from ai_core import detect_project_stack, get_cached_stack, ProjectStack


async def pre_task_hook(
    agent_type: str,
    task_type: str,
    task_input: dict[str, Any],
    memory: Any,  # PAIMemory instance
    permission_level: int = 1,
    project_id: str | None = None,
    domain_id: str | None = None,
) -> dict[str, Any]:
    """
    Execute pre-task hook with enhanced OBSERVE phase retrieval.

    Performs parallel queries to gather:
    - Domain-specific learnings based on task content
    - Known issues/errors for similar tasks
    - Recent observations about the domain
    - Tool usage patterns (if task involves specific tools)

    Args:
        agent_type: Type of agent executing the task
        task_type: Type of task being executed
        task_input: Task input data
        memory: PAI memory instance
        permission_level: Permission level of the agent (for ACL filtering)
        project_id: Optional project context for scope filtering
        domain_id: Optional domain context for scope filtering

    Returns:
        Context dict with:
        - correlation_id: Unique ID for task tracking
        - relevant_learnings: List of relevant learnings (categorized)
        - known_issues: List of known issues/errors
        - domain_context: Domain-specific context
        - observe_metadata: Statistics about retrieval
        - started_at: Timestamp
    """
    correlation_id = str(uuid.uuid4())

    # Build query from task input
    query_parts = [task_type]
    for key, value in task_input.items():
        if isinstance(value, str) and len(value) < 200:
            query_parts.append(value)
        elif key in ("content", "message", "prompt", "query"):
            query_parts.append(str(value)[:200])

    query = " ".join(query_parts)[:500]

    # Define parallel queries for OBSERVE phase
    async def search_general_learnings():
        """Search for general relevant learnings."""
        return await memory.search_learnings(
            query=query,
            limit=5,
            agent_type=agent_type,
            permission_level=permission_level,
            project_id=project_id,
            domain_id=domain_id,
        )

    async def search_domain_learnings():
        """Search for domain-specific learnings."""
        # Extract potential domain hints from task input
        domain_query = query
        if "file" in task_input or "path" in task_input:
            file_path = task_input.get("file") or task_input.get("path", "")
            if isinstance(file_path, str):
                # Extract file extension for domain context
                if "." in file_path:
                    ext = file_path.rsplit(".", 1)[-1]
                    domain_query = f"{ext} file {query}"

        return await memory.search_learnings(
            query=domain_query[:200],
            category="domain",
            limit=3,
            agent_type=agent_type,
            permission_level=permission_level,
            project_id=project_id,
            domain_id=domain_id,
        )

    async def search_known_issues():
        """Search for known issues and errors."""
        return await memory.search_learnings(
            query=f"error issue problem {query[:100]}",
            category="error",
            limit=3,
            agent_type=agent_type,
            permission_level=permission_level,
            project_id=project_id,
            domain_id=domain_id,
        )

    async def search_recent_observations():
        """Search for recent observations in this domain."""
        return await memory.search_learnings(
            query=query[:200],
            phase=PAIPhase.OBSERVE,
            limit=3,
            agent_type=agent_type,
            permission_level=permission_level,
            project_id=project_id,
            domain_id=domain_id,
        )

    async def search_tool_patterns():
        """Search for tool usage patterns if task involves tools."""
        if task_type in ("tool_use", "execute", "build"):
            return await memory.search_learnings(
                query=f"tool pattern {query[:100]}",
                category="tool_pattern",
                limit=2,
                agent_type=agent_type,
                permission_level=permission_level,
            )
        return []

    async def detect_stack():
        """Detect project technology stack from files."""
        # Try to find project path from task input
        project_path = None

        # Check for explicit project_path
        if "project_path" in task_input:
            project_path = task_input["project_path"]
        # Check for file/path that might indicate project location
        elif "file" in task_input or "path" in task_input:
            file_path = task_input.get("file") or task_input.get("path", "")
            if isinstance(file_path, str) and file_path:
                # Try to find project root by looking for common markers
                import os
                current = os.path.dirname(file_path) if os.path.isfile(file_path) else file_path
                for _ in range(10):  # Max 10 levels up
                    if any(os.path.exists(os.path.join(current, marker))
                           for marker in [".env", "docker-compose.yml", "package.json", "requirements.txt", ".git"]):
                        project_path = current
                        break
                    parent = os.path.dirname(current)
                    if parent == current:
                        break
                    current = parent
        # Check for working_directory
        elif "working_directory" in task_input:
            project_path = task_input["working_directory"]

        if project_path:
            # First check cache, then detect
            cached = get_cached_stack(project_path)
            if cached:
                return cached
            return await asyncio.to_thread(detect_project_stack, project_path)
        return None

    # Execute all queries in parallel
    results = await asyncio.gather(
        search_general_learnings(),
        search_domain_learnings(),
        search_known_issues(),
        search_recent_observations(),
        search_tool_patterns(),
        detect_stack(),
        return_exceptions=True,
    )

    # Process results
    general_learnings = results[0] if not isinstance(results[0], Exception) else []
    domain_learnings = results[1] if not isinstance(results[1], Exception) else []
    known_issues = results[2] if not isinstance(results[2], Exception) else []
    observations = results[3] if not isinstance(results[3], Exception) else []
    tool_patterns = results[4] if not isinstance(results[4], Exception) else []
    project_stack: ProjectStack | None = results[5] if not isinstance(results[5], Exception) else None

    # Deduplicate by ID
    seen_ids = set()
    all_learnings = []

    for learning in general_learnings + domain_learnings + observations:
        learning_id = learning.get("id")
        if learning_id and learning_id not in seen_ids:
            seen_ids.add(learning_id)
            all_learnings.append(learning)

    # Track learning IDs for feedback loop
    learning_ids = [l.get("id") for l in all_learnings if l.get("id")]
    issue_ids = [i.get("id") for i in known_issues if i.get("id")]
    pattern_ids = [p.get("id") for p in tool_patterns if p.get("id")]

    # Store task start in HOT memory with enhanced metadata
    input_stats = {
        "key_count": len(task_input),
        "has_content": "content" in task_input or "message" in task_input,
        "has_files": "file" in task_input or "path" in task_input,
    }

    await memory.store_task_trace(
        task_id=correlation_id,
        phase=PAIPhase.OBSERVE,
        data={
            "agent_type": agent_type,
            "task_type": task_type,
            "started_at": datetime.utcnow().isoformat(),
            "input_stats": input_stats,
            "retrieval_stats": {
                "general_learnings": len(general_learnings),
                "domain_learnings": len(domain_learnings),
                "known_issues": len(known_issues),
                "observations": len(observations),
                "tool_patterns": len(tool_patterns),
                "stack_detected": project_stack is not None,
            },
            "project_stack": project_stack.to_dict() if project_stack else None,
        },
    )

    return {
        "correlation_id": correlation_id,
        # Categorized learnings for structured injection
        "relevant_learnings": all_learnings,
        "known_issues": known_issues,
        "domain_context": domain_learnings,
        "tool_patterns": tool_patterns,
        # Project technology stack
        "project_stack": project_stack,
        # Tracking IDs for feedback loop
        "learning_ids": learning_ids + issue_ids + pattern_ids,
        # Metadata
        "observe_metadata": {
            "total_learnings_retrieved": len(all_learnings),
            "total_issues_retrieved": len(known_issues),
            "total_patterns_retrieved": len(tool_patterns),
            "stack_detected": project_stack is not None,
            "query_length": len(query),
            "parallel_queries": 6,
        },
        "started_at": datetime.utcnow().isoformat(),
    }


def format_observe_context(context: dict[str, Any]) -> str:
    """
    Format OBSERVE context for injection into Claude messages.

    Args:
        context: Context dict from pre_task_hook

    Returns:
        Formatted string for context injection
    """
    sections = []

    # Format project stack (most important - put first)
    stack: ProjectStack | None = context.get("project_stack")
    if stack:
        stack_lines = [f"- Project: {stack.project_name}"]
        if stack.language:
            stack_lines.append(f"- Language: {stack.language}")
        if stack.framework:
            stack_lines.append(f"- Framework: {stack.framework}")
        if stack.database:
            db = stack.database
            db_info = f"- Database: {db.type}"
            if db.version:
                db_info += f" {db.version}"
            if db.container_name:
                db_info += f" (container: {db.container_name})"
            elif db.host and db.host != "localhost":
                db_info += f" ({db.host}:{db.port})"
            stack_lines.append(db_info)
        if stack.uses_docker:
            stack_lines.append(f"- Docker: {len(stack.containers)} containers")
        if stack.package_manager:
            stack_lines.append(f"- Package Manager: {stack.package_manager}")
        sections.append(f"[Project Stack]\n" + "\n".join(stack_lines))

    # Format relevant learnings
    learnings = context.get("relevant_learnings", [])
    if learnings:
        learnings_text = "\n".join(
            f"- {l.get('content', l.get('text', str(l)))[:200]}"
            for l in learnings[:5]
        )
        sections.append(f"[Relevant Context]\n{learnings_text}")

    # Format known issues
    issues = context.get("known_issues", [])
    if issues:
        issues_text = "\n".join(
            f"- {i.get('content', i.get('text', str(i)))[:200]}"
            for i in issues[:3]
        )
        sections.append(f"[Known Issues]\n{issues_text}")

    # Format tool patterns
    patterns = context.get("tool_patterns", [])
    if patterns:
        patterns_text = "\n".join(
            f"- {p.get('content', p.get('text', str(p)))[:150]}"
            for p in patterns[:2]
        )
        sections.append(f"[Tool Patterns]\n{patterns_text}")

    return "\n\n".join(sections) if sections else ""


def format_task_context_for_prompt(
    context: dict[str, Any],
    pai_phase: str | None = None,
    include_telos: bool = True,
) -> dict[str, Any]:
    """
    Format task context for injection into agent system prompts.

    This function prepares context data that can be injected into the
    agent's _session_context for dynamic prompt enhancement.

    Args:
        context: Context dict from pre_task_hook
        pai_phase: Current PAI phase (OBSERVE, THINK, PLAN, BUILD, EXECUTE, VERIFY)
        include_telos: Whether to include TELOS goal context

    Returns:
        Dict with formatted context ready for _session_context injection:
        - warm_learnings: Pre-warmed relevant learnings
        - phase_context: Phase-specific guidance
        - telos_context: Current goals/objectives
        - project_stack: Detected technology stack
    """
    result = {}

    # Include project stack information (critical for infrastructure decisions)
    stack: ProjectStack | None = context.get("project_stack")
    if stack:
        result["project_stack"] = {
            "project_name": stack.project_name,
            "language": stack.language,
            "framework": stack.framework,
            "package_manager": stack.package_manager,
            "uses_docker": stack.uses_docker,
            "containers": stack.containers,
            "database": {
                "type": stack.database.type,
                "version": stack.database.version,
                "host": stack.database.host,
                "port": stack.database.port,
                "database": stack.database.database,
                "container_name": stack.database.container_name,
            } if stack.database else None,
            "detection_sources": stack.detection_sources,
            "confidence": stack.confidence,
        }

    # Format warm learnings for system prompt injection
    learnings = context.get("relevant_learnings", [])
    issues = context.get("known_issues", [])
    patterns = context.get("tool_patterns", [])

    warm_learnings = []
    for learning in learnings[:5]:
        warm_learnings.append({
            "content": learning.get("content", learning.get("text", str(learning)))[:200],
            "category": learning.get("category", "general"),
            "id": learning.get("id"),
        })
    for issue in issues[:3]:
        warm_learnings.append({
            "content": f"[ISSUE] {issue.get('content', issue.get('text', str(issue)))[:180]}",
            "category": "known_issue",
            "id": issue.get("id"),
        })

    result["warm_learnings"] = warm_learnings

    # Format phase-specific context
    if pai_phase:
        phase_guidance = {
            "OBSERVE": "Focus on gathering information. Use search_memory and exploration tools before acting.",
            "THINK": "Analyze the problem. Consider past learnings and potential approaches.",
            "PLAN": "Design your approach. Use spawn_plan_agent for complex tasks.",
            "BUILD": "Implement incrementally. Use aider_code for multi-file changes.",
            "EXECUTE": "Execute tools carefully. Check results after each action.",
            "VERIFY": "Validate results. Store successful patterns as learnings.",
        }
        result["phase_context"] = phase_guidance.get(pai_phase.upper(), "")

    # Add tool pattern recommendations
    if patterns:
        pattern_text = "Recommended patterns:\n" + "\n".join(
            f"- {p.get('content', str(p))[:100]}" for p in patterns[:2]
        )
        if result.get("phase_context"):
            result["phase_context"] += f"\n\n{pattern_text}"
        else:
            result["phase_context"] = pattern_text

    # Add stack-aware guidance for BUILD phase
    if stack and pai_phase and pai_phase.upper() == "BUILD":
        stack_guidance = []
        if stack.database:
            stack_guidance.append(f"Database: Use {stack.database.type} syntax and conventions")
        if stack.framework:
            stack_guidance.append(f"Framework: Follow {stack.framework} patterns")
        if stack_guidance:
            guidance_text = "\n\nProject-specific guidance:\n" + "\n".join(f"- {g}" for g in stack_guidance)
            if result.get("phase_context"):
                result["phase_context"] += guidance_text
            else:
                result["phase_context"] = guidance_text.strip()

    return result
