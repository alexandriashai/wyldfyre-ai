"""
Post-task hook - Executed after each agent task.

Responsibilities:
- Extract learnings from task execution using LearningExtractor
- Store results in memory
- Update metrics
- Trigger learning synthesis
"""

from datetime import datetime
from typing import Any

from ai_memory import Learning, PAIPhase
from ai_memory.learning_extractor import LearningExtractor


# Global extractor instance
_extractor = LearningExtractor()


async def post_task_hook(
    agent_type: str,
    task_type: str,
    task_result: dict[str, Any],
    correlation_id: str,
    memory: Any,  # PAIMemory instance
    success: bool = True,
    permission_level: int = 1,
) -> dict[str, Any]:
    """
    Execute post-task hook with automatic learning extraction.

    Args:
        agent_type: Type of agent that executed the task
        task_type: Type of task that was executed
        task_result: Task result data
        correlation_id: Task correlation ID
        memory: PAI memory instance
        success: Whether task succeeded
        permission_level: Permission level of the agent (for ACL)

    Returns:
        Dict with hook execution results
    """
    learnings_stored = 0

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

    # Use LearningExtractor for automatic extraction
    extracted_learnings = _extractor.extract_from_result(
        task_id=correlation_id,
        result=task_result,
        agent_type=agent_type,
        permission_level=permission_level,
    )

    # Store each extracted learning
    for learning in extracted_learnings:
        await memory.store_learning(learning, agent_type=agent_type)
        learnings_stored += 1

    # Also handle explicit learnings in the old format for backward compatibility
    if success and "learnings" in task_result:
        for learning_data in task_result["learnings"]:
            # Skip if already processed by extractor (check content match)
            content = learning_data.get("content", "") if isinstance(learning_data, dict) else str(learning_data)
            if any(l.content == content for l in extracted_learnings):
                continue

            learning = Learning(
                content=content,
                phase=PAIPhase(learning_data.get("phase", "learn")) if isinstance(learning_data, dict) else PAIPhase.LEARN,
                category=learning_data.get("category", task_type) if isinstance(learning_data, dict) else task_type,
                task_id=correlation_id,
                agent_type=agent_type,
                confidence=learning_data.get("confidence", 0.8) if isinstance(learning_data, dict) else 0.8,
                created_by_agent=agent_type,
                permission_level=permission_level,
            )
            await memory.store_learning(learning, agent_type=agent_type)
            learnings_stored += 1

    # Store error learnings for failed tasks (if not already captured by extractor)
    if not success and "error" in task_result:
        error_content = f"Task {task_type} failed: {task_result['error']}"
        if not any(l.content == error_content for l in extracted_learnings):
            learning = Learning(
                content=error_content,
                phase=PAIPhase.LEARN,
                category="error",
                task_id=correlation_id,
                agent_type=agent_type,
                confidence=0.9,
                metadata={"error_type": task_result.get("error_type", "unknown")},
                created_by_agent=agent_type,
                permission_level=permission_level,
            )
            await memory.store_learning(learning, agent_type=agent_type)
            learnings_stored += 1

    # Promote task traces to WARM memory
    await memory.promote_to_warm(correlation_id)

    return {"learnings_stored": learnings_stored}
