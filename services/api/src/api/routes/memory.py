"""
Memory and learnings routes.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ai_core import get_logger
from ai_memory import PAIPhase, QdrantStore

from ..dependencies import CurrentUserDep, RedisDep

logger = get_logger(__name__)

router = APIRouter(prefix="/memory", tags=["Memory"])

# Collection name used by agents for storing learnings
LEARNINGS_COLLECTION = "agent_learnings"


async def get_qdrant_store() -> QdrantStore:
    """Get connected QdrantStore instance."""
    store = QdrantStore(collection_name=LEARNINGS_COLLECTION)
    await store.connect()
    return store


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
        qdrant = await get_qdrant_store()

        # Build filter if phase specified
        search_filter = None
        if phase:
            search_filter = {"phase": phase.value}

        results = await qdrant.search(
            query=query,
            limit=limit,
            score_threshold=0.5,  # Lower threshold for broader results
            filter=search_filter,
        )

        await qdrant.disconnect()

        return {
            "query": query,
            "results": [
                {
                    "id": r["id"],
                    "content": r.get("text", ""),
                    "score": r.get("score", 0),
                    "phase": r.get("metadata", {}).get("phase"),
                    "category": r.get("metadata", {}).get("category"),
                    "agent": r.get("metadata", {}).get("agent"),
                    "created_at": r.get("metadata", {}).get("created_at"),
                    "metadata": r.get("metadata", {}),
                }
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
        qdrant = await get_qdrant_store()

        # Build filter
        filter_conditions = {}
        if phase:
            filter_conditions["phase"] = phase.value
        if agent:
            filter_conditions["agent"] = agent

        # scroll() returns (documents, next_offset)
        # Note: offset is a point ID string in Qdrant, not numeric
        results, next_offset = await qdrant.scroll(
            filter=filter_conditions if filter_conditions else None,
            limit=limit,
            offset=None,  # Qdrant scroll uses point ID, not numeric offset
        )

        await qdrant.disconnect()

        return {
            "learnings": [
                {
                    "id": r["id"],
                    "content": r.get("text", ""),
                    "phase": r.get("metadata", {}).get("phase"),
                    "outcome": r.get("metadata", {}).get("outcome", "success"),
                    "agent": r.get("metadata", {}).get("agent"),
                    "created_at": r.get("metadata", {}).get("created_at"),
                    "utility_score": r.get("metadata", {}).get("utility_score", 0),
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

    Returns stats in format expected by frontend:
    - total_memories: total count
    - by_tier: {hot, warm, cold}
    - by_agent: {agent_name: count}
    """
    hot_count = 0
    warm_count = 0
    by_agent: dict[str, int] = {}

    # Get hot tier stats from Redis
    try:
        cursor = 0
        while True:
            cursor, keys = await redis.scan(cursor, match="memory:hot:*", count=1000)
            hot_count += len(keys)
            if cursor == 0:
                break
    except Exception as e:
        logger.warning("Failed to get hot tier stats", error=str(e))

    # Get warm tier stats from Qdrant
    try:
        qdrant = await get_qdrant_store()
        warm_count = await qdrant.count()

        # Get agent breakdown by scrolling through documents
        all_docs, _ = await qdrant.scroll(limit=1000)
        for doc in all_docs:
            agent = doc.get("metadata", {}).get("agent", "unknown")
            by_agent[agent] = by_agent.get(agent, 0) + 1

        await qdrant.disconnect()
    except Exception as e:
        logger.warning("Failed to get warm tier stats", error=str(e))

    return {
        "total_memories": hot_count + warm_count,
        "by_tier": {
            "hot": hot_count,
            "warm": warm_count,
            "cold": 0,  # TODO: implement cold tier count
        },
        "by_agent": by_agent,
    }


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
