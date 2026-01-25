"""
Conversation schemas.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from database.models import ConversationStatus, PlanStatus


class ConversationCreate(BaseModel):
    """Create conversation request."""

    title: str | None = Field(None, max_length=500)
    project_id: str = Field(..., description="Project ID is required for all conversations")
    domain_id: str | None = None
    tags: list[str] = Field(default_factory=list)


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


class TagsUpdate(BaseModel):
    """Update conversation tags."""

    tags: list[str] = Field(..., max_length=20)


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

    # Tags
    tags: list[str] = Field(default_factory=list)

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_conversation(cls, conversation) -> "ConversationResponse":
        """Create response from ORM model with tags resolved."""
        tag_values = [t.tag for t in conversation.tags] if conversation.tags else []
        return cls(
            id=conversation.id,
            title=conversation.title,
            summary=conversation.summary,
            status=conversation.status,
            message_count=conversation.message_count,
            last_message_at=conversation.last_message_at,
            plan_content=conversation.plan_content,
            plan_status=conversation.plan_status,
            plan_approved_at=conversation.plan_approved_at,
            user_id=conversation.user_id,
            project_id=conversation.project_id,
            domain_id=conversation.domain_id,
            tags=tag_values,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )


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
