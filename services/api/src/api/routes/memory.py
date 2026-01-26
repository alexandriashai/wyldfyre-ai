"""
Memory and learnings routes.

Supports scoped learnings:
- GLOBAL: Shared across all projects
- PROJECT: Isolated to a specific project
- DOMAIN: Isolated to a specific domain/site
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_core import (
    CircuitOpenError,
    LLMClient,
    get_all_breaker_status,
    get_logger,
    reset_circuit_breaker,
)
from ai_memory import LearningScope, PAIPhase, QdrantStore

from ..dependencies import CurrentUserDep, DbSessionDep, RedisDep

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
                    "tags": r.get("metadata", {}).get("tags", []),  # Tags for filtering
                    "created_at": r.get("metadata", {}).get("created_at"),
                    "metadata": r.get("metadata", {}),
                }
                for r in filtered_results
            ],
            "count": len(filtered_results),
        }

    except CircuitOpenError as e:
        logger.warning("Memory search blocked by circuit breaker", error=str(e))
        return {
            "query": query,
            "results": [],
            "count": 0,
            "error": "Embedding service temporarily unavailable (circuit breaker open). Will auto-recover shortly.",
            "circuit_breaker": True,
        }
    except Exception as e:
        logger.error("Memory search failed", error=str(e))
        return {
            "query": query,
            "results": [],
            "count": 0,
            "error": str(e),
        }


@router.get("/circuit-breaker")
async def circuit_breaker_status(current_user: CurrentUserDep) -> dict[str, Any]:
    """Get circuit breaker status for memory-related services."""
    return {"breakers": get_all_breaker_status()}


@router.post("/circuit-breaker/reset")
async def circuit_breaker_reset(
    current_user: CurrentUserDep,
    name: str = Query("openai-embeddings", description="Circuit breaker name to reset"),
) -> dict[str, Any]:
    """Reset a circuit breaker to restore service."""
    success = reset_circuit_breaker(name)
    if success:
        logger.info("Circuit breaker reset via API", name=name, user=current_user.id)
        return {"status": "reset", "name": name}
    return {"status": "not_found", "name": name}


@router.get("/learnings")
async def list_learnings(
    current_user: CurrentUserDep,
    phase: PAIPhase | None = None,
    agent: str | None = None,
    scope: LearningScope | None = Query(None, description="Filter by scope (global/project/domain)"),
    project_id: str | None = Query(None, description="Filter to global + this project's learnings"),
    domain_id: str | None = Query(None, description="Filter to global + this domain's learnings"),
    tag: str | None = Query(None, description="Filter by tag (exact match)"),
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

        # Over-fetch for scope/tag filtering
        fetch_limit = limit * 3 if (project_id or domain_id or tag) else limit

        results, next_offset = await qdrant.scroll(
            filter=filter_conditions if filter_conditions else None,
            limit=fetch_limit,
            offset=None,
        )

        # Apply scope and tag filtering
        if project_id or domain_id or tag:
            filtered_results = []
            for r in results:
                metadata = r.get("metadata", r)
                result_scope = metadata.get("scope", "global")
                result_project = metadata.get("project_id")
                result_domain = metadata.get("domain_id")
                result_tags = metadata.get("tags", [])

                # Scope filtering
                scope_match = True
                if project_id or domain_id:
                    if result_scope == "global":
                        scope_match = True
                    elif result_scope == "project":
                        scope_match = project_id and result_project == project_id
                    elif result_scope == "domain":
                        scope_match = domain_id and result_domain == domain_id

                # Tag filtering
                tag_match = True
                if tag:
                    tag_match = tag in result_tags

                if scope_match and tag_match:
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
                    "category": r.get("metadata", {}).get("category"),
                    "outcome": r.get("metadata", {}).get("outcome", "success"),
                    "agent": r.get("metadata", {}).get("agent"),
                    "scope": r.get("metadata", {}).get("scope", "global"),
                    "project_id": r.get("metadata", {}).get("project_id"),
                    "domain_id": r.get("metadata", {}).get("domain_id"),
                    "tags": r.get("metadata", {}).get("tags", []),  # Tags for filtering
                    "created_at": r.get("metadata", {}).get("created_at") or r.get("metadata", {}).get("timestamp"),
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


class CreateLearningRequest(BaseModel):
    """Request body for creating a new learning."""

    content: str
    phase: PAIPhase | None = None
    category: str | None = None
    scope: LearningScope = LearningScope.GLOBAL
    project_id: str | None = None
    domain_id: str | None = None
    confidence: float | None = None
    tags: list[str] | None = None  # Tags for filtering and categorization
    metadata: dict[str, Any] | None = None


@router.post("/learnings")
async def create_learning(
    body: CreateLearningRequest,
    current_user: CurrentUserDep,
) -> dict[str, Any]:
    """
    Store a new learning/memory.

    Creates a new entry in the vector store with the given content and metadata.
    """
    try:
        qdrant = await get_qdrant_store()

        # Build metadata
        meta: dict[str, Any] = {
            "phase": body.phase.value if body.phase else None,
            "category": body.category,
            "scope": body.scope.value,
            "outcome": "success",
            "agent": "user",
            "tags": body.tags or [],  # Tags for filtering
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if body.project_id:
            meta["project_id"] = body.project_id
        if body.domain_id:
            meta["domain_id"] = body.domain_id
        if body.confidence is not None:
            meta["confidence"] = body.confidence
        if body.metadata:
            meta.update(body.metadata)

        doc_id = await qdrant.upsert(
            id=None,
            text=body.content,
            metadata=meta,
        )

        await qdrant.disconnect()

        return {
            "id": doc_id,
            "content": body.content,
            "phase": body.phase.value if body.phase else None,
            "category": body.category,
            "scope": body.scope.value,
            "tags": body.tags or [],
            "created_at": meta["created_at"],
            "message": "Learning stored successfully",
        }

    except Exception as e:
        logger.error("Failed to create learning", error=str(e))
        return {"error": str(e)}


class UpdateLearningRequest(BaseModel):
    """Request body for updating a learning."""

    content: str | None = None
    phase: PAIPhase | None = None
    category: str | None = None
    confidence: float | None = None
    tags: list[str] | None = None  # Tags for filtering and categorization
    metadata: dict[str, Any] | None = None


@router.get("/learnings/{learning_id}")
async def get_learning(
    learning_id: str,
    current_user: CurrentUserDep,
) -> dict[str, Any]:
    """Get a single learning by ID."""
    try:
        qdrant = await get_qdrant_store()
        result = await qdrant.get(learning_id)
        await qdrant.disconnect()

        if not result:
            return {"error": "Learning not found", "id": learning_id}

        return {
            "id": result["id"],
            "content": result.get("text", ""),
            "phase": result.get("metadata", {}).get("phase"),
            "category": result.get("metadata", {}).get("category"),
            "confidence": result.get("metadata", {}).get("confidence"),
            "agent": result.get("metadata", {}).get("agent_type"),
            "scope": result.get("metadata", {}).get("scope", "global"),
            "tags": result.get("metadata", {}).get("tags", []),  # Tags for filtering
            "created_at": result.get("metadata", {}).get("created_at"),
            "updated_at": result.get("metadata", {}).get("updated_at"),
            "metadata": result.get("metadata", {}),
        }

    except Exception as e:
        logger.error("Failed to get learning", id=learning_id, error=str(e))
        return {"error": str(e), "id": learning_id}


@router.put("/learnings/{learning_id}")
async def update_learning(
    learning_id: str,
    body: UpdateLearningRequest,
    current_user: CurrentUserDep,
) -> dict[str, Any]:
    """
    Update an existing learning.

    Only re-embeds if content changes. Metadata fields are merged with existing.
    """
    try:
        qdrant = await get_qdrant_store()

        # Build metadata updates
        meta_updates: dict[str, Any] = {}
        if body.phase is not None:
            meta_updates["phase"] = body.phase.value
        if body.category is not None:
            meta_updates["category"] = body.category
        if body.confidence is not None:
            meta_updates["confidence"] = body.confidence
        if body.tags is not None:
            meta_updates["tags"] = body.tags
        if body.metadata:
            meta_updates.update(body.metadata)

        # Add updated_at timestamp
        meta_updates["updated_at"] = datetime.now(timezone.utc).isoformat()

        result = await qdrant.update(
            id=learning_id,
            text=body.content,
            metadata=meta_updates if meta_updates else None,
        )

        await qdrant.disconnect()

        if not result:
            return {"error": "Learning not found", "id": learning_id}

        return {
            "id": result["id"],
            "content": result.get("text", ""),
            "phase": result.get("metadata", {}).get("phase"),
            "category": result.get("metadata", {}).get("category"),
            "confidence": result.get("metadata", {}).get("confidence"),
            "tags": result.get("metadata", {}).get("tags", []),
            "updated_at": result.get("metadata", {}).get("updated_at"),
            "message": "Learning updated successfully",
        }

    except Exception as e:
        logger.error("Failed to update learning", id=learning_id, error=str(e))
        return {"error": str(e), "id": learning_id}


@router.delete("/learnings/{learning_id}")
async def delete_learning(
    learning_id: str,
    current_user: CurrentUserDep,
) -> dict[str, Any]:
    """Delete a learning by ID."""
    try:
        qdrant = await get_qdrant_store()
        success = await qdrant.delete(learning_id)
        await qdrant.disconnect()

        if success:
            return {"message": "Learning deleted", "id": learning_id}
        return {"error": "Failed to delete learning", "id": learning_id}

    except Exception as e:
        logger.error("Failed to delete learning", id=learning_id, error=str(e))
        return {"error": str(e), "id": learning_id}


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


# --- Synthesize Learnings Endpoint ---

EXTRACTION_SYSTEM_PROMPT = """You are a knowledge extraction system. Extract discrete, reusable insights from the conversation.

Focus on:
- Architecture patterns and conventions used in this project
- User preferences and workflow habits
- Technical gotchas and lessons learned
- Tool/library usage patterns
- Configuration and deployment knowledge

Avoid:
- Task-specific steps that aren't reusable
- Obvious/trivial information
- Transient state or temporary decisions

Each learning must be a standalone, self-contained statement that would be useful in future conversations.

Respond with a JSON array of objects:
[
  {
    "content": "The extracted learning as a clear, actionable statement",
    "category": "pattern|convention|preference|architecture|gotcha",
    "scope": "global|project",
    "confidence": 0.5-0.9,
    "file_references": ["relative/path/to/file.ts"]
  }
]

Only output valid JSON. No preamble or explanation."""

CODEBASE_ANALYSIS_PROMPT = """You are a codebase analyst. Given file contents from a project, derive knowledge about how the application works.

Extract learnings about:
- How specific features/systems work (e.g., "The review system uses X pattern")
- Data flow and relationships between components
- Business logic and domain rules
- API contracts and integration points
- State management patterns
- Authentication/authorization flows
- Database schemas and relationships
- Configuration and environment handling

Format each learning as a clear, factual statement that explains HOW something works, not just WHAT exists.

Good examples:
- "The review system stores reviews in the 'reviews' table with a foreign key to 'listings', and calculates aggregate ratings via a PostgreSQL trigger on insert/update"
- "User authentication flows through AuthProvider → useAuth hook → JWT validation middleware, with tokens stored in httpOnly cookies"
- "File uploads are processed by the media-service which resizes images to 3 sizes (thumb, medium, large) before storing in S3"

Bad examples:
- "There is a reviews table" (too vague, doesn't explain how it works)
- "The app uses React" (obvious, not useful)

Respond with a JSON array:
[
  {
    "content": "Clear explanation of how this system/feature works",
    "category": "architecture|data-flow|business-logic|integration|security|feature",
    "scope": "project",
    "confidence": 0.6-0.95,
    "file_references": ["paths/to/relevant/files"],
    "related_entities": ["ComponentName", "tableName", "apiEndpoint"]
  }
]

Only output valid JSON. No preamble or explanation."""

CODEBASE_QUESTION_PROMPT = """You are a codebase analyst answering a specific question about how the application works.

Given the question and relevant file contents, provide a detailed answer and extract learnings.

Your response should:
1. Directly answer the question with specifics from the code
2. Extract reusable learnings about the system

Respond with JSON:
{
  "answer": "Detailed answer to the question based on the code",
  "learnings": [
    {
      "content": "A discrete, reusable learning derived from this analysis",
      "category": "architecture|data-flow|business-logic|integration|security|feature",
      "scope": "project",
      "confidence": 0.6-0.95,
      "file_references": ["paths/to/files"],
      "related_entities": ["names of components, tables, endpoints involved"]
    }
  ]
}

Only output valid JSON."""

CLASSIFICATION_SYSTEM_PROMPT = """You are a learning classifier. Given a candidate learning, file evidence, and existing related learnings, determine the appropriate action.

Actions:
- "create": New information not covered by existing learnings
- "update": Refines or improves an existing learning (provide merged content)
- "delete": An existing learning is now outdated/contradicted

Respond with a JSON object:
{
  "action": "create|update|delete",
  "content": "final learning text (merged if update, null if delete)",
  "confidence": 0.0-1.0,
  "verified": true/false,
  "evidence": "Brief description of what confirmed/denied the learning",
  "reason": "Only for delete: why the existing learning is obsolete",
  "target_existing_id": "ID of existing learning to update/delete, or null for create"
}

Only output valid JSON. No preamble or explanation."""

EVIDENCE_SEARCH_PROMPT = """You are a codebase evidence finder. Given a claim/learning, generate search queries to find supporting or contradicting evidence in a codebase.

Output a JSON object with specific search terms:
{
  "file_patterns": ["glob patterns to find relevant files, e.g. '**/auth/*.ts', 'src/**/api.py'"],
  "grep_terms": ["exact strings or regex to grep for, e.g. 'useAuth', 'class.*Repository'"],
  "function_names": ["specific function or class names to look for"],
  "import_patterns": ["import statements that would indicate usage, e.g. 'from auth import', 'import { useAuth }'"],
  "counter_evidence_terms": ["terms that would CONTRADICT the claim if found"]
}

Be specific. Focus on technical identifiers (function names, class names, import paths, config keys) that would definitively prove or disprove the claim.

Only output valid JSON."""

EVIDENCE_ANALYSIS_PROMPT = """You are an evidence analyzer. Given a claim and file evidence found in the codebase, determine if the claim is VERIFIED, PARTIALLY_VERIFIED, UNVERIFIED, or CONTRADICTED.

Analyze carefully:
1. Does the evidence directly support the claim?
2. Is there contradicting evidence?
3. How confident can we be?

Respond with a JSON object:
{
  "verdict": "VERIFIED|PARTIALLY_VERIFIED|UNVERIFIED|CONTRADICTED",
  "confidence": 0.0-1.0,
  "supporting_evidence": ["list of specific evidence that supports the claim"],
  "contradicting_evidence": ["list of specific evidence that contradicts the claim"],
  "summary": "Brief explanation of why this verdict was reached",
  "refined_claim": "If the evidence suggests a more accurate version of the claim, provide it here, otherwise null"
}

Only output valid JSON."""


class SynthesizeRequest(BaseModel):
    """Request body for synthesize endpoint."""

    content: str
    project_id: str | None = None
    domain_id: str | None = None
    conversation_id: str | None = None
    verify: bool = True
    # Mode: "conversation" extracts from chat, "codebase" analyzes project files,
    # "question" answers a specific question about the codebase
    mode: str = "conversation"  # conversation | codebase | question
    # For codebase/question mode: specific paths or patterns to analyze
    file_patterns: list[str] | None = None
    # For question mode: the question to answer
    question: str | None = None


class RelatedExisting(BaseModel):
    """Related existing learning."""

    id: str
    content: str
    similarity: float


class EvidenceDetail(BaseModel):
    """Detailed evidence information from thorough search."""

    verdict: str = "UNVERIFIED"  # VERIFIED, PARTIALLY_VERIFIED, UNVERIFIED, CONTRADICTED
    supporting_evidence: list[str] = []
    contradicting_evidence: list[str] = []
    files_searched: int = 0
    summary: str | None = None


class SynthesizeProposal(BaseModel):
    """A single synthesize proposal."""

    action: str  # create, update, delete
    content: str | None = None
    category: str | None = None
    confidence: float = 0.0
    verified: bool = False
    scope: str = "project"
    evidence: str | None = None
    evidence_detail: EvidenceDetail | None = None  # Detailed evidence from agent search
    reason: str | None = None
    related_existing: RelatedExisting | None = None


class SynthesizeResponse(BaseModel):
    """Response from synthesize endpoint."""

    proposals: list[SynthesizeProposal]
    # For question mode: the direct answer to the question
    answer: str | None = None
    # Mode that was used
    mode: str = "conversation"
    # Files that were analyzed (for codebase/question modes)
    files_analyzed: list[str] | None = None


def _safe_read_file(root_path: str, relative_path: str, max_chars: int = 3000) -> str | None:
    """Safely read a file within project root, preventing path traversal."""
    if not root_path or not relative_path:
        return None

    # Block path traversal
    if ".." in relative_path or relative_path.startswith("/"):
        return None

    resolved = os.path.realpath(os.path.join(root_path, relative_path))
    canonical_root = os.path.realpath(root_path)

    if not resolved.startswith(canonical_root + os.sep) and resolved != canonical_root:
        return None

    if not os.path.isfile(resolved):
        return None

    try:
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            return f.read(max_chars)
    except Exception:
        return None


def _grep_project(root_path: str, pattern: str, max_results: int = 5) -> list[str]:
    """Run a simple grep in the project for a pattern, return matching file paths."""
    if not root_path or not pattern or not os.path.isdir(root_path):
        return []

    try:
        result = subprocess.run(
            ["grep", "-rl", "--include=*.ts", "--include=*.tsx", "--include=*.py",
             "--include=*.js", "--include=*.jsx", pattern, root_path],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            files = result.stdout.strip().split("\n")[:max_results]
            # Convert to relative paths
            return [os.path.relpath(f, root_path) for f in files if f]
    except Exception:
        pass
    return []


def _grep_with_context(root_path: str, pattern: str, max_results: int = 5, context_lines: int = 3) -> list[dict[str, Any]]:
    """Run grep with context, returning file path, line number, and surrounding context."""
    if not root_path or not pattern or not os.path.isdir(root_path):
        return []

    results = []
    try:
        result = subprocess.run(
            ["grep", "-rn", f"-C{context_lines}",
             "--include=*.ts", "--include=*.tsx", "--include=*.py",
             "--include=*.js", "--include=*.jsx", "--include=*.json",
             "--include=*.yaml", "--include=*.yml",
             pattern, root_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            current_file = None
            current_match = {"file": "", "line": 0, "context": []}

            for line in result.stdout.split("\n")[:200]:  # Cap output
                if not line.strip():
                    if current_match["context"]:
                        results.append(current_match)
                        current_match = {"file": "", "line": 0, "context": []}
                    continue

                # Parse grep output format: file:line:content or file-line-content
                if ":" in line:
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        file_path = os.path.relpath(parts[0], root_path)
                        try:
                            line_num = int(parts[1])
                            content = parts[2]
                            if file_path != current_match["file"]:
                                if current_match["context"]:
                                    results.append(current_match)
                                current_match = {"file": file_path, "line": line_num, "context": []}
                            current_match["context"].append(content)
                        except ValueError:
                            current_match["context"].append(line)

                if len(results) >= max_results:
                    break

            if current_match["context"]:
                results.append(current_match)
    except Exception as e:
        logger.warning("Grep with context failed", error=str(e))

    return results[:max_results]


def _glob_files(root_path: str, patterns: list[str], max_results: int = 20) -> list[str]:
    """Find files matching glob patterns."""
    import glob as glob_module

    if not root_path or not os.path.isdir(root_path):
        return []

    found_files = set()
    for pattern in patterns:
        # Handle both relative and absolute patterns
        if pattern.startswith("**/"):
            # Recursive pattern
            full_pattern = os.path.join(root_path, pattern)
        elif pattern.startswith("/"):
            continue  # Skip absolute paths for safety
        else:
            full_pattern = os.path.join(root_path, "**", pattern)

        try:
            matches = glob_module.glob(full_pattern, recursive=True)
            for m in matches[:max_results]:
                if os.path.isfile(m):
                    found_files.add(os.path.relpath(m, root_path))
        except Exception:
            pass

        if len(found_files) >= max_results:
            break

    return list(found_files)[:max_results]


async def _analyze_codebase_files(
    llm: "LLMClient",
    root_path: str,
    file_patterns: list[str] | None = None,
    question: str | None = None,
    max_files: int = 15,
    max_chars_per_file: int = 4000,
) -> dict[str, Any]:
    """
    Analyze codebase files to derive learnings about application functionality.

    Args:
        llm: LLM client
        root_path: Project root path
        file_patterns: Glob patterns to find relevant files
        question: Optional specific question to answer
        max_files: Maximum files to analyze
        max_chars_per_file: Max characters to read per file

    Returns:
        {
            "answer": str | None (if question mode),
            "candidates": list[dict] (extracted learnings),
            "files_analyzed": list[str]
        }
    """
    files_to_analyze: list[str] = []

    # Find files based on patterns or smart defaults
    if file_patterns:
        files_to_analyze = _glob_files(root_path, file_patterns, max_results=max_files)
    else:
        # Smart defaults: find main source files
        default_patterns = [
            "src/**/*.ts", "src/**/*.tsx", "src/**/*.py",
            "app/**/*.ts", "app/**/*.tsx", "app/**/*.py",
            "lib/**/*.ts", "lib/**/*.py",
            "services/**/*.py", "packages/**/*.py",
            "**/models/*.py", "**/routes/*.py", "**/api/*.py",
            "**/components/**/*.tsx", "**/hooks/**/*.ts",
        ]
        files_to_analyze = _glob_files(root_path, default_patterns, max_results=max_files * 2)

    if not files_to_analyze:
        return {
            "answer": "No source files found to analyze" if question else None,
            "candidates": [],
            "files_analyzed": [],
        }

    # If there's a question, use LLM to identify most relevant files first
    if question and len(files_to_analyze) > max_files:
        # Generate search terms from the question
        search_response = await llm.create_message(
            model="fast",
            max_tokens=256,
            system="Extract search terms from this question to find relevant code files. Output JSON: {\"terms\": [\"term1\", \"term2\"]}",
            messages=[{"role": "user", "content": question}],
        )
        search_data = _parse_json_response(search_response.text_content)
        if search_data and search_data.get("terms"):
            # Filter files by relevance to search terms
            relevant_files = []
            for term in search_data["terms"][:5]:
                matches = _grep_project(root_path, term, max_results=5)
                relevant_files.extend(matches)
            # Prioritize matched files
            relevant_set = set(relevant_files)
            files_to_analyze = (
                [f for f in files_to_analyze if f in relevant_set][:max_files // 2] +
                [f for f in files_to_analyze if f not in relevant_set][:max_files // 2]
            )

    files_to_analyze = files_to_analyze[:max_files]

    # Read file contents
    file_contents: list[dict[str, str]] = []
    for file_path in files_to_analyze:
        content = _safe_read_file(root_path, file_path, max_chars=max_chars_per_file)
        if content:
            file_contents.append({
                "path": file_path,
                "content": content,
            })

    if not file_contents:
        return {
            "answer": "Could not read any files" if question else None,
            "candidates": [],
            "files_analyzed": [],
        }

    # Build analysis input
    files_text = ""
    for fc in file_contents:
        files_text += f"\n\n=== FILE: {fc['path']} ===\n{fc['content']}"

    # Choose prompt based on mode
    if question:
        prompt = CODEBASE_QUESTION_PROMPT
        user_content = f"Question: {question}\n\nRelevant files:{files_text}"
    else:
        prompt = CODEBASE_ANALYSIS_PROMPT
        user_content = f"Analyze these files and extract learnings about how the application works:{files_text}"

    # Call LLM for analysis
    analysis_response = await llm.create_message(
        model="balanced",  # Use balanced model for better analysis
        max_tokens=2048,
        system=prompt,
        messages=[{"role": "user", "content": user_content}],
    )

    result = _parse_json_response(analysis_response.text_content)

    if question:
        # Question mode response
        if result and isinstance(result, dict):
            return {
                "answer": result.get("answer", ""),
                "candidates": result.get("learnings", []),
                "files_analyzed": [fc["path"] for fc in file_contents],
            }
        return {
            "answer": analysis_response.text_content,
            "candidates": [],
            "files_analyzed": [fc["path"] for fc in file_contents],
        }
    else:
        # Codebase analysis mode
        if result and isinstance(result, list):
            return {
                "answer": None,
                "candidates": result,
                "files_analyzed": [fc["path"] for fc in file_contents],
            }
        return {
            "answer": None,
            "candidates": [],
            "files_analyzed": [fc["path"] for fc in file_contents],
        }


async def _thorough_evidence_search(
    llm: "LLMClient",
    claim: str,
    root_path: str,
    file_refs: list[str],
) -> dict[str, Any]:
    """
    Perform thorough agent-based evidence search for a claim.

    Returns:
        {
            "verdict": "VERIFIED|PARTIALLY_VERIFIED|UNVERIFIED|CONTRADICTED",
            "confidence": float,
            "supporting_evidence": list[str],
            "contradicting_evidence": list[str],
            "summary": str,
            "refined_claim": str | None,
            "files_searched": int,
            "evidence_snippets": list[dict]
        }
    """
    from ai_core import LLMClient

    # Step 1: Generate search queries
    search_response = await llm.create_message(
        model="fast",
        max_tokens=512,
        system=EVIDENCE_SEARCH_PROMPT,
        messages=[{"role": "user", "content": f"Claim to verify:\n{claim}"}],
    )

    search_queries = _parse_json_response(search_response.text_content)
    if not search_queries:
        search_queries = {
            "file_patterns": [],
            "grep_terms": [],
            "function_names": [],
            "import_patterns": [],
            "counter_evidence_terms": [],
        }

    # Step 2: Collect evidence from multiple sources
    evidence_snippets: list[dict[str, Any]] = []
    files_searched = set()

    # 2a. Check explicitly referenced files
    for ref in file_refs[:5]:
        content = _safe_read_file(root_path, ref, max_chars=3000)
        if content:
            evidence_snippets.append({
                "source": "referenced_file",
                "file": ref,
                "content": content[:1500],
            })
            files_searched.add(ref)

    # 2b. Search using generated file patterns
    file_patterns = search_queries.get("file_patterns", [])
    if file_patterns:
        matched_files = _glob_files(root_path, file_patterns, max_results=10)
        for mf in matched_files:
            if mf not in files_searched:
                content = _safe_read_file(root_path, mf, max_chars=2000)
                if content:
                    evidence_snippets.append({
                        "source": "pattern_match",
                        "file": mf,
                        "content": content[:1000],
                    })
                    files_searched.add(mf)

    # 2c. Grep for specific terms (supporting evidence)
    grep_terms = search_queries.get("grep_terms", []) + search_queries.get("function_names", [])
    for term in grep_terms[:5]:
        if not term or len(term) < 3:
            continue
        matches = _grep_with_context(root_path, term, max_results=3, context_lines=5)
        for match in matches:
            if match["file"] not in files_searched:
                evidence_snippets.append({
                    "source": "grep_match",
                    "file": match["file"],
                    "line": match["line"],
                    "term": term,
                    "content": "\n".join(match["context"]),
                })
                files_searched.add(match["file"])

    # 2d. Grep for import patterns
    import_patterns = search_queries.get("import_patterns", [])
    for pattern in import_patterns[:3]:
        if not pattern:
            continue
        matches = _grep_with_context(root_path, pattern, max_results=2, context_lines=2)
        for match in matches:
            evidence_snippets.append({
                "source": "import_pattern",
                "file": match["file"],
                "term": pattern,
                "content": "\n".join(match["context"]),
            })

    # 2e. Search for counter-evidence
    counter_terms = search_queries.get("counter_evidence_terms", [])
    counter_evidence_found = []
    for term in counter_terms[:3]:
        if not term or len(term) < 3:
            continue
        matches = _grep_with_context(root_path, term, max_results=2, context_lines=3)
        for match in matches:
            counter_evidence_found.append({
                "source": "counter_evidence",
                "file": match["file"],
                "term": term,
                "content": "\n".join(match["context"]),
            })

    if counter_evidence_found:
        evidence_snippets.extend(counter_evidence_found)

    # Step 3: Analyze collected evidence with LLM
    if not evidence_snippets:
        return {
            "verdict": "UNVERIFIED",
            "confidence": 0.3,
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "summary": "No relevant code evidence found in the codebase",
            "refined_claim": None,
            "files_searched": len(files_searched),
            "evidence_snippets": [],
        }

    # Format evidence for analysis
    evidence_text = ""
    for i, snippet in enumerate(evidence_snippets[:15], 1):
        source = snippet.get("source", "unknown")
        file = snippet.get("file", "unknown")
        content = snippet.get("content", "")[:800]
        term = snippet.get("term", "")

        evidence_text += f"\n--- Evidence {i} ({source}) ---\n"
        evidence_text += f"File: {file}\n"
        if term:
            evidence_text += f"Search term: {term}\n"
        evidence_text += f"Content:\n{content}\n"

    analysis_prompt = f"""Claim to verify:
"{claim}"

Evidence found in codebase:
{evidence_text}

Analyze this evidence carefully. Consider:
1. Does the code actually demonstrate what the claim states?
2. Are there any contradictions or alternative patterns?
3. How confident can we be based on this evidence?"""

    analysis_response = await llm.create_message(
        model="fast",
        max_tokens=768,
        system=EVIDENCE_ANALYSIS_PROMPT,
        messages=[{"role": "user", "content": analysis_prompt}],
    )

    analysis = _parse_json_response(analysis_response.text_content)
    if not analysis:
        # Fallback if parsing fails
        has_evidence = len(evidence_snippets) > 0
        return {
            "verdict": "PARTIALLY_VERIFIED" if has_evidence else "UNVERIFIED",
            "confidence": 0.5 if has_evidence else 0.3,
            "supporting_evidence": [f"Found {len(evidence_snippets)} potential evidence snippets"],
            "contradicting_evidence": [],
            "summary": "Evidence found but analysis inconclusive",
            "refined_claim": None,
            "files_searched": len(files_searched),
            "evidence_snippets": evidence_snippets[:5],
        }

    return {
        "verdict": analysis.get("verdict", "UNVERIFIED"),
        "confidence": analysis.get("confidence", 0.5),
        "supporting_evidence": analysis.get("supporting_evidence", []),
        "contradicting_evidence": analysis.get("contradicting_evidence", []),
        "summary": analysis.get("summary", ""),
        "refined_claim": analysis.get("refined_claim"),
        "files_searched": len(files_searched),
        "evidence_snippets": evidence_snippets[:5],
    }


async def _get_conversation_context(redis, conversation_id: str) -> str:
    """Fetch conversation history from Redis."""
    try:
        # Get message IDs from the conversation list
        message_ids = await redis.lrange(f"conversation:{conversation_id}:messages", 0, -1)
        if not message_ids:
            return ""

        messages_text = []
        for msg_id in message_ids[-20:]:  # Last 20 messages for context
            msg_data = await redis.hgetall(f"message:{msg_id}")
            if msg_data:
                role = msg_data.get("role", "unknown")
                content = msg_data.get("content", "")
                if content:
                    messages_text.append(f"[{role}]: {content}")

        return "\n\n".join(messages_text)
    except Exception as e:
        logger.warning("Failed to fetch conversation context", error=str(e))
        return ""


async def _get_project_root(db: AsyncSession, project_id: str) -> str | None:
    """Get project root_path from database."""
    try:
        from database.models.project import Project
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        return project.root_path if project else None
    except Exception as e:
        logger.warning("Failed to get project root", error=str(e))
        return None


def _parse_json_response(text: str) -> Any:
    """Parse JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize_learnings(
    body: SynthesizeRequest,
    current_user: CurrentUserDep,
    redis: RedisDep,
    db: DbSessionDep,
) -> SynthesizeResponse:
    """
    Synthesize learnings from a message or codebase analysis using AI.

    Modes:
    - "conversation": Extract learnings from chat messages (default)
    - "codebase": Analyze project files to derive application knowledge
    - "question": Answer a specific question about the codebase and extract learnings

    Pipeline:
    1. Gather context (conversation history, project root)
    2. Extract candidate learnings via LLM (mode-dependent)
    3. Verify candidates against codebase + classify against existing learnings
    """
    llm = LLMClient()
    proposals: list[SynthesizeProposal] = []
    answer: str | None = None
    files_analyzed: list[str] | None = None

    # --- Step 1: Gather Context ---
    conversation_context = ""
    if body.conversation_id:
        conversation_context = await _get_conversation_context(redis, body.conversation_id)

    root_path: str | None = None
    if body.project_id:
        root_path = await _get_project_root(db, body.project_id)

    # --- Step 2: Extract Candidate Learnings (mode-dependent) ---
    candidates: list[dict[str, Any]] = []

    if body.mode in ("codebase", "question") and root_path:
        # Codebase analysis or question-answering mode
        try:
            analysis_result = await _analyze_codebase_files(
                llm=llm,
                root_path=root_path,
                file_patterns=body.file_patterns,
                question=body.question or (body.content if body.mode == "question" else None),
                max_files=15,
                max_chars_per_file=4000,
            )
            candidates = analysis_result.get("candidates", [])
            answer = analysis_result.get("answer")
            files_analyzed = analysis_result.get("files_analyzed", [])

            if not candidates and body.mode == "question":
                # For question mode, if no structured learnings, create one from the answer
                if answer:
                    candidates = [{
                        "content": answer[:500],  # Truncate long answers
                        "category": "feature",
                        "scope": "project",
                        "confidence": 0.7,
                        "file_references": files_analyzed[:3] if files_analyzed else [],
                    }]

        except Exception as e:
            logger.error("Codebase analysis failed", error=str(e), mode=body.mode)
            return SynthesizeResponse(
                proposals=[],
                answer=f"Analysis failed: {str(e)}",
                mode=body.mode,
                files_analyzed=[],
            )

    else:
        # Conversation extraction mode (default)
        extraction_input = ""
        if conversation_context:
            extraction_input += f"=== CONVERSATION CONTEXT ===\n{conversation_context}\n\n"
        extraction_input += f"=== TARGET MESSAGE (extract learnings from this) ===\n{body.content}"

        try:
            extraction_response = await llm.create_message(
                model="fast",
                max_tokens=2048,
                system=EXTRACTION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": extraction_input}],
            )
            candidates = _parse_json_response(extraction_response.text_content) or []
        except Exception as e:
            logger.error("LLM extraction failed", error=str(e))
            return SynthesizeResponse(proposals=[], mode=body.mode)

    if not candidates or not isinstance(candidates, list):
        return SynthesizeResponse(
            proposals=[],
            answer=answer,
            mode=body.mode,
            files_analyzed=files_analyzed,
        )

    # --- Step 3: Verify + Classify each candidate ---
    qdrant = await get_qdrant_store()

    for candidate in candidates[:10]:  # Cap at 10 candidates
        content = candidate.get("content", "")
        category = candidate.get("category", "pattern")
        scope = candidate.get("scope", "project")
        base_confidence = candidate.get("confidence", 0.7)
        file_refs = candidate.get("file_references", [])

        # 3a. Thorough codebase verification via agent search
        evidence_result: dict[str, Any] = {
            "verdict": "UNVERIFIED",
            "confidence": base_confidence,
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "summary": "",
            "refined_claim": None,
        }
        verified = False

        if body.verify and root_path:
            try:
                evidence_result = await _thorough_evidence_search(
                    llm=llm,
                    claim=content,
                    root_path=root_path,
                    file_refs=file_refs,
                )

                verdict = evidence_result.get("verdict", "UNVERIFIED")

                if verdict == "VERIFIED":
                    verified = True
                    base_confidence = max(base_confidence, evidence_result.get("confidence", 0.85))
                elif verdict == "PARTIALLY_VERIFIED":
                    verified = True
                    base_confidence = evidence_result.get("confidence", 0.6)
                elif verdict == "CONTRADICTED":
                    # Evidence contradicts the claim - significantly lower confidence
                    base_confidence = max(0.2, evidence_result.get("confidence", 0.3))
                    verified = False
                else:  # UNVERIFIED
                    # No evidence found - moderate confidence reduction
                    if file_refs:
                        base_confidence = max(0.3, base_confidence - 0.2)
                    else:
                        base_confidence = max(0.4, base_confidence - 0.1)

                # Use refined claim if provided
                if evidence_result.get("refined_claim"):
                    content = evidence_result["refined_claim"]

            except Exception as e:
                logger.warning("Thorough evidence search failed", claim=content[:50], error=str(e))
                # Fallback to basic verification
                if file_refs:
                    for ref in file_refs[:3]:
                        if _safe_read_file(root_path, ref, max_chars=100):
                            verified = True
                            break

        # 3b. Semantic search for related existing learnings
        related_existing: RelatedExisting | None = None
        existing_context = ""

        try:
            search_filter = {}
            if body.project_id:
                search_filter["project_id"] = body.project_id

            search_results = await qdrant.search(
                query=content,
                limit=3,
                score_threshold=0.6,
                filter=search_filter if search_filter else None,
            )

            if search_results:
                top = search_results[0]
                related_existing = RelatedExisting(
                    id=top["id"],
                    content=top.get("text", ""),
                    similarity=top.get("score", 0.0),
                )
                existing_context = "\n".join(
                    f"- [{r['id']}] (score={r.get('score', 0):.2f}): {r.get('text', '')}"
                    for r in search_results
                )
        except Exception as e:
            logger.warning("Semantic search failed during synthesize", error=str(e))

        # 3c. Classification via LLM
        # Build evidence summary from thorough search
        evidence_summary = ""
        if evidence_result.get("supporting_evidence"):
            evidence_summary += "Supporting evidence:\n"
            for ev in evidence_result["supporting_evidence"][:5]:
                evidence_summary += f"  - {ev}\n"
        if evidence_result.get("contradicting_evidence"):
            evidence_summary += "Contradicting evidence:\n"
            for ev in evidence_result["contradicting_evidence"][:3]:
                evidence_summary += f"  - {ev}\n"
        if evidence_result.get("summary"):
            evidence_summary += f"\nEvidence analysis: {evidence_result['summary']}\n"
        if not evidence_summary:
            evidence_summary = "No file evidence available"

        classification_input = f"""Candidate learning: "{content}"
Category: {category}
Scope: {scope}
Evidence verdict: {evidence_result.get('verdict', 'UNVERIFIED')}
Evidence confidence: {evidence_result.get('confidence', base_confidence):.2f}

{evidence_summary}

Related existing learnings:
{existing_context if existing_context else "No similar existing learnings found"}
"""

        try:
            classify_response = await llm.create_message(
                model="fast",
                max_tokens=512,
                system=CLASSIFICATION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": classification_input}],
            )

            classification = _parse_json_response(classify_response.text_content)
            if classification and isinstance(classification, dict):
                action = classification.get("action", "create")
                final_content = classification.get("content", content)
                final_confidence = classification.get("confidence", base_confidence)
                is_verified = classification.get("verified", verified)
                evidence_text = classification.get("evidence", None)
                reason = classification.get("reason", None)

                # If action targets an existing learning, use the related_existing
                target_id = classification.get("target_existing_id")
                if target_id and not related_existing:
                    # Try to find it in search results
                    pass
                elif action in ("update", "delete") and not related_existing:
                    # Can't update/delete without a target - fallback to create
                    action = "create"

                # Build evidence detail from thorough search
                evidence_detail = EvidenceDetail(
                    verdict=evidence_result.get("verdict", "UNVERIFIED"),
                    supporting_evidence=evidence_result.get("supporting_evidence", [])[:5],
                    contradicting_evidence=evidence_result.get("contradicting_evidence", [])[:3],
                    files_searched=evidence_result.get("files_searched", 0),
                    summary=evidence_result.get("summary"),
                )

                proposals.append(SynthesizeProposal(
                    action=action,
                    content=final_content if action != "delete" else None,
                    category=category,
                    confidence=round(final_confidence, 2),
                    verified=is_verified,
                    scope=scope,
                    evidence=evidence_text,
                    evidence_detail=evidence_detail,
                    reason=reason if action == "delete" else None,
                    related_existing=related_existing if action in ("update", "delete") else None,
                ))
            else:
                # Fallback: create proposal without classification
                evidence_detail = EvidenceDetail(
                    verdict=evidence_result.get("verdict", "UNVERIFIED"),
                    supporting_evidence=evidence_result.get("supporting_evidence", [])[:5],
                    contradicting_evidence=evidence_result.get("contradicting_evidence", [])[:3],
                    files_searched=evidence_result.get("files_searched", 0),
                    summary=evidence_result.get("summary"),
                )
                proposals.append(SynthesizeProposal(
                    action="create",
                    content=content,
                    category=category,
                    confidence=round(base_confidence, 2),
                    verified=verified,
                    scope=scope,
                    evidence=evidence_result.get("summary"),
                    evidence_detail=evidence_detail,
                    related_existing=None,
                ))
        except Exception as e:
            logger.warning("Classification LLM call failed", error=str(e))
            # Still add as a create proposal
            evidence_detail = EvidenceDetail(
                verdict=evidence_result.get("verdict", "UNVERIFIED"),
                supporting_evidence=evidence_result.get("supporting_evidence", [])[:5],
                contradicting_evidence=evidence_result.get("contradicting_evidence", [])[:3],
                files_searched=evidence_result.get("files_searched", 0),
                summary=evidence_result.get("summary"),
            )
            proposals.append(SynthesizeProposal(
                action="create",
                content=content,
                category=category,
                confidence=round(base_confidence, 2),
                verified=verified,
                scope=scope,
                evidence=evidence_result.get("summary"),
                evidence_detail=evidence_detail,
                related_existing=None,
            ))

    await qdrant.disconnect()
    return SynthesizeResponse(
        proposals=proposals,
        answer=answer,
        mode=body.mode,
        files_analyzed=files_analyzed,
    )
