"""
Conversation schemas.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from ai_db import ConversationStatus, PlanStatus


class ConversationCreate(BaseModel):
    """Create conversation request."""

    title: str | None = Field(None, max_length=500)
    project_id: str | None = None
    domain_id: str | None = None


class ConversationUpdate(BaseModel):
    """Update conversation request."""

    title: str | None = Field(None, max_length=500)
    project_id: str | None = None
    domain_id: str | None = None
    status: ConversationStatus | None = None


class PlanUpdate(BaseModel):
    """Update conversation plan."""

    plan_content: str
    plan_status: PlanStatus = PlanStatus.DRAFT


class ConversationResponse(BaseModel):
    """Conversation information response."""

    id: str
    title: str | None
    summary: str | None
    status: ConversationStatus
    message_count: int
    last_message_at: datetime | None

    # Planning
    plan_content: str | None
    plan_status: PlanStatus | None
    plan_approved_at: datetime | None

    # Relationships
    user_id: str
    project_id: str | None
    domain_id: str | None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """Conversation list response."""

    conversations: list[ConversationResponse]
    total: int
    page: int
    page_size: int


class ConversationWithMessagesResponse(BaseModel):
    """Conversation with message history."""

    conversation: ConversationResponse
    messages: list[dict]  # Messages from Redis


class MessageResponse(BaseModel):
    """Message response."""

    id: str
    role: str
    content: str
    agent: str | None
    timestamp: str
