"""
Memory tools for vector search and knowledge storage.

These tools allow agents to:
- Search the vector database for relevant information
- Store new learnings and knowledge with scope isolation
- Manage memory collections

Scope Levels:
- GLOBAL: Shared across all projects (general patterns, best practices)
- PROJECT: Specific to a project (conventions, architecture decisions)
- DOMAIN: Specific to a domain/site (client preferences, site configs)
"""

from typing import Any

from ai_core import get_logger, get_settings
from ai_memory import LearningScope, QdrantStore

from ..tools import ToolResult, tool

logger = get_logger(__name__)

# Default collection for agent learnings
DEFAULT_COLLECTION = "agent_learnings"


async def _get_qdrant_store(collection: str | None = None) -> QdrantStore:
    """Get a connected Qdrant store."""
    store = QdrantStore(collection_name=collection or DEFAULT_COLLECTION)
    await store.connect()
    return store


@tool(
    name="search_memory",
    description="""Search the vector database for relevant information using semantic similarity.
    Use this to find past learnings, stored knowledge, or similar content.
    The search uses embeddings to find semantically similar content, not just keyword matches.

    Scope Filtering:
    - Pass project_id to include GLOBAL + that project's learnings
    - Pass domain_id to include GLOBAL + that domain's learnings
    - Learnings from other projects/domains are automatically excluded""",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search query",
            },
            "collection": {
                "type": "string",
                "description": "Collection to search (default: agent_learnings)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results (default: 10)",
                "default": 10,
            },
            "score_threshold": {
                "type": "number",
                "description": "Minimum similarity score 0-1 (default: 0.7)",
                "default": 0.7,
            },
            "filter": {
                "type": "object",
                "description": "Metadata filter (e.g., {\"category\": \"ssl\", \"agent\": \"infra\"})",
            },
            "project_id": {
                "type": "string",
                "description": "Project context - returns GLOBAL + this project's learnings only",
            },
            "domain_id": {
                "type": "string",
                "description": "Domain context - returns GLOBAL + this domain's learnings only",
            },
        },
        "required": ["query"],
    },
)
async def search_memory(
    query: str,
    collection: str | None = None,
    limit: int = 10,
    score_threshold: float = 0.7,
    filter: dict[str, Any] | None = None,
    project_id: str | None = None,
    domain_id: str | None = None,
) -> ToolResult:
    """Search vector database for relevant information with scope filtering."""
    store = None
    try:
        store = await _get_qdrant_store(collection)

        # Over-fetch to account for scope filtering
        fetch_limit = limit * 3 if (project_id or domain_id) else limit

        results = await store.search(
            query=query,
            limit=fetch_limit,
            score_threshold=score_threshold,
            filter=filter,
        )

        # Apply scope filtering if project/domain context provided
        if project_id or domain_id:
            filtered_results = []
            for r in results:
                metadata = r.get("metadata", r)
                scope = metadata.get("scope", "global")
                result_project = metadata.get("project_id")
                result_domain = metadata.get("domain_id")

                if scope == "global":
                    filtered_results.append(r)
                elif scope == "project":
                    if project_id and result_project == project_id:
                        filtered_results.append(r)
                elif scope == "domain":
                    if domain_id and result_domain == domain_id:
                        filtered_results.append(r)
                else:
                    # Unknown scope - treat as global
                    filtered_results.append(r)

                if len(filtered_results) >= limit:
                    break
            results = filtered_results

        if not results:
            return ToolResult.ok({
                "message": "No relevant results found",
                "query": query,
                "project_id": project_id,
                "domain_id": domain_id,
                "results": [],
                "count": 0,
            })

        return ToolResult.ok({
            "message": f"Found {len(results)} relevant results",
            "query": query,
            "project_id": project_id,
            "domain_id": domain_id,
            "results": results,
            "count": len(results),
        })

    except Exception as e:
        logger.error("Memory search failed", query=query, error=str(e))
        return ToolResult.fail(f"Memory search failed: {e}")
    finally:
        if store:
            await store.disconnect()


@tool(
    name="store_memory",
    description="""Store information in the vector database for future retrieval.
    Use this to save learnings, important findings, or knowledge that should be remembered.
    The content will be embedded and can be found via semantic search later.

    Scope Levels:
    - GLOBAL (default): Shared across all projects - use for general patterns, best practices
    - PROJECT: Specific to a project - use for project conventions, architecture decisions
    - DOMAIN: Specific to a domain/site - use for client preferences, site-specific configs

    IMPORTANT: Use the appropriate scope to prevent context bleeding between projects!""",
    parameters={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The text content to store",
            },
            "collection": {
                "type": "string",
                "description": "Collection to store in (default: agent_learnings)",
            },
            "category": {
                "type": "string",
                "description": "Category for organization (e.g., 'ssl', 'docker', 'nginx')",
            },
            "phase": {
                "type": "string",
                "enum": ["observe", "think", "plan", "build", "execute", "verify", "learn"],
                "description": "PAI phase this learning came from (default: learn)",
                "default": "learn",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags for filtering",
            },
            "source": {
                "type": "string",
                "description": "Source of the information (e.g., 'task:123', 'manual')",
            },
            "importance": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "Importance level",
                "default": "medium",
            },
            "scope": {
                "type": "string",
                "enum": ["global", "project", "domain"],
                "description": "Scope level - global (shared), project (project-specific), domain (site-specific)",
                "default": "global",
            },
            "project_id": {
                "type": "string",
                "description": "Project ID (required if scope is 'project')",
            },
            "domain_id": {
                "type": "string",
                "description": "Domain ID (required if scope is 'domain')",
            },
            "agent": {
                "type": "string",
                "description": "Agent that created this memory (auto-detected if not provided)",
            },
        },
        "required": ["content"],
    },
)
async def store_memory(
    content: str,
    collection: str | None = None,
    category: str | None = None,
    phase: str = "learn",
    tags: list[str] | None = None,
    source: str | None = None,
    importance: str = "medium",
    scope: str = "global",
    project_id: str | None = None,
    domain_id: str | None = None,
    agent: str | None = None,
) -> ToolResult:
    """Store content in vector database with scope isolation."""
    from datetime import datetime, timezone

    store = None
    try:
        # Validate scope requirements
        if scope == "project" and not project_id:
            return ToolResult.fail("project_id is required when scope is 'project'")
        if scope == "domain" and not domain_id:
            return ToolResult.fail("domain_id is required when scope is 'domain'")

        store = await _get_qdrant_store(collection)

        metadata = {
            "category": category,
            "phase": phase,
            "outcome": "success",
            "tags": tags or [],
            "source": source,
            "importance": importance,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            # Scope fields
            "scope": scope,
            "project_id": project_id,
            "domain_id": domain_id,
        }
        # Remove None values (but keep scope and phase)
        metadata = {k: v for k, v in metadata.items() if v is not None or k in ("scope", "phase")}

        doc_id = await store.upsert(
            id=None,  # Auto-generate ID
            text=content,
            metadata=metadata,
        )

        return ToolResult.ok({
            "message": f"Successfully stored in memory (scope: {scope})",
            "id": doc_id,
            "collection": collection or DEFAULT_COLLECTION,
            "category": category,
            "phase": phase,
            "scope": scope,
            "project_id": project_id,
            "domain_id": domain_id,
        })

    except Exception as e:
        logger.error("Memory store failed", error=str(e))
        return ToolResult.fail(f"Memory store failed: {e}")
    finally:
        if store:
            await store.disconnect()


@tool(
    name="list_memory_collections",
    description="List all available memory collections in the vector database.",
    parameters={
        "type": "object",
        "properties": {},
    },
)
async def list_memory_collections() -> ToolResult:
    """List all Qdrant collections."""
    try:
        from qdrant_client import AsyncQdrantClient
        
        settings = get_settings().qdrant
        client = AsyncQdrantClient(
            host=settings.host,
            port=settings.port,
            api_key=settings.api_key.get_secret_value() or None,
        )
        
        collections_response = await client.get_collections()
        await client.close()
        
        collections = []
        for col in collections_response.collections:
            collections.append({
                "name": col.name,
            })
        
        return ToolResult.ok({
            "message": f"Found {len(collections)} collections",
            "collections": collections,
            "count": len(collections),
        })
        
    except Exception as e:
        logger.error("List collections failed", error=str(e))
        return ToolResult.fail(f"List collections failed: {e}")


@tool(
    name="get_memory_stats",
    description="Get statistics about a memory collection (document count, etc.).",
    parameters={
        "type": "object",
        "properties": {
            "collection": {
                "type": "string",
                "description": "Collection name (default: agent_learnings)",
            },
        },
    },
)
async def get_memory_stats(collection: str | None = None) -> ToolResult:
    """Get collection statistics."""
    try:
        from qdrant_client import AsyncQdrantClient
        
        settings = get_settings().qdrant
        client = AsyncQdrantClient(
            host=settings.host,
            port=settings.port,
            api_key=settings.api_key.get_secret_value() or None,
        )
        
        collection_name = collection or DEFAULT_COLLECTION
        
        try:
            info = await client.get_collection(collection_name)
            
            stats = {
                "collection": collection_name,
                "points_count": info.points_count,
                "indexed_vectors_count": info.indexed_vectors_count,
                "status": info.status.value if info.status else "unknown",
            }
            
            await client.close()
            
            return ToolResult.ok({
                "message": f"Collection '{collection_name}' has {info.points_count} documents",
                **stats,
            })
            
        except Exception as e:
            if "not found" in str(e).lower():
                await client.close()
                return ToolResult.ok({
                    "message": f"Collection '{collection_name}' does not exist",
                    "collection": collection_name,
                    "exists": False,
                })
            raise
        
    except Exception as e:
        logger.error("Get memory stats failed", error=str(e))
        return ToolResult.fail(f"Get memory stats failed: {e}")


@tool(
    name="delete_memory",
    description="Delete a specific memory entry by its ID.",
    parameters={
        "type": "object",
        "properties": {
            "memory_id": {
                "type": "string",
                "description": "The document ID to delete",
            },
            "collection": {
                "type": "string",
                "description": "Collection name (default: agent_learnings)",
            },
        },
        "required": ["memory_id"],
    },
    permission_level=1,
)
async def delete_memory(memory_id: str, collection: str | None = None) -> ToolResult:
    """Delete a memory entry."""
    store = None
    try:
        store = await _get_qdrant_store(collection)

        success = await store.delete(memory_id)

        if success:
            return ToolResult.ok({
                "message": "Successfully deleted memory entry",
                "id": memory_id,
                "collection": collection or DEFAULT_COLLECTION,
            })
        else:
            return ToolResult.fail(f"Failed to delete memory entry: {memory_id}")

    except Exception as e:
        logger.error("Delete memory failed", memory_id=memory_id, error=str(e))
        return ToolResult.fail(f"Delete memory failed: {e}")
    finally:
        if store:
            await store.disconnect()
