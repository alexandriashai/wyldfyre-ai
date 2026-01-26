"""
Phase-specific memory manager for PAI phases.

Provides phase-specific retrieval and storage with:
- Parallel async queries per phase
- Result caching within task scope
- Feedback loop tracking for used learnings
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from ai_core import get_logger

from .pai_memory import Learning, LearningScope, PAIMemory, PAIPhase
from .skill_library import SkillLibrary

logger = get_logger(__name__)

# Cache TTL in seconds
CACHE_TTL = 300  # 5 minutes


@dataclass
class CacheEntry:
    """Cached query result with expiration."""
    data: Any
    timestamp: float

    def is_expired(self) -> bool:
        return time.time() - self.timestamp > CACHE_TTL


@dataclass
class PhaseContext:
    """Context retrieved for a specific phase."""
    phase: PAIPhase
    learnings: list[dict[str, Any]] = field(default_factory=list)
    skills: list[dict[str, Any]] = field(default_factory=list)
    patterns: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    learning_ids: list[str] = field(default_factory=list)  # Track IDs for feedback


class PhaseMemoryManager:
    """
    Manages phase-specific memory retrieval and storage with async parallel queries.

    Key features:
    - Phase-specific query templates for each PAI phase
    - Parallel async queries to reduce latency
    - Result caching within task scope (300s TTL)
    - Tracks used learning IDs for feedback loop
    """

    # Phase-specific query configurations
    PHASE_QUERIES = {
        PAIPhase.OBSERVE: {
            "categories": ["domain", "context", "known_issue"],
            "limit": 5,
            "description": "Domain context and known issues",
        },
        PAIPhase.THINK: {
            "categories": ["reasoning", "analysis", "strategy"],
            "limit": 5,
            "description": "Reasoning patterns and analysis strategies",
        },
        PAIPhase.PLAN: {
            "categories": ["plan", "tool_pattern", "anti_pattern"],
            "limit": 5,
            "description": "Successful plans and tool patterns",
        },
        PAIPhase.BUILD: {
            "categories": ["tool_success", "tool_error", "tool_pattern"],
            "limit": 3,
            "description": "Tool usage patterns",
        },
        PAIPhase.EXECUTE: {
            "categories": ["execution", "tool_success", "tool_error"],
            "limit": 3,
            "description": "Execution patterns",
        },
        PAIPhase.VERIFY: {
            "categories": ["verification", "validation", "error"],
            "limit": 3,
            "description": "Verification strategies and error patterns",
        },
        PAIPhase.LEARN: {
            "categories": ["learning", "pattern", "insight"],
            "limit": 5,
            "description": "Previous learnings and insights",
        },
    }

    def __init__(
        self,
        memory: PAIMemory,
        skill_library: SkillLibrary | None = None,
    ):
        """
        Initialize PhaseMemoryManager.

        Args:
            memory: PAIMemory instance for storage and retrieval
            skill_library: Optional SkillLibrary for skill retrieval
        """
        self._memory = memory
        self._skill_library = skill_library
        self._cache: dict[str, CacheEntry] = {}
        self._used_learning_ids: dict[str, set[str]] = {}  # task_id -> set of learning IDs

    async def get_phase_context(
        self,
        phase: PAIPhase,
        task_id: str,
        task_description: str,
        agent_type: str,
        permission_level: int = 1,
        project_id: str | None = None,
        domain_id: str | None = None,
        tool_name: str | None = None,
        **kwargs: Any,
    ) -> PhaseContext:
        """
        Get phase-specific context using parallel queries.

        Args:
            phase: The PAI phase to get context for
            task_id: Current task ID (for caching and tracking)
            task_description: Description of the task for semantic search
            agent_type: Type of agent making the request
            permission_level: Permission level for ACL filtering
            project_id: Optional project context for scope filtering
            domain_id: Optional domain context for scope filtering
            tool_name: Optional tool name for BUILD phase
            **kwargs: Additional phase-specific parameters

        Returns:
            PhaseContext with relevant learnings, skills, and patterns
        """
        # Check cache first
        cache_key = f"{task_id}:{phase.value}:{tool_name or ''}"
        if cache_key in self._cache and not self._cache[cache_key].is_expired():
            cached = self._cache[cache_key].data
            # Track learning IDs even from cache
            if task_id not in self._used_learning_ids:
                self._used_learning_ids[task_id] = set()
            self._used_learning_ids[task_id].update(cached.learning_ids)
            return cached

        # Get phase-specific query config
        config = self.PHASE_QUERIES.get(phase, {
            "categories": ["general"],
            "limit": 3,
            "description": "General context",
        })

        # Build parallel queries
        queries = []

        # Query 1: Semantic search on task description
        queries.append(self._search_by_query(
            query=task_description,
            phase=phase,
            limit=config["limit"],
            agent_type=agent_type,
            permission_level=permission_level,
            project_id=project_id,
            domain_id=domain_id,
        ))

        # Query 2: Category-specific searches (parallel for each category)
        for category in config["categories"]:
            queries.append(self._search_by_category(
                query=task_description,
                category=category,
                limit=config["limit"],
                agent_type=agent_type,
                permission_level=permission_level,
                project_id=project_id,
                domain_id=domain_id,
            ))

        # Query 3: Tool-specific search for BUILD phase
        if phase == PAIPhase.BUILD and tool_name:
            queries.append(self._search_tool_patterns(
                tool_name=tool_name,
                agent_type=agent_type,
                permission_level=permission_level,
            ))

        # Query 4: Skills from SkillLibrary (for THINK/PLAN phases)
        if phase in (PAIPhase.THINK, PAIPhase.PLAN) and self._skill_library:
            queries.append(self._get_applicable_skills(
                task_description=task_description,
                min_success_rate=0.6,
            ))

        # Execute all queries in parallel
        results = await asyncio.gather(*queries, return_exceptions=True)

        # Process results
        context = PhaseContext(phase=phase)
        seen_ids: set[str] = set()

        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Phase context query failed: {result}")
                continue

            if isinstance(result, list):
                for item in result:
                    item_id = item.get("id")
                    if item_id and item_id not in seen_ids:
                        seen_ids.add(item_id)

                        # Categorize the result
                        item_category = item.get("category", "general")
                        if item_category in ("tool_success", "tool_error", "tool_pattern"):
                            context.patterns.append(item)
                        else:
                            context.learnings.append(item)

                        # Track learning ID for feedback
                        if item_id:
                            context.learning_ids.append(item_id)

            elif isinstance(result, dict) and "skills" in result:
                context.skills = result["skills"]

        # Sort learnings by utility score (descending)
        context.learnings.sort(
            key=lambda x: x.get("utility_score", 0.5),
            reverse=True,
        )

        # Limit total learnings
        context.learnings = context.learnings[:config["limit"] * 2]

        # Add metadata
        context.metadata = {
            "phase": phase.value,
            "query_count": len(queries),
            "learnings_found": len(context.learnings),
            "patterns_found": len(context.patterns),
            "skills_found": len(context.skills),
        }

        # Cache the result
        self._cache[cache_key] = CacheEntry(data=context, timestamp=time.time())

        # Track used learning IDs for feedback
        if task_id not in self._used_learning_ids:
            self._used_learning_ids[task_id] = set()
        self._used_learning_ids[task_id].update(context.learning_ids)

        logger.debug(
            f"Phase context retrieved",
            phase=phase.value,
            learnings=len(context.learnings),
            patterns=len(context.patterns),
            skills=len(context.skills),
        )

        return context

    async def _search_by_query(
        self,
        query: str,
        phase: PAIPhase,
        limit: int,
        agent_type: str,
        permission_level: int,
        project_id: str | None = None,
        domain_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search learnings by query with phase filter."""
        return await self._memory.search_learnings(
            query=query[:200],  # Limit query length
            phase=phase,
            limit=limit,
            agent_type=agent_type,
            permission_level=permission_level,
            project_id=project_id,
            domain_id=domain_id,
        )

    async def _search_by_category(
        self,
        query: str,
        category: str,
        limit: int,
        agent_type: str,
        permission_level: int,
        project_id: str | None = None,
        domain_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search learnings by category."""
        return await self._memory.search_learnings(
            query=query[:200],
            category=category,
            limit=limit,
            agent_type=agent_type,
            permission_level=permission_level,
            project_id=project_id,
            domain_id=domain_id,
        )

    async def _search_tool_patterns(
        self,
        tool_name: str,
        agent_type: str,
        permission_level: int,
    ) -> list[dict[str, Any]]:
        """Search for tool-specific patterns."""
        results = []

        # Search for successful patterns
        success_results = await self._memory.search_learnings(
            query=f"{tool_name} successful usage pattern",
            category="tool_success",
            limit=3,
            agent_type=agent_type,
            permission_level=permission_level,
        )
        results.extend(success_results)

        # Search for error patterns
        error_results = await self._memory.search_learnings(
            query=f"{tool_name} error issue problem",
            category="tool_error",
            limit=2,
            agent_type=agent_type,
            permission_level=permission_level,
        )
        results.extend(error_results)

        return results

    async def _get_applicable_skills(
        self,
        task_description: str,
        min_success_rate: float = 0.6,
    ) -> dict[str, Any]:
        """Get applicable skills from SkillLibrary."""
        if not self._skill_library:
            return {"skills": []}

        try:
            skills = await self._skill_library.find_applicable_skills(
                task_description=task_description,
                min_success_rate=min_success_rate,
                limit=5,
            )
            return {"skills": [s.to_dict() for s in skills]}
        except Exception as e:
            logger.warning(f"Skill lookup failed: {e}")
            return {"skills": []}

    async def store_phase_insight(
        self,
        phase: PAIPhase,
        task_id: str,
        insight: str,
        category: str,
        confidence: float = 0.7,
        agent_type: str = "",
        permission_level: int = 1,
        project_id: str | None = None,
        domain_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Store a phase-specific insight as a learning.

        Args:
            phase: The PAI phase this insight came from
            task_id: Task ID for correlation
            insight: The insight content to store
            category: Category for the insight
            confidence: Confidence score (0-1)
            agent_type: Type of agent storing the insight
            permission_level: Permission level for ACL
            project_id: Optional project scope
            domain_id: Optional domain scope
            metadata: Additional metadata

        Returns:
            Document ID if stored successfully, None otherwise
        """
        # Determine scope based on project/domain
        scope = LearningScope.GLOBAL
        if domain_id:
            scope = LearningScope.DOMAIN
        elif project_id:
            scope = LearningScope.PROJECT

        learning = Learning(
            content=insight,
            phase=phase,
            category=category,
            task_id=task_id,
            agent_type=agent_type,
            confidence=confidence,
            metadata=metadata or {},
            created_by_agent=agent_type,
            permission_level=permission_level,
            scope=scope,
            project_id=project_id,
            domain_id=domain_id,
        )

        doc_id = await self._memory.store_learning(learning, agent_type=agent_type)

        if doc_id:
            logger.debug(
                f"Stored phase insight",
                phase=phase.value,
                category=category,
                doc_id=doc_id,
            )

        return doc_id

    async def apply_feedback(
        self,
        task_id: str,
        success: bool,
        boost_amount: float = 0.1,
        decay_amount: float = 0.05,
    ) -> dict[str, int]:
        """
        Apply feedback to learnings used during a task.

        Boosts utility scores on success, decays on failure.

        Args:
            task_id: Task ID to apply feedback for
            success: Whether the task succeeded
            boost_amount: Amount to boost on success
            decay_amount: Amount to decay on failure

        Returns:
            Dict with counts of boosted/decayed learnings
        """
        if task_id not in self._used_learning_ids:
            return {"boosted": 0, "decayed": 0}

        learning_ids = self._used_learning_ids[task_id]
        boosted = 0
        decayed = 0

        for learning_id in learning_ids:
            try:
                if success:
                    result = await self._memory.boost_learning(learning_id, boost_amount)
                    if result:
                        boosted += 1
                else:
                    result = await self._memory.decay_learning(learning_id, decay_amount)
                    if result:
                        decayed += 1
            except Exception as e:
                logger.warning(f"Failed to apply feedback to learning {learning_id}: {e}")

        # Clean up tracking
        del self._used_learning_ids[task_id]

        logger.info(
            f"Applied feedback for task {task_id}",
            success=success,
            boosted=boosted,
            decayed=decayed,
        )

        return {"boosted": boosted, "decayed": decayed}

    def get_used_learning_ids(self, task_id: str) -> list[str]:
        """Get the learning IDs used during a task."""
        return list(self._used_learning_ids.get(task_id, set()))

    def clear_cache(self, task_id: str | None = None) -> None:
        """
        Clear the context cache.

        Args:
            task_id: If provided, only clear cache for this task.
                    If None, clear entire cache.
        """
        if task_id:
            # Clear cache entries for specific task
            keys_to_remove = [k for k in self._cache if k.startswith(f"{task_id}:")]
            for key in keys_to_remove:
                del self._cache[key]
            # Also clear used learning IDs
            self._used_learning_ids.pop(task_id, None)
        else:
            # Clear all cache
            self._cache.clear()
            self._used_learning_ids.clear()


def format_learnings_for_context(
    learnings: list[dict[str, Any]],
    max_items: int = 5,
    include_confidence: bool = False,
) -> str:
    """
    Format learnings into a string for context injection.

    Args:
        learnings: List of learning dicts
        max_items: Maximum items to include
        include_confidence: Whether to include confidence scores

    Returns:
        Formatted string of learnings
    """
    if not learnings:
        return ""

    lines = []
    for learning in learnings[:max_items]:
        content = learning.get("content", learning.get("text", str(learning)))

        # Truncate long content
        if len(content) > 200:
            content = content[:197] + "..."

        if include_confidence:
            confidence = learning.get("confidence", 0.5)
            utility = learning.get("utility_score", 0.5)
            lines.append(f"- {content} (conf: {confidence:.0%}, util: {utility:.0%})")
        else:
            lines.append(f"- {content}")

    return "\n".join(lines)


def format_phase_context_for_injection(
    context: PhaseContext,
    include_patterns: bool = True,
    include_skills: bool = True,
) -> str:
    """
    Format a PhaseContext for injection into Claude messages.

    Args:
        context: PhaseContext to format
        include_patterns: Whether to include patterns section
        include_skills: Whether to include skills section

    Returns:
        Formatted context string
    """
    sections = []

    if context.learnings:
        learnings_text = format_learnings_for_context(context.learnings, max_items=5)
        sections.append(f"[Relevant Learnings]\n{learnings_text}")

    if include_patterns and context.patterns:
        patterns_text = format_learnings_for_context(context.patterns, max_items=3)
        sections.append(f"[Tool Patterns]\n{patterns_text}")

    if include_skills and context.skills:
        skills_text = "\n".join(
            f"- {s.get('name', 'Unknown')}: {s.get('description', '')[:100]}"
            for s in context.skills[:3]
        )
        sections.append(f"[Applicable Skills]\n{skills_text}")

    return "\n\n".join(sections) if sections else ""
