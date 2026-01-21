"""
Memory and learnings routes.

Supports scoped learnings:
- GLOBAL: Shared across all projects
- PROJECT: Isolated to a specific project
- DOMAIN: Isolated to a specific domain/site
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ai_core import get_logger
from ai_memory import LearningScope, PAIPhase, QdrantStore

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
    # Scope filtering - pass project/domain context
    project_id: str | None = Query(None, description="Filter to global + this project's learnings"),
    domain_id: str | None = Query(None, description="Filter to global + this domain's learnings"),
) -> dict[str, Any]:
    """
    Semantic search across memory with scope filtering.

    Scope Rules:
    - GLOBAL learnings are always included
    - PROJECT learnings only included if project_id matches
    - DOMAIN learnings only included if domain_id matches

    Pass project_id and/or domain_id to filter out learnings from other projects/domains.
    """
    try:
        qdrant = await get_qdrant_store()

        # Build filter if phase specified
        search_filter = None
        if phase:
            search_filter = {"phase": phase.value}

        # Over-fetch to account for scope filtering
        results = await qdrant.search(
            query=query,
            limit=limit * 3,
            score_threshold=0.5,
            filter=search_filter,
        )

        # Apply scope filtering
        filtered_results = []
        for r in results:
            metadata = r.get("metadata", r)
            scope = metadata.get("scope", "global")
            result_project = metadata.get("project_id")
            result_domain = metadata.get("domain_id")

            # Check scope access
            if scope == "global":
                filtered_results.append(r)
            elif scope == "project":
                if project_id and result_project == project_id:
                    filtered_results.append(r)
            elif scope == "domain":
                if domain_id and result_domain == domain_id:
                    filtered_results.append(r)
            else:
                # Unknown scope - treat as global (backward compat)
                filtered_results.append(r)

            if len(filtered_results) >= limit:
                break

        await qdrant.disconnect()

        return {
            "query": query,
            "project_id": project_id,
            "domain_id": domain_id,
            "results": [
                {
                    "id": r["id"],
                    "content": r.get("text", ""),
                    "score": r.get("score", 0),
                    "phase": r.get("metadata", {}).get("phase"),
                    "category": r.get("metadata", {}).get("category"),
                    "agent": r.get("metadata", {}).get("agent"),
                    "scope": r.get("metadata", {}).get("scope", "global"),
                    "created_at": r.get("metadata", {}).get("created_at"),
                    "metadata": r.get("metadata", {}),
                }
                for r in filtered_results
            ],
            "count": len(filtered_results),
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
    scope: LearningScope | None = Query(None, description="Filter by scope (global/project/domain)"),
    project_id: str | None = Query(None, description="Filter to global + this project's learnings"),
    domain_id: str | None = Query(None, description="Filter to global + this domain's learnings"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """
    Browse stored learnings with scope filtering.

    Pass project_id and/or domain_id to see only learnings accessible in that context.
    """
    try:
        qdrant = await get_qdrant_store()

        # Build filter
        filter_conditions = {}
        if phase:
            filter_conditions["phase"] = phase.value
        if agent:
            filter_conditions["agent"] = agent
        if scope:
            filter_conditions["scope"] = scope.value

        # Over-fetch for scope filtering
        fetch_limit = limit * 3 if (project_id or domain_id) else limit

        results, next_offset = await qdrant.scroll(
            filter=filter_conditions if filter_conditions else None,
            limit=fetch_limit,
            offset=None,
        )

        # Apply scope filtering if project/domain context provided
        if project_id or domain_id:
            filtered_results = []
            for r in results:
                metadata = r.get("metadata", r)
                result_scope = metadata.get("scope", "global")
                result_project = metadata.get("project_id")
                result_domain = metadata.get("domain_id")

                if result_scope == "global":
                    filtered_results.append(r)
                elif result_scope == "project":
                    if project_id and result_project == project_id:
                        filtered_results.append(r)
                elif result_scope == "domain":
                    if domain_id and result_domain == domain_id:
                        filtered_results.append(r)
                else:
                    filtered_results.append(r)

                if len(filtered_results) >= limit:
                    break
            results = filtered_results

        await qdrant.disconnect()

        return {
            "learnings": [
                {
                    "id": r["id"],
                    "content": r.get("text", ""),
                    "phase": r.get("metadata", {}).get("phase"),
                    "outcome": r.get("metadata", {}).get("outcome", "success"),
                    "agent": r.get("metadata", {}).get("agent"),
                    "scope": r.get("metadata", {}).get("scope", "global"),
                    "project_id": r.get("metadata", {}).get("project_id"),
                    "domain_id": r.get("metadata", {}).get("domain_id"),
                    "created_at": r.get("metadata", {}).get("created_at"),
                    "utility_score": r.get("metadata", {}).get("utility_score", 0),
                }
                for r in results[:limit]
            ],
            "count": len(results[:limit]),
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
