"""
Plan CRUD routes.

Provides full plan management with list, view, edit, delete, clone, follow-up, and AI modify.
"""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ai_core import get_logger
from ai_messaging import PubSubManager, RedisClient

from ..dependencies import CurrentUserDep, RedisDep, get_redis
from ..plan_mode import Plan, PlanManager, PlanStatus, StepStatus
from ..schemas.plans import (
    PlanCloneRequest,
    PlanDetailResponse,
    PlanFollowUpRequest,
    PlanHistoryEntry,
    PlanHistoryResponse,
    PlanListItem,
    PlanListResponse,
    PlanModifyRequest,
    PlanOperationResponse,
    PlanUpdate as PlanCRUDUpdate,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/plans", tags=["Plans"])


async def _scan_user_plans(redis: RedisClient, user_id: str) -> list[dict]:
    """Scan Redis for all plans belonging to a user."""
    plans = []
    cursor = 0

    while True:
        cursor, keys = await redis.scan(cursor=cursor, match="plan:*", count=100)
        for key in keys:
            # Skip history keys (they are LISTs, not strings)
            if ":history" in key:
                continue
            plan_data = await redis.get(key)
            if plan_data:
                try:
                    plan = json.loads(plan_data)
                    if plan.get("user_id") == user_id:
                        plans.append(plan)
                except json.JSONDecodeError:
                    continue
        if cursor == 0:
            break

    return plans


async def _get_plan_history(redis: RedisClient, plan_id: str) -> list[dict]:
    """Get modification history for a plan."""
    history_key = f"plan:{plan_id}:history"
    history_data = await redis.lrange(history_key, 0, -1)
    entries = []
    for entry in history_data or []:
        try:
            entries.append(json.loads(entry))
        except json.JSONDecodeError:
            continue
    return entries


async def _add_history_entry(
    redis: RedisClient,
    plan_id: str,
    action: str,
    changes: dict,
    actor: str | None = None,
    details: str | None = None,
) -> None:
    """Add an entry to plan modification history."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "changes": changes,
        "actor": actor,
        "details": details,
    }
    history_key = f"plan:{plan_id}:history"
    await redis.lpush(history_key, json.dumps(entry))
    # Keep last 100 entries
    await redis.ltrim(history_key, 0, 99)


@router.get("", response_model=PlanListResponse)
async def list_plans(
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
    status_filter: str | None = Query(None, alias="status", description="Filter by status: active, paused, completed, failed, stuck, all"),
    project_id: str | None = Query(None, description="Filter by project"),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
) -> PlanListResponse:
    """
    List all plans for the current user with optional filters.

    Status filters:
    - active: executing or approved plans
    - paused: paused plans
    - completed: completed plans
    - failed: failed plans
    - stuck: paused or failed plans with partial progress
    - all: no filter (default)
    """
    # Scan all plans for this user
    all_plans = await _scan_user_plans(redis, current_user.sub)

    # Apply status filter
    status_map = {
        "active": ["executing", "approved"],
        "paused": ["paused"],
        "completed": ["completed"],
        "failed": ["failed"],
        "stuck": ["paused", "failed"],
        "all": None,
    }

    filter_statuses = status_map.get(status_filter or "all")

    filtered_plans = []
    for plan in all_plans:
        plan_status = plan.get("status", "")

        # Apply project filter
        if project_id and plan.get("project_id") != project_id:
            continue

        # Apply status filter
        if filter_statuses:
            if plan_status not in filter_statuses:
                continue

            # For "stuck" filter, also require partial progress
            if status_filter == "stuck":
                steps = plan.get("steps", [])
                completed = sum(1 for s in steps if s.get("status") == "completed")
                if completed == 0:
                    continue

        filtered_plans.append(plan)

    # Sort by created_at descending
    filtered_plans.sort(
        key=lambda p: p.get("created_at", ""),
        reverse=True,
    )

    # Apply pagination
    total = len(filtered_plans)
    paginated = filtered_plans[offset:offset + limit]

    return PlanListResponse(
        plans=[PlanListItem.from_plan(p) for p in paginated],
        total=total,
        offset=offset,
        limit=limit,
        filter_status=status_filter,
    )


@router.get("/{plan_id}", response_model=PlanDetailResponse)
async def get_plan(
    plan_id: str,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
    include_history: bool = Query(False, description="Include modification history"),
) -> PlanDetailResponse:
    """
    Get full plan details including step progress and todos.
    """
    plan_manager = PlanManager(redis)
    plan = await plan_manager.get_plan(plan_id)

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {plan_id} not found",
        )

    if plan.user_id != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return PlanDetailResponse.from_plan(plan.to_dict())


@router.patch("/{plan_id}", response_model=PlanOperationResponse)
async def update_plan(
    plan_id: str,
    request: PlanCRUDUpdate,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> PlanOperationResponse:
    """
    Update plan title, description, or steps.

    Note: Cannot update steps while plan is executing.
    """
    plan_manager = PlanManager(redis)
    plan = await plan_manager.get_plan(plan_id)

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {plan_id} not found",
        )

    if plan.user_id != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Cannot modify steps while executing
    if request.steps is not None and plan.status == PlanStatus.EXECUTING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot modify steps while plan is executing",
        )

    changes = {}

    if request.title is not None:
        changes["title"] = {"old": plan.title, "new": request.title}
        plan.title = request.title

    if request.description is not None:
        changes["description"] = {"old": plan.description, "new": request.description}
        plan.description = request.description

    if request.steps is not None:
        changes["steps"] = {"count": len(request.steps)}
        await plan_manager.set_steps(plan_id, request.steps)
        # Reload plan after step update
        plan = await plan_manager.get_plan(plan_id)

    if request.metadata is not None:
        changes["metadata"] = request.metadata
        plan.metadata.update(request.metadata)

    # Save changes
    await plan_manager._save_plan(plan)

    # Record history
    await _add_history_entry(
        redis,
        plan_id,
        "manual_edit",
        changes,
        actor="user",
    )

    logger.info(
        "Plan updated",
        plan_id=plan_id,
        user_id=current_user.sub,
        changes=list(changes.keys()),
    )

    return PlanOperationResponse(
        success=True,
        plan_id=plan_id,
        message="Plan updated successfully",
        plan=PlanDetailResponse.from_plan(plan.to_dict()),
    )


@router.delete("/{plan_id}")
async def delete_plan(
    plan_id: str,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> dict[str, str]:
    """
    Delete a plan.

    Note: Cannot delete plans that are currently executing.
    """
    plan_manager = PlanManager(redis)
    plan = await plan_manager.get_plan(plan_id)

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {plan_id} not found",
        )

    if plan.user_id != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    if plan.status == PlanStatus.EXECUTING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a plan that is currently executing. Pause or cancel it first.",
        )

    # Delete plan from Redis
    await redis.delete(f"plan:{plan_id}")
    await redis.delete(f"plan:{plan_id}:history")

    # Remove from conversation active plan reference
    if plan.conversation_id:
        await redis.delete(f"conversation:{plan.conversation_id}:active_plan")

    logger.info(
        "Plan deleted",
        plan_id=plan_id,
        user_id=current_user.sub,
    )

    return {"message": f"Plan {plan_id} deleted"}


@router.get("/{plan_id}/history", response_model=PlanHistoryResponse)
async def get_plan_history(
    plan_id: str,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
    limit: int = Query(50, le=100),
) -> PlanHistoryResponse:
    """
    Get modification history for a plan.
    """
    plan_manager = PlanManager(redis)
    plan = await plan_manager.get_plan(plan_id)

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {plan_id} not found",
        )

    if plan.user_id != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    history = await _get_plan_history(redis, plan_id)

    return PlanHistoryResponse(
        plan_id=plan_id,
        entries=[PlanHistoryEntry(**h) for h in history[:limit]],
        total_entries=len(history),
    )


@router.post("/{plan_id}/clone", response_model=PlanOperationResponse)
async def clone_plan(
    plan_id: str,
    request: PlanCloneRequest,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> PlanOperationResponse:
    """
    Clone an existing plan as a new draft.

    Useful for using completed plans as templates.
    """
    plan_manager = PlanManager(redis)
    plan = await plan_manager.get_plan(plan_id)

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {plan_id} not found",
        )

    if plan.user_id != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Create new plan as copy
    new_plan = Plan(
        id=str(uuid4()),
        conversation_id=plan.conversation_id,
        user_id=current_user.sub,
        title=request.new_title or f"{plan.title} (Copy)",
        description=plan.description,
        status=PlanStatus.PENDING,
        metadata=plan.metadata.copy(),
        exploration_notes=plan.exploration_notes.copy(),
        files_explored=plan.files_explored.copy(),
        project_id=plan.project_id,  # Inherit project from original
    )

    # Copy steps with optional status reset
    for step in plan.steps:
        from ..plan_mode import PlanStep

        new_step = PlanStep(
            id=str(uuid4()),
            order=step.order,
            title=step.title,
            description=step.description,
            status=StepStatus.PENDING if request.reset_status else step.status,
            agent=step.agent,
            estimated_duration=step.estimated_duration,
            dependencies=[],  # Reset dependencies for new plan
        )
        new_plan.steps.append(new_step)

    # Save new plan
    await plan_manager._save_plan(new_plan)

    # Record history for new plan
    await _add_history_entry(
        redis,
        new_plan.id,
        "created",
        {"cloned_from": plan_id},
        actor="user",
    )

    logger.info(
        "Plan cloned",
        original_plan_id=plan_id,
        new_plan_id=new_plan.id,
        user_id=current_user.sub,
    )

    return PlanOperationResponse(
        success=True,
        plan_id=new_plan.id,
        message=f"Plan cloned from {plan_id}",
        plan=PlanDetailResponse.from_plan(new_plan.to_dict()),
    )


@router.post("/{plan_id}/follow-up", response_model=PlanOperationResponse)
async def follow_up_plan(
    plan_id: str,
    request: PlanFollowUpRequest,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> PlanOperationResponse:
    """
    Resume a stuck or paused plan with AI analysis.

    The supervisor will analyze what went wrong and suggest how to proceed.
    """
    plan_manager = PlanManager(redis)
    plan = await plan_manager.get_plan(plan_id)

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {plan_id} not found",
        )

    if plan.user_id != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Only allow follow-up on paused or failed plans
    if plan.status not in (PlanStatus.PAUSED, PlanStatus.FAILED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot follow up on plan with status: {plan.status.value}. Plan must be paused or failed.",
        )

    # Publish follow-up task to supervisor
    pubsub = PubSubManager(redis)
    await pubsub.start()

    try:
        task = {
            "type": "task_request",
            "task_type": "plan_follow_up",
            "user_id": current_user.sub,
            "payload": {
                "plan_id": plan_id,
                "plan": plan.to_dict(),
                "context": request.context,
                "action": request.action,
                "conversation_id": plan.conversation_id,
            },
        }
        await pubsub.publish("agent:supervisor:tasks", task)

        logger.info(
            "Plan follow-up requested",
            plan_id=plan_id,
            user_id=current_user.sub,
            action=request.action,
        )
    finally:
        await pubsub.stop()

    # Record history
    await _add_history_entry(
        redis,
        plan_id,
        "follow_up_requested",
        {"action": request.action, "context": request.context},
        actor="user",
    )

    return PlanOperationResponse(
        success=True,
        plan_id=plan_id,
        message="Follow-up analysis started. The supervisor will analyze and resume the plan.",
        plan=PlanDetailResponse.from_plan(plan.to_dict()),
    )


@router.post("/{plan_id}/modify", response_model=PlanOperationResponse)
async def modify_plan_with_ai(
    plan_id: str,
    request: PlanModifyRequest,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> PlanOperationResponse:
    """
    Have the supervisor modify the plan based on a natural language request.

    Example requests:
    - "Add a testing step after implementation"
    - "Remove the deployment step"
    - "Reorder steps to do database changes first"
    """
    plan_manager = PlanManager(redis)
    plan = await plan_manager.get_plan(plan_id)

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {plan_id} not found",
        )

    if plan.user_id != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Cannot modify while executing
    if plan.status == PlanStatus.EXECUTING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot modify plan while it is executing. Pause it first.",
        )

    # Publish modification task to supervisor
    pubsub = PubSubManager(redis)
    await pubsub.start()

    try:
        task = {
            "type": "task_request",
            "task_type": "plan_modify",
            "user_id": current_user.sub,
            "payload": {
                "plan_id": plan_id,
                "plan": plan.to_dict(),
                "modification_request": request.request,
                "constraints": request.constraints,
                "conversation_id": plan.conversation_id,
            },
        }
        await pubsub.publish("agent:supervisor:tasks", task)

        logger.info(
            "Plan modification requested",
            plan_id=plan_id,
            user_id=current_user.sub,
            request=request.request[:100],
        )
    finally:
        await pubsub.stop()

    # Record history
    await _add_history_entry(
        redis,
        plan_id,
        "ai_modify_requested",
        {"request": request.request, "constraints": request.constraints},
        actor="user",
    )

    return PlanOperationResponse(
        success=True,
        plan_id=plan_id,
        message="Modification request sent to supervisor. The plan will be updated shortly.",
        plan=PlanDetailResponse.from_plan(plan.to_dict()),
    )


@router.post("/{plan_id}/pause", response_model=PlanOperationResponse)
async def pause_plan(
    plan_id: str,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> PlanOperationResponse:
    """
    Pause a running plan.
    """
    plan_manager = PlanManager(redis)
    plan = await plan_manager.get_plan(plan_id)

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {plan_id} not found",
        )

    if plan.user_id != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    if plan.status != PlanStatus.EXECUTING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot pause plan with status: {plan.status.value}",
        )

    await plan_manager.pause_execution(plan_id)

    # Reload plan
    plan = await plan_manager.get_plan(plan_id)

    # Record history
    await _add_history_entry(
        redis,
        plan_id,
        "status_change",
        {"old_status": "executing", "new_status": "paused"},
        actor="user",
    )

    return PlanOperationResponse(
        success=True,
        plan_id=plan_id,
        message="Plan paused",
        plan=PlanDetailResponse.from_plan(plan.to_dict()),
    )


@router.post("/{plan_id}/resume", response_model=PlanOperationResponse)
async def resume_plan(
    plan_id: str,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> PlanOperationResponse:
    """
    Resume a paused plan.
    """
    plan_manager = PlanManager(redis)
    plan = await plan_manager.get_plan(plan_id)

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {plan_id} not found",
        )

    if plan.user_id != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    if plan.status != PlanStatus.PAUSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resume plan with status: {plan.status.value}",
        )

    await plan_manager.resume_execution(plan_id)

    # Trigger execution via supervisor
    pubsub = PubSubManager(redis)
    await pubsub.start()

    try:
        await pubsub.publish(
            "agent:supervisor:tasks",
            {
                "type": "task_request",
                "task_type": "execute_plan",
                "user_id": current_user.sub,
                "payload": {
                    "plan_id": plan_id,
                    "conversation_id": plan.conversation_id,
                    "user_id": current_user.sub,
                    "resume": True,
                },
            },
        )
    finally:
        await pubsub.stop()

    # Reload plan
    plan = await plan_manager.get_plan(plan_id)

    # Record history
    await _add_history_entry(
        redis,
        plan_id,
        "status_change",
        {"old_status": "paused", "new_status": "executing"},
        actor="user",
    )

    return PlanOperationResponse(
        success=True,
        plan_id=plan_id,
        message="Plan resumed",
        plan=PlanDetailResponse.from_plan(plan.to_dict()),
    )
