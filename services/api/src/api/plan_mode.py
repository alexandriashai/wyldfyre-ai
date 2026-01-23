"""
Plan Mode - Structured task planning for AI agents.

Provides Claude Code-style plan mode where the agent:
1. Analyzes the task
2. Creates a structured plan with steps
3. Presents the plan for user approval
4. Executes steps with progress tracking
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from ai_core import get_logger
from ai_messaging import RedisClient

logger = get_logger(__name__)


class PlanStatus(str, Enum):
    """Status of a plan."""
    EXPLORING = "exploring"    # Agent is exploring codebase (read-only tools only)
    DRAFTING = "drafting"      # Agent is creating the plan
    PENDING = "pending"        # Awaiting user approval
    APPROVED = "approved"      # User approved, ready to execute
    EXECUTING = "executing"    # Currently executing steps
    PAUSED = "paused"          # Execution paused by user
    COMPLETED = "completed"    # All steps completed
    CANCELLED = "cancelled"    # User cancelled the plan
    FAILED = "failed"          # Execution failed


class StepStatus(str, Enum):
    """Status of a plan step."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class PlanStep:
    """A single step in a plan."""
    id: str
    order: int
    title: str
    description: str
    status: StepStatus = StepStatus.PENDING
    agent: Optional[str] = None  # Which agent will handle this
    estimated_duration: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)  # Step IDs this depends on
    output: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "order": self.order,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "agent": self.agent,
            "estimated_duration": self.estimated_duration,
            "dependencies": self.dependencies,
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class Plan:
    """A structured task plan."""
    id: str
    conversation_id: str
    user_id: str
    title: str
    description: str
    status: PlanStatus = PlanStatus.DRAFTING
    steps: list[PlanStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    approved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_step: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    exploration_notes: list[str] = field(default_factory=list)
    files_explored: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at.isoformat(),
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "current_step": self.current_step,
            "progress": self.progress,
            "metadata": self.metadata,
            "exploration_notes": self.exploration_notes,
            "files_explored": self.files_explored,
        }

    @property
    def progress(self) -> float:
        """Calculate completion percentage."""
        if not self.steps:
            return 0.0
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        return (completed / len(self.steps)) * 100


class PlanManager:
    """
    Manages plan creation, approval, and execution.

    Stores plans in Redis for real-time access and persistence.
    """

    def __init__(self, redis: RedisClient):
        self.redis = redis
        self._active_plans: dict[str, Plan] = {}

    async def create_plan(
        self,
        conversation_id: str,
        user_id: str,
        title: str,
        description: str,
    ) -> Plan:
        """Create a new plan (starts in EXPLORING phase)."""
        plan = Plan(
            id=str(uuid4()),
            conversation_id=conversation_id,
            user_id=user_id,
            title=title,
            description=description,
            status=PlanStatus.EXPLORING,
        )

        self._active_plans[plan.id] = plan
        await self._save_plan(plan)

        logger.info("Plan created in exploring phase", plan_id=plan.id, title=title)
        return plan

    async def start_exploration(self, plan_id: str) -> bool:
        """Transition a plan to exploring phase."""
        plan = await self.get_plan(plan_id)
        if not plan:
            return False

        plan.status = PlanStatus.EXPLORING
        await self._save_plan(plan)
        logger.info("Plan exploration started", plan_id=plan_id)
        return True

    async def add_exploration_note(
        self,
        plan_id: str,
        note: str,
        file_path: str | None = None,
    ) -> bool:
        """Add an exploration note and optionally track a file explored."""
        plan = await self.get_plan(plan_id)
        if not plan:
            return False

        plan.exploration_notes.append(note)
        if file_path and file_path not in plan.files_explored:
            plan.files_explored.append(file_path)

        await self._save_plan(plan)
        return True

    async def finish_exploration(self, plan_id: str) -> bool:
        """Transition from exploring to drafting phase."""
        plan = await self.get_plan(plan_id)
        if not plan or plan.status != PlanStatus.EXPLORING:
            return False

        plan.status = PlanStatus.DRAFTING
        await self._save_plan(plan)
        logger.info(
            "Plan exploration finished, now drafting",
            plan_id=plan_id,
            files_explored=len(plan.files_explored),
            notes_count=len(plan.exploration_notes),
        )
        return True

    async def add_step(
        self,
        plan_id: str,
        title: str,
        description: str,
        agent: Optional[str] = None,
        estimated_duration: Optional[str] = None,
        dependencies: Optional[list[str]] = None,
    ) -> Optional[PlanStep]:
        """Add a step to a plan."""
        plan = await self.get_plan(plan_id)
        if not plan:
            return None

        step = PlanStep(
            id=str(uuid4()),
            order=len(plan.steps) + 1,
            title=title,
            description=description,
            agent=agent,
            estimated_duration=estimated_duration,
            dependencies=dependencies or [],
        )

        plan.steps.append(step)
        await self._save_plan(plan)

        logger.debug("Step added to plan", plan_id=plan_id, step_id=step.id)
        return step

    async def set_steps(
        self,
        plan_id: str,
        steps: list[dict[str, Any]],
    ) -> bool:
        """Set all steps for a plan at once."""
        plan = await self.get_plan(plan_id)
        if not plan:
            return False

        plan.steps = [
            PlanStep(
                id=str(uuid4()),
                order=i + 1,
                title=s.get("title", f"Step {i + 1}"),
                description=s.get("description", ""),
                agent=s.get("agent"),
                estimated_duration=s.get("estimated_duration"),
                dependencies=s.get("dependencies", []),
            )
            for i, s in enumerate(steps)
        ]

        plan.status = PlanStatus.PENDING
        await self._save_plan(plan)
        return True

    async def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get a plan by ID."""
        if plan_id in self._active_plans:
            return self._active_plans[plan_id]

        # Try to load from Redis
        return await self._load_plan(plan_id)

    async def get_active_plan(self, conversation_id: str) -> Optional[Plan]:
        """Get the active plan for a conversation."""
        # Check memory cache first
        for plan in self._active_plans.values():
            if plan.conversation_id == conversation_id and plan.status not in (
                PlanStatus.COMPLETED,
                PlanStatus.CANCELLED,
                PlanStatus.FAILED,
            ):
                return plan

        # Check Redis
        plan_id = await self.redis.get(f"conversation:{conversation_id}:active_plan")
        if plan_id:
            return await self.get_plan(plan_id)

        return None

    async def approve_plan(self, plan_id: str) -> bool:
        """Approve a plan for execution."""
        plan = await self.get_plan(plan_id)
        if not plan or plan.status != PlanStatus.PENDING:
            return False

        plan.status = PlanStatus.APPROVED
        plan.approved_at = datetime.now(timezone.utc)
        await self._save_plan(plan)

        logger.info("Plan approved", plan_id=plan_id)
        return True

    async def reject_plan(self, plan_id: str) -> bool:
        """Reject/cancel a plan."""
        plan = await self.get_plan(plan_id)
        if not plan:
            return False

        plan.status = PlanStatus.CANCELLED
        await self._save_plan(plan)

        logger.info("Plan rejected", plan_id=plan_id)
        return True

    async def start_execution(self, plan_id: str) -> bool:
        """Start executing a plan."""
        plan = await self.get_plan(plan_id)
        if not plan or plan.status != PlanStatus.APPROVED:
            return False

        plan.status = PlanStatus.EXECUTING
        plan.current_step = 0
        await self._save_plan(plan)

        logger.info("Plan execution started", plan_id=plan_id)
        return True

    async def update_step_status(
        self,
        plan_id: str,
        step_id: str,
        status: StepStatus,
        output: Optional[str] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Update the status of a step."""
        plan = await self.get_plan(plan_id)
        if not plan:
            return False

        for step in plan.steps:
            if step.id == step_id:
                step.status = status

                if status == StepStatus.IN_PROGRESS:
                    step.started_at = datetime.now(timezone.utc)
                elif status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED):
                    step.completed_at = datetime.now(timezone.utc)

                if output:
                    step.output = output
                if error:
                    step.error = error

                # Update current step pointer
                if status == StepStatus.COMPLETED:
                    plan.current_step = step.order

                # Check if all steps completed
                all_done = all(
                    s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED)
                    for s in plan.steps
                )
                if all_done:
                    plan.status = PlanStatus.COMPLETED
                    plan.completed_at = datetime.now(timezone.utc)

                # Check for failure
                if status == StepStatus.FAILED:
                    plan.status = PlanStatus.FAILED

                await self._save_plan(plan)
                return True

        return False

    async def pause_execution(self, plan_id: str) -> bool:
        """Pause plan execution."""
        plan = await self.get_plan(plan_id)
        if not plan or plan.status != PlanStatus.EXECUTING:
            return False

        plan.status = PlanStatus.PAUSED
        await self._save_plan(plan)
        return True

    async def resume_execution(self, plan_id: str) -> bool:
        """Resume paused plan execution."""
        plan = await self.get_plan(plan_id)
        if not plan or plan.status != PlanStatus.PAUSED:
            return False

        plan.status = PlanStatus.EXECUTING
        await self._save_plan(plan)
        return True

    async def _save_plan(self, plan: Plan) -> None:
        """Save plan to Redis."""
        import json

        key = f"plan:{plan.id}"
        await self.redis.set(key, json.dumps(plan.to_dict()))

        # Also store active plan reference
        if plan.status not in (PlanStatus.COMPLETED, PlanStatus.CANCELLED, PlanStatus.FAILED):
            await self.redis.set(
                f"conversation:{plan.conversation_id}:active_plan",
                plan.id,
            )
        else:
            await self.redis.delete(f"conversation:{plan.conversation_id}:active_plan")

        self._active_plans[plan.id] = plan

    async def _load_plan(self, plan_id: str) -> Optional[Plan]:
        """Load plan from Redis."""
        import json

        key = f"plan:{plan_id}"
        data = await self.redis.get(key)
        if not data:
            return None

        try:
            plan_data = json.loads(data)
            plan = Plan(
                id=plan_data["id"],
                conversation_id=plan_data["conversation_id"],
                user_id=plan_data["user_id"],
                title=plan_data["title"],
                description=plan_data["description"],
                status=PlanStatus(plan_data["status"]),
                created_at=datetime.fromisoformat(plan_data["created_at"]),
                current_step=plan_data.get("current_step", 0),
                metadata=plan_data.get("metadata", {}),
                exploration_notes=plan_data.get("exploration_notes", []),
                files_explored=plan_data.get("files_explored", []),
            )

            if plan_data.get("approved_at"):
                plan.approved_at = datetime.fromisoformat(plan_data["approved_at"])
            if plan_data.get("completed_at"):
                plan.completed_at = datetime.fromisoformat(plan_data["completed_at"])

            # Load steps
            for step_data in plan_data.get("steps", []):
                step = PlanStep(
                    id=step_data["id"],
                    order=step_data["order"],
                    title=step_data["title"],
                    description=step_data["description"],
                    status=StepStatus(step_data["status"]),
                    agent=step_data.get("agent"),
                    estimated_duration=step_data.get("estimated_duration"),
                    dependencies=step_data.get("dependencies", []),
                    output=step_data.get("output"),
                    error=step_data.get("error"),
                )
                if step_data.get("started_at"):
                    step.started_at = datetime.fromisoformat(step_data["started_at"])
                if step_data.get("completed_at"):
                    step.completed_at = datetime.fromisoformat(step_data["completed_at"])
                plan.steps.append(step)

            self._active_plans[plan.id] = plan
            return plan

        except Exception as e:
            logger.error("Failed to load plan", plan_id=plan_id, error=str(e))
            return None


def format_plan_for_display(plan: Plan) -> str:
    """Format a plan for display in chat."""
    lines = [
        f"## 📋 Plan: {plan.title}",
        "",
        f"**Status:** {plan.status.value.replace('_', ' ').title()}",
        f"**Progress:** {plan.progress:.0f}%",
        "",
        "### Steps:",
        "",
    ]

    status_icons = {
        StepStatus.PENDING: "⬜",
        StepStatus.IN_PROGRESS: "🔄",
        StepStatus.COMPLETED: "✅",
        StepStatus.SKIPPED: "⏭️",
        StepStatus.FAILED: "❌",
    }

    for step in plan.steps:
        icon = status_icons.get(step.status, "⬜")
        agent_info = f" ({step.agent})" if step.agent else ""
        lines.append(f"{step.order}. {icon} **{step.title}**{agent_info}")
        if step.description:
            lines.append(f"   {step.description}")
        if step.error:
            lines.append(f"   ⚠️ Error: {step.error}")
        lines.append("")

    if plan.status == PlanStatus.EXPLORING:
        if plan.files_explored:
            lines.append(f"**Files explored:** {len(plan.files_explored)}")
        if plan.exploration_notes:
            lines.append(f"**Notes collected:** {len(plan.exploration_notes)}")
        lines.append("")
        lines.append("_Agent is exploring the codebase with read-only tools..._")

    if plan.status == PlanStatus.PENDING:
        lines.extend([
            "---",
            "Reply with:",
            "- `approve` to start execution",
            "- `reject` to cancel this plan",
            "- `modify` to suggest changes",
        ])

    return "\n".join(lines)
