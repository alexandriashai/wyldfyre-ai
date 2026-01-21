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
from typing import Any

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


class Learning:
    """Represents a learning extracted from a task."""

    def __init__(
        self,
        content: str,
        phase: PAIPhase,
        category: str,
        task_id: str | None = None,
        agent_type: str | None = None,
        confidence: float = 0.8,
        metadata: dict[str, Any] | None = None,
    ):
        self.content = content
        self.phase = phase
        self.category = category
        self.task_id = task_id
        self.agent_type = agent_type
        self.confidence = confidence
        self.metadata = metadata or {}
        self.created_at = datetime.now(timezone.utc)

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
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Learning":
        """Create from dictionary."""
        learning = cls(
            content=data["content"],
            phase=PAIPhase(data["phase"]),
            category=data["category"],
            task_id=data.get("task_id"),
            agent_type=data.get("agent_type"),
            confidence=data.get("confidence", 0.8),
            metadata=data.get("metadata", {}),
        )
        if "created_at" in data:
            learning.created_at = datetime.fromisoformat(data["created_at"])
        return learning


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
            return json.loads(data)
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

    async def store_learning(self, learning: Learning) -> str | None:
        """Store a learning in WARM tier (Qdrant)."""
        if not self._qdrant:
            logger.warning("Qdrant not configured, skipping WARM storage")
            return None

        doc_id = await self._qdrant.upsert(
            id=None,
            text=learning.content,
            metadata={
                "phase": learning.phase.value,
                "category": learning.category,
                "task_id": learning.task_id,
                "agent_type": learning.agent_type,
                "confidence": learning.confidence,
                "created_at": learning.created_at.isoformat(),
                **learning.metadata,
            },
        )
        memory_operations_total.labels(
            tier="warm", operation="store", status="success"
        ).inc()
        return doc_id

    async def search_learnings(
        self,
        query: str,
        phase: PAIPhase | None = None,
        category: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search learnings in WARM tier."""
        if not self._qdrant:
            return []

        filter_dict = {}
        if phase:
            filter_dict["phase"] = phase.value
        if category:
            filter_dict["category"] = category

        return await self._qdrant.search(
            query=query,
            limit=limit,
            filter=filter_dict if filter_dict else None,
        )

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

    async def read_cold(self, filepath: Path) -> dict[str, Any] | None:
        """Read archived data from COLD tier."""
        if not filepath.exists():
            return None

        async with aiofiles.open(filepath, "r") as f:
            content = await f.read()
            return json.loads(content)

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
