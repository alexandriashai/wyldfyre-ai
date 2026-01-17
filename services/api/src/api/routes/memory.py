"""
Memory and learnings routes.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ai_core import get_logger
from ai_memory import PAIMemory, PAIPhase, QdrantStore

from ..dependencies import CurrentUserDep, RedisDep

logger = get_logger(__name__)

router = APIRouter(prefix="/memory", tags=["Memory"])


class SearchRequest(BaseModel):
    """Memory search request."""

    query: str
    limit: int = 10
    phase: PAIPhase | None = None


class SearchResult(BaseModel):
    """Search result item."""

    id: str
    content: str
    score: float
    phase: str | None
    agent: str | None
    timestamp: str | None


@router.get("/search")
async def search_memory(
    current_user: CurrentUserDep,
    query: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(10, ge=1, le=50),
    phase: PAIPhase | None = None,
) -> dict[str, Any]:
    """
    Semantic search across memory.

    Searches the warm tier (Qdrant) for relevant learnings.
    """
    try:
        qdrant = QdrantStore()

        # Build filter if phase specified
        search_filter = None
        if phase:
            search_filter = {"phase": phase.value}

        results = await qdrant.search(
            collection="learnings",
            query_text=query,
            limit=limit,
            filter_conditions=search_filter,
        )

        return {
            "query": query,
            "results": [
                SearchResult(
                    id=r.id,
                    content=r.payload.get("content", ""),
                    score=r.score,
                    phase=r.payload.get("phase"),
                    agent=r.payload.get("agent"),
                    timestamp=r.payload.get("timestamp"),
                )
                for r in results
            ],
            "count": len(results),
        }

    except Exception as e:
        logger.error("Memory search failed", error=str(e))
        return {
            "query": query,
            "results": [],
            "count": 0,
            "error": str(e),
        }


@router.get("/learnings")
async def list_learnings(
    current_user: CurrentUserDep,
    phase: PAIPhase | None = None,
    agent: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """
    Browse stored learnings.
    """
    try:
        qdrant = QdrantStore()

        # Build filter
        filter_conditions = {}
        if phase:
            filter_conditions["phase"] = phase.value
        if agent:
            filter_conditions["agent"] = agent

        results = await qdrant.scroll(
            collection="learnings",
            limit=limit,
            offset=offset,
            filter_conditions=filter_conditions if filter_conditions else None,
        )

        return {
            "learnings": [
                {
                    "id": r.id,
                    "content": r.payload.get("content", ""),
                    "phase": r.payload.get("phase"),
                    "agent": r.payload.get("agent"),
                    "timestamp": r.payload.get("timestamp"),
                    "utility_score": r.payload.get("utility_score", 0),
                }
                for r in results
            ],
            "count": len(results),
            "offset": offset,
        }

    except Exception as e:
        logger.error("Failed to list learnings", error=str(e))
        return {
            "learnings": [],
            "count": 0,
            "error": str(e),
        }


@router.get("/stats")
async def memory_stats(
    current_user: CurrentUserDep,
    redis: RedisDep,
) -> dict[str, Any]:
    """
    Get memory system statistics.
    """
    stats = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tiers": {
            "hot": {"type": "redis", "items": 0},
            "warm": {"type": "qdrant", "items": 0},
            "cold": {"type": "file", "items": 0},
        },
        "phases": {},
    }

    # Get hot tier stats from Redis
    try:
        # Count keys with memory prefix
        hot_count = 0
        cursor = 0
        while True:
            cursor, keys = await redis.scan(cursor, match="memory:hot:*", count=1000)
            hot_count += len(keys)
            if cursor == 0:
                break
        stats["tiers"]["hot"]["items"] = hot_count
    except Exception as e:
        logger.warning("Failed to get hot tier stats", error=str(e))

    # Get warm tier stats from Qdrant
    try:
        qdrant = QdrantStore()
        collection_info = await qdrant.get_collection_info("learnings")
        if collection_info:
            stats["tiers"]["warm"]["items"] = collection_info.get("points_count", 0)

            # Get phase breakdown
            for phase in PAIPhase:
                count = await qdrant.count(
                    collection="learnings",
                    filter_conditions={"phase": phase.value},
                )
                stats["phases"][phase.value] = count
    except Exception as e:
        logger.warning("Failed to get warm tier stats", error=str(e))

    return stats


@router.get("/phases")
async def list_phases(
    current_user: CurrentUserDep,
) -> dict[str, Any]:
    """
    Get information about PAI algorithm phases.
    """
    return {
        "phases": [
            {
                "name": phase.value,
                "order": i + 1,
                "description": _get_phase_description(phase),
            }
            for i, phase in enumerate(PAIPhase)
        ],
    }


def _get_phase_description(phase: PAIPhase) -> str:
    """Get description for a PAI phase."""
    descriptions = {
        PAIPhase.OBSERVE: "Gather information and context about the task",
        PAIPhase.THINK: "Analyze observations and form initial understanding",
        PAIPhase.PLAN: "Create structured approach to solve the problem",
        PAIPhase.BUILD: "Implement the solution based on the plan",
        PAIPhase.EXECUTE: "Run and apply the implementation",
        PAIPhase.VERIFY: "Validate results and check for correctness",
        PAIPhase.LEARN: "Extract learnings and update memory",
    }
    return descriptions.get(phase, "")
