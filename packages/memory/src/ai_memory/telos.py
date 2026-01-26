"""
TELOS Goal System - Dynamic goal management with learning integration.

TELOS provides a hierarchical goal system that evolves based on task outcomes,
learnings, and user feedback. Unlike static goal files, TELOS actively learns
and updates itself.

Architecture:
- Global TELOS: Organization-wide mission, beliefs, narratives, models
- Project TELOS: Project-specific goals, strategies, challenges, learnings

Integration:
- Syncs with PAI Memory for learnings (by utility score)
- Extracts strategies from successful multi-step tasks
- Tracks goal progress across related tasks
- Captures ideas from user messages
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, TYPE_CHECKING

import aiofiles

if TYPE_CHECKING:
    from .pai_memory import PAIMemory

# Patterns for detecting ideas in user messages
IDEA_PATTERNS = [
    re.compile(r"(?i)I should\s+(.+)", re.IGNORECASE),
    re.compile(r"(?i)what if\s+(.+)", re.IGNORECASE),
    re.compile(r"(?i)maybe we could\s+(.+)", re.IGNORECASE),
    re.compile(r"(?i)it would be cool to\s+(.+)", re.IGNORECASE),
    re.compile(r"(?i)TODO:\s*(.+)", re.IGNORECASE),
    re.compile(r"(?i)idea:\s*(.+)", re.IGNORECASE),
    re.compile(r"(?i)we should\s+(.+)", re.IGNORECASE),
    re.compile(r"(?i)let's\s+(.+)", re.IGNORECASE),
]


class TelosFileType(str, Enum):
    """Types of TELOS files."""
    # Static core files (populated via Web UI or chat)
    MISSION = "MISSION.md"
    BELIEFS = "BELIEFS.md"
    NARRATIVES = "NARRATIVES.md"

    # Dynamic tracking files
    GOALS = "GOALS.md"
    PROJECTS = "PROJECTS.md"
    CHALLENGES = "CHALLENGES.md"
    IDEAS = "IDEAS.md"

    # Learning files (synced from PAI memory)
    LEARNED = "LEARNED.md"
    STRATEGIES = "STRATEGIES.md"
    MODELS = "MODELS.md"


class GoalStatus(str, Enum):
    """Status of a goal."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class GoalPriority(str, Enum):
    """Priority levels for goals."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Goal:
    """Represents a tracked goal."""
    id: str
    name: str
    description: str
    status: GoalStatus = GoalStatus.PENDING
    priority: GoalPriority = GoalPriority.MEDIUM
    progress: float = 0.0  # 0-100
    project_id: str | None = None
    related_tasks: list[str] = field(default_factory=list)
    milestones: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    target_date: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "progress": self.progress,
            "project_id": self.project_id,
            "related_tasks": self.related_tasks,
            "milestones": self.milestones,
            "created_at": self.created_at.isoformat(),
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Goal":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            status=GoalStatus(data.get("status", "pending")),
            priority=GoalPriority(data.get("priority", "medium")),
            progress=data.get("progress", 0.0),
            project_id=data.get("project_id"),
            related_tasks=data.get("related_tasks", []),
            milestones=data.get("milestones", []),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(timezone.utc),
            target_date=datetime.fromisoformat(data["target_date"]) if data.get("target_date") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            metadata=data.get("metadata", {}),
        )


@dataclass
class Strategy:
    """Represents an extracted successful strategy."""
    id: str
    name: str
    description: str
    pattern: list[str]  # Steps of the strategy
    success_rate: float = 0.0
    use_count: int = 0
    project_id: str | None = None
    task_types: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "pattern": self.pattern,
            "success_rate": self.success_rate,
            "use_count": self.use_count,
            "project_id": self.project_id,
            "task_types": self.task_types,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "metadata": self.metadata,
        }


@dataclass
class Challenge:
    """Represents a tracked challenge/blocker."""
    id: str
    description: str
    status: str = "active"  # active, resolved, deferred
    error_pattern: str | None = None
    resolution: str | None = None
    occurrences: int = 1
    project_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "error_pattern": self.error_pattern,
            "resolution": self.resolution,
            "occurrences": self.occurrences,
            "project_id": self.project_id,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata,
        }


@dataclass
class Idea:
    """Represents a captured idea."""
    id: str
    content: str
    source: str  # "user_message", "task_result", "manual"
    project_id: str | None = None
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source,
            "project_id": self.project_id,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class TelosContext:
    """Context loaded from TELOS files."""
    # Static core
    mission: str = ""
    beliefs: str = ""
    narratives: str = ""

    # Dynamic tracking
    goals: list[Goal] = field(default_factory=list)
    challenges: list[Challenge] = field(default_factory=list)
    ideas: list[Idea] = field(default_factory=list)

    # Learning
    learned: str = ""
    strategies: list[Strategy] = field(default_factory=list)
    models: str = ""

    # Metadata
    project_id: str | None = None
    loaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TelosManager:
    """
    Hierarchical TELOS management with learning integration.

    Manages both Global TELOS (organization-wide) and Project TELOS
    (project-specific) with bidirectional sync to PAI Memory.
    """

    def __init__(
        self,
        telos_dir: str | Path = "/home/wyld-core/pai/TELOS",
        memory: "PAIMemory | None" = None,
    ):
        self.telos_dir = Path(telos_dir)
        self._memory = memory
        self._goals_cache: dict[str, Goal] = {}
        self._strategies_cache: dict[str, Strategy] = {}
        self._challenges_cache: dict[str, Challenge] = {}

    async def initialize(self) -> None:
        """Initialize TELOS directories and default files."""
        # Create global TELOS directory
        self.telos_dir.mkdir(parents=True, exist_ok=True)

        # Create projects subdirectory
        (self.telos_dir / "projects").mkdir(exist_ok=True)

        # Create default global TELOS files if they don't exist
        for file_type in TelosFileType:
            file_path = self.telos_dir / file_type.value
            if not file_path.exists():
                await self._create_default_file(file_path, file_type)

    async def _create_default_file(self, file_path: Path, file_type: TelosFileType) -> None:
        """Create a default TELOS file with template content."""
        templates = {
            TelosFileType.MISSION: """# Mission

> Define your organization's core purpose and mission here.

## Core Mission

[Your mission statement goes here]

## Vision

[Your long-term vision goes here]

---
*Last updated: {timestamp}*
""",
            TelosFileType.BELIEFS: """# Beliefs & Values

> Define your core beliefs and values that guide decision-making.

## Core Values

1. **[Value 1]**: Description
2. **[Value 2]**: Description
3. **[Value 3]**: Description

## Guiding Principles

- Principle 1
- Principle 2
- Principle 3

---
*Last updated: {timestamp}*
""",
            TelosFileType.NARRATIVES: """# Narratives & Context

> Tell your story - why you built this, what drives you.

## Our Story

[Your story goes here]

## Context

[Important context for the AI to understand]

---
*Last updated: {timestamp}*
""",
            TelosFileType.GOALS: """# Goals

> Track active goals and their progress.

## Active Goals

*No active goals yet. Goals will be tracked here as you work.*

## Completed Goals

*Completed goals will be archived here.*

---
*Last synced: {timestamp}*
""",
            TelosFileType.PROJECTS: """# Projects

> Track active projects and their status.

## Active Projects

*No active projects yet.*

## Archived Projects

*Completed projects will be archived here.*

---
*Last updated: {timestamp}*
""",
            TelosFileType.CHALLENGES: """# Challenges & Blockers

> Track recurring issues and their resolutions.

## Active Challenges

*No active challenges recorded.*

## Resolved Challenges

*Resolved challenges with solutions will be documented here.*

---
*Last synced: {timestamp}*
""",
            TelosFileType.IDEAS: """# Ideas

> Captured ideas for future consideration.

## Pending Ideas

*Ideas captured from conversations will appear here.*

## Implemented Ideas

*Ideas that have been implemented.*

---
*Last updated: {timestamp}*
""",
            TelosFileType.LEARNED: """# Learnings

> Top learnings synced from PAI Memory by utility score.

## Top Learnings

*Learnings will be synced from memory based on utility scores.*

---
*Last synced: {timestamp}*
""",
            TelosFileType.STRATEGIES: """# Strategies

> Successful patterns extracted from task executions.

## Proven Strategies

*Successful multi-step patterns will be documented here.*

---
*Last synced: {timestamp}*
""",
            TelosFileType.MODELS: """# Mental Models

> Frameworks and models used for reasoning.

## Active Models

*Mental models and frameworks will be documented here.*

---
*Last updated: {timestamp}*
""",
        }

        template = templates.get(file_type, "# {file_type}\n\n*Content goes here.*\n")
        content = template.format(
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            file_type=file_type.value.replace(".md", ""),
        )

        async with aiofiles.open(file_path, "w") as f:
            await f.write(content)

    # =========================================================================
    # Context Loading
    # =========================================================================

    async def load_context(self, project_id: str | None = None) -> TelosContext:
        """
        Load Global TELOS + Project TELOS if project_id provided.

        Args:
            project_id: Optional project ID to load project-specific TELOS

        Returns:
            TelosContext with loaded data
        """
        context = TelosContext(project_id=project_id)

        # Load global TELOS
        global_telos = await self.load_global_telos()
        context.mission = global_telos.get("mission", "")
        context.beliefs = global_telos.get("beliefs", "")
        context.narratives = global_telos.get("narratives", "")
        context.models = global_telos.get("models", "")

        # Load global learnings
        context.learned = global_telos.get("learned", "")

        # Load global goals and strategies
        context.goals = await self._load_goals()
        context.strategies = await self._load_strategies()
        context.challenges = await self._load_challenges()
        context.ideas = await self._load_ideas()

        # If project_id, also load project-specific TELOS
        if project_id:
            project_telos = await self.load_project_telos(project_id)
            # Merge project data with global (project takes precedence)
            if project_telos.get("goals"):
                context.goals.extend(project_telos["goals"])
            if project_telos.get("learned"):
                context.learned += f"\n\n## Project Learnings\n{project_telos['learned']}"
            if project_telos.get("strategies"):
                context.strategies.extend(project_telos["strategies"])
            if project_telos.get("challenges"):
                context.challenges.extend(project_telos["challenges"])
            if project_telos.get("ideas"):
                context.ideas.extend(project_telos["ideas"])

        return context

    async def load_global_telos(self) -> dict[str, str]:
        """Load MISSION, BELIEFS, NARRATIVES, MODELS, LEARNED."""
        result = {}

        async def read_file(file_type: TelosFileType) -> tuple[str, str]:
            file_path = self.telos_dir / file_type.value
            if file_path.exists():
                async with aiofiles.open(file_path, "r") as f:
                    content = await f.read()
                return file_type.name.lower(), content
            return file_type.name.lower(), ""

        # Read all files in parallel
        tasks = [
            read_file(TelosFileType.MISSION),
            read_file(TelosFileType.BELIEFS),
            read_file(TelosFileType.NARRATIVES),
            read_file(TelosFileType.MODELS),
            read_file(TelosFileType.LEARNED),
        ]

        results = await asyncio.gather(*tasks)
        for name, content in results:
            result[name] = content

        return result

    async def load_project_telos(self, project_id: str) -> dict[str, Any]:
        """Load project-specific GOALS, STRATEGIES, CHALLENGES, LEARNED."""
        project_dir = self.telos_dir / "projects" / project_id
        result: dict[str, Any] = {
            "goals": [],
            "learned": "",
            "strategies": [],
            "challenges": [],
            "ideas": [],
        }

        if not project_dir.exists():
            return result

        # Read project files
        for file_type in [TelosFileType.GOALS, TelosFileType.LEARNED, TelosFileType.STRATEGIES,
                          TelosFileType.CHALLENGES, TelosFileType.IDEAS]:
            file_path = project_dir / file_type.value
            if file_path.exists():
                async with aiofiles.open(file_path, "r") as f:
                    content = await f.read()
                result[file_type.name.lower()] = content

        return result

    # =========================================================================
    # Static File Management (via Web UI or Chat)
    # =========================================================================

    async def update_mission(self, content: str) -> None:
        """Update global MISSION.md (from wizard or chat)."""
        await self._update_file(TelosFileType.MISSION, content)

    async def update_beliefs(self, content: str) -> None:
        """Update global BELIEFS.md."""
        await self._update_file(TelosFileType.BELIEFS, content)

    async def update_narratives(self, content: str) -> None:
        """Update global NARRATIVES.md."""
        await self._update_file(TelosFileType.NARRATIVES, content)

    async def update_models(self, content: str) -> None:
        """Update global MODELS.md."""
        await self._update_file(TelosFileType.MODELS, content)

    async def _update_file(
        self,
        file_type: TelosFileType,
        content: str,
        project_id: str | None = None,
    ) -> None:
        """Update a TELOS file."""
        if project_id:
            file_path = self.telos_dir / "projects" / project_id / file_type.value
            file_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            file_path = self.telos_dir / file_type.value

        # Add timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        if not content.endswith("\n"):
            content += "\n"
        content += f"\n---\n*Last updated: {timestamp}*\n"

        async with aiofiles.open(file_path, "w") as f:
            await f.write(content)

    # =========================================================================
    # Project TELOS Lifecycle
    # =========================================================================

    async def init_project_telos(self, project_id: str, name: str) -> None:
        """Create project TELOS directory with templates."""
        project_dir = self.telos_dir / "projects" / project_id
        project_dir.mkdir(parents=True, exist_ok=True)

        # Create project-specific files
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # GOALS.md for project
        goals_content = f"""# {name} - Goals

## Project Goals

*Define project-specific goals here.*

## Milestones

*Track project milestones.*

---
*Created: {timestamp}*
"""
        async with aiofiles.open(project_dir / "GOALS.md", "w") as f:
            await f.write(goals_content)

        # LEARNED.md for project
        learned_content = f"""# {name} - Learnings

## Project Learnings

*Project-specific learnings will be synced here.*

---
*Created: {timestamp}*
"""
        async with aiofiles.open(project_dir / "LEARNED.md", "w") as f:
            await f.write(learned_content)

        # STRATEGIES.md for project
        strategies_content = f"""# {name} - Strategies

## Successful Strategies

*Strategies that work for this project.*

---
*Created: {timestamp}*
"""
        async with aiofiles.open(project_dir / "STRATEGIES.md", "w") as f:
            await f.write(strategies_content)

        # CHALLENGES.md for project
        challenges_content = f"""# {name} - Challenges

## Active Challenges

*Project-specific blockers and issues.*

## Resolved Challenges

*Resolved issues with solutions.*

---
*Created: {timestamp}*
"""
        async with aiofiles.open(project_dir / "CHALLENGES.md", "w") as f:
            await f.write(challenges_content)

        # IDEAS.md for project
        ideas_content = f"""# {name} - Ideas

## Project Ideas

*Ideas captured in project context.*

---
*Created: {timestamp}*
"""
        async with aiofiles.open(project_dir / "IDEAS.md", "w") as f:
            await f.write(ideas_content)

    async def archive_project_telos(self, project_id: str) -> None:
        """Archive completed project's TELOS."""
        project_dir = self.telos_dir / "projects" / project_id
        archive_dir = self.telos_dir / "projects" / "_archived" / project_id

        if project_dir.exists():
            archive_dir.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.move(str(project_dir), str(archive_dir))

    # =========================================================================
    # Dynamic Updates (Auto-triggered)
    # =========================================================================

    async def sync_learnings(self, project_id: str | None = None, limit: int = 20) -> int:
        """
        Sync top learnings from PAI memory to LEARNED.md.

        Args:
            project_id: If provided, sync to project LEARNED.md
            limit: Maximum learnings to sync

        Returns:
            Number of learnings synced
        """
        if not self._memory:
            return 0

        # Get top learnings by utility score
        learnings = await self._memory.get_learnings_by_utility(
            min_utility=0.6,  # Only high-utility learnings
            limit=limit,
        )

        if not learnings:
            return 0

        # Sort by utility score
        learnings.sort(key=lambda x: x.get("utility_score", 0), reverse=True)

        # Format learnings for markdown
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        content = f"# Learnings\n\n*Last synced: {timestamp}*\n\n## Top Learnings (by utility score)\n\n"

        for i, learning in enumerate(learnings, 1):
            utility = learning.get("utility_score", 0.5)
            text = learning.get("content", learning.get("text", ""))[:200]
            phase = learning.get("phase", "learn").upper()
            content += f"{i}. **[{utility:.2f}]** {text}\n"
            content += f"   - Phase: {phase}\n\n"

        # Write to appropriate file
        if project_id:
            await self._update_file(TelosFileType.LEARNED, content, project_id)
        else:
            await self._update_file(TelosFileType.LEARNED, content)

        return len(learnings)

    async def update_goal_progress(
        self,
        goal_id: str,
        progress: float,
        project_id: str | None = None,
    ) -> bool:
        """
        Track goal completion progress.

        Args:
            goal_id: ID of the goal to update
            progress: New progress value (0-100)
            project_id: Optional project context

        Returns:
            True if updated successfully
        """
        # Load current goals
        goals = await self._load_goals(project_id)

        # Find and update goal
        for goal in goals:
            if goal.id == goal_id:
                goal.progress = min(100.0, max(0.0, progress))
                if goal.progress >= 100.0:
                    goal.status = GoalStatus.COMPLETED
                    goal.completed_at = datetime.now(timezone.utc)
                elif goal.progress > 0:
                    goal.status = GoalStatus.IN_PROGRESS

                # Save updated goals
                await self._save_goals(goals, project_id)
                return True

        return False

    async def add_goal(
        self,
        name: str,
        description: str,
        priority: GoalPriority = GoalPriority.MEDIUM,
        project_id: str | None = None,
        target_date: datetime | None = None,
        milestones: list[dict[str, Any]] | None = None,
    ) -> Goal:
        """Add a new goal."""
        import uuid
        goal = Goal(
            id=f"GOAL-{uuid.uuid4().hex[:8].upper()}",
            name=name,
            description=description,
            priority=priority,
            project_id=project_id,
            target_date=target_date,
            milestones=milestones or [],
        )

        goals = await self._load_goals(project_id)
        goals.append(goal)
        await self._save_goals(goals, project_id)

        return goal

    async def extract_strategy(
        self,
        task_traces: list[dict[str, Any]],
        project_id: str | None = None,
    ) -> Strategy | None:
        """
        Extract successful patterns from task traces to STRATEGIES.md.

        Args:
            task_traces: List of task execution traces
            project_id: Optional project context

        Returns:
            Extracted Strategy if successful pattern detected
        """
        if len(task_traces) < 3:
            return None

        # Extract tool sequence from traces
        tool_sequence = []
        for trace in task_traces:
            if "tool_name" in trace:
                tool_sequence.append(trace["tool_name"])
            elif "phase" in trace:
                tool_sequence.append(f"phase:{trace['phase']}")

        if len(tool_sequence) < 3:
            return None

        # Create strategy
        import uuid
        strategy = Strategy(
            id=f"STRAT-{uuid.uuid4().hex[:8].upper()}",
            name=f"Multi-step pattern ({len(tool_sequence)} steps)",
            description="Automatically extracted successful pattern",
            pattern=tool_sequence[:10],  # Limit to 10 steps
            success_rate=1.0,  # Initially successful
            use_count=1,
            project_id=project_id,
        )

        # Save strategy
        strategies = await self._load_strategies(project_id)
        strategies.append(strategy)
        await self._save_strategies(strategies, project_id)

        return strategy

    async def capture_idea(
        self,
        idea_content: str,
        source: str = "user_message",
        project_id: str | None = None,
        tags: list[str] | None = None,
    ) -> Idea:
        """
        Capture idea to project or global IDEAS.md.

        Args:
            idea_content: The idea content
            source: Source of the idea (user_message, task_result, manual)
            project_id: Optional project context
            tags: Optional tags for categorization

        Returns:
            Created Idea object
        """
        import uuid
        idea = Idea(
            id=f"IDEA-{uuid.uuid4().hex[:8].upper()}",
            content=idea_content,
            source=source,
            project_id=project_id,
            tags=tags or [],
        )

        ideas = await self._load_ideas(project_id)
        ideas.append(idea)
        await self._save_ideas(ideas, project_id)

        return idea

    async def update_challenges(
        self,
        challenge_description: str,
        status: str = "active",
        error_pattern: str | None = None,
        resolution: str | None = None,
        project_id: str | None = None,
    ) -> Challenge:
        """
        Track project challenge resolution.

        Args:
            challenge_description: Description of the challenge
            status: Status (active, resolved, deferred)
            error_pattern: Optional error pattern for matching
            resolution: Resolution if resolved
            project_id: Optional project context

        Returns:
            Challenge object (new or updated)
        """
        challenges = await self._load_challenges(project_id)

        # Check if similar challenge exists
        for challenge in challenges:
            if (challenge.description.lower() in challenge_description.lower() or
                challenge_description.lower() in challenge.description.lower()):
                # Update existing challenge
                challenge.occurrences += 1
                if status == "resolved" and resolution:
                    challenge.status = "resolved"
                    challenge.resolution = resolution
                    challenge.resolved_at = datetime.now(timezone.utc)
                await self._save_challenges(challenges, project_id)
                return challenge

        # Create new challenge
        import uuid
        challenge = Challenge(
            id=f"CHAL-{uuid.uuid4().hex[:8].upper()}",
            description=challenge_description,
            status=status,
            error_pattern=error_pattern,
            resolution=resolution,
            project_id=project_id,
        )

        challenges.append(challenge)
        await self._save_challenges(challenges, project_id)

        return challenge

    async def detect_ideas_in_message(
        self,
        message: str,
        project_id: str | None = None,
    ) -> list[Idea]:
        """
        Detect and capture ideas from user messages using pattern matching.

        Args:
            message: User message to scan
            project_id: Optional project context

        Returns:
            List of captured ideas
        """
        captured_ideas = []

        for pattern in IDEA_PATTERNS:
            matches = pattern.findall(message)
            for match in matches:
                idea = await self.capture_idea(
                    idea_content=match.strip(),
                    source="user_message",
                    project_id=project_id,
                )
                captured_ideas.append(idea)

        return captured_ideas

    # =========================================================================
    # Context Injection
    # =========================================================================

    def get_relevant_telos(self, task_type: str) -> list[str]:
        """
        Get relevant TELOS file types for a task type.

        Args:
            task_type: Type of task being executed

        Returns:
            List of relevant TelosFileType names
        """
        relevance_map = {
            "planning": ["MISSION", "GOALS", "STRATEGIES", "CHALLENGES"],
            "coding": ["PROJECTS", "LEARNED", "STRATEGIES"],
            "research": ["GOALS", "IDEAS", "MODELS"],
            "debugging": ["CHALLENGES", "LEARNED", "STRATEGIES"],
            "review": ["BELIEFS", "LEARNED", "STRATEGIES"],
            "default": ["MISSION", "GOALS", "LEARNED"],
        }

        return relevance_map.get(task_type, relevance_map["default"])

    async def get_context_for_task(
        self,
        task_type: str,
        project_id: str | None = None,
    ) -> str:
        """
        Get formatted TELOS context for injection into task.

        Args:
            task_type: Type of task being executed
            project_id: Optional project context

        Returns:
            Formatted context string for injection
        """
        context_parts = []
        relevant_files = self.get_relevant_telos(task_type)
        context = await self.load_context(project_id)

        # Format based on relevance
        if "MISSION" in relevant_files and context.mission:
            # Extract just the core mission (first meaningful paragraph)
            mission_lines = [l for l in context.mission.split("\n") if l.strip() and not l.startswith("#")]
            if mission_lines:
                context_parts.append(f"[Mission] {mission_lines[0][:200]}")

        if "GOALS" in relevant_files and context.goals:
            active_goals = [g for g in context.goals if g.status in (GoalStatus.IN_PROGRESS, GoalStatus.PENDING)]
            if active_goals:
                goals_text = ", ".join(f"{g.name} ({g.progress:.0f}%)" for g in active_goals[:3])
                context_parts.append(f"[Active Goals] {goals_text}")

        if "LEARNED" in relevant_files and context.learned:
            # Extract top learnings
            learned_lines = [l for l in context.learned.split("\n")
                           if l.strip() and l.startswith(("1.", "2.", "3."))]
            if learned_lines:
                context_parts.append(f"[Key Learnings] {' '.join(learned_lines[:3])[:300]}")

        if "STRATEGIES" in relevant_files and context.strategies:
            # Include top strategy
            if context.strategies:
                top_strategy = context.strategies[0]
                context_parts.append(f"[Strategy] {top_strategy.name}: {' -> '.join(top_strategy.pattern[:5])}")

        if "CHALLENGES" in relevant_files and context.challenges:
            active_challenges = [c for c in context.challenges if c.status == "active"]
            if active_challenges:
                context_parts.append(f"[Active Challenges] {active_challenges[0].description[:150]}")

        return "\n".join(context_parts)

    # =========================================================================
    # Private Helpers
    # =========================================================================

    async def _load_goals(self, project_id: str | None = None) -> list[Goal]:
        """Load goals from file or cache."""
        cache_key = f"goals:{project_id or 'global'}"
        if cache_key in self._goals_cache:
            return list(self._goals_cache.values())

        goals_file = self._get_file_path(TelosFileType.GOALS, project_id)
        if not goals_file.exists():
            return []

        async with aiofiles.open(goals_file, "r") as f:
            content = await f.read()

        # Parse goals from markdown (simplified - in production, use structured data)
        goals = []
        # For now, return empty - structured data would be in a separate JSON file
        return goals

    async def _save_goals(self, goals: list[Goal], project_id: str | None = None) -> None:
        """Save goals to markdown file."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        content = f"# Goals\n\n## Active Goals\n\n"

        active_goals = [g for g in goals if g.status != GoalStatus.COMPLETED]
        completed_goals = [g for g in goals if g.status == GoalStatus.COMPLETED]

        for goal in active_goals:
            status_emoji = {
                GoalStatus.PENDING: "⏳",
                GoalStatus.IN_PROGRESS: "🔄",
                GoalStatus.BLOCKED: "🚫",
            }.get(goal.status, "📌")

            content += f"### [{goal.id}] {goal.name} {status_emoji}\n"
            content += f"- **Status**: {goal.status.value.title()} ({goal.progress:.0f}%)\n"
            content += f"- **Priority**: {goal.priority.value.title()}\n"
            content += f"- **Created**: {goal.created_at.strftime('%Y-%m-%d')}\n"
            if goal.target_date:
                content += f"- **Target**: {goal.target_date.strftime('%Y-%m-%d')}\n"
            content += f"\n{goal.description}\n\n"

            if goal.milestones:
                content += "**Milestones:**\n"
                for ms in goal.milestones:
                    done = "x" if ms.get("completed") else " "
                    content += f"- [{done}] {ms.get('name', 'Milestone')}\n"
                content += "\n"

        content += "## Completed Goals\n\n"
        for goal in completed_goals[:5]:  # Limit to last 5 completed
            content += f"- ✅ [{goal.id}] {goal.name} - Completed {goal.completed_at.strftime('%Y-%m-%d') if goal.completed_at else 'N/A'}\n"

        content += f"\n---\n*Last synced: {timestamp}*\n"

        await self._update_file(TelosFileType.GOALS, content, project_id)

    async def _load_strategies(self, project_id: str | None = None) -> list[Strategy]:
        """Load strategies."""
        # Simplified - would use structured data in production
        return list(self._strategies_cache.values())

    async def _save_strategies(self, strategies: list[Strategy], project_id: str | None = None) -> None:
        """Save strategies to markdown file."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        content = "# Strategies\n\n## Successful Strategies\n\n"

        for strategy in strategies:
            content += f"### [{strategy.id}] {strategy.name}\n"
            content += f"**Success Rate**: {strategy.success_rate*100:.0f}% ({strategy.use_count} uses)\n\n"
            content += "**Pattern**:\n"
            for i, step in enumerate(strategy.pattern, 1):
                content += f"{i}. {step}\n"
            content += "\n"

        content += f"\n---\n*Last synced: {timestamp}*\n"

        await self._update_file(TelosFileType.STRATEGIES, content, project_id)
        # Update cache
        for s in strategies:
            self._strategies_cache[s.id] = s

    async def _load_challenges(self, project_id: str | None = None) -> list[Challenge]:
        """Load challenges."""
        return list(self._challenges_cache.values())

    async def _save_challenges(self, challenges: list[Challenge], project_id: str | None = None) -> None:
        """Save challenges to markdown file."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        active = [c for c in challenges if c.status == "active"]
        resolved = [c for c in challenges if c.status == "resolved"]

        content = "# Challenges & Blockers\n\n## Active Challenges\n\n"

        for challenge in active:
            content += f"### [{challenge.id}] {challenge.description[:100]}\n"
            content += f"- **Occurrences**: {challenge.occurrences}\n"
            content += f"- **First seen**: {challenge.created_at.strftime('%Y-%m-%d')}\n"
            if challenge.error_pattern:
                content += f"- **Error pattern**: `{challenge.error_pattern[:50]}`\n"
            content += "\n"

        content += "## Resolved Challenges\n\n"
        for challenge in resolved[:10]:  # Last 10
            content += f"### [{challenge.id}] {challenge.description[:100]}\n"
            content += f"- **Resolution**: {challenge.resolution}\n"
            content += f"- **Resolved**: {challenge.resolved_at.strftime('%Y-%m-%d') if challenge.resolved_at else 'N/A'}\n\n"

        content += f"\n---\n*Last synced: {timestamp}*\n"

        await self._update_file(TelosFileType.CHALLENGES, content, project_id)
        # Update cache
        for c in challenges:
            self._challenges_cache[c.id] = c

    async def _load_ideas(self, project_id: str | None = None) -> list[Idea]:
        """Load ideas."""
        # Simplified - would use structured data in production
        return []

    async def _save_ideas(self, ideas: list[Idea], project_id: str | None = None) -> None:
        """Save ideas to markdown file."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        content = "# Ideas\n\n## Pending Ideas\n\n"

        for idea in ideas:
            tags_str = f" [{', '.join(idea.tags)}]" if idea.tags else ""
            content += f"- **[{idea.id}]** {idea.content}{tags_str}\n"
            content += f"  - Source: {idea.source}, {idea.created_at.strftime('%Y-%m-%d')}\n"

        content += f"\n---\n*Last updated: {timestamp}*\n"

        await self._update_file(TelosFileType.IDEAS, content, project_id)

    def _get_file_path(self, file_type: TelosFileType, project_id: str | None = None) -> Path:
        """Get file path for a TELOS file."""
        if project_id:
            return self.telos_dir / "projects" / project_id / file_type.value
        return self.telos_dir / file_type.value


# =========================================================================
# Module-level singleton
# =========================================================================

_telos_manager: TelosManager | None = None


def get_telos_manager(
    telos_dir: str | Path = "/home/wyld-core/pai/TELOS",
    memory: "PAIMemory | None" = None,
) -> TelosManager:
    """Get or create the global TELOS manager."""
    global _telos_manager
    if _telos_manager is None:
        _telos_manager = TelosManager(telos_dir, memory)
    return _telos_manager


async def init_telos(
    telos_dir: str | Path = "/home/wyld-core/pai/TELOS",
    memory: "PAIMemory | None" = None,
) -> TelosManager:
    """Initialize and return the TELOS manager."""
    manager = get_telos_manager(telos_dir, memory)
    await manager.initialize()
    return manager
