"""
Plan CRUD schemas.

Provides schemas for plan list, detail, update, clone, and modification operations.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TodoItem(BaseModel):
    """A single todo item within a step."""

    text: str
    completed: bool = False


class StepProgress(BaseModel):
    """Plan step with detailed progress tracking."""

    index: int
    id: str
    title: str
    description: str
    status: str  # pending, in_progress, completed, skipped, failed
    agent: str | None = None
    todos: list[TodoItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    completed_todos: int = 0
    total_todos: int = 0
    output: str | None = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    estimated_duration: str | None = None

    @classmethod
    def from_plan_step(cls, step: dict, index: int) -> "StepProgress":
        """Create StepProgress from raw plan step dict."""
        todos = step.get("todos", [])
        # Handle both string todos and dict todos
        todo_items = []
        completed_count = 0
        for todo in todos:
            if isinstance(todo, dict):
                todo_items.append(TodoItem(**todo))
                if todo.get("completed"):
                    completed_count += 1
            else:
                # String todo - mark completed if step is completed
                is_completed = step.get("status") == "completed"
                todo_items.append(TodoItem(text=str(todo), completed=is_completed))
                if is_completed:
                    completed_count += 1

        return cls(
            index=index,
            id=step.get("id", ""),
            title=step.get("title", ""),
            description=step.get("description", ""),
            status=step.get("status", "pending"),
            agent=step.get("agent"),
            todos=todo_items,
            notes=step.get("notes", []),
            completed_todos=completed_count,
            total_todos=len(todo_items),
            output=step.get("output"),
            error=step.get("error"),
            started_at=step.get("started_at"),
            completed_at=step.get("completed_at"),
            estimated_duration=step.get("estimated_duration"),
        )


class PlanListItem(BaseModel):
    """Compact plan info for list views."""

    id: str
    title: str
    description: str | None = None
    status: str
    created_at: str
    updated_at: str | None = None
    total_steps: int
    completed_steps: int
    is_running: bool = False  # status == executing
    is_stuck: bool = False  # paused or failed with partial progress
    conversation_id: str | None = None
    project_id: str | None = None

    @classmethod
    def from_plan(cls, plan: dict) -> "PlanListItem":
        """Create list item from plan dict."""
        steps = plan.get("steps", [])
        completed = sum(1 for s in steps if s.get("status") == "completed")
        status = plan.get("status", "pending")

        return cls(
            id=plan.get("id", ""),
            title=plan.get("title", "Untitled Plan"),
            description=plan.get("description"),
            status=status,
            created_at=plan.get("created_at", ""),
            updated_at=plan.get("updated_at"),
            total_steps=len(steps),
            completed_steps=completed,
            is_running=status == "executing",
            is_stuck=status in ("paused", "failed") and completed > 0,
            conversation_id=plan.get("conversation_id"),
            project_id=plan.get("project_id"),
        )


class PlanDetailResponse(BaseModel):
    """Full plan details with step progress."""

    id: str
    title: str
    description: str | None = None
    status: str
    steps: list[StepProgress]
    current_step_index: int
    total_steps: int
    completed_steps: int
    is_running: bool = False
    is_complete: bool = False
    is_stuck: bool = False
    overall_progress: float = 0.0  # 0.0 - 1.0
    created_at: str
    updated_at: str | None = None
    approved_at: str | None = None
    completed_at: str | None = None
    conversation_id: str | None = None
    user_id: str | None = None
    project_id: str | None = None
    exploration_notes: list[str] = Field(default_factory=list)
    files_explored: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_plan(cls, plan: dict) -> "PlanDetailResponse":
        """Create detailed response from plan dict."""
        raw_steps = plan.get("steps", [])
        steps = [StepProgress.from_plan_step(s, i) for i, s in enumerate(raw_steps)]
        completed = sum(1 for s in steps if s.status == "completed")
        status = plan.get("status", "pending")
        total = len(steps)

        return cls(
            id=plan.get("id", ""),
            title=plan.get("title", "Untitled Plan"),
            description=plan.get("description"),
            status=status,
            steps=steps,
            current_step_index=plan.get("current_step", 0),
            total_steps=total,
            completed_steps=completed,
            is_running=status == "executing",
            is_complete=status == "completed",
            is_stuck=status in ("paused", "failed") and completed > 0,
            overall_progress=completed / total if total > 0 else 0.0,
            created_at=plan.get("created_at", ""),
            updated_at=plan.get("updated_at"),
            approved_at=plan.get("approved_at"),
            completed_at=plan.get("completed_at"),
            conversation_id=plan.get("conversation_id"),
            user_id=plan.get("user_id"),
            project_id=plan.get("project_id"),
            exploration_notes=plan.get("exploration_notes", []),
            files_explored=plan.get("files_explored", []),
            metadata=plan.get("metadata", {}),
        )


class PlanListResponse(BaseModel):
    """Paginated plan list response."""

    plans: list[PlanListItem]
    total: int
    offset: int
    limit: int
    filter_status: str | None = None


class PlanUpdate(BaseModel):
    """Update plan request."""

    title: str | None = None
    description: str | None = None
    steps: list[dict] | None = None  # Raw step dicts
    status: str | None = None
    metadata: dict[str, Any] | None = None


class PlanModifyRequest(BaseModel):
    """AI-assisted plan modification request."""

    request: str = Field(..., description="Natural language modification request")
    constraints: list[str] | None = Field(None, description="Optional constraints for the modification")


class PlanCloneRequest(BaseModel):
    """Clone plan request."""

    new_title: str | None = Field(None, description="Title for the cloned plan")
    reset_status: bool = Field(True, description="Reset all step statuses to pending")


class PlanFollowUpRequest(BaseModel):
    """Follow-up request for stuck/paused plans."""

    context: str | None = Field(None, description="Additional context for resumption")
    action: str = Field("analyze_and_resume", description="What to do: analyze_and_resume, skip_current, etc.")


class PlanHistoryEntry(BaseModel):
    """Single entry in plan modification history."""

    timestamp: str
    action: str  # created, manual_edit, ai_modify, status_change, step_completed, step_failed
    changes: dict[str, Any]
    actor: str | None = None  # "user" or agent name
    details: str | None = None


class PlanHistoryResponse(BaseModel):
    """Plan modification history response."""

    plan_id: str
    entries: list[PlanHistoryEntry]
    total_entries: int


class PlanOperationResponse(BaseModel):
    """Generic operation response."""

    success: bool
    plan_id: str
    message: str
    plan: PlanDetailResponse | None = None
