"""
Experience Replay and Consolidation (Improvement 4)

Implements nightly consolidation: merge similar learnings, extract meta-patterns,
decay stale knowledge, and prune low-utility learnings.
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from ai_core import get_logger
from ai_memory import Learning, LearningScope, PAIMemory, PAIPhase

logger = get_logger(__name__)


class LearningConsolidator:
    """
    Consolidates learnings to maintain a lean, high-quality knowledge base.

    Operations:
    - Merge similar learnings (>92% semantic similarity)
    - Extract meta-patterns from clusters
    - Promote successful patterns to skills
    - Decay stale learnings
    - Prune low-utility learnings
    """

    def __init__(
        self,
        pai_memory: PAIMemory,
        skill_library: Any = None,  # Optional SkillLibrary
    ):
        self.memory = pai_memory
        self.skills = skill_library

    async def run_consolidation(self) -> dict[str, Any]:
        """
        Run the full consolidation pipeline.

        Returns:
            Statistics about the consolidation run
        """
        logger.info("Starting learning consolidation...")
        start_time = datetime.now(timezone.utc)

        stats = {
            "started_at": start_time.isoformat(),
            "merged": 0,
            "patterns_found": 0,
            "new_skills": 0,
            "decayed": 0,
            "pruned": 0,
            "errors": [],
        }

        try:
            # Phase 1: Merge similar learnings
            merged = await self._merge_similar_learnings()
            stats["merged"] = merged
            logger.info(f"Phase 1 complete: Merged {merged} learnings")
        except Exception as e:
            stats["errors"].append(f"Merge phase: {str(e)}")
            logger.error(f"Merge phase failed: {e}")

        try:
            # Phase 2: Extract meta-patterns
            patterns = await self._extract_meta_patterns()
            stats["patterns_found"] = len(patterns)
            logger.info(f"Phase 2 complete: Found {len(patterns)} meta-patterns")
        except Exception as e:
            stats["errors"].append(f"Pattern extraction: {str(e)}")
            logger.error(f"Pattern extraction failed: {e}")

        try:
            # Phase 3: Promote successful patterns to skills
            if self.skills:
                new_skills = await self._promote_to_skills(patterns if "patterns" in dir() else [])
                stats["new_skills"] = len(new_skills)
                logger.info(f"Phase 3 complete: Created {len(new_skills)} new skills")
        except Exception as e:
            stats["errors"].append(f"Skill promotion: {str(e)}")
            logger.error(f"Skill promotion failed: {e}")

        try:
            # Phase 4: Decay stale learnings
            decayed = await self._decay_stale_learnings()
            stats["decayed"] = decayed
            logger.info(f"Phase 4 complete: Decayed {decayed} stale learnings")
        except Exception as e:
            stats["errors"].append(f"Decay phase: {str(e)}")
            logger.error(f"Decay phase failed: {e}")

        try:
            # Phase 5: Prune low-utility learnings
            pruned = await self._prune_low_utility()
            stats["pruned"] = pruned
            logger.info(f"Phase 5 complete: Pruned {pruned} low-utility learnings")
        except Exception as e:
            stats["errors"].append(f"Prune phase: {str(e)}")
            logger.error(f"Prune phase failed: {e}")

        stats["completed_at"] = datetime.now(timezone.utc).isoformat()
        stats["duration_seconds"] = (datetime.now(timezone.utc) - start_time).total_seconds()

        logger.info(f"Consolidation complete: {stats}")
        return stats

    async def _merge_similar_learnings(
        self,
        similarity_threshold: float = 0.92,
    ) -> int:
        """
        Merge learnings with >92% semantic similarity.

        Keeps the highest utility learning and merges metadata from others.

        Returns:
            Number of learnings merged (deleted)
        """
        learnings = await self.memory.get_all_learnings(limit=1000)
        if len(learnings) < 2:
            return 0

        merged_count = 0

        # Group by category for efficiency
        by_category: dict[str, list[Learning]] = defaultdict(list)
        for learning in learnings:
            by_category[learning.category].append(learning)

        # Process each category
        for category, category_learnings in by_category.items():
            if len(category_learnings) < 2:
                continue

            # Find clusters using simple pairwise comparison
            # (In production, use embedding clustering for efficiency)
            clusters = await self._cluster_by_content(category_learnings, similarity_threshold)

            for cluster in clusters:
                if len(cluster) < 2:
                    continue

                # Keep the learning with highest utility
                primary = max(cluster, key=lambda l: l.utility_score)

                for secondary in cluster:
                    if secondary.content == primary.content:
                        continue

                    # Merge metadata
                    primary.access_count += secondary.access_count
                    primary.metadata.update({
                        k: v for k, v in secondary.metadata.items()
                        if k not in primary.metadata
                    })

                    # Delete the secondary learning using public API
                    try:
                        # Use search_learnings to find the learning ID
                        similar = await self.memory.search_learnings(
                            query=secondary.content,
                            limit=1,
                        )
                        if similar and similar[0].get("score", 0) > 0.98:
                            learning_id = similar[0].get("id")
                            if learning_id:
                                await self.memory.delete_learning(learning_id)
                                merged_count += 1
                    except Exception as e:
                        logger.debug(f"Failed to delete merged learning: {e}")

                # Update the primary learning using public API
                try:
                    similar = await self.memory.search_learnings(
                        query=primary.content,
                        limit=1,
                    )
                    if similar:
                        learning_id = similar[0].get("id")
                        if learning_id:
                            await self.memory.update_learning(
                                id=learning_id,
                                metadata={
                                    "access_count": primary.access_count,
                                    "merged_count": len(cluster) - 1,
                                    **primary.metadata,
                                },
                            )
                except Exception as e:
                    logger.debug(f"Failed to update primary learning: {e}")

        return merged_count

    async def _cluster_by_content(
        self,
        learnings: list[Learning],
        threshold: float,
    ) -> list[list[Learning]]:
        """
        Cluster learnings by content similarity.

        Simple greedy clustering - each learning joins the first cluster
        where it has high similarity with the cluster representative.
        """
        clusters: list[list[Learning]] = []

        for learning in learnings:
            added = False

            for cluster in clusters:
                representative = cluster[0]

                # Check similarity using public search_learnings API
                try:
                    similar = await self.memory.search_learnings(
                        query=learning.content,
                        limit=5,
                    )
                    for result in similar:
                        if result.get("text", "") == representative.content:
                            if result.get("score", 0) >= threshold:
                                cluster.append(learning)
                                added = True
                                break
                except Exception:
                    pass

                if added:
                    break

            if not added:
                clusters.append([learning])

        return [c for c in clusters if len(c) > 1]

    async def _extract_meta_patterns(self) -> list[dict[str, Any]]:
        """
        Find patterns across multiple learnings.

        Groups learnings by project and success status to identify
        recurring success patterns and anti-patterns.
        """
        patterns = []

        # Get execution outcome learnings
        outcome_learnings = await self.memory.get_learnings_by_category("execution_outcome")
        if not outcome_learnings:
            outcome_learnings = await self.memory.get_learnings_by_category("plan_completion")

        if not outcome_learnings:
            return patterns

        # Group by project
        by_project: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for learning_dict in outcome_learnings:
            project_id = learning_dict.get("project_id") or "global"
            by_project[project_id].append(learning_dict)

        for project_id, project_learnings in by_project.items():
            successes = [
                l for l in project_learnings
                if l.get("metadata", {}).get("success") or l.get("metadata", {}).get("feedback_type") == "full_success"
            ]
            failures = [
                l for l in project_learnings
                if l.get("metadata", {}).get("feedback_type") in ("mostly_failed", "partial_success")
                or l.get("category") == "error_pattern"
            ]

            # Extract success patterns
            if len(successes) >= 3:
                pattern = await self._identify_success_pattern(successes, project_id)
                if pattern:
                    patterns.append(pattern)

            # Extract anti-patterns
            if len(failures) >= 3:
                anti_pattern = await self._identify_failure_pattern(failures, project_id)
                if anti_pattern:
                    patterns.append(anti_pattern)

        return patterns

    async def _identify_success_pattern(
        self,
        successes: list[dict[str, Any]],
        project_id: str,
    ) -> dict[str, Any] | None:
        """Identify common elements in successful executions."""
        if len(successes) < 3:
            return None

        # Extract common metadata
        common_elements = {
            "file_extensions": [],
            "step_counts": [],
            "iteration_counts": [],
        }

        for s in successes:
            meta = s.get("metadata", {})
            if meta.get("file_extensions"):
                common_elements["file_extensions"].extend(meta["file_extensions"])
            if meta.get("steps_completed"):
                common_elements["step_counts"].append(meta["steps_completed"])
            if meta.get("iterations_used"):
                common_elements["iteration_counts"].append(meta["iterations_used"])

        # Find most common elements
        from collections import Counter
        ext_counts = Counter(common_elements["file_extensions"])
        most_common_ext = ext_counts.most_common(3)

        avg_steps = sum(common_elements["step_counts"]) / len(common_elements["step_counts"]) if common_elements["step_counts"] else 0
        avg_iterations = sum(common_elements["iteration_counts"]) / len(common_elements["iteration_counts"]) if common_elements["iteration_counts"] else 0

        if not most_common_ext:
            return None

        pattern = {
            "type": "success_pattern",
            "project_id": project_id,
            "sample_size": len(successes),
            "common_file_types": [ext for ext, _ in most_common_ext],
            "avg_steps": round(avg_steps, 1),
            "avg_iterations": round(avg_iterations, 1),
            "description": f"Successful execution pattern: typically involves {most_common_ext[0][0]} files, ~{round(avg_steps)} steps, ~{round(avg_iterations)} iterations per step",
        }

        # Store as a learning
        learning = Learning(
            content=pattern["description"],
            phase=PAIPhase.LEARN,
            category="meta_pattern",
            scope=LearningScope.PROJECT if project_id != "global" else LearningScope.GLOBAL,
            project_id=project_id if project_id != "global" else None,
            confidence=0.85,
            utility_score=0.7,
            metadata=pattern,
        )
        await self.memory.store_learning(learning)

        return pattern

    async def _identify_failure_pattern(
        self,
        failures: list[dict[str, Any]],
        project_id: str,
    ) -> dict[str, Any] | None:
        """Identify common elements in failed executions."""
        if len(failures) < 3:
            return None

        # Extract common failure indicators
        failed_steps = []
        error_types = []

        for f in failures:
            meta = f.get("metadata", {})
            if meta.get("failed_steps"):
                failed_steps.extend(meta["failed_steps"])
            if meta.get("error_type"):
                error_types.append(meta["error_type"])

        from collections import Counter
        step_counts = Counter(failed_steps)
        common_failures = step_counts.most_common(3)

        if not common_failures:
            return None

        pattern = {
            "type": "failure_pattern",
            "project_id": project_id,
            "sample_size": len(failures),
            "common_failure_points": [step for step, _ in common_failures],
            "description": f"Anti-pattern: steps like '{common_failures[0][0]}' frequently fail in this project. Consider breaking into smaller tasks.",
        }

        # Store as a learning
        learning = Learning(
            content=pattern["description"],
            phase=PAIPhase.LEARN,
            category="anti_pattern",
            scope=LearningScope.PROJECT if project_id != "global" else LearningScope.GLOBAL,
            project_id=project_id if project_id != "global" else None,
            confidence=0.8,
            utility_score=0.65,
            metadata=pattern,
        )
        await self.memory.store_learning(learning)

        return pattern

    async def _promote_to_skills(self, patterns: list[dict[str, Any]]) -> list[Any]:
        """Promote successful patterns to the skill library."""
        if not self.skills:
            return []

        new_skills = []

        # Get high-utility technique learnings
        techniques = await self.memory.get_learnings_by_utility(
            min_utility=0.8,
            limit=50,
        )

        # Filter for technique category with high access count
        promotable = [
            t for t in techniques
            if t.get("category") == "technique"
            and t.get("access_count", 0) >= 3
        ]

        for technique in promotable:
            try:
                # Check if similar skill exists
                existing = await self.skills.find_applicable_skills(
                    goal=technique.get("text", technique.get("content", "")),
                    context={},
                    min_success_rate=0.5,
                    limit=1,
                )
                if existing:
                    continue

                # Create skill from technique
                from ai_memory.skill_library import Skill, SkillLevel

                skill = Skill(
                    id=f"skill_auto_{technique.get('id', '')[:8]}",
                    name=technique.get("text", "")[:40],
                    level=SkillLevel.SKILL,
                    description=technique.get("text", ""),
                    preconditions=[],
                    postconditions=["success:true"],
                    steps=[{
                        "title": "Execute learned pattern",
                        "description": technique.get("text", ""),
                    }],
                    parameters={},
                    success_rate=technique.get("utility_score", 0.5),
                    tags=["auto-learned", "technique"],
                )

                await self.skills._store_skill(skill)
                new_skills.append(skill)

            except Exception as e:
                logger.debug(f"Failed to promote technique to skill: {e}")

        return new_skills

    async def _decay_stale_learnings(
        self,
        stale_days: int = 30,
        decay_amount: float = 0.1,
    ) -> int:
        """
        Decay learnings not accessed in stale_days.

        Args:
            stale_days: Days without access before decay
            decay_amount: Amount to decay utility score

        Returns:
            Number of learnings decayed
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
        stale = await self.memory.get_learnings_before(cutoff, limit=200)

        decayed = 0
        for learning in stale:
            # Find the learning ID using public API
            try:
                similar = await self.memory.search_learnings(
                    query=learning.content,
                    limit=1,
                )
                if similar and similar[0].get("score", 0) > 0.95:
                    learning_id = similar[0].get("id")
                    if learning_id:
                        await self.memory.decay_learning(learning_id, decay_amount)
                        decayed += 1
            except Exception as e:
                logger.debug(f"Failed to decay learning: {e}")

        return decayed

    async def _prune_low_utility(
        self,
        threshold: float = 0.1,
        min_age_days: int = 7,
    ) -> int:
        """
        Remove learnings with utility below threshold.

        Only prunes learnings older than min_age_days to give new learnings
        a chance to prove themselves.

        Args:
            threshold: Utility threshold below which to prune
            min_age_days: Minimum age in days before eligible for pruning

        Returns:
            Number of learnings pruned
        """
        low_utility = await self.memory.get_learnings_by_utility(
            max_utility=threshold,
            limit=100,
        )

        pruned = 0
        min_age_cutoff = datetime.now(timezone.utc) - timedelta(days=min_age_days)

        for learning_dict in low_utility:
            # Check age
            created_str = learning_dict.get("created_at")
            if created_str:
                try:
                    created_at = datetime.fromisoformat(created_str)
                    if created_at > min_age_cutoff:
                        continue  # Too young to prune
                except (ValueError, TypeError):
                    pass

            # Prune the learning
            learning_id = learning_dict.get("id")
            if learning_id:
                try:
                    await self.memory.delete_learning(learning_id)
                    pruned += 1
                except Exception as e:
                    logger.debug(f"Failed to prune learning {learning_id}: {e}")

        return pruned


async def schedule_consolidation(
    pai_memory: PAIMemory,
    skill_library: Any = None,
    run_hour: int = 3,
) -> None:
    """
    Schedule nightly consolidation job.

    Args:
        pai_memory: PAIMemory instance
        skill_library: Optional SkillLibrary instance
        run_hour: Hour (UTC) to run consolidation (default 3 AM)
    """
    consolidator = LearningConsolidator(pai_memory, skill_library)

    while True:
        now = datetime.now(timezone.utc)

        # Calculate next run time
        next_run = now.replace(hour=run_hour, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)

        # Sleep until next run
        sleep_seconds = (next_run - now).total_seconds()
        logger.info(f"Consolidation scheduled for {next_run.isoformat()}, sleeping {sleep_seconds/3600:.1f} hours")

        await asyncio.sleep(sleep_seconds)

        # Run consolidation
        try:
            result = await consolidator.run_consolidation()
            logger.info(f"Scheduled consolidation complete: {result}")
        except Exception as e:
            logger.error(f"Scheduled consolidation failed: {e}")


async def run_immediate_consolidation(
    pai_memory: PAIMemory,
    skill_library: Any = None,
) -> dict[str, Any]:
    """
    Run consolidation immediately (for manual invocation).

    Args:
        pai_memory: PAIMemory instance
        skill_library: Optional SkillLibrary instance

    Returns:
        Consolidation statistics
    """
    consolidator = LearningConsolidator(pai_memory, skill_library)
    return await consolidator.run_consolidation()
