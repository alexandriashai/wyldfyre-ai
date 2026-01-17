"""
Task management routes.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import TaskStatus, get_logger
from ai_messaging import PubSubManager, RedisClient

from ..database import get_db_session
from ..dependencies import CurrentUserDep, get_redis
from ..schemas import TaskListResponse, TaskResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    status_filter: TaskStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> TaskListResponse:
    """
    List tasks for the current user.
    """
    from ai_db import Task

    # Build query
    query = select(Task).where(Task.user_id == current_user.sub)

    if status_filter:
        query = query.where(Task.status == status_filter)

    # Get total count
    count_query = select(Task.id).where(Task.user_id == current_user.sub)
    if status_filter:
        count_query = count_query.where(Task.status == status_filter)

    # This is a simplified count - in production use func.count()
    count_result = await db.execute(count_query)
    total = len(list(count_result.scalars().all()))

    # Apply pagination
    query = (
        query.order_by(Task.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    tasks = list(result.scalars().all())

    return TaskListResponse(
        tasks=[TaskResponse.model_validate(t) for t in tasks],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> TaskResponse:
    """
    Get task details by ID.
    """
    from ai_db import Task

    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == current_user.sub)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    return TaskResponse.model_validate(task)


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    redis: RedisClient = Depends(get_redis),
) -> dict[str, Any]:
    """
    Request task cancellation.
    """
    from ai_db import Task

    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == current_user.sub)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    # Can only cancel pending or running tasks
    if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel task with status {task.status.value}",
        )

    # Publish cancellation request
    try:
        pubsub = PubSubManager(redis)
        await pubsub.publish(
            channel="system:commands",
            message={
                "command": "cancel_task",
                "task_id": task_id,
                "correlation_id": task.correlation_id,
            },
        )

        # Update status to cancelled
        task.status = TaskStatus.CANCELLED
        await db.flush()

        logger.info("Task cancelled", task_id=task_id)

        return {
            "success": True,
            "message": f"Task {task_id} cancelled",
        }

    except Exception as e:
        logger.error("Failed to cancel task", task_id=task_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {e}",
        )
