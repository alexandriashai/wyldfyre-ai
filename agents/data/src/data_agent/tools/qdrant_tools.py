"""
Qdrant vector database tools for the Data Agent.

These tools provide advanced operations for managing the vector database:
- Collection management (create, delete, describe)
- Bulk operations (batch insert)
- Index management
- Advanced search with filters
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ai_core import CapabilityCategory, get_logger, get_settings
from base_agent import ToolResult, tool

logger = get_logger(__name__)


async def _get_qdrant_client():
    """Get a Qdrant client."""
    from qdrant_client import AsyncQdrantClient

    settings = get_settings().qdrant
    client = AsyncQdrantClient(
        host=settings.host,
        port=settings.port,
        api_key=settings.api_key.get_secret_value() or None,
    )
    return client


@tool(
    name="qdrant_create_collection",
    description="""Create a new Qdrant collection with specified vector dimensions and configuration.
    Use this to set up new storage for embeddings.""",
    parameters={
        "type": "object",
        "properties": {
            "collection_name": {
                "type": "string",
                "description": "Name for the new collection",
            },
            "vector_size": {
                "type": "integer",
                "description": "Dimension of vectors (e.g., 1536 for OpenAI ada-002)",
                "default": 1536,
            },
            "distance": {
                "type": "string",
                "enum": ["cosine", "euclid", "dot"],
                "description": "Distance metric for similarity",
                "default": "cosine",
            },
            "on_disk": {
                "type": "boolean",
                "description": "Store vectors on disk (for large collections)",
                "default": False,
            },
        },
        "required": ["collection_name"],
    },
    permission_level=2,
    capability_category=CapabilityCategory.DATA,
)
async def qdrant_create_collection(
    collection_name: str,
    vector_size: int = 1536,
    distance: str = "cosine",
    on_disk: bool = False,
) -> ToolResult:
    """Create a new Qdrant collection."""
    try:
        from qdrant_client.models import Distance, VectorParams

        client = await _get_qdrant_client()

        # Map distance string to enum
        distance_map = {
            "cosine": Distance.COSINE,
            "euclid": Distance.EUCLID,
            "dot": Distance.DOT,
        }

        await client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=distance_map.get(distance, Distance.COSINE),
                on_disk=on_disk,
            ),
        )

        await client.close()

        return ToolResult.ok({
            "message": f"Collection '{collection_name}' created",
            "collection": collection_name,
            "vector_size": vector_size,
            "distance": distance,
            "on_disk": on_disk,
        })

    except Exception as e:
        logger.error("Create collection failed", collection=collection_name, error=str(e))
        return ToolResult.fail(f"Create collection failed: {e}")


@tool(
    name="qdrant_delete_collection",
    description="""Delete a Qdrant collection and all its data.
    WARNING: This is destructive and cannot be undone.""",
    parameters={
        "type": "object",
        "properties": {
            "collection_name": {
                "type": "string",
                "description": "Name of the collection to delete",
            },
        },
        "required": ["collection_name"],
    },
    permission_level=2,
    capability_category=CapabilityCategory.DATA,
    requires_confirmation=True,
)
async def qdrant_delete_collection(collection_name: str) -> ToolResult:
    """Delete a Qdrant collection."""
    try:
        client = await _get_qdrant_client()

        # Verify collection exists
        collections = await client.get_collections()
        exists = any(c.name == collection_name for c in collections.collections)

        if not exists:
            await client.close()
            return ToolResult.fail(f"Collection '{collection_name}' not found")

        await client.delete_collection(collection_name)
        await client.close()

        return ToolResult.ok({
            "message": f"Collection '{collection_name}' deleted",
            "collection": collection_name,
        })

    except Exception as e:
        logger.error("Delete collection failed", collection=collection_name, error=str(e))
        return ToolResult.fail(f"Delete collection failed: {e}")


@tool(
    name="qdrant_describe_collection",
    description="""Get detailed information about a Qdrant collection including
    vector configuration, indexing status, and statistics.""",
    parameters={
        "type": "object",
        "properties": {
            "collection_name": {
                "type": "string",
                "description": "Name of the collection to describe",
            },
        },
        "required": ["collection_name"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.DATA,
)
async def qdrant_describe_collection(collection_name: str) -> ToolResult:
    """Describe a Qdrant collection."""
    try:
        client = await _get_qdrant_client()

        info = await client.get_collection(collection_name)

        result = {
            "collection": collection_name,
            "status": info.status.value if info.status else "unknown",
            "points_count": info.points_count,
            "vectors_count": info.vectors_count,
            "indexed_vectors_count": info.indexed_vectors_count,
            "segments_count": info.segments_count,
        }

        # Get vector config
        if info.config and info.config.params:
            params = info.config.params
            if hasattr(params, "vectors"):
                vec_config = params.vectors
                if hasattr(vec_config, "size"):
                    result["vector_size"] = vec_config.size
                    result["distance"] = vec_config.distance.value if vec_config.distance else None
                    result["on_disk"] = vec_config.on_disk

        # Get optimizer config
        if info.config and info.config.optimizer_config:
            opt = info.config.optimizer_config
            result["indexing_threshold"] = opt.indexing_threshold

        await client.close()

        return ToolResult.ok(result)

    except Exception as e:
        if "not found" in str(e).lower():
            return ToolResult.fail(f"Collection '{collection_name}' not found")
        logger.error("Describe collection failed", collection=collection_name, error=str(e))
        return ToolResult.fail(f"Describe collection failed: {e}")


@tool(
    name="qdrant_batch_upsert",
    description="""Batch insert or update points in a Qdrant collection.
    Use this for efficient bulk operations.""",
    parameters={
        "type": "object",
        "properties": {
            "collection_name": {
                "type": "string",
                "description": "Target collection name",
            },
            "points": {
                "type": "array",
                "description": "Array of points to upsert. Each point should have 'text' and optionally 'metadata'",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Point ID (auto-generated if not provided)"},
                        "text": {"type": "string", "description": "Text content to embed"},
                        "metadata": {"type": "object", "description": "Additional metadata"},
                    },
                    "required": ["text"],
                },
            },
        },
        "required": ["collection_name", "points"],
    },
    permission_level=2,
    capability_category=CapabilityCategory.DATA,
)
async def qdrant_batch_upsert(
    collection_name: str,
    points: list[dict[str, Any]],
) -> ToolResult:
    """Batch upsert points to a collection."""
    try:
        from ai_memory import QdrantStore

        store = QdrantStore(collection_name=collection_name)
        await store.connect()

        inserted_ids = []
        errors = []

        for i, point in enumerate(points):
            try:
                text = point.get("text", "")
                metadata = point.get("metadata", {})
                point_id = point.get("id")

                doc_id = await store.upsert(
                    id=point_id,
                    text=text,
                    metadata=metadata,
                )
                inserted_ids.append(doc_id)

            except Exception as e:
                errors.append({"index": i, "error": str(e)})

        await store.disconnect()

        return ToolResult.ok({
            "message": f"Batch upsert completed: {len(inserted_ids)} succeeded, {len(errors)} failed",
            "collection": collection_name,
            "inserted_count": len(inserted_ids),
            "inserted_ids": inserted_ids[:20],  # Limit returned IDs
            "error_count": len(errors),
            "errors": errors[:10] if errors else None,
        })

    except Exception as e:
        logger.error("Batch upsert failed", collection=collection_name, error=str(e))
        return ToolResult.fail(f"Batch upsert failed: {e}")


@tool(
    name="qdrant_advanced_search",
    description="""Perform advanced vector search with complex filters.
    Supports multiple filter conditions, score boosting, and grouping.""",
    parameters={
        "type": "object",
        "properties": {
            "collection_name": {
                "type": "string",
                "description": "Collection to search",
            },
            "query": {
                "type": "string",
                "description": "Natural language search query",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results",
                "default": 10,
            },
            "score_threshold": {
                "type": "number",
                "description": "Minimum similarity score (0-1)",
                "default": 0.0,
            },
            "must_match": {
                "type": "object",
                "description": "Required metadata conditions (all must match)",
            },
            "should_match": {
                "type": "object",
                "description": "Optional metadata conditions (at least one should match)",
            },
            "must_not_match": {
                "type": "object",
                "description": "Exclusion conditions (none should match)",
            },
        },
        "required": ["collection_name", "query"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.DATA,
)
async def qdrant_advanced_search(
    collection_name: str,
    query: str,
    limit: int = 10,
    score_threshold: float = 0.0,
    must_match: dict[str, Any] | None = None,
    should_match: dict[str, Any] | None = None,
    must_not_match: dict[str, Any] | None = None,
) -> ToolResult:
    """Advanced vector search with complex filters."""
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        from ai_memory import QdrantStore

        store = QdrantStore(collection_name=collection_name)
        await store.connect()

        # Build filter
        qdrant_filter = None
        conditions = []

        def build_conditions(match_dict: dict, condition_type: str) -> list:
            """Build Qdrant filter conditions from a dictionary."""
            conds = []
            for key, value in match_dict.items():
                conds.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value),
                    )
                )
            return conds

        must = []
        should = []
        must_not = []

        if must_match:
            must = build_conditions(must_match, "must")
        if should_match:
            should = build_conditions(should_match, "should")
        if must_not_match:
            must_not = build_conditions(must_not_match, "must_not")

        if must or should or must_not:
            qdrant_filter = Filter(
                must=must or None,
                should=should or None,
                must_not=must_not or None,
            )

        # Perform search with filter
        results = await store.search(
            query=query,
            limit=limit,
            score_threshold=score_threshold,
            filter=qdrant_filter,
        )

        await store.disconnect()

        # Format results
        formatted_results = []
        for r in results:
            formatted_results.append({
                "id": r.get("id"),
                "score": round(r.get("score", 0), 4),
                "text": r.get("text", "")[:500],  # Truncate
                "metadata": r.get("metadata", {}),
            })

        return ToolResult.ok({
            "message": f"Found {len(formatted_results)} results",
            "collection": collection_name,
            "query": query,
            "results": formatted_results,
            "count": len(formatted_results),
        })

    except Exception as e:
        logger.error("Advanced search failed", collection=collection_name, error=str(e))
        return ToolResult.fail(f"Advanced search failed: {e}")


@tool(
    name="qdrant_delete_points",
    description="""Delete points from a collection by IDs or filter conditions.""",
    parameters={
        "type": "object",
        "properties": {
            "collection_name": {
                "type": "string",
                "description": "Target collection",
            },
            "ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of point IDs to delete",
            },
            "point_filter": {
                "type": "object",
                "description": "Metadata filter to match points for deletion",
            },
        },
        "required": ["collection_name"],
    },
    permission_level=2,
    capability_category=CapabilityCategory.DATA,
    requires_confirmation=True,
)
async def qdrant_delete_points(
    collection_name: str,
    ids: list[str] | None = None,
    point_filter: dict[str, Any] | None = None,
) -> ToolResult:
    """Delete points from a collection."""
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue, PointIdsList

        if not ids and not point_filter:
            return ToolResult.fail("Either 'ids' or 'point_filter' must be provided")

        client = await _get_qdrant_client()

        if ids:
            # Delete by IDs
            await client.delete(
                collection_name=collection_name,
                points_selector=PointIdsList(points=ids),
            )
            deleted_count = len(ids)
        else:
            # Delete by filter
            conditions = []
            for key, value in (point_filter or {}).items():
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )

            qdrant_filter = Filter(must=conditions)

            # First count matching points
            results = await client.scroll(
                collection_name=collection_name,
                scroll_filter=qdrant_filter,
                limit=10000,
                with_payload=False,
                with_vectors=False,
            )
            deleted_count = len(results[0]) if results else 0

            # Delete
            await client.delete(
                collection_name=collection_name,
                points_selector=qdrant_filter,
            )

        await client.close()

        return ToolResult.ok({
            "message": f"Deleted {deleted_count} points from '{collection_name}'",
            "collection": collection_name,
            "deleted_count": deleted_count,
        })

    except Exception as e:
        logger.error("Delete points failed", collection=collection_name, error=str(e))
        return ToolResult.fail(f"Delete points failed: {e}")


@tool(
    name="qdrant_scroll_points",
    description="""Scroll through all points in a collection with optional filtering.
    Useful for inspection and bulk operations.""",
    parameters={
        "type": "object",
        "properties": {
            "collection_name": {
                "type": "string",
                "description": "Collection to scroll",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum points to return",
                "default": 100,
            },
            "offset": {
                "type": "string",
                "description": "Pagination offset (point ID)",
            },
            "point_filter": {
                "type": "object",
                "description": "Metadata filter",
            },
            "with_payload": {
                "type": "boolean",
                "description": "Include point payloads",
                "default": True,
            },
        },
        "required": ["collection_name"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.DATA,
)
async def qdrant_scroll_points(
    collection_name: str,
    limit: int = 100,
    offset: str | None = None,
    point_filter: dict[str, Any] | None = None,
    with_payload: bool = True,
) -> ToolResult:
    """Scroll through points in a collection."""
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        client = await _get_qdrant_client()

        # Build filter if provided
        qdrant_filter = None
        if point_filter:
            conditions = []
            for key, value in point_filter.items():
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
            qdrant_filter = Filter(must=conditions)

        # Scroll
        results, next_offset = await client.scroll(
            collection_name=collection_name,
            scroll_filter=qdrant_filter,
            limit=min(limit, 1000),  # Cap at 1000
            offset=offset,
            with_payload=with_payload,
            with_vectors=False,
        )

        await client.close()

        # Format results
        points = []
        for point in results:
            p = {
                "id": str(point.id),
            }
            if with_payload and point.payload:
                p["payload"] = point.payload
            points.append(p)

        return ToolResult.ok({
            "message": f"Retrieved {len(points)} points",
            "collection": collection_name,
            "points": points,
            "count": len(points),
            "next_offset": str(next_offset) if next_offset else None,
        })

    except Exception as e:
        logger.error("Scroll points failed", collection=collection_name, error=str(e))
        return ToolResult.fail(f"Scroll points failed: {e}")
