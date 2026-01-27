"""
Session start hook - Executed when an agent session begins.

Responsibilities:
- Load TELOS context (mission, goals, strategies)
- Warm up memory caches
- Initialize status line
- Verify agent permissions
- Load relevant project context
"""

from datetime import datetime, timezone
from typing import Any

from ai_memory import PAIMemory, TelosManager, get_telos_manager


async def session_start_hook(
    agent_type: str,
    agent_name: str,
    session_id: str,
    memory: PAIMemory | None = None,
    telos: TelosManager | None = None,
    project_id: str | None = None,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Execute session start hook to prepare agent context.

    Args:
        agent_type: Type of agent starting the session
        agent_name: Name of the agent instance
        session_id: Unique session identifier
        memory: PAI memory instance (optional)
        telos: TELOS manager instance (optional)
        project_id: Optional project context
        user_id: Optional user identifier
        metadata: Additional session metadata

    Returns:
        Context dict with:
        - telos_context: Loaded TELOS context
        - warm_learnings: Pre-loaded relevant learnings
        - session_metadata: Session tracking metadata
        - status: Session initialization status
    """
    result = {
        "session_id": session_id,
        "agent_type": agent_type,
        "agent_name": agent_name,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "telos_context": "",
        "warm_learnings": [],
        "project_id": project_id,
        "status": "initialized",
    }

    # Initialize TELOS manager if not provided
    if telos is None:
        try:
            telos = get_telos_manager()
            await telos.initialize()
        except Exception as e:
            result["telos_error"] = str(e)

    # Load TELOS context (including agent-specific MODELS and STRATEGIES)
    if telos:
        try:
            # Determine task type for relevance filtering
            task_type = metadata.get("task_type", "default") if metadata else "default"
            telos_context = await telos.get_context_for_task(
                task_type,
                project_id=project_id,
                agent_type=agent_type,
            )
            result["telos_context"] = telos_context
        except Exception as e:
            result["telos_error"] = str(e)

    # Pre-warm memory with recent learnings
    if memory:
        try:
            # Search for recent high-utility learnings
            warm_learnings = await memory.search_learnings(
                query=f"{agent_type} session startup context",
                limit=5,
                agent_type=agent_type,
                permission_level=4,
                project_id=project_id,
            )
            result["warm_learnings"] = warm_learnings
            result["learnings_count"] = len(warm_learnings)
        except Exception as e:
            result["memory_error"] = str(e)
            result["learnings_count"] = 0

    # Store session start in HOT memory for tracking
    if memory:
        try:
            from ai_memory import PAIPhase
            await memory.store_task_trace(
                task_id=session_id,
                phase=PAIPhase.OBSERVE,
                data={
                    "event": "session_start",
                    "agent_type": agent_type,
                    "agent_name": agent_name,
                    "project_id": project_id,
                    "user_id": user_id,
                    "started_at": result["started_at"],
                    "telos_loaded": bool(result["telos_context"]),
                    "learnings_preloaded": result.get("learnings_count", 0),
                },
            )
        except Exception:
            pass  # Non-critical

    result["status"] = "ready"
    return result


def format_session_context(context: dict[str, Any]) -> str:
    """
    Format session context for injection into agent system prompt.

    Args:
        context: Context dict from session_start_hook

    Returns:
        Formatted context string
    """
    parts = []

    # Include TELOS context
    if context.get("telos_context"):
        parts.append(f"[TELOS Context]\n{context['telos_context']}")

    # Include pre-warmed learnings
    learnings = context.get("warm_learnings", [])
    if learnings:
        learnings_text = "\n".join(
            f"- {l.get('content', l.get('text', str(l)))[:150]}"
            for l in learnings[:3]
        )
        parts.append(f"[Session Learnings]\n{learnings_text}")

    # Include project context if available
    if context.get("project_id"):
        parts.append(f"[Project] {context['project_id']}")

    return "\n\n".join(parts) if parts else ""
