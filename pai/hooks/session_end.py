"""
Session end hook - Executed when an agent session ends.

Responsibilities:
- Archive session interactions to memory
- Sync top learnings to TELOS LEARNED.md
- Generate session summary
- Update goal progress based on session work
- Clean up temporary resources
"""

from datetime import datetime, timezone
from typing import Any

from ai_memory import PAIMemory, PAIPhase, TelosManager, get_telos_manager


async def session_end_hook(
    agent_type: str,
    agent_name: str,
    session_id: str,
    memory: PAIMemory | None = None,
    telos: TelosManager | None = None,
    project_id: str | None = None,
    session_stats: dict[str, Any] | None = None,
    task_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Execute session end hook to archive and sync learnings.

    Args:
        agent_type: Type of agent ending the session
        agent_name: Name of the agent instance
        session_id: Session identifier
        memory: PAI memory instance (optional)
        telos: TELOS manager instance (optional)
        project_id: Optional project context
        session_stats: Statistics from the session
        task_results: Results from tasks executed in session

    Returns:
        Dict with:
        - learnings_synced: Count of learnings synced to TELOS
        - session_archived: Whether session was archived
        - summary: Session summary
        - status: Hook execution status
    """
    result = {
        "session_id": session_id,
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "learnings_synced": 0,
        "session_archived": False,
        "summary": "",
        "status": "completed",
    }

    stats = session_stats or {}
    ended_at = datetime.now(timezone.utc)

    # Initialize TELOS manager if not provided
    if telos is None:
        try:
            telos = get_telos_manager()
        except Exception as e:
            result["telos_error"] = str(e)

    # Sync top learnings to TELOS
    if telos and memory:
        try:
            synced_count = await telos.sync_learnings(project_id=project_id, limit=20)
            result["learnings_synced"] = synced_count
        except Exception as e:
            result["sync_error"] = str(e)

    # Generate session summary
    summary_parts = []

    if stats.get("tasks_completed", 0) > 0:
        summary_parts.append(f"Completed {stats['tasks_completed']} tasks")

    if stats.get("tools_used", 0) > 0:
        summary_parts.append(f"Used {stats['tools_used']} tool calls")

    if stats.get("learnings_extracted", 0) > 0:
        summary_parts.append(f"Extracted {stats['learnings_extracted']} learnings")

    if stats.get("errors", 0) > 0:
        summary_parts.append(f"Encountered {stats['errors']} errors")

    result["summary"] = ". ".join(summary_parts) if summary_parts else "Session completed"

    # Archive session to memory
    if memory:
        try:
            # Store session end trace
            await memory.store_task_trace(
                task_id=session_id,
                phase=PAIPhase.VERIFY,
                data={
                    "event": "session_end",
                    "agent_type": agent_type,
                    "agent_name": agent_name,
                    "project_id": project_id,
                    "ended_at": result["ended_at"],
                    "summary": result["summary"],
                    "stats": stats,
                    "learnings_synced": result["learnings_synced"],
                },
            )

            # Promote session traces to WARM memory
            await memory.promote_to_warm(session_id)
            result["session_archived"] = True
        except Exception as e:
            result["archive_error"] = str(e)

    # Extract strategies from successful multi-step tasks
    if telos and task_results:
        successful_tasks = [t for t in task_results if t.get("success", False)]
        for task in successful_tasks:
            traces = task.get("traces", [])
            if len(traces) >= 3:  # Multi-step task
                try:
                    await telos.extract_strategy(traces, project_id)
                except Exception:
                    pass  # Non-critical

    # Update goal progress if any goals were tracked
    if telos and stats.get("goal_updates"):
        for goal_update in stats["goal_updates"]:
            try:
                await telos.update_goal_progress(
                    goal_id=goal_update["goal_id"],
                    progress=goal_update["progress"],
                    project_id=project_id,
                )
            except Exception:
                pass  # Non-critical

    return result


async def archive_session_learnings(
    memory: PAIMemory,
    session_id: str,
    agent_type: str,
    learnings: list[dict[str, Any]],
) -> int:
    """
    Archive learnings from a session to COLD storage.

    Args:
        memory: PAI memory instance
        session_id: Session identifier
        agent_type: Type of agent
        learnings: List of learning dicts to archive

    Returns:
        Number of learnings archived
    """
    from ai_memory import Learning, LearningScope

    archived = 0
    for learning_data in learnings:
        try:
            learning = Learning(
                content=learning_data.get("content", learning_data.get("text", "")),
                phase=PAIPhase(learning_data.get("phase", "learn")),
                category=learning_data.get("category", "session"),
                task_id=session_id,
                agent_type=agent_type,
                confidence=learning_data.get("confidence", 0.8),
                scope=LearningScope.GLOBAL,
                metadata={"session_id": session_id},
            )
            await memory.archive_to_cold(
                learning,
                summary=f"Session {session_id} learning",
            )
            archived += 1
        except Exception:
            continue

    return archived
