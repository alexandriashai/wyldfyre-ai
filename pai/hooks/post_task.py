"""
Post-task hook - Executed after each agent task.

Responsibilities:
- Extract learnings from task execution
- Store results in memory
- Update metrics
- Trigger learning synthesis
"""

from datetime import datetime
from typing import Any

from ai_memory import Learning, PAIPhase


async def post_task_hook(
    agent_type: str,
    task_type: str,
    task_result: dict[str, Any],
    correlation_id: str,
    memory: Any,  # PAIMemory instance
    success: bool = True,
) -> None:
    """
    Execute post-task hook.

    Args:
        agent_type: Type of agent that executed the task
        task_type: Type of task that was executed
        task_result: Task result data
        correlation_id: Task correlation ID
        memory: PAI memory instance
        success: Whether task succeeded
    """
    # Store task completion in HOT memory
    await memory.store_task_trace(
        task_id=correlation_id,
        phase=PAIPhase.VERIFY,
        data={
            "agent_type": agent_type,
            "task_type": task_type,
            "success": success,
            "completed_at": datetime.utcnow().isoformat(),
        },
    )

    # Extract and store learnings
    if success and "learnings" in task_result:
        for learning_data in task_result["learnings"]:
            learning = Learning(
                content=learning_data.get("content", ""),
                phase=PAIPhase(learning_data.get("phase", "learn")),
                category=learning_data.get("category", task_type),
                task_id=correlation_id,
                agent_type=agent_type,
                confidence=learning_data.get("confidence", 0.8),
            )
            await memory.store_learning(learning)

    # Store error learnings for failed tasks
    if not success and "error" in task_result:
        learning = Learning(
            content=f"Task {task_type} failed: {task_result['error']}",
            phase=PAIPhase.LEARN,
            category="error",
            task_id=correlation_id,
            agent_type=agent_type,
            confidence=0.9,
            metadata={"error_type": task_result.get("error_type", "unknown")},
        )
        await memory.store_learning(learning)

    # Promote task traces to WARM memory
    await memory.promote_to_warm(correlation_id)
