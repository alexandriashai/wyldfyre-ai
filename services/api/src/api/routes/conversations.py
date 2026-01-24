"""
Conversation management routes.

Conversations are now persisted to the database while maintaining Redis caching
for fast message retrieval.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import get_logger
from database.models import Conversation, ConversationStatus, PlanStatus
from ai_messaging import RedisClient

from ..database import get_db_session
from ..dependencies import CurrentUserDep, RedisDep, get_redis
from ..schemas.conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
    ConversationWithMessagesResponse,
    MessageResponse,
    PlanUpdate,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    redis: RedisClient = Depends(get_redis),
    project_id: str | None = Query(None, description="Filter by project"),
    domain_id: str | None = Query(None, description="Filter by domain"),
    status_filter: ConversationStatus | None = Query(None, alias="status"),
    search: str | None = Query(None, description="Search in title"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> ConversationListResponse:
    """
    List conversations for the current user with optional filters.
    """
    # Build query
    query = select(Conversation).where(Conversation.user_id == current_user.sub)

    if project_id:
        query = query.where(Conversation.project_id == project_id)

    if domain_id:
        query = query.where(Conversation.domain_id == domain_id)

    if status_filter:
        query = query.where(Conversation.status == status_filter)
    else:
        # Default to exclude deleted
        query = query.where(Conversation.status != ConversationStatus.DELETED)

    if search:
        query = query.where(Conversation.title.ilike(f"%{search}%"))

    # Get total count
    count_query = select(func.count(Conversation.id)).where(
        Conversation.user_id == current_user.sub
    )
    if project_id:
        count_query = count_query.where(Conversation.project_id == project_id)
    if domain_id:
        count_query = count_query.where(Conversation.domain_id == domain_id)
    if status_filter:
        count_query = count_query.where(Conversation.status == status_filter)
    else:
        count_query = count_query.where(Conversation.status != ConversationStatus.DELETED)
    if search:
        count_query = count_query.where(Conversation.title.ilike(f"%{search}%"))

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Apply pagination and ordering
    query = (
        query.order_by(Conversation.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    conversations = list(result.scalars().all())

    return ConversationListResponse(
        conversations=[ConversationResponse.model_validate(c) for c in conversations],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: ConversationCreate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    redis: RedisClient = Depends(get_redis),
) -> ConversationResponse:
    """
    Create a new conversation.

    Persists to database and creates Redis cache entry.
    """
    # Create in database
    conversation = Conversation(
        title=request.title or "New Conversation",
        user_id=current_user.sub,
        project_id=request.project_id,
        domain_id=request.domain_id,
    )

    db.add(conversation)
    await db.flush()
    await db.refresh(conversation)

    # Also store in Redis for fast access
    conv_key = f"conversation:{conversation.id}"
    now = datetime.now(timezone.utc).isoformat()
    await redis.hset(
        conv_key,
        mapping={
            "id": conversation.id,
            "user_id": current_user.sub,
            "title": conversation.title or "",
            "project_id": request.project_id or "",
            "domain_id": request.domain_id or "",
            "created_at": now,
            "updated_at": now,
            "message_count": "0",
        },
    )

    # Add to user's conversation list
    conv_list_key = f"user:{current_user.sub}:conversations"
    await redis.lpush(conv_list_key, conversation.id)

    logger.info(
        "Conversation created",
        conversation_id=conversation.id,
        user_id=current_user.sub,
        project_id=request.project_id,
    )

    return ConversationResponse.model_validate(conversation)


@router.get("/{conversation_id}", response_model=ConversationWithMessagesResponse)
async def get_conversation(
    conversation_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    redis: RedisClient = Depends(get_redis),
    message_limit: int = Query(100, ge=1, le=500),
) -> ConversationWithMessagesResponse:
    """
    Get conversation with message history.

    Conversation metadata comes from DB, messages from Redis.
    """
    # Get conversation from DB
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.sub,
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    # Get messages from Redis
    messages_key = f"conversation:{conversation_id}:messages"
    message_ids = await redis.lrange(messages_key, 0, message_limit - 1)

    messages = []
    for msg_id in message_ids or []:
        msg_key = f"message:{msg_id}"
        msg_data = await redis.hgetall(msg_key)
        if msg_data:
            messages.append({
                "id": msg_id,
                "role": msg_data.get("role", "user"),
                "content": msg_data.get("content", ""),
                "agent": msg_data.get("agent"),
                "timestamp": msg_data.get("timestamp", ""),
            })

    return ConversationWithMessagesResponse(
        conversation=ConversationResponse.model_validate(conversation),
        messages=messages,
    )


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    request: ConversationUpdate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    redis: RedisClient = Depends(get_redis),
) -> ConversationResponse:
    """
    Update a conversation.
    """
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.sub,
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(conversation, field, value)

    await db.flush()
    await db.refresh(conversation)

    # Update Redis cache
    conv_key = f"conversation:{conversation_id}"
    if request.title is not None:
        await redis.hset(conv_key, "title", request.title)
    if request.project_id is not None:
        await redis.hset(conv_key, "project_id", request.project_id)
    if request.domain_id is not None:
        await redis.hset(conv_key, "domain_id", request.domain_id)

    logger.info(
        "Conversation updated",
        conversation_id=conversation_id,
        user_id=current_user.sub,
    )

    return ConversationResponse.model_validate(conversation)


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
    redis: RedisClient = Depends(get_redis),
) -> dict[str, str]:
    """
    Delete a conversation (soft delete - marks as DELETED).
    """
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.sub,
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    # Soft delete in DB
    conversation.status = ConversationStatus.DELETED
    await db.flush()

    # Clean up Redis
    messages_key = f"conversation:{conversation_id}:messages"
    message_ids = await redis.lrange(messages_key, 0, -1)
    for msg_id in message_ids or []:
        await redis.delete(f"message:{msg_id}")
    await redis.delete(messages_key)
    await redis.delete(f"conversation:{conversation_id}")

    # Remove from user's list
    conv_list_key = f"user:{current_user.sub}:conversations"
    await redis.lrem(conv_list_key, 0, conversation_id)

    logger.info(
        "Conversation deleted",
        conversation_id=conversation_id,
        user_id=current_user.sub,
    )

    return {"message": f"Conversation {conversation_id} deleted"}


# --- Plan Management Endpoints (Claude CLI Style) ---


@router.get("/{conversation_id}/plan")
async def get_conversation_plan(
    conversation_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    Get the current plan for a conversation.
    """
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.sub,
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    return {
        "conversation_id": conversation_id,
        "plan_content": conversation.plan_content,
        "plan_status": conversation.plan_status.value if conversation.plan_status else None,
        "plan_approved_at": conversation.plan_approved_at.isoformat() if conversation.plan_approved_at else None,
    }


@router.put("/{conversation_id}/plan")
async def update_conversation_plan(
    conversation_id: str,
    request: PlanUpdate,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    Update the plan for a conversation.

    Used by agents to submit plans for approval.
    """
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.sub,
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    conversation.plan_content = request.plan_content
    conversation.plan_status = request.plan_status

    await db.flush()
    await db.refresh(conversation)

    logger.info(
        "Conversation plan updated",
        conversation_id=conversation_id,
        user_id=current_user.sub,
        plan_status=request.plan_status.value,
    )

    return {
        "conversation_id": conversation_id,
        "plan_content": conversation.plan_content,
        "plan_status": conversation.plan_status.value,
        "message": "Plan updated",
    }


@router.post("/{conversation_id}/plan/approve")
async def approve_conversation_plan(
    conversation_id: str,
    current_user: CurrentUserDep,
    redis: RedisDep,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    Approve the current plan for a conversation.
    """
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.sub,
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    if not conversation.plan_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No plan to approve",
        )

    conversation.plan_status = PlanStatus.APPROVED
    conversation.plan_approved_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(conversation)

    logger.info(
        "Conversation plan approved",
        conversation_id=conversation_id,
        user_id=current_user.sub,
    )

    # Get active plan from Redis and trigger execution
    from ..plan_mode import PlanManager
    from ai_messaging import PubSubManager

    plan_manager = PlanManager(redis)
    plan = await plan_manager.get_active_plan(conversation_id)

    if plan:
        # Guard: only approve plans that are ready (pending status with steps)
        plan_data_raw = await redis.get(f"plan:{plan.id}")
        if plan_data_raw:
            import json as json_mod
            plan_data = json_mod.loads(plan_data_raw)
            plan_status_val = plan_data.get("status", "")
            if plan_status_val in ("exploring", "drafting"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Plan is still being created. Please wait for it to finish.",
                )
            if not plan_data.get("steps"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Plan has no steps. It may still be generating.",
                )

        # Mark plan as approved
        await plan_manager.approve_plan(plan.id)

        # Get root_path from plan data for execution context
        plan_root_path = plan_data.get("root_path") if plan_data_raw else None

        # Trigger execution via supervisor
        pubsub = PubSubManager(redis)
        await pubsub.start()
        try:
            payload = {
                "plan_id": plan.id,
                "conversation_id": conversation_id,
                "user_id": current_user.sub,
            }
            if plan_root_path:
                payload["root_path"] = plan_root_path

            await pubsub.publish(
                "agent:supervisor:tasks",
                {
                    "type": "task_request",
                    "task_type": "execute_plan",
                    "user_id": current_user.sub,
                    "payload": payload,
                },
            )
            logger.info(
                "Plan execution triggered",
                plan_id=plan.id,
                conversation_id=conversation_id,
                root_path=plan_root_path,
            )
        finally:
            await pubsub.stop()

    return {
        "conversation_id": conversation_id,
        "plan_status": "approved",
        "plan_approved_at": conversation.plan_approved_at.isoformat(),
        "message": "Plan approved and execution started",
    }


@router.post("/{conversation_id}/plan/reject")
async def reject_conversation_plan(
    conversation_id: str,
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    Reject the current plan for a conversation.
    """
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.sub,
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    if not conversation.plan_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No plan to reject",
        )

    conversation.plan_status = PlanStatus.REJECTED
    conversation.plan_approved_at = None

    await db.flush()
    await db.refresh(conversation)

    logger.info(
        "Conversation plan rejected",
        conversation_id=conversation_id,
        user_id=current_user.sub,
    )

    return {
        "conversation_id": conversation_id,
        "plan_status": "rejected",
        "message": "Plan rejected",
    }
