"""
Rollback Manager for Task Execution

Tracks file changes during task/step execution and enables rollback
to restore files to their pre-modification state.
"""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field, asdict
from enum import Enum

import structlog

logger = structlog.get_logger()


class ChangeType(str, Enum):
    """Type of file change."""
    CREATE = "create"      # New file created
    MODIFY = "modify"      # Existing file modified
    DELETE = "delete"      # File deleted


@dataclass
class FileSnapshot:
    """Snapshot of a file's state before and after modification."""
    path: str
    change_type: ChangeType
    original_content: str | None  # None if file was created (didn't exist)
    original_hash: str | None     # Hash of original content
    new_content: str | None = None       # Content after modification (for redo)
    new_hash: str | None = None          # Hash of new content
    rolled_back: bool = False            # True if this snapshot has been rolled back
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "change_type": self.change_type.value,
            "original_content": self.original_content,
            "original_hash": self.original_hash,
            "new_content": self.new_content,
            "new_hash": self.new_hash,
            "rolled_back": self.rolled_back,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FileSnapshot":
        return cls(
            path=data["path"],
            change_type=ChangeType(data["change_type"]),
            original_content=data.get("original_content"),
            original_hash=data.get("original_hash"),
            new_content=data.get("new_content"),
            new_hash=data.get("new_hash"),
            rolled_back=data.get("rolled_back", False),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )


@dataclass
class StepRollbackData:
    """Rollback data for a single step."""
    step_id: str
    step_title: str
    snapshots: list[FileSnapshot] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "step_title": self.step_title,
            "snapshots": [s.to_dict() for s in self.snapshots],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StepRollbackData":
        return cls(
            step_id=data["step_id"],
            step_title=data["step_title"],
            snapshots=[FileSnapshot.from_dict(s) for s in data.get("snapshots", [])],
            started_at=data.get("started_at", datetime.now(timezone.utc).isoformat()),
            completed_at=data.get("completed_at"),
        )


@dataclass
class PlanRollbackData:
    """Rollback data for an entire plan."""
    plan_id: str
    conversation_id: str
    steps: dict[str, StepRollbackData] = field(default_factory=dict)  # step_id -> StepRollbackData
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "conversation_id": self.conversation_id,
            "steps": {k: v.to_dict() for k, v in self.steps.items()},
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlanRollbackData":
        return cls(
            plan_id=data["plan_id"],
            conversation_id=data["conversation_id"],
            steps={k: StepRollbackData.from_dict(v) for k, v in data.get("steps", {}).items()},
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )


@dataclass
class TaskRollbackData:
    """Rollback data for a single task (non-plan execution)."""
    task_id: str
    conversation_id: str
    user_id: str
    snapshots: list[FileSnapshot] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "snapshots": [s.to_dict() for s in self.snapshots],
            "created_at": self.created_at,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskRollbackData":
        return cls(
            task_id=data["task_id"],
            conversation_id=data["conversation_id"],
            user_id=data.get("user_id", ""),
            snapshots=[FileSnapshot.from_dict(s) for s in data.get("snapshots", [])],
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            description=data.get("description", ""),
        )


class RollbackManager:
    """
    Manages file snapshots and rollback operations for task execution.

    Supports both plan-based execution (with steps) and single-task execution.

    Usage for Plans:
        manager = RollbackManager(redis_client)
        await manager.start_plan(plan_id, conversation_id)
        await manager.start_step(plan_id, step_id, step_title)
        await manager.snapshot_file(plan_id, step_id, file_path)
        result = await manager.rollback_step(plan_id, step_id)
        result = await manager.rollback_plan(plan_id)

    Usage for Single Tasks:
        await manager.start_task(task_id, conversation_id, user_id)
        await manager.snapshot_task_file(task_id, file_path)
        result = await manager.rollback_task(task_id)
    """

    ROLLBACK_KEY_PREFIX = "rollback:"
    TASK_ROLLBACK_KEY_PREFIX = "task_rollback:"
    ROLLBACK_TTL = 86400 * 7  # Keep rollback data for 7 days

    def __init__(self, redis_client):
        self._redis = redis_client
        self._current_plan: PlanRollbackData | None = None

    def _get_plan_key(self, plan_id: str) -> str:
        return f"{self.ROLLBACK_KEY_PREFIX}{plan_id}"

    def _compute_hash(self, content: str) -> str:
        """Compute hash of file content for integrity checking."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def _load_plan_data(self, plan_id: str) -> PlanRollbackData | None:
        """Load plan rollback data from Redis."""
        key = self._get_plan_key(plan_id)
        data = await self._redis.get(key)
        if data:
            return PlanRollbackData.from_dict(json.loads(data))
        return None

    async def _save_plan_data(self, data: PlanRollbackData) -> None:
        """Save plan rollback data to Redis."""
        key = self._get_plan_key(data.plan_id)
        await self._redis.set(key, json.dumps(data.to_dict()), ex=self.ROLLBACK_TTL)

    async def start_plan(self, plan_id: str, conversation_id: str) -> None:
        """
        Initialize rollback tracking for a plan.

        Args:
            plan_id: Unique plan identifier
            conversation_id: Associated conversation ID
        """
        self._current_plan = PlanRollbackData(
            plan_id=plan_id,
            conversation_id=conversation_id,
        )
        await self._save_plan_data(self._current_plan)
        logger.info("Rollback tracking started", plan_id=plan_id)

    async def start_step(self, plan_id: str, step_id: str, step_title: str) -> None:
        """
        Start tracking a new step.

        Args:
            plan_id: Plan identifier
            step_id: Step identifier
            step_title: Human-readable step title
        """
        plan_data = await self._load_plan_data(plan_id)
        if not plan_data:
            # Auto-create plan data if it doesn't exist
            plan_data = PlanRollbackData(plan_id=plan_id, conversation_id="")

        plan_data.steps[step_id] = StepRollbackData(
            step_id=step_id,
            step_title=step_title,
        )
        await self._save_plan_data(plan_data)
        logger.debug("Step rollback tracking started", plan_id=plan_id, step_id=step_id)

    async def complete_step(self, plan_id: str, step_id: str) -> None:
        """Mark a step as completed."""
        plan_data = await self._load_plan_data(plan_id)
        if plan_data and step_id in plan_data.steps:
            plan_data.steps[step_id].completed_at = datetime.now(timezone.utc).isoformat()
            await self._save_plan_data(plan_data)

    async def snapshot_file(
        self,
        plan_id: str,
        step_id: str,
        file_path: str,
        change_type: ChangeType = ChangeType.MODIFY,
    ) -> bool:
        """
        Snapshot a file before modification.

        Args:
            plan_id: Plan identifier
            step_id: Current step identifier
            file_path: Path to the file being modified
            change_type: Type of change (create, modify, delete)

        Returns:
            True if snapshot was created, False if file was already snapshotted
        """
        plan_data = await self._load_plan_data(plan_id)
        if not plan_data:
            logger.warning("No plan data found for snapshot", plan_id=plan_id)
            return False

        if step_id not in plan_data.steps:
            # Auto-create step if needed
            plan_data.steps[step_id] = StepRollbackData(step_id=step_id, step_title="Unknown step")

        step_data = plan_data.steps[step_id]

        # Check if file already snapshotted in this step
        existing_paths = {s.path for s in step_data.snapshots}
        if file_path in existing_paths:
            logger.debug("File already snapshotted", path=file_path, step_id=step_id)
            return False

        # Read current file content (if exists)
        original_content = None
        original_hash = None
        path = Path(file_path)

        if change_type != ChangeType.CREATE and path.exists():
            try:
                original_content = path.read_text()
                original_hash = self._compute_hash(original_content)
            except Exception as e:
                logger.warning("Failed to read file for snapshot", path=file_path, error=str(e))

        # Create snapshot
        snapshot = FileSnapshot(
            path=file_path,
            change_type=change_type,
            original_content=original_content,
            original_hash=original_hash,
        )
        step_data.snapshots.append(snapshot)
        await self._save_plan_data(plan_data)

        logger.debug(
            "File snapshotted",
            path=file_path,
            change_type=change_type.value,
            has_content=original_content is not None,
        )
        return True

    async def capture_after_content(
        self,
        plan_id: str,
        step_id: str,
        file_path: str,
    ) -> bool:
        """
        Capture the "after" content of a file for redo support.
        Call this after a file has been modified.

        Args:
            plan_id: Plan identifier
            step_id: Step identifier
            file_path: Path to the file that was modified

        Returns:
            True if after content was captured
        """
        plan_data = await self._load_plan_data(plan_id)
        if not plan_data or step_id not in plan_data.steps:
            return False

        step_data = plan_data.steps[step_id]

        # Find the snapshot for this file
        for snapshot in step_data.snapshots:
            if snapshot.path == file_path:
                # Read current (new) file content
                path = Path(file_path)
                if path.exists():
                    try:
                        snapshot.new_content = path.read_text()
                        snapshot.new_hash = self._compute_hash(snapshot.new_content)
                        await self._save_plan_data(plan_data)
                        logger.debug("Captured after content", path=file_path)
                        return True
                    except Exception as e:
                        logger.warning("Failed to capture after content", path=file_path, error=str(e))
                break

        return False

    async def rollback_step(
        self,
        plan_id: str,
        step_id: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Rollback all file changes from a specific step.

        Args:
            plan_id: Plan identifier
            step_id: Step to rollback
            dry_run: If True, don't actually modify files, just report what would happen

        Returns:
            Dict with rollback results
        """
        plan_data = await self._load_plan_data(plan_id)
        if not plan_data:
            return {"success": False, "error": "Plan not found", "files_restored": []}

        if step_id not in plan_data.steps:
            return {"success": False, "error": "Step not found", "files_restored": []}

        step_data = plan_data.steps[step_id]
        files_restored = []
        files_deleted = []
        errors = []

        # Process snapshots in reverse order (undo last changes first)
        for snapshot in reversed(step_data.snapshots):
            try:
                path = Path(snapshot.path)

                if dry_run:
                    if snapshot.change_type == ChangeType.CREATE:
                        files_deleted.append(snapshot.path)
                    else:
                        files_restored.append(snapshot.path)
                    continue

                if snapshot.change_type == ChangeType.CREATE:
                    # File was created - delete it
                    if path.exists():
                        path.unlink()
                        files_deleted.append(snapshot.path)
                        logger.info("Deleted created file", path=snapshot.path)
                elif snapshot.change_type == ChangeType.DELETE:
                    # File was deleted - restore it
                    if snapshot.original_content is not None:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(snapshot.original_content)
                        files_restored.append(snapshot.path)
                        logger.info("Restored deleted file", path=snapshot.path)
                else:
                    # File was modified - restore original content
                    if snapshot.original_content is not None:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(snapshot.original_content)
                        files_restored.append(snapshot.path)
                        logger.info("Restored modified file", path=snapshot.path)

                # Mark snapshot as rolled back (for redo support)
                if not dry_run:
                    snapshot.rolled_back = True

            except Exception as e:
                error_msg = f"Failed to rollback {snapshot.path}: {str(e)}"
                errors.append(error_msg)
                logger.error("Rollback error", path=snapshot.path, error=str(e))

        # Save state with rolled_back flags (unless dry run)
        if not dry_run and not errors:
            await self._save_plan_data(plan_data)

        return {
            "success": len(errors) == 0,
            "step_id": step_id,
            "step_title": step_data.step_title,
            "files_restored": files_restored,
            "can_redo": not dry_run and not errors,  # Can redo if rollback succeeded
            "files_deleted": files_deleted,
            "errors": errors,
            "dry_run": dry_run,
        }

    async def rollback_plan(
        self,
        plan_id: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Rollback all file changes from an entire plan.

        Args:
            plan_id: Plan identifier
            dry_run: If True, don't actually modify files

        Returns:
            Dict with rollback results
        """
        plan_data = await self._load_plan_data(plan_id)
        if not plan_data:
            return {"success": False, "error": "Plan not found", "steps": []}

        step_results = []
        all_files_restored = []
        all_files_deleted = []
        all_errors = []

        # Rollback steps in reverse order (last step first)
        step_ids = list(plan_data.steps.keys())
        for step_id in reversed(step_ids):
            result = await self.rollback_step(plan_id, step_id, dry_run=dry_run)
            step_results.append(result)
            all_files_restored.extend(result.get("files_restored", []))
            all_files_deleted.extend(result.get("files_deleted", []))
            all_errors.extend(result.get("errors", []))

        # Clear plan data after successful rollback (unless dry run)
        if not dry_run and not all_errors:
            await self._redis.delete(self._get_plan_key(plan_id))

        return {
            "success": len(all_errors) == 0,
            "plan_id": plan_id,
            "steps_rolled_back": len(step_results),
            "files_restored": all_files_restored,
            "files_deleted": all_files_deleted,
            "errors": all_errors,
            "step_results": step_results,
            "dry_run": dry_run,
        }

    async def get_rollback_info(self, plan_id: str) -> dict[str, Any] | None:
        """
        Get information about available rollback for a plan.

        Args:
            plan_id: Plan identifier

        Returns:
            Dict with rollback info or None if no data exists
        """
        plan_data = await self._load_plan_data(plan_id)
        if not plan_data:
            return None

        steps_info = []
        total_files = 0

        for step_id, step_data in plan_data.steps.items():
            file_count = len(step_data.snapshots)
            total_files += file_count
            rolled_back_count = sum(1 for s in step_data.snapshots if s.rolled_back)
            can_redo = rolled_back_count > 0 and all(s.new_content is not None for s in step_data.snapshots if s.rolled_back)
            steps_info.append({
                "step_id": step_id,
                "step_title": step_data.step_title,
                "files_modified": file_count,
                "files_rolled_back": rolled_back_count,
                "can_redo": can_redo,
                "file_paths": [s.path for s in step_data.snapshots],
                "started_at": step_data.started_at,
                "completed_at": step_data.completed_at,
            })

        return {
            "plan_id": plan_id,
            "conversation_id": plan_data.conversation_id,
            "created_at": plan_data.created_at,
            "total_steps": len(plan_data.steps),
            "total_files_modified": total_files,
            "steps": steps_info,
        }

    async def clear_rollback_data(self, plan_id: str) -> bool:
        """
        Clear rollback data for a plan (e.g., after user confirms changes).

        Args:
            plan_id: Plan identifier

        Returns:
            True if data was cleared
        """
        key = self._get_plan_key(plan_id)
        result = await self._redis.delete(key)
        if result:
            logger.info("Rollback data cleared", plan_id=plan_id)
        return result > 0

    async def redo_step(
        self,
        plan_id: str,
        step_id: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Redo (reapply) file changes that were previously rolled back for a step.

        Args:
            plan_id: Plan identifier
            step_id: Step to redo
            dry_run: If True, don't actually modify files

        Returns:
            Dict with redo results
        """
        plan_data = await self._load_plan_data(plan_id)
        if not plan_data:
            return {"success": False, "error": "Plan not found", "files_reapplied": []}

        if step_id not in plan_data.steps:
            return {"success": False, "error": "Step not found", "files_reapplied": []}

        step_data = plan_data.steps[step_id]
        files_reapplied = []
        files_created = []
        errors = []

        # Only process rolled-back snapshots that have new_content
        rolled_back_snapshots = [s for s in step_data.snapshots if s.rolled_back]
        if not rolled_back_snapshots:
            return {"success": False, "error": "No rolled-back changes to redo", "files_reapplied": []}

        # Process snapshots in original order (reapply changes)
        for snapshot in rolled_back_snapshots:
            if snapshot.new_content is None and snapshot.change_type != ChangeType.DELETE:
                errors.append(f"No new content available for {snapshot.path}")
                continue

            try:
                path = Path(snapshot.path)

                if dry_run:
                    if snapshot.change_type == ChangeType.CREATE:
                        files_created.append(snapshot.path)
                    elif snapshot.change_type == ChangeType.DELETE:
                        files_reapplied.append(snapshot.path)  # Will delete again
                    else:
                        files_reapplied.append(snapshot.path)
                    continue

                if snapshot.change_type == ChangeType.CREATE:
                    # Recreate the file
                    if snapshot.new_content is not None:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(snapshot.new_content)
                        files_created.append(snapshot.path)
                        logger.info("Recreated file", path=snapshot.path)
                elif snapshot.change_type == ChangeType.DELETE:
                    # Delete the file again
                    if path.exists():
                        path.unlink()
                        files_reapplied.append(snapshot.path)
                        logger.info("Re-deleted file", path=snapshot.path)
                else:
                    # Reapply modification
                    if snapshot.new_content is not None:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(snapshot.new_content)
                        files_reapplied.append(snapshot.path)
                        logger.info("Reapplied modification", path=snapshot.path)

                # Mark snapshot as no longer rolled back
                if not dry_run:
                    snapshot.rolled_back = False

            except Exception as e:
                error_msg = f"Failed to redo {snapshot.path}: {str(e)}"
                errors.append(error_msg)
                logger.error("Redo error", path=snapshot.path, error=str(e))

        # Save state (unless dry run)
        if not dry_run:
            await self._save_plan_data(plan_data)

        return {
            "success": len(errors) == 0,
            "step_id": step_id,
            "step_title": step_data.step_title,
            "files_reapplied": files_reapplied,
            "files_created": files_created,
            "errors": errors,
            "dry_run": dry_run,
        }

    async def redo_plan(
        self,
        plan_id: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Redo (reapply) all rolled-back file changes for an entire plan.

        Args:
            plan_id: Plan identifier
            dry_run: If True, don't actually modify files

        Returns:
            Dict with redo results
        """
        plan_data = await self._load_plan_data(plan_id)
        if not plan_data:
            return {"success": False, "error": "Plan not found", "steps": []}

        step_results = []
        all_files_reapplied = []
        all_files_created = []
        all_errors = []

        # Redo steps in original order
        step_ids = list(plan_data.steps.keys())
        for step_id in step_ids:
            # Check if step has rolled-back changes
            step_data = plan_data.steps[step_id]
            if not any(s.rolled_back for s in step_data.snapshots):
                continue

            result = await self.redo_step(plan_id, step_id, dry_run=dry_run)
            step_results.append(result)
            all_files_reapplied.extend(result.get("files_reapplied", []))
            all_files_created.extend(result.get("files_created", []))
            all_errors.extend(result.get("errors", []))

        if not step_results:
            return {"success": False, "error": "No rolled-back changes to redo", "steps": []}

        return {
            "success": len(all_errors) == 0,
            "plan_id": plan_id,
            "steps_redone": len(step_results),
            "files_reapplied": all_files_reapplied,
            "files_created": all_files_created,
            "errors": all_errors,
            "step_results": step_results,
            "dry_run": dry_run,
        }

    # =========================================================================
    # Task-Level Rollback (for non-plan single tasks)
    # =========================================================================

    def _get_task_key(self, task_id: str) -> str:
        return f"{self.TASK_ROLLBACK_KEY_PREFIX}{task_id}"

    async def _load_task_data(self, task_id: str) -> TaskRollbackData | None:
        """Load task rollback data from Redis."""
        key = self._get_task_key(task_id)
        data = await self._redis.get(key)
        if data:
            return TaskRollbackData.from_dict(json.loads(data))
        return None

    async def _save_task_data(self, data: TaskRollbackData) -> None:
        """Save task rollback data to Redis."""
        key = self._get_task_key(data.task_id)
        await self._redis.set(key, json.dumps(data.to_dict()), ex=self.ROLLBACK_TTL)

    async def start_task(
        self,
        task_id: str,
        conversation_id: str,
        user_id: str,
        description: str = "",
    ) -> None:
        """
        Initialize rollback tracking for a single task.

        Args:
            task_id: Unique task identifier
            conversation_id: Associated conversation ID
            user_id: User who initiated the task
            description: Optional description of the task
        """
        task_data = TaskRollbackData(
            task_id=task_id,
            conversation_id=conversation_id,
            user_id=user_id,
            description=description,
        )
        await self._save_task_data(task_data)
        logger.info("Task rollback tracking started", task_id=task_id)

    async def snapshot_task_file(
        self,
        task_id: str,
        file_path: str,
        change_type: ChangeType = ChangeType.MODIFY,
    ) -> bool:
        """
        Snapshot a file before modification for a single task.

        Args:
            task_id: Task identifier
            file_path: Path to the file being modified
            change_type: Type of change

        Returns:
            True if snapshot was created
        """
        task_data = await self._load_task_data(task_id)
        if not task_data:
            logger.warning("No task data found for snapshot", task_id=task_id)
            return False

        # Check if file already snapshotted
        existing_paths = {s.path for s in task_data.snapshots}
        if file_path in existing_paths:
            return False

        # Read current file content
        original_content = None
        original_hash = None
        path = Path(file_path)

        if change_type != ChangeType.CREATE and path.exists():
            try:
                original_content = path.read_text()
                original_hash = self._compute_hash(original_content)
            except Exception as e:
                logger.warning("Failed to read file for task snapshot", path=file_path, error=str(e))

        snapshot = FileSnapshot(
            path=file_path,
            change_type=change_type,
            original_content=original_content,
            original_hash=original_hash,
        )
        task_data.snapshots.append(snapshot)
        await self._save_task_data(task_data)
        return True

    async def capture_task_after_content(
        self,
        task_id: str,
        file_path: str,
    ) -> bool:
        """Capture after content for a task file modification."""
        task_data = await self._load_task_data(task_id)
        if not task_data:
            return False

        for snapshot in task_data.snapshots:
            if snapshot.path == file_path:
                path = Path(file_path)
                if path.exists():
                    try:
                        snapshot.new_content = path.read_text()
                        snapshot.new_hash = self._compute_hash(snapshot.new_content)
                        await self._save_task_data(task_data)
                        return True
                    except Exception:
                        pass
                break
        return False

    async def rollback_task(
        self,
        task_id: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Rollback all file changes from a single task.

        Args:
            task_id: Task identifier
            dry_run: If True, don't actually modify files

        Returns:
            Dict with rollback results
        """
        task_data = await self._load_task_data(task_id)
        if not task_data:
            return {"success": False, "error": "Task not found", "files_restored": []}

        files_restored = []
        files_deleted = []
        errors = []

        for snapshot in reversed(task_data.snapshots):
            try:
                path = Path(snapshot.path)

                if dry_run:
                    if snapshot.change_type == ChangeType.CREATE:
                        files_deleted.append(snapshot.path)
                    else:
                        files_restored.append(snapshot.path)
                    continue

                if snapshot.change_type == ChangeType.CREATE:
                    if path.exists():
                        path.unlink()
                        files_deleted.append(snapshot.path)
                elif snapshot.change_type == ChangeType.DELETE:
                    if snapshot.original_content is not None:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(snapshot.original_content)
                        files_restored.append(snapshot.path)
                else:
                    if snapshot.original_content is not None:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(snapshot.original_content)
                        files_restored.append(snapshot.path)

                if not dry_run:
                    snapshot.rolled_back = True

            except Exception as e:
                errors.append(f"Failed to rollback {snapshot.path}: {str(e)}")

        if not dry_run:
            await self._save_task_data(task_data)

        return {
            "success": len(errors) == 0,
            "task_id": task_id,
            "files_restored": files_restored,
            "files_deleted": files_deleted,
            "errors": errors,
            "dry_run": dry_run,
            "can_redo": not dry_run and not errors,
        }

    async def redo_task(
        self,
        task_id: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Redo (reapply) rolled-back file changes for a single task.

        Args:
            task_id: Task identifier
            dry_run: If True, don't actually modify files

        Returns:
            Dict with redo results
        """
        task_data = await self._load_task_data(task_id)
        if not task_data:
            return {"success": False, "error": "Task not found", "files_reapplied": []}

        rolled_back = [s for s in task_data.snapshots if s.rolled_back]
        if not rolled_back:
            return {"success": False, "error": "No rolled-back changes to redo", "files_reapplied": []}

        files_reapplied = []
        files_created = []
        errors = []

        for snapshot in rolled_back:
            if snapshot.new_content is None and snapshot.change_type != ChangeType.DELETE:
                errors.append(f"No new content for {snapshot.path}")
                continue

            try:
                path = Path(snapshot.path)

                if dry_run:
                    if snapshot.change_type == ChangeType.CREATE:
                        files_created.append(snapshot.path)
                    else:
                        files_reapplied.append(snapshot.path)
                    continue

                if snapshot.change_type == ChangeType.CREATE:
                    if snapshot.new_content:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(snapshot.new_content)
                        files_created.append(snapshot.path)
                elif snapshot.change_type == ChangeType.DELETE:
                    if path.exists():
                        path.unlink()
                        files_reapplied.append(snapshot.path)
                else:
                    if snapshot.new_content:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(snapshot.new_content)
                        files_reapplied.append(snapshot.path)

                if not dry_run:
                    snapshot.rolled_back = False

            except Exception as e:
                errors.append(f"Failed to redo {snapshot.path}: {str(e)}")

        if not dry_run:
            await self._save_task_data(task_data)

        return {
            "success": len(errors) == 0,
            "task_id": task_id,
            "files_reapplied": files_reapplied,
            "files_created": files_created,
            "errors": errors,
            "dry_run": dry_run,
        }

    async def get_task_rollback_info(self, task_id: str) -> dict[str, Any] | None:
        """Get information about available rollback for a task."""
        task_data = await self._load_task_data(task_id)
        if not task_data:
            return None

        rolled_back_count = sum(1 for s in task_data.snapshots if s.rolled_back)
        can_redo = rolled_back_count > 0 and all(
            s.new_content is not None for s in task_data.snapshots if s.rolled_back
        )

        return {
            "task_id": task_id,
            "conversation_id": task_data.conversation_id,
            "created_at": task_data.created_at,
            "description": task_data.description,
            "files_modified": len(task_data.snapshots),
            "files_rolled_back": rolled_back_count,
            "can_redo": can_redo,
            "file_paths": [s.path for s in task_data.snapshots],
        }
