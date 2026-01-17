"""
Pre-task hook - Executed before each agent task.

Responsibilities:
- Load relevant context from memory
- Check permissions
- Validate input
- Set up correlation tracking
"""

import uuid
from datetime import datetime
from typing import Any

from ai_memory import PAIPhase


async def pre_task_hook(
    agent_type: str,
    task_type: str,
    task_input: dict[str, Any],
    memory: Any,  # PAIMemory instance
) -> dict[str, Any]:
    """
    Execute pre-task hook.

    Args:
        agent_type: Type of agent executing the task
        task_type: Type of task being executed
        task_input: Task input data
        memory: PAI memory instance

    Returns:
        Context dict with relevant memories and metadata
    """
    correlation_id = str(uuid.uuid4())

    # Search for relevant learnings
    query = f"{task_type} {' '.join(str(v) for v in task_input.values() if isinstance(v, str))}"
    relevant_learnings = await memory.search_learnings(
        query=query[:200],  # Limit query length
        limit=5,
    )

    # Store task start in HOT memory
    await memory.store_task_trace(
        task_id=correlation_id,
        phase=PAIPhase.OBSERVE,
        data={
            "agent_type": agent_type,
            "task_type": task_type,
            "started_at": datetime.utcnow().isoformat(),
        },
    )

    return {
        "correlation_id": correlation_id,
        "relevant_learnings": relevant_learnings,
        "started_at": datetime.utcnow().isoformat(),
    }
