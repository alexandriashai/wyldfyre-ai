"""
Post-task hook - Executed after each agent task.

Enhanced with:
- Feedback loop for used learnings (boost/decay)
- Trace-based learning extraction
- Learning consolidation

Responsibilities:
- Extract learnings from task execution using LearningExtractor
- Apply feedback to used learnings based on task outcome
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
    used_learning_ids: list[str] | None = None,
    task_traces: list[dict[str, Any]] | None = None,
    project_id: str | None = None,
    domain_id: str | None = None,
) -> dict[str, Any]:
    """
    Execute post-task hook with enhanced learning extraction and feedback.

    Args:
        agent_type: Type of agent that executed the task
        task_type: Type of task that was executed
        task_result: Task result data
        correlation_id: Task correlation ID
        memory: PAI memory instance
        success: Whether task succeeded
        permission_level: Permission level of the agent (for ACL)
        used_learning_ids: Optional list of learning IDs that were used during task
        task_traces: Optional list of task traces for trace-based extraction
        project_id: Optional project context for scoped learnings
        domain_id: Optional domain context for scoped learnings

    Returns:
        Dict with hook execution results including:
        - learnings_stored: Count of new learnings stored
        - learnings_boosted: Count of learnings boosted (on success)
        - learnings_decayed: Count of learnings decayed (on failure)
    """
    learnings_stored = 0
    learnings_boosted = 0
    learnings_decayed = 0

    # Store task completion in HOT memory
    await memory.store_task_trace(
        task_id=correlation_id,
        phase=PAIPhase.VERIFY,
        data={
            "agent_type": agent_type,
            "task_type": task_type,
            "success": success,
            "completed_at": datetime.utcnow().isoformat(),
            "used_learnings_count": len(used_learning_ids) if used_learning_ids else 0,
        },
    )

    # === Apply feedback to used learnings ===
    if used_learning_ids:
        for learning_id in used_learning_ids:
            try:
                if success:
                    result = await memory.boost_learning(learning_id, amount=0.1)
                    if result:
                        learnings_boosted += 1
                else:
                    result = await memory.decay_learning(learning_id, amount=0.05)
                    if result:
                        learnings_decayed += 1
            except Exception:
                # Silently continue if individual feedback fails
                pass

    # === Use LearningExtractor for automatic extraction from result ===
    extracted_learnings = _extractor.extract_from_result(
        task_id=correlation_id,
        result=task_result,
        agent_type=agent_type,
        permission_level=permission_level,
    )

    # === Extract from task traces if provided ===
    if task_traces:
        trace_learnings = _extractor.extract_from_traces(
            traces=task_traces,
            task_id=correlation_id,
            agent_type=agent_type,
            permission_level=permission_level,
        )
        extracted_learnings.extend(trace_learnings)

    # === Consolidate to avoid redundancy ===
    if len(extracted_learnings) > 1:
        extracted_learnings = _extractor.consolidate_learnings(
            extracted_learnings,
            similarity_threshold=0.85,
        )

    # Store each extracted learning with scope
    for learning in extracted_learnings:
        # Apply project/domain scope if provided
        if domain_id:
            learning.scope = "domain"
            learning.domain_id = domain_id
        elif project_id:
            learning.scope = "project"
            learning.project_id = project_id

        await memory.store_learning(learning, agent_type=agent_type)
        learnings_stored += 1

    # === Handle explicit learnings in the old format (backward compatibility) ===
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
                project_id=project_id,
                domain_id=domain_id,
            )
            await memory.store_learning(learning, agent_type=agent_type)
            learnings_stored += 1

    # === Store error learnings for failed tasks (if not already captured) ===
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
                project_id=project_id,
                domain_id=domain_id,
            )
            await memory.store_learning(learning, agent_type=agent_type)
            learnings_stored += 1

    # === Store LEARN phase trace ===
    await memory.store_task_trace(
        task_id=correlation_id,
        phase=PAIPhase.LEARN,
        data={
            "agent_type": agent_type,
            "task_type": task_type,
            "learnings_stored": learnings_stored,
            "learnings_boosted": learnings_boosted,
            "learnings_decayed": learnings_decayed,
            "feedback_applied": bool(used_learning_ids),
        },
    )

    # Promote task traces to WARM memory
    await memory.promote_to_warm(correlation_id)

    return {
        "learnings_stored": learnings_stored,
        "learnings_boosted": learnings_boosted,
        "learnings_decayed": learnings_decayed,
        "feedback_applied": bool(used_learning_ids),
    }


async def analyze_execution_result(
    memory: Any,
    tool_name: str,
    tool_arguments: dict[str, Any],
    result: dict[str, Any],
    task_id: str,
    agent_type: str,
    learnings_used: list[str] | None = None,
    permission_level: int = 1,
) -> list[Learning]:
    """
    Analyze a tool execution result for mid-execution learning.

    Called after each tool execution to extract immediate learnings
    and apply feedback to learnings that were used.

    Args:
        memory: PAI memory instance
        tool_name: Name of the executed tool
        tool_arguments: Arguments passed to the tool
        result: Tool execution result
        task_id: Current task ID
        agent_type: Type of agent
        learnings_used: IDs of learnings that informed this tool use
        permission_level: Permission level for ACL

    Returns:
        List of Learning objects extracted from the result
    """
    learnings = []
    success = result.get("success", True)

    # Extract learnings from tool result
    tool_learnings = _extractor.extract_from_tool_result(
        tool_name=tool_name,
        tool_arguments=tool_arguments,
        result=result,
        task_id=task_id,
        agent_type=agent_type,
        permission_level=permission_level,
    )

    # Store extracted learnings
    for learning in tool_learnings:
        doc_id = await memory.store_learning(learning, agent_type=agent_type)
        if doc_id:
            learnings.append(learning)

    # Apply feedback to learnings that were used for this tool call
    if learnings_used:
        for learning_id in learnings_used:
            try:
                if success:
                    await memory.boost_learning(learning_id, 0.1)
                else:
                    await memory.decay_learning(learning_id, 0.05)
            except Exception:
                pass

    return learnings


def is_notable_result(result: dict[str, Any]) -> bool:
    """
    Check if a tool result is notable enough for learning extraction.

    Args:
        result: Tool execution result

    Returns:
        True if the result should be analyzed for learnings
    """
    # Always analyze errors
    if not result.get("success", True) or result.get("error"):
        return True

    # Check output for notable patterns
    output = str(result.get("output", ""))

    # Skip empty or very short outputs
    if len(output) < 20:
        return False

    # Notable if output contains learning indicators
    notable_indicators = [
        "created", "updated", "deleted", "modified",
        "success", "complete", "found", "discovered",
        "error", "warning", "failed", "issue",
    ]

    output_lower = output.lower()
    return any(indicator in output_lower for indicator in notable_indicators)
