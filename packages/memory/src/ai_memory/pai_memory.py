"""
PAI (Personal AI) Memory System - 3-tier memory architecture.

HOT (Redis): Real-time task traces, 24-hour retention
WARM (Qdrant): Synthesized learnings, 30-day retention, searchable
COLD (File): Immutable historical reference, 365-day retention
"""

import json
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, cast

import aiofiles

from ai_core import get_logger, memory_items_count, memory_operations_total

from .embeddings import get_embedding_service
from .qdrant import QdrantStore

logger = get_logger(__name__)


class MemoryTier(str, Enum):
    """Memory tier levels."""
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class PAIPhase(str, Enum):
    """PAI Algorithm phases."""
    OBSERVE = "observe"
    THINK = "think"
    PLAN = "plan"
    BUILD = "build"
    EXECUTE = "execute"
    VERIFY = "verify"
    LEARN = "learn"


class LearningScope(str, Enum):
    """
    Scope levels for learning isolation.

    GLOBAL: Shared across all projects - general patterns, best practices
    PROJECT: Specific to a project - project conventions, architecture decisions
    DOMAIN: Specific to a domain/site - site-specific configs, client preferences
    """
    GLOBAL = "global"
    PROJECT = "project"
    DOMAIN = "domain"


class Learning:
    """
    Represents a learning extracted from a task.

    Learnings can be scoped at three levels:
    - GLOBAL: Applies to all projects (general patterns, best practices)
    - PROJECT: Specific to a project (conventions, architecture decisions)
    - DOMAIN: Specific to a domain/site (client preferences, site configs)

    Improvement 1: Added utility_score, access_count, last_accessed for feedback loop.
    """

    def __init__(
        self,
        content: str,
        phase: PAIPhase,
        category: str,
        task_id: str | None = None,
        agent_type: str | None = None,
        confidence: float = 0.8,
        metadata: dict[str, Any] | None = None,
        # Tags for filtering and categorization
        tags: list[str] | None = None,
        # ACL fields
        created_by_agent: str = "",
        permission_level: int = 1,
        sensitivity: str = "internal",
        allowed_agents: list[str] | None = None,
        # Scope fields for project isolation
        scope: LearningScope = LearningScope.GLOBAL,
        project_id: str | None = None,
        domain_id: str | None = None,
        # Utility tracking fields (Improvement 1)
        utility_score: float = 0.5,
        access_count: int = 0,
        last_accessed: datetime | None = None,
    ):
        self.content = content
        self.phase = phase
        self.category = category
        self.task_id = task_id
        self.agent_type = agent_type
        self.confidence = confidence
        self.metadata = metadata or {}
        self.tags = tags or []  # Tags for filtering and categorization
        self.created_at = datetime.now(timezone.utc)
        # ACL fields
        self.created_by_agent = created_by_agent or agent_type or ""
        self.permission_level = permission_level  # Minimum level to access (1=READ_WRITE default)
        self.sensitivity = sensitivity  # public/internal/restricted
        self.allowed_agents = allowed_agents or []  # Optional whitelist
        # Scope fields
        self.scope = scope
        self.project_id = project_id
        self.domain_id = domain_id
        # Utility tracking fields (Improvement 1: Outcome Feedback Loop)
        self.utility_score = utility_score  # 0-1, starts neutral at 0.5
        self.access_count = access_count
        self.last_accessed = last_accessed

    def boost(self, amount: float = 0.1) -> None:
        """Boost utility score after successful use."""
        self.utility_score = min(1.0, self.utility_score + amount)
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)

    def decay(self, amount: float = 0.05) -> None:
        """Decay utility score after failure or time."""
        self.utility_score = max(0.0, self.utility_score - amount)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "phase": self.phase.value,
            "category": self.category,
            "task_id": self.task_id,
            "agent_type": self.agent_type,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "tags": self.tags,  # Tags for filtering
            "created_at": self.created_at.isoformat(),
            # ACL fields
            "created_by_agent": self.created_by_agent,
            "permission_level": self.permission_level,
            "sensitivity": self.sensitivity,
            "allowed_agents": self.allowed_agents,
            # Scope fields
            "scope": self.scope.value,
            "project_id": self.project_id,
            "domain_id": self.domain_id,
            # Utility tracking fields (Improvement 1)
            "utility_score": self.utility_score,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Learning":
        """Create from dictionary."""
        # Parse scope with backward compatibility
        scope_str = data.get("scope", "global")
        try:
            scope = LearningScope(scope_str)
        except ValueError:
            scope = LearningScope.GLOBAL

        # Parse last_accessed with backward compatibility
        last_accessed = None
        if data.get("last_accessed"):
            try:
                last_accessed = datetime.fromisoformat(data["last_accessed"])
            except (ValueError, TypeError):
                pass

        learning = cls(
            content=data["content"],
            phase=PAIPhase(data["phase"]),
            category=data["category"],
            task_id=data.get("task_id"),
            agent_type=data.get("agent_type"),
            confidence=data.get("confidence", 0.8),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),  # Tags for filtering
            # ACL fields
            created_by_agent=data.get("created_by_agent", ""),
            permission_level=data.get("permission_level", 1),
            sensitivity=data.get("sensitivity", "internal"),
            allowed_agents=data.get("allowed_agents", []),
            # Scope fields
            scope=scope,
            project_id=data.get("project_id"),
            domain_id=data.get("domain_id"),
            # Utility tracking fields (Improvement 1)
            utility_score=data.get("utility_score", 0.5),
            access_count=data.get("access_count", 0),
            last_accessed=last_accessed,
        )
        if "created_at" in data:
            learning.created_at = datetime.fromisoformat(data["created_at"])
        return learning

    def is_accessible_in_context(
        self,
        project_id: str | None = None,
        domain_id: str | None = None,
    ) -> bool:
        """
        Check if this learning is accessible in the given project/domain context.

        Rules:
        - GLOBAL learnings are always accessible
        - PROJECT learnings only accessible if project_id matches
        - DOMAIN learnings only accessible if domain_id matches
        """
        if self.scope == LearningScope.GLOBAL:
            return True
        if self.scope == LearningScope.PROJECT:
            return self.project_id is not None and self.project_id == project_id
        if self.scope == LearningScope.DOMAIN:
            return self.domain_id is not None and self.domain_id == domain_id
        return True  # Default allow


class PAIMemory:
    """
    PAI Memory System managing 3-tier memory.

    Tiers:
    - HOT: Redis for real-time data (24h TTL)
    - WARM: Qdrant for searchable learnings (30d)
    - COLD: File archive for historical data (365d)
    """

    def __init__(
        self,
        redis_client: Any,  # RedisClient from ai_messaging
        qdrant_store: QdrantStore | None = None,
        cold_storage_path: Path | None = None,
    ):
        self._redis = redis_client
        self._qdrant = qdrant_store
        self._cold_path = cold_storage_path or Path("pai/MEMORY")
        self._embedding_service = get_embedding_service()

        # TTLs
        self._hot_ttl = 24 * 60 * 60  # 24 hours
        self._warm_ttl = 30 * 24 * 60 * 60  # 30 days

    async def initialize(self) -> None:
        """Initialize memory stores."""
        if self._qdrant:
            await self._qdrant.connect()

        # Ensure cold storage directories exist
        for phase in PAIPhase:
            phase_dir = self._cold_path / "Learning" / phase.value.upper()
            phase_dir.mkdir(parents=True, exist_ok=True)

        logger.info("PAI Memory initialized")

    # =========================================================================
    # ACL (Access Control List) Methods
    # =========================================================================

    def _check_memory_acl(
        self,
        learning: Learning | dict[str, Any],
        agent_type: str,
        permission_level: int,
        capabilities: set[str] | None = None,
    ) -> bool:
        """
        Balanced ACL check - enables work while protecting sensitive data.

        Args:
            learning: Learning object or dict with ACL fields
            agent_type: Type of agent requesting access
            permission_level: Agent's permission level (1-4)
            capabilities: Optional set of agent capabilities

        Returns:
            True if access allowed, False otherwise
        """
        if isinstance(learning, dict):
            required_level: int = learning.get("permission_level", 1)
            sensitivity: str = learning.get("sensitivity", "internal")
            allowed: list[str] = learning.get("allowed_agents", [])
            created_by: str = learning.get("created_by_agent", "")
            category: str = learning.get("category", "")
        else:
            required_level = learning.permission_level
            sensitivity = learning.sensitivity
            allowed = learning.allowed_agents
            created_by = learning.created_by_agent
            category = learning.category

        # Rule 1: Creator always has access (enables continuity)
        if created_by == agent_type:
            return True

        # Rule 2: Supervisor (level 4) can access everything (oversight)
        if permission_level >= 4:
            return True

        # Rule 3: Public learnings are accessible to all
        if sensitivity == "public":
            return True

        # Rule 4: Internal learnings - accessible to same level or higher
        if sensitivity == "internal":
            return permission_level >= required_level

        # Rule 5: Restricted - only whitelisted agents
        if sensitivity == "restricted":
            return agent_type in allowed

        # Default: allow (err on side of productivity)
        return True

    # =========================================================================
    # HOT Tier Operations (Redis)
    # =========================================================================

    async def store_hot(
        self,
        key: str,
        data: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        """Store data in HOT tier (Redis)."""
        ttl = ttl or self._hot_ttl
        await self._redis.set(
            f"pai:hot:{key}",
            json.dumps(data),
            ex=ttl,
        )
        memory_operations_total.labels(
            tier="hot", operation="store", status="success"
        ).inc()

    async def get_hot(self, key: str) -> dict[str, Any] | None:
        """Get data from HOT tier."""
        data = await self._redis.get(f"pai:hot:{key}")
        if data:
            return cast(dict[str, Any], json.loads(data))
        return None

    async def store_task_trace(
        self,
        task_id: str,
        phase: PAIPhase,
        data: dict[str, Any],
    ) -> None:
        """Store task execution trace in HOT tier."""
        trace_key = f"task:{task_id}:trace:{phase.value}"
        trace_data = {
            "phase": phase.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        await self.store_hot(trace_key, trace_data)

        # Also add to task's trace list
        list_key = f"pai:hot:task:{task_id}:traces"
        await self._redis.rpush(list_key, json.dumps(trace_data))
        await self._redis.expire(list_key, self._hot_ttl)

    async def get_task_traces(self, task_id: str) -> list[dict[str, Any]]:
        """Get all traces for a task."""
        list_key = f"pai:hot:task:{task_id}:traces"
        traces = await self._redis.lrange(list_key, 0, -1)
        return [json.loads(t) for t in traces]

    # =========================================================================
    # WARM Tier Operations (Qdrant)
    # =========================================================================

    # Minimum content requirements for storage
    MIN_CONTENT_LENGTH = 20
    MIN_CONFIDENCE = 0.4

    async def store_learning(
        self,
        learning: Learning,
        agent_type: str = "",
        deduplicate: bool = True,
    ) -> str | None:
        """
        Store a learning in WARM tier (Qdrant) with optional deduplication.

        Includes quality checks to prevent low-value learnings from being stored.

        Args:
            learning: Learning object to store
            agent_type: Optional override for created_by_agent field
            deduplicate: Whether to check for duplicate learnings (default True)

        Returns:
            Document ID if stored successfully, None otherwise
        """
        if not self._qdrant:
            logger.warning("Qdrant not configured, skipping WARM storage")
            return None

        # === Quality gate: Final check before storage ===
        # Minimum content length
        if len(learning.content.strip()) < self.MIN_CONTENT_LENGTH:
            logger.debug(f"Learning rejected: content too short ({len(learning.content)} chars)")
            return None

        # Minimum confidence
        if learning.confidence < self.MIN_CONFIDENCE:
            logger.debug(f"Learning rejected: confidence too low ({learning.confidence})")
            return None

        # Reject content that's mostly non-alphabetic (likely code or data)
        alpha_ratio = sum(1 for c in learning.content if c.isalpha()) / max(len(learning.content), 1)
        if alpha_ratio < 0.4:
            logger.debug(f"Learning rejected: too much non-text content (alpha ratio: {alpha_ratio:.2f})")
            return None

        # Set creator if not already set
        if not learning.created_by_agent:
            learning.created_by_agent = agent_type or learning.agent_type or ""

        # === Deduplication check ===
        if deduplicate:
            try:
                # Search for similar existing learnings using semantic search
                similar = await self._qdrant.search(
                    query=learning.content,
                    limit=3,
                    filter={"agent_type": learning.agent_type} if learning.agent_type else None,
                )

                # Check for high similarity matches
                for result in similar:
                    score = result.get("score", 0)
                    existing = result.get("metadata", result)

                    # Check if same agent and category with high similarity
                    if (
                        score >= 0.92
                        and existing.get("agent_type") == learning.agent_type
                        and existing.get("category") == learning.category
                    ):
                        existing_id: str = str(result.get("id", "unknown"))
                        logger.info(
                            f"Duplicate learning detected (score={score:.3f}), skipping: {learning.content[:50]}..."
                        )
                        memory_operations_total.labels(
                            tier="warm", operation="deduplicate", status="skipped"
                        ).inc()
                        return existing_id  # Return existing ID

            except Exception as e:
                # If deduplication fails, continue with storage
                logger.warning(f"Deduplication check failed, proceeding with storage: {e}")

        doc_id = await self._qdrant.upsert(
            id=None,
            text=learning.content,
            metadata={
                "phase": learning.phase.value,
                "category": learning.category,
                "task_id": learning.task_id,
                "agent_type": learning.agent_type,
                "confidence": learning.confidence,
                "tags": learning.tags,  # Tags for filtering
                "created_at": learning.created_at.isoformat(),
                # ACL fields
                "created_by_agent": learning.created_by_agent,
                "permission_level": learning.permission_level,
                "sensitivity": learning.sensitivity,
                "allowed_agents": learning.allowed_agents,
                # Scope fields for project isolation
                "scope": learning.scope.value,
                "project_id": learning.project_id,
                "domain_id": learning.domain_id,
                # Utility tracking fields (Improvement 1)
                "utility_score": learning.utility_score,
                "access_count": learning.access_count,
                "last_accessed": learning.last_accessed.isoformat() if learning.last_accessed else None,
                **learning.metadata,
            },
        )
        memory_operations_total.labels(
            tier="warm", operation="store", status="success"
        ).inc()
        return doc_id

    async def update_learning(
        self,
        id: str,
        content: str | None = None,
        phase: PAIPhase | None = None,
        category: str | None = None,
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Update an existing learning in WARM tier.

        Only re-embeds if content changes. Metadata fields are merged.

        Args:
            id: Learning document ID
            content: New content text (None = keep existing)
            phase: New phase (None = keep existing)
            category: New category (None = keep existing)
            confidence: New confidence score (None = keep existing)
            metadata: Additional metadata to merge (None = keep existing)

        Returns:
            Updated document dict, or None if not found
        """
        if not self._qdrant:
            logger.warning("Qdrant not configured, cannot update")
            return None

        # Build metadata updates
        meta_updates: dict[str, Any] = {}
        if phase is not None:
            meta_updates["phase"] = phase.value
        if category is not None:
            meta_updates["category"] = category
        if confidence is not None:
            meta_updates["confidence"] = confidence
        if metadata:
            meta_updates.update(metadata)

        # Add updated_at timestamp
        meta_updates["updated_at"] = datetime.now(timezone.utc).isoformat()

        result = await self._qdrant.update(
            id=id,
            text=content,
            metadata=meta_updates if meta_updates else None,
        )

        if result:
            memory_operations_total.labels(
                tier="warm", operation="update", status="success"
            ).inc()
            logger.info("Learning updated", id=id)
        else:
            logger.warning("Learning not found for update", id=id)

        return result

    async def get_learning(self, id: str) -> dict[str, Any] | None:
        """Get a single learning by ID."""
        if not self._qdrant:
            return None
        return await self._qdrant.get(id)

    async def search_learnings(
        self,
        query: str,
        phase: PAIPhase | None = None,
        category: str | None = None,
        limit: int = 10,
        agent_type: str = "supervisor",
        permission_level: int = 4,
        # Scope filtering - pass current context to filter learnings
        project_id: str | None = None,
        domain_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search learnings in WARM tier with ACL and scope filtering.

        Scope Filtering Rules:
        - GLOBAL learnings are always included
        - PROJECT learnings only included if project_id matches
        - DOMAIN learnings only included if domain_id matches
        - Learnings from other projects/domains are excluded

        Args:
            query: Search query
            phase: Optional PAI phase filter
            category: Optional category filter
            limit: Maximum results to return
            agent_type: Type of agent making the request (for ACL)
            permission_level: Permission level of requesting agent (1-4)
            project_id: Current project context (for scope filtering)
            domain_id: Current domain context (for scope filtering)

        Returns:
            List of learning dicts that pass ACL and scope checks
        """
        if not self._qdrant:
            return []

        filter_dict = {}
        if phase:
            filter_dict["phase"] = phase.value
        if category:
            filter_dict["category"] = category

        # Request more results than limit to account for ACL + scope filtering
        results = await self._qdrant.search(
            query=query,
            limit=limit * 3,  # Over-fetch to account for filtering
            filter=filter_dict if filter_dict else None,
        )

        # Filter results by ACL and scope
        filtered_results = []
        for result in results:
            # Check ACL first
            if not self._check_memory_acl(result, agent_type, permission_level):
                logger.debug(
                    f"ACL blocked access to learning for {agent_type}",
                    extra={"category": result.get("category", "unknown")},
                )
                continue

            # Check scope - determine if learning is accessible in current context
            result_scope = result.get("scope", "global")
            result_project = result.get("project_id")
            result_domain = result.get("domain_id")

            if result_scope == "global":
                # Global learnings are always accessible
                filtered_results.append(result)
            elif result_scope == "project":
                # Project learnings only if we're in that project
                if project_id and result_project == project_id:
                    filtered_results.append(result)
                else:
                    logger.debug(
                        f"Scope blocked project learning (current={project_id}, learning={result_project})"
                    )
            elif result_scope == "domain":
                # Domain learnings only if we're in that domain
                if domain_id and result_domain == domain_id:
                    filtered_results.append(result)
                else:
                    logger.debug(
                        f"Scope blocked domain learning (current={domain_id}, learning={result_domain})"
                    )
            else:
                # Unknown scope - treat as global (backward compatibility)
                filtered_results.append(result)

            if len(filtered_results) >= limit:
                break

        return filtered_results

    # =========================================================================
    # COLD Tier Operations (File Archive)
    # =========================================================================

    async def archive_to_cold(
        self,
        learning: Learning,
        summary: str | None = None,
    ) -> Path:
        """Archive a learning to COLD tier (file system)."""
        phase_dir = self._cold_path / "Learning" / learning.phase.value.upper()
        phase_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = learning.created_at.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{learning.category}.json"
        filepath = phase_dir / filename

        archive_data = {
            **learning.to_dict(),
            "summary": summary,
            "archived_at": datetime.now(timezone.utc).isoformat(),
        }

        async with aiofiles.open(filepath, "w") as f:
            await f.write(json.dumps(archive_data, indent=2))

        memory_operations_total.labels(
            tier="cold", operation="archive", status="success"
        ).inc()
        logger.info("Archived learning to COLD tier", path=str(filepath))
        return filepath

    async def flush(self, task_id: str | None = None) -> dict[str, int]:
        """
        Flush pending operations and ensure data persistence.

        Args:
            task_id: Optional task ID to flush specific task data

        Returns:
            Dict with counts of flushed items per tier
        """
        flushed = {"hot": 0, "warm": 0, "cold": 0}

        try:
            # 1. Promote eligible HOT data to WARM
            if task_id:
                traces = await self.get_task_traces(task_id)
                for trace in traces:
                    if trace.get("phase") == PAIPhase.VERIFY.value:
                        promoted = await self.promote_to_warm(task_id)
                        flushed["warm"] = len(promoted)
                        break

            # 2. Archive old WARM data to COLD
            archived = await self.archive_old_warm(older_than_days=30)
            flushed["cold"] = archived

            # 3. Ensure Redis persistence (if configured for AOF)
            if self._redis:
                try:
                    await self._redis.bgsave()
                except Exception as redis_err:
                    # bgsave may fail if already in progress, which is fine
                    logger.debug(f"Redis bgsave skipped: {redis_err}")

            logger.info(f"PAI flush complete: {flushed}")
            return flushed

        except Exception as e:
            logger.error(f"PAI flush error: {e}")
            raise

    async def read_cold(self, filepath: Path) -> dict[str, Any] | None:
        """Read archived data from COLD tier."""
        if not filepath.exists():
            return None

        async with aiofiles.open(filepath, "r") as f:
            content = await f.read()
            return cast(dict[str, Any], json.loads(content))

    async def list_cold_learnings(
        self,
        phase: PAIPhase | None = None,
        since: datetime | None = None,
    ) -> list[Path]:
        """List archived learnings in COLD tier."""
        if phase:
            search_dirs = [self._cold_path / "Learning" / phase.value.upper()]
        else:
            search_dirs = [
                self._cold_path / "Learning" / p.value.upper()
                for p in PAIPhase
            ]

        files = []
        for dir_path in search_dirs:
            if dir_path.exists():
                for f in dir_path.glob("*.json"):
                    if since:
                        # Parse timestamp from filename
                        try:
                            ts_str = f.stem.split("_")[0] + "_" + f.stem.split("_")[1]
                            file_time = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                            if file_time >= since:
                                files.append(f)
                        except (IndexError, ValueError):
                            files.append(f)
                    else:
                        files.append(f)

        return sorted(files, reverse=True)

    # =========================================================================
    # Cross-Tier Operations
    # =========================================================================

    async def promote_to_warm(self, task_id: str) -> list[str]:
        """
        Promote task traces from HOT to WARM tier.

        Synthesizes learnings from task execution traces
        and stores them in the searchable WARM tier.
        """
        traces = await self.get_task_traces(task_id)
        if not traces:
            return []

        learning_ids = []

        for trace in traces:
            phase = PAIPhase(trace.get("phase", "execute"))

            # Extract learning from trace
            if "learning" in trace:
                learning = Learning(
                    content=trace["learning"],
                    phase=phase,
                    category=trace.get("category", "general"),
                    task_id=task_id,
                    agent_type=trace.get("agent_type"),
                    metadata=trace.get("metadata", {}),
                )

                doc_id = await self.store_learning(learning)
                if doc_id:
                    learning_ids.append(doc_id)

        logger.info(
            "Promoted learnings to WARM tier",
            task_id=task_id,
            count=len(learning_ids),
        )
        return learning_ids

    async def archive_old_warm(
        self,
        older_than_days: int = 30,
        high_confidence_days: int = 60,
        high_confidence_threshold: float = 0.9,
        batch_size: int = 100,
        delete_after_archive: bool = True,
    ) -> int:
        """
        Archive old WARM tier data to COLD tier.

        Retention Policy:
        - Standard learnings: Archive after `older_than_days` (default 30)
        - High-confidence learnings (>= threshold): Keep longer, archive after
          `high_confidence_days` (default 60)
        - Error learnings: Always archive after standard period
        - After successful archive, optionally delete from WARM tier

        Args:
            older_than_days: Days before archiving standard learnings
            high_confidence_days: Days before archiving high-confidence learnings
            high_confidence_threshold: Confidence level considered "high"
            batch_size: Number of documents to process per batch
            delete_after_archive: Whether to delete from WARM after archiving

        Returns:
            Number of learnings archived
        """
        if not self._qdrant:
            return 0

        now = datetime.now(timezone.utc)
        standard_cutoff = now - timedelta(days=older_than_days)
        high_confidence_cutoff = now - timedelta(days=high_confidence_days)

        archived_count = 0
        deleted_ids: list[str] = []
        offset = None

        logger.info(
            "Starting WARM tier archive",
            standard_cutoff=standard_cutoff.isoformat(),
            high_confidence_cutoff=high_confidence_cutoff.isoformat(),
        )

        while True:
            # Scroll through all documents in batches
            documents, offset = await self._qdrant.scroll(
                limit=batch_size,
                offset=offset,
            )

            if not documents:
                break

            for doc in documents:
                metadata = doc.get("metadata", {})
                created_at_str = metadata.get("created_at")

                if not created_at_str:
                    continue

                try:
                    created_at = datetime.fromisoformat(created_at_str)
                except ValueError:
                    logger.warning(
                        "Invalid created_at format",
                        doc_id=doc["id"],
                        created_at=created_at_str,
                    )
                    continue

                confidence = metadata.get("confidence", 0.5)
                category = metadata.get("category", "general")

                # Determine if this learning should be archived
                should_archive = False

                if category == "error":
                    # Error learnings: use standard cutoff
                    should_archive = created_at < standard_cutoff
                elif confidence >= high_confidence_threshold:
                    # High-confidence learnings: keep longer
                    should_archive = created_at < high_confidence_cutoff
                else:
                    # Standard learnings
                    should_archive = created_at < standard_cutoff

                if should_archive:
                    # Reconstruct Learning object
                    learning = Learning(
                        content=doc.get("text", ""),
                        phase=PAIPhase(metadata.get("phase", "learn")),
                        category=category,
                        task_id=metadata.get("task_id"),
                        agent_type=metadata.get("agent_type"),
                        confidence=confidence,
                        metadata={
                            k: v for k, v in metadata.items()
                            if k not in ("phase", "category", "task_id",
                                        "agent_type", "confidence", "created_at")
                        },
                    )
                    learning.created_at = created_at

                    # Generate summary based on phase and category
                    summary = self._generate_archive_summary(learning)

                    try:
                        await self.archive_to_cold(learning, summary=summary)
                        archived_count += 1
                        deleted_ids.append(doc["id"])
                    except Exception as e:
                        logger.error(
                            "Failed to archive learning",
                            doc_id=doc["id"],
                            error=str(e),
                        )

            # Delete archived documents from WARM tier in batches
            if delete_after_archive and len(deleted_ids) >= batch_size:
                await self._qdrant.delete_batch(deleted_ids)
                deleted_ids = []

            if offset is None:
                break

        # Delete any remaining archived documents
        if delete_after_archive and deleted_ids:
            await self._qdrant.delete_batch(deleted_ids)

        logger.info(
            "WARM tier archive completed",
            archived=archived_count,
            deleted=delete_after_archive,
        )
        return archived_count

    def _generate_archive_summary(self, learning: Learning) -> str:
        """Generate a summary for an archived learning."""
        phase_summaries = {
            PAIPhase.OBSERVE: "Observation from task execution",
            PAIPhase.THINK: "Analysis and reasoning insight",
            PAIPhase.PLAN: "Planning decision or strategy",
            PAIPhase.BUILD: "Implementation approach or pattern",
            PAIPhase.EXECUTE: "Execution outcome or behavior",
            PAIPhase.VERIFY: "Verification result or quality check",
            PAIPhase.LEARN: "Extracted learning or improvement",
        }

        base_summary = phase_summaries.get(learning.phase, "General learning")

        parts = [base_summary]

        if learning.category:
            parts.append(f"Category: {learning.category}")

        if learning.agent_type:
            parts.append(f"Agent: {learning.agent_type}")

        if learning.confidence >= 0.9:
            parts.append("High confidence")
        elif learning.confidence < 0.6:
            parts.append("Low confidence")

        return " | ".join(parts)

    async def cleanup_cold_storage(self, older_than_days: int = 365) -> int:
        """
        Remove very old COLD tier data.

        Args:
            older_than_days: Days before permanent deletion (default 365)

        Returns:
            Number of files deleted
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        deleted_count = 0

        for phase in PAIPhase:
            phase_dir = self._cold_path / "Learning" / phase.value.upper()
            if not phase_dir.exists():
                continue

            for filepath in phase_dir.glob("*.json"):
                try:
                    # Parse timestamp from filename
                    ts_str = filepath.stem.split("_")[0] + "_" + filepath.stem.split("_")[1]
                    file_time = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")

                    if file_time < cutoff:
                        filepath.unlink()
                        deleted_count += 1
                        logger.debug("Deleted old COLD file", path=str(filepath))

                except (IndexError, ValueError) as e:
                    logger.warning(
                        "Could not parse timestamp from filename",
                        path=str(filepath),
                        error=str(e),
                    )

        logger.info(
            "COLD tier cleanup completed",
            deleted=deleted_count,
            cutoff=cutoff.isoformat(),
        )
        return deleted_count

    # =========================================================================
    # Utility Tracking Methods (Improvement 1: Outcome Feedback Loop)
    # =========================================================================

    async def boost_learning(self, learning_id: str, amount: float = 0.1) -> bool:
        """
        Boost a learning's utility score after successful use.

        Args:
            learning_id: ID of the learning to boost
            amount: Amount to boost (default 0.1)

        Returns:
            True if successful, False otherwise
        """
        if not self._qdrant:
            return False

        try:
            learning_data = await self._qdrant.get(learning_id)
            if not learning_data:
                return False

            current_utility = learning_data.get("utility_score", 0.5)
            current_access = learning_data.get("access_count", 0)

            new_utility = min(1.0, current_utility + amount)
            new_access = current_access + 1

            await self._qdrant.update(
                id=learning_id,
                metadata={
                    "utility_score": new_utility,
                    "access_count": new_access,
                    "last_accessed": datetime.now(timezone.utc).isoformat(),
                },
            )
            logger.debug(f"Boosted learning {learning_id}: utility {current_utility:.2f} -> {new_utility:.2f}")
            return True
        except Exception as e:
            logger.warning(f"Failed to boost learning {learning_id}: {e}")
            return False

    async def decay_learning(self, learning_id: str, amount: float = 0.05) -> bool:
        """
        Decay a learning's utility score after failure or time.

        Args:
            learning_id: ID of the learning to decay
            amount: Amount to decay (default 0.05)

        Returns:
            True if successful, False otherwise
        """
        if not self._qdrant:
            return False

        try:
            learning_data = await self._qdrant.get(learning_id)
            if not learning_data:
                return False

            current_utility = learning_data.get("utility_score", 0.5)
            new_utility = max(0.0, current_utility - amount)

            await self._qdrant.update(
                id=learning_id,
                metadata={"utility_score": new_utility},
            )
            logger.debug(f"Decayed learning {learning_id}: utility {current_utility:.2f} -> {new_utility:.2f}")
            return True
        except Exception as e:
            logger.warning(f"Failed to decay learning {learning_id}: {e}")
            return False

    async def get_learnings_by_utility(
        self,
        min_utility: float | None = None,
        max_utility: float | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get learnings filtered by utility score range.

        Args:
            min_utility: Minimum utility score (inclusive)
            max_utility: Maximum utility score (inclusive)
            limit: Maximum results to return

        Returns:
            List of learning dicts matching the utility range
        """
        if not self._qdrant:
            return []

        # Use scroll to get all learnings, then filter
        results = []
        offset = None

        while len(results) < limit:
            documents, offset = await self._qdrant.scroll(limit=100, offset=offset)

            if not documents:
                break

            for doc in documents:
                # Access utility_score from metadata (scroll returns {id, text, metadata: {...}})
                metadata = doc.get("metadata", {})
                utility = metadata.get("utility_score", 0.5)

                if min_utility is not None and utility < min_utility:
                    continue
                if max_utility is not None and utility > max_utility:
                    continue

                # Flatten the doc for easier access downstream
                flattened = {
                    "id": doc.get("id"),
                    "text": doc.get("text", ""),
                    "content": doc.get("text", ""),  # Alias for compatibility
                    **metadata,
                }
                results.append(flattened)
                if len(results) >= limit:
                    break

            if offset is None:
                break

        return results

    async def get_all_learnings(self, limit: int = 1000) -> list[Learning]:
        """
        Get all learnings from WARM tier.

        Args:
            limit: Maximum learnings to return

        Returns:
            List of Learning objects
        """
        if not self._qdrant:
            return []

        learnings = []
        offset = None

        while len(learnings) < limit:
            documents, offset = await self._qdrant.scroll(limit=100, offset=offset)

            if not documents:
                break

            for doc in documents:
                try:
                    # scroll returns {id, text, metadata: {...}} - flatten for Learning.from_dict
                    metadata = doc.get("metadata", {})
                    learning_dict = {
                        "content": doc.get("text", ""),
                        "id": doc.get("id"),
                        **metadata,
                    }
                    learning = Learning.from_dict(learning_dict)
                    learnings.append(learning)
                except Exception:
                    continue

                if len(learnings) >= limit:
                    break

            if offset is None:
                break

        return learnings

    async def delete_learning(self, learning_id: str) -> bool:
        """
        Delete a learning from WARM tier.

        Args:
            learning_id: ID of the learning to delete

        Returns:
            True if successful, False otherwise
        """
        if not self._qdrant:
            return False

        try:
            await self._qdrant.delete(learning_id)
            logger.info(f"Deleted learning {learning_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to delete learning {learning_id}: {e}")
            return False

    async def get_learnings_by_category(
        self,
        category: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get learnings filtered by category.

        Args:
            category: Category to filter by
            limit: Maximum results to return

        Returns:
            List of learning dicts matching the category
        """
        if not self._qdrant:
            return []

        # Use scroll with filter instead of search (empty query doesn't work well)
        results = []
        offset = None

        while len(results) < limit:
            documents, offset = await self._qdrant.scroll(
                limit=min(100, limit - len(results)),
                offset=offset,
                filter={"category": category},
            )

            if not documents:
                break

            for doc in documents:
                # Flatten the doc structure
                metadata = doc.get("metadata", {})
                flattened = {
                    "id": doc.get("id"),
                    "text": doc.get("text", ""),
                    "content": doc.get("text", ""),
                    **metadata,
                }
                results.append(flattened)

            if offset is None:
                break

        return results[:limit]

    async def get_learnings_before(
        self,
        cutoff: datetime,
        limit: int = 100,
    ) -> list[Learning]:
        """
        Get learnings not accessed since cutoff date.

        Args:
            cutoff: Datetime cutoff for last_accessed
            limit: Maximum results to return

        Returns:
            List of Learning objects not accessed since cutoff
        """
        if not self._qdrant:
            return []

        stale_learnings = []
        offset = None

        while len(stale_learnings) < limit:
            documents, offset = await self._qdrant.scroll(limit=100, offset=offset)

            if not documents:
                break

            for doc in documents:
                # Access metadata fields correctly (scroll returns {id, text, metadata: {...}})
                metadata = doc.get("metadata", {})
                last_accessed_str = metadata.get("last_accessed")

                # If never accessed, check created_at
                if not last_accessed_str:
                    created_str = metadata.get("created_at")
                    if created_str:
                        try:
                            created_at = datetime.fromisoformat(created_str)
                            if created_at < cutoff:
                                learning_dict = {
                                    "content": doc.get("text", ""),
                                    "id": doc.get("id"),
                                    **metadata,
                                }
                                learning = Learning.from_dict(learning_dict)
                                stale_learnings.append(learning)
                        except (ValueError, TypeError):
                            pass
                else:
                    try:
                        last_accessed = datetime.fromisoformat(last_accessed_str)
                        if last_accessed < cutoff:
                            learning_dict = {
                                "content": doc.get("text", ""),
                                "id": doc.get("id"),
                                **metadata,
                            }
                            learning = Learning.from_dict(learning_dict)
                            stale_learnings.append(learning)
                    except (ValueError, TypeError):
                        pass

                if len(stale_learnings) >= limit:
                    break

            if offset is None:
                break

        return stale_learnings


# =============================================================================
# Knowledge Federation (Improvement 5: Multi-Agent Knowledge Federation)
# =============================================================================

class KnowledgeFederation:
    """
    Federated knowledge sharing with privacy-respecting scopes.

    Enables cross-project pattern propagation while maintaining project isolation.
    """

    def __init__(self, pai_memory: PAIMemory):
        self.memory = pai_memory

    async def get_federated_context(
        self,
        query: str,
        current_project_id: str,
        include_global: bool = True,
        include_similar_projects: bool = True,
    ) -> list[tuple[Learning, float]]:
        """
        Get knowledge from multiple scopes with relevance weighting.

        Args:
            query: Search query
            current_project_id: Current project context
            include_global: Whether to include global learnings
            include_similar_projects: Whether to include similar project learnings

        Returns:
            List of (Learning, weight) tuples sorted by weighted relevance
        """
        results: list[tuple[Learning, float]] = []

        # Helper to convert search result to Learning
        def _to_learning(l_dict: dict[str, Any]) -> Learning:
            # search_learnings returns {id, score, text, metadata: {...}}
            # Flatten for Learning.from_dict
            metadata = l_dict.get("metadata", {})
            return Learning.from_dict({
                "content": l_dict.get("text", ""),
                "id": l_dict.get("id"),
                **metadata,
            })

        # 1. Current project learnings (highest priority)
        project_learnings = await self.memory.search_learnings(
            query=query,
            project_id=current_project_id,
            limit=10,
        )
        for l_dict in project_learnings:
            try:
                learning = _to_learning(l_dict)
                results.append((learning, 1.0))  # Full weight
            except Exception:
                continue

        # 2. Global learnings (medium priority)
        if include_global:
            global_learnings = await self.memory.search_learnings(
                query=query,
                limit=5,
            )
            for l_dict in global_learnings:
                metadata = l_dict.get("metadata", {})
                if metadata.get("scope") == "global":
                    try:
                        learning = _to_learning(l_dict)
                        results.append((learning, 0.7))
                    except Exception:
                        continue

        # 3. Similar project learnings (lower priority, anonymized)
        if include_similar_projects:
            similar_projects = await self._find_similar_projects(current_project_id)
            for similar_project_id in similar_projects[:3]:
                cross_learnings = await self.memory.search_learnings(
                    query=query,
                    project_id=similar_project_id,
                    limit=3,
                )
                for l_dict in cross_learnings:
                    try:
                        learning = _to_learning(l_dict)
                        anonymized = self._anonymize_learning(learning)
                        results.append((anonymized, 0.4))
                    except Exception:
                        continue

        # Sort by weighted relevance (weight * utility_score)
        results.sort(
            key=lambda x: x[1] * x[0].utility_score,
            reverse=True,
        )

        return results[:15]

    async def _find_similar_projects(self, project_id: str) -> list[str]:
        """
        Find projects with similar tech stack/patterns.

        This is a placeholder - in production, this would query project metadata
        to find projects with similar languages, frameworks, etc.
        """
        # TODO: Implement project metadata querying
        # For now, return empty list as we don't have project metadata yet
        return []

    def _anonymize_learning(self, learning: Learning) -> Learning:
        """Remove project-specific details from a learning."""
        # Generalize content by removing specific file paths and project names
        content = learning.content
        # Simple anonymization - remove absolute paths
        import re
        content = re.sub(r"/home/[^/\s]+/[^\s]+", "<project-path>", content)

        return Learning(
            content=content,
            phase=learning.phase,
            category=learning.category,
            scope=LearningScope.GLOBAL,  # Mark as federated
            confidence=learning.confidence * 0.8,  # Reduce confidence for cross-project
            utility_score=learning.utility_score,
            access_count=learning.access_count,
            metadata={
                k: v for k, v in learning.metadata.items()
                if k not in ["project_id", "file_paths", "user_id", "plan_id"]
            },
        )

    async def promote_to_global(self, learning_id: str) -> Learning | None:
        """
        Promote high-utility project learning to global scope.

        Args:
            learning_id: ID of the learning to promote

        Returns:
            New global Learning if promoted, None otherwise
        """
        learning_data = await self.memory.get_learning(learning_id)
        if not learning_data:
            return None

        # get_learning returns {id, text, metadata: {...}} - access fields from metadata
        metadata = learning_data.get("metadata", {})
        utility = metadata.get("utility_score", 0.5)
        access_count = metadata.get("access_count", 0)

        # Only promote high-utility, well-used learnings
        if utility >= 0.8 and access_count >= 5:
            global_learning = Learning(
                content=self._generalize_content(learning_data.get("text", "")),
                phase=PAIPhase(metadata.get("phase", "learn")),
                category=metadata.get("category", "general"),
                scope=LearningScope.GLOBAL,
                confidence=metadata.get("confidence", 0.8),
                utility_score=utility,
                access_count=0,  # Reset for global tracking
                metadata={"promoted_from": learning_id},
            )
            await self.memory.store_learning(global_learning)
            logger.info(f"Promoted learning {learning_id} to global scope")
            return global_learning

        return None

    def _generalize_content(self, content: str) -> str:
        """Generalize content for cross-project use."""
        import re
        # Remove project-specific paths
        content = re.sub(r"/home/[^/\s]+/[^\s]+", "<path>", content)
        # Remove specific IDs
        content = re.sub(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", "<id>", content)
        return content
