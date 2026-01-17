"""
PAI (Personal AI) Memory System - 3-tier memory architecture.

HOT (Redis): Real-time task traces, 24-hour retention
WARM (Qdrant): Synthesized learnings, 30-day retention, searchable
COLD (File): Immutable historical reference, 365-day retention
"""

import json
from datetime import datetime, timedelta
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
        self.created_at = datetime.utcnow()

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
            "timestamp": datetime.utcnow().isoformat(),
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
            "archived_at": datetime.utcnow().isoformat(),
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

    async def archive_old_warm(self, older_than_days: int = 30) -> int:
        """Archive old WARM tier data to COLD tier."""
        if not self._qdrant:
            return 0

        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        archived_count = 0

        # This would require scrolling through Qdrant
        # Implementation depends on specific retention policy
        logger.info("Archive operation completed", archived=archived_count)
        return archived_count
