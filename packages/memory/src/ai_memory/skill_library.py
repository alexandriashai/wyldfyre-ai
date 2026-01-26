"""
Hierarchical Skill Library (Improvement 3)

Build a searchable skill library with hierarchical composition:
Primitives → Skills → Workflows

This enables reuse of proven patterns and faster plan generation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from ai_core import get_logger

logger = get_logger(__name__)


class SkillLevel(Enum):
    """Skill abstraction level."""
    PRIMITIVE = "primitive"  # Single tool call
    SKILL = "skill"          # Composition of primitives
    WORKFLOW = "workflow"    # Composition of skills


@dataclass
class Skill:
    """
    Represents a reusable skill pattern.

    Skills can be primitives (single actions), composed skills (multiple primitives),
    or workflows (multiple skills).
    """
    id: str
    name: str
    level: SkillLevel
    description: str
    preconditions: list[str]  # Required state/context
    postconditions: list[str]  # Guaranteed outcomes
    steps: list[dict[str, Any]]  # For compound skills
    parameters: dict[str, dict[str, Any]]  # name -> {type, required, default}
    success_rate: float = 0.5
    avg_duration_ms: int = 0
    use_count: int = 0
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "level": self.level.value,
            "description": self.description,
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "steps": self.steps,
            "parameters": self.parameters,
            "success_rate": self.success_rate,
            "avg_duration_ms": self.avg_duration_ms,
            "use_count": self.use_count,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Skill":
        """Create from dictionary."""
        skill = cls(
            id=data["id"],
            name=data["name"],
            level=SkillLevel(data.get("level", "skill")),
            description=data.get("description", ""),
            preconditions=data.get("preconditions", []),
            postconditions=data.get("postconditions", []),
            steps=data.get("steps", []),
            parameters=data.get("parameters", {}),
            success_rate=data.get("success_rate", 0.5),
            avg_duration_ms=data.get("avg_duration_ms", 0),
            use_count=data.get("use_count", 0),
            tags=data.get("tags", []),
        )
        if data.get("created_at"):
            try:
                skill.created_at = datetime.fromisoformat(data["created_at"])
            except (ValueError, TypeError):
                pass
        if data.get("last_used"):
            try:
                skill.last_used = datetime.fromisoformat(data["last_used"])
            except (ValueError, TypeError):
                pass
        return skill

    def update_stats(self, success: bool, duration_ms: int) -> None:
        """Update skill statistics after use."""
        self.use_count += 1
        self.last_used = datetime.now(timezone.utc)

        # Update success rate with exponential moving average
        alpha = 0.2  # Weight for new observation
        new_success = 1.0 if success else 0.0
        self.success_rate = (1 - alpha) * self.success_rate + alpha * new_success

        # Update average duration with exponential moving average
        if self.avg_duration_ms == 0:
            self.avg_duration_ms = duration_ms
        else:
            self.avg_duration_ms = int((1 - alpha) * self.avg_duration_ms + alpha * duration_ms)


class SkillLibrary:
    """
    Searchable skill library with hierarchical composition.

    Stores skills in Qdrant for semantic search and retrieval.

    Usage:
        # Option 1: Pass a pre-configured QdrantStore for skill_library collection
        qdrant_store = QdrantStore(collection_name="skill_library")
        await qdrant_store.connect()
        skill_lib = SkillLibrary(qdrant_store)

        # Option 2: Pass None and call initialize() to create internal store
        skill_lib = SkillLibrary(None)
        await skill_lib.initialize()
    """

    def __init__(self, qdrant_store: Any | None = None):
        """
        Initialize skill library.

        Args:
            qdrant_store: Pre-configured QdrantStore for skill_library collection,
                         or None to create one during initialize()
        """
        self._qdrant = qdrant_store
        self._owns_qdrant = qdrant_store is None  # Track if we need to create our own
        self._cache: dict[str, Skill] = {}  # In-memory cache for frequent access

    async def initialize(self) -> None:
        """Initialize the skill library, creating QdrantStore if needed."""
        if self._qdrant is None and self._owns_qdrant:
            try:
                from .qdrant import QdrantStore
                self._qdrant = QdrantStore(collection_name="skill_library")
                await self._qdrant.connect()
                logger.info("Skill library initialized with new QdrantStore")
            except Exception as e:
                logger.warning(f"Failed to initialize skill library QdrantStore: {e}")
        elif self._qdrant:
            logger.info("Skill library initialized with provided QdrantStore")

    async def find_applicable_skills(
        self,
        goal: str,
        context: dict[str, Any],
        min_success_rate: float = 0.6,
        limit: int = 5,
    ) -> list[Skill]:
        """
        Find skills that match goal and meet preconditions.

        Args:
            goal: The goal/task description
            context: Current execution context
            min_success_rate: Minimum success rate to consider
            limit: Maximum skills to return

        Returns:
            List of applicable skills sorted by success rate
        """
        if not self._qdrant:
            return []

        try:
            # Semantic search on goal (QdrantStore uses collection from constructor)
            candidates = await self._qdrant.search(
                query=goal,
                limit=20,
            )

            # Filter by preconditions and success rate
            applicable = []
            for result in candidates:
                try:
                    # Search returns {id, score, text, metadata} - extract skill data from metadata
                    metadata = result.get("metadata", {})
                    skill_dict = {
                        "id": result.get("id"),
                        **metadata,
                    }
                    skill = Skill.from_dict(skill_dict)

                    # Check preconditions
                    if not self._preconditions_met(skill, context):
                        continue

                    # Check success rate
                    if skill.success_rate < min_success_rate:
                        continue

                    applicable.append(skill)
                except Exception:
                    continue

            # Sort by success rate (descending)
            applicable.sort(key=lambda s: s.success_rate, reverse=True)

            return applicable[:limit]

        except Exception as e:
            logger.warning(f"Failed to find applicable skills: {e}")
            return []

    def _preconditions_met(self, skill: Skill, context: dict[str, Any]) -> bool:
        """Check if all preconditions are met."""
        for precondition in skill.preconditions:
            # Simple key-based check
            # Format: "key:value" or just "key" for existence
            if ":" in precondition:
                key, expected = precondition.split(":", 1)
                if str(context.get(key)) != expected:
                    return False
            else:
                if precondition not in context:
                    return False
        return True

    async def has_skill_for(self, step: dict[str, Any]) -> bool:
        """Check if a skill exists for the given step."""
        step_desc = step.get("description", "") or step.get("title", "")
        if not step_desc:
            return False

        skills = await self.find_applicable_skills(
            goal=step_desc,
            context={},
            min_success_rate=0.5,
            limit=1,
        )
        return len(skills) > 0

    async def compose_workflow(self, skills: list[Skill]) -> dict[str, Any]:
        """
        Compose multiple skills into a workflow.

        Args:
            skills: List of skills to compose

        Returns:
            Workflow definition dict
        """
        # Merge steps from all skills
        all_steps = []
        for skill in skills:
            for step in skill.steps:
                all_steps.append({
                    **step,
                    "skill_id": skill.id,
                    "skill_name": skill.name,
                })

        return {
            "type": "workflow",
            "skills": [s.id for s in skills],
            "skill_names": [s.name for s in skills],
            "steps": all_steps,
            "estimated_duration_ms": sum(s.avg_duration_ms for s in skills),
            "expected_success_rate": min(s.success_rate for s in skills) if skills else 0.0,
        }

    async def learn_skill_from_execution(
        self,
        plan: dict[str, Any],
        outcome: dict[str, Any],
    ) -> Skill | None:
        """
        Extract reusable skill from successful execution.

        Args:
            plan: The executed plan
            outcome: Execution outcome with success status

        Returns:
            New Skill if learned, None otherwise
        """
        if not outcome.get("success"):
            return None

        try:
            skill = Skill(
                id=f"skill_{uuid4().hex[:8]}",
                name=self._generate_skill_name(plan),
                level=SkillLevel.SKILL,
                description=plan.get("goal", plan.get("description", "")),
                preconditions=self._extract_preconditions(plan),
                postconditions=self._extract_postconditions(outcome),
                steps=self._templatize_steps(plan.get("steps", [])),
                parameters=self._extract_parameters(plan),
                success_rate=1.0,  # First success
                avg_duration_ms=outcome.get("duration_ms", 0),
                use_count=1,
                tags=self._extract_tags(plan),
            )

            await self._store_skill(skill)
            logger.info(f"Learned new skill: {skill.name} (id: {skill.id})")
            return skill

        except Exception as e:
            logger.warning(f"Failed to learn skill from execution: {e}")
            return None

    def _generate_skill_name(self, plan: dict[str, Any]) -> str:
        """Generate a descriptive skill name from plan."""
        goal = plan.get("goal", plan.get("description", plan.get("title", "Unknown")))

        # Extract key action words
        action_words = ["create", "add", "update", "fix", "implement", "build", "configure"]
        for word in action_words:
            if word in goal.lower():
                # Extract the target after the action word
                parts = goal.lower().split(word, 1)
                if len(parts) > 1:
                    target = parts[1].strip()[:30]
                    return f"{word.capitalize()} {target}"

        # Fallback to truncated goal
        return goal[:40] if len(goal) <= 40 else goal[:37] + "..."

    def _extract_preconditions(self, plan: dict[str, Any]) -> list[str]:
        """Extract preconditions from plan context."""
        preconditions = []

        # Check for project type
        if plan.get("project_type"):
            preconditions.append(f"project_type:{plan['project_type']}")

        # Check for language/framework
        if plan.get("language"):
            preconditions.append(f"language:{plan['language']}")
        if plan.get("framework"):
            preconditions.append(f"framework:{plan['framework']}")

        # Check for required files
        files = plan.get("files", [])
        for f in files[:3]:  # Limit to 3 key files
            if isinstance(f, dict):
                f = f.get("path", "")
            if f:
                # Extract file pattern (e.g., "*.tsx" from "src/App.tsx")
                if "." in f:
                    ext = f.split(".")[-1]
                    preconditions.append(f"has_file_type:{ext}")

        return preconditions

    def _extract_postconditions(self, outcome: dict[str, Any]) -> list[str]:
        """Extract postconditions from execution outcome."""
        postconditions = []

        # Files created/modified
        files_modified = outcome.get("files_modified", [])
        if files_modified:
            postconditions.append(f"modifies_files:{len(files_modified)}")

        # Success indicators
        if outcome.get("success"):
            postconditions.append("success:true")

        return postconditions

    def _templatize_steps(self, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert plan steps into reusable templates."""
        templates = []

        for step in steps:
            template = {
                "title": step.get("title", ""),
                "description": step.get("description", ""),
                "agent": step.get("agent"),
                "file_patterns": [],
            }

            # Extract file patterns instead of specific paths
            files = step.get("files", [])
            for f in files:
                if isinstance(f, dict):
                    f = f.get("path", "")
                if f and "." in f:
                    # Convert specific path to pattern
                    parts = f.split("/")
                    if len(parts) > 1:
                        pattern = f"**/{parts[-1]}"
                    else:
                        pattern = f"*.{f.split('.')[-1]}"
                    template["file_patterns"].append(pattern)

            templates.append(template)

        return templates

    def _extract_parameters(self, plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Extract parameterizable values from plan."""
        params = {}

        # Root path is always a parameter
        if plan.get("root_path"):
            params["root_path"] = {
                "type": "string",
                "required": True,
                "default": plan["root_path"],
                "description": "Project root directory",
            }

        # Project name
        if plan.get("project_name"):
            params["project_name"] = {
                "type": "string",
                "required": False,
                "default": plan["project_name"],
                "description": "Project name",
            }

        return params

    def _extract_tags(self, plan: dict[str, Any]) -> list[str]:
        """Extract tags for skill categorization."""
        tags = []

        # Language/framework tags
        if plan.get("language"):
            tags.append(plan["language"].lower())
        if plan.get("framework"):
            tags.append(plan["framework"].lower())

        # Action type tags
        description = (plan.get("description", "") + plan.get("goal", "")).lower()
        action_tags = {
            "create": ["creation", "new"],
            "fix": ["bugfix", "fix"],
            "update": ["modification", "update"],
            "refactor": ["refactoring"],
            "test": ["testing"],
            "configure": ["configuration"],
        }
        for action, tag_list in action_tags.items():
            if action in description:
                tags.extend(tag_list)
                break

        return list(set(tags))

    async def _store_skill(self, skill: Skill) -> str | None:
        """Store a skill in the library."""
        if not self._qdrant:
            return None

        try:
            # QdrantStore uses collection from constructor, not as parameter
            doc_id = await self._qdrant.upsert(
                id=skill.id,
                text=f"{skill.name} - {skill.description}",
                metadata=skill.to_dict(),
            )
            self._cache[skill.id] = skill
            return doc_id
        except Exception as e:
            logger.warning(f"Failed to store skill: {e}")
            return None

    async def update_skill_stats(
        self,
        skill_id: str,
        success: bool,
        duration_ms: int,
    ) -> bool:
        """
        Update skill statistics after use.

        Args:
            skill_id: ID of the skill used
            success: Whether execution was successful
            duration_ms: Execution duration in milliseconds

        Returns:
            True if updated successfully
        """
        # Try cache first
        skill = self._cache.get(skill_id)

        if not skill and self._qdrant:
            try:
                # QdrantStore.get() returns {id, text, metadata}
                data = await self._qdrant.get(skill_id)
                if data:
                    metadata = data.get("metadata", {})
                    skill_dict = {"id": data.get("id"), **metadata}
                    skill = Skill.from_dict(skill_dict)
            except Exception:
                pass

        if not skill:
            return False

        skill.update_stats(success, duration_ms)

        # Persist update
        await self._store_skill(skill)
        return True

    async def get_skill(self, skill_id: str) -> Skill | None:
        """Get a skill by ID."""
        # Try cache first
        if skill_id in self._cache:
            return self._cache[skill_id]

        if not self._qdrant:
            return None

        try:
            # QdrantStore.get() returns {id, text, metadata}
            data = await self._qdrant.get(skill_id)
            if data:
                metadata = data.get("metadata", {})
                skill_dict = {"id": data.get("id"), **metadata}
                skill = Skill.from_dict(skill_dict)
                self._cache[skill_id] = skill
                return skill
        except Exception as e:
            logger.warning(f"Failed to get skill {skill_id}: {e}")

        return None

    async def instantiate_skill(
        self,
        skill: Skill,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Instantiate a skill into a plan with context.

        Args:
            skill: The skill to instantiate
            context: Current context for parameter substitution

        Returns:
            Plan dict ready for execution
        """
        # Substitute parameters in steps
        steps = []
        for template in skill.steps:
            step = {
                "title": template.get("title", ""),
                "description": template.get("description", ""),
                "agent": template.get("agent"),
                "files": [],
                "skill_source": skill.id,
            }

            # Resolve file patterns to actual files
            for pattern in template.get("file_patterns", []):
                if context.get("root_path"):
                    resolved = pattern.replace("**", context["root_path"])
                    step["files"].append(resolved)

            steps.append(step)

        return {
            "title": skill.name,
            "description": skill.description,
            "steps": steps,
            "skill_id": skill.id,
            "estimated_duration_ms": skill.avg_duration_ms,
            "expected_success_rate": skill.success_rate,
        }
