"""
Conversation management routes.
"""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ai_core import get_logger
from ai_messaging import RedisClient

from ..dependencies import CurrentUserDep, get_redis

logger = get_logger(__name__)

router = APIRouter(prefix="/conversations", tags=["Conversations"])


class ConversationCreate(BaseModel):
    """Create conversation request."""

    title: str | None = None


class MessageCreate(BaseModel):
    """Add message to conversation."""

    content: str
    role: str = "user"  # user, assistant, system


class ConversationResponse(BaseModel):
    """Conversation response."""

    id: str
    user_id: str
    title: str | None
    created_at: str
    updated_at: str
    message_count: int


class MessageResponse(BaseModel):
    """Message response."""

    id: str
    role: str
    content: str
    agent: str | None
    timestamp: str


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
    limit: int = Query(50, ge=1, le=100),
) -> list[ConversationResponse]:
    """
    List conversations for the current user.
    """
    try:
        # Get conversation IDs for user
        conv_list_key = f"user:{current_user.sub}:conversations"
        conv_ids = await redis.lrange(conv_list_key, 0, limit - 1)

        conversations = []
        for conv_id in conv_ids or []:
            conv_key = f"conversation:{conv_id}"
            conv_data = await redis.hgetall(conv_key)

            if conv_data:
                conversations.append(
                    ConversationResponse(
                        id=conv_id,
                        user_id=conv_data.get("user_id", current_user.sub),
                        title=conv_data.get("title"),
                        created_at=conv_data.get("created_at", ""),
                        updated_at=conv_data.get("updated_at", ""),
                        message_count=int(conv_data.get("message_count", 0)),
                    )
                )

        return conversations

    except Exception as e:
        logger.error("Failed to list conversations", error=str(e))
        return []


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: ConversationCreate,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> ConversationResponse:
    """
    Create a new conversation.
    """
    conv_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conv_data = {
        "id": conv_id,
        "user_id": current_user.sub,
        "title": request.title or "New Conversation",
        "created_at": now,
        "updated_at": now,
        "message_count": "0",
    }

    # Store conversation
    conv_key = f"conversation:{conv_id}"
    await redis.hset(conv_key, mapping=conv_data)

    # Add to user's conversation list
    conv_list_key = f"user:{current_user.sub}:conversations"
    await redis.lpush(conv_list_key, conv_id)

    logger.info(
        "Conversation created",
        conversation_id=conv_id,
        user_id=current_user.sub,
    )

    return ConversationResponse(
        id=conv_id,
        user_id=current_user.sub,
        title=conv_data["title"],
        created_at=now,
        updated_at=now,
        message_count=0,
    )


@router.get("/{conversation_id}", response_model=dict[str, Any])
async def get_conversation(
    conversation_id: str,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """
    Get conversation with message history.
    """
    # Get conversation metadata
    conv_key = f"conversation:{conversation_id}"
    conv_data = await redis.hgetall(conv_key)

    if not conv_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    # Verify ownership
    if conv_data.get("user_id") != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Get messages
    messages_key = f"conversation:{conversation_id}:messages"
    message_ids = await redis.lrange(messages_key, 0, limit - 1)

    messages = []
    for msg_id in message_ids or []:
        msg_key = f"message:{msg_id}"
        msg_data = await redis.hgetall(msg_key)
        if msg_data:
            messages.append(
                MessageResponse(
                    id=msg_id,
                    role=msg_data.get("role", "user"),
                    content=msg_data.get("content", ""),
                    agent=msg_data.get("agent"),
                    timestamp=msg_data.get("timestamp", ""),
                )
            )

    return {
        "conversation": ConversationResponse(
            id=conversation_id,
            user_id=conv_data.get("user_id", ""),
            title=conv_data.get("title"),
            created_at=conv_data.get("created_at", ""),
            updated_at=conv_data.get("updated_at", ""),
            message_count=int(conv_data.get("message_count", 0)),
        ),
        "messages": messages,
    }


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: CurrentUserDep,
    redis: RedisClient = Depends(get_redis),
) -> dict[str, str]:
    """
    Delete a conversation and all its messages.
    """
    # Get conversation to verify ownership
    conv_key = f"conversation:{conversation_id}"
    conv_data = await redis.hgetall(conv_key)

    if not conv_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    if conv_data.get("user_id") != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Delete messages
    messages_key = f"conversation:{conversation_id}:messages"
    message_ids = await redis.lrange(messages_key, 0, -1)
    for msg_id in message_ids or []:
        await redis.delete(f"message:{msg_id}")
    await redis.delete(messages_key)

    # Delete conversation
    await redis.delete(conv_key)

    # Remove from user's list
    conv_list_key = f"user:{current_user.sub}:conversations"
    await redis.lrem(conv_list_key, 0, conversation_id)

    logger.info(
        "Conversation deleted",
        conversation_id=conversation_id,
        user_id=current_user.sub,
    )

    return {"message": f"Conversation {conversation_id} deleted"}
