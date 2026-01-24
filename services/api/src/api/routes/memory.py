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
                    "category": r.get("metadata", {}).get("category"),
                    "outcome": r.get("metadata", {}).get("outcome", "success"),
                    "agent": r.get("metadata", {}).get("agent"),
                    "scope": r.get("metadata", {}).get("scope", "global"),
                    "project_id": r.get("metadata", {}).get("project_id"),
                    "domain_id": r.get("metadata", {}).get("domain_id"),
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


class SynthesizeRequest(BaseModel):
    """Request body for synthesize endpoint."""

    content: str
    project_id: str | None = None
    domain_id: str | None = None
    conversation_id: str | None = None
    verify: bool = True


class RelatedExisting(BaseModel):
    """Related existing learning."""

    id: str
    content: str
    similarity: float


class SynthesizeProposal(BaseModel):
    """A single synthesize proposal."""

    action: str  # create, update, delete
    content: str | None = None
    category: str | None = None
    confidence: float = 0.0
    verified: bool = False
    scope: str = "project"
    evidence: str | None = None
    reason: str | None = None
    related_existing: RelatedExisting | None = None


class SynthesizeResponse(BaseModel):
    """Response from synthesize endpoint."""

    proposals: list[SynthesizeProposal]


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
    Synthesize learnings from a message using AI.

    Pipeline:
    1. Gather context (conversation history, project root)
    2. Extract candidate learnings via LLM
    3. Verify candidates against codebase + classify against existing learnings
    """
    llm = LLMClient()
    proposals: list[SynthesizeProposal] = []

    # --- Step 1: Gather Context ---
    conversation_context = ""
    if body.conversation_id:
        conversation_context = await _get_conversation_context(redis, body.conversation_id)

    root_path: str | None = None
    if body.project_id:
        root_path = await _get_project_root(db, body.project_id)

    # Build extraction input
    extraction_input = ""
    if conversation_context:
        extraction_input += f"=== CONVERSATION CONTEXT ===\n{conversation_context}\n\n"
    extraction_input += f"=== TARGET MESSAGE (extract learnings from this) ===\n{body.content}"

    # --- Step 2: Extract Candidate Learnings ---
    try:
        extraction_response = await llm.create_message(
            model="fast",
            max_tokens=2048,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": extraction_input}],
        )
    except Exception as e:
        logger.error("LLM extraction failed", error=str(e))
        return SynthesizeResponse(proposals=[])

    candidates = _parse_json_response(extraction_response.text_content)
    if not candidates or not isinstance(candidates, list):
        return SynthesizeResponse(proposals=[])

    # --- Step 3: Verify + Classify each candidate ---
    qdrant = await get_qdrant_store()

    for candidate in candidates[:10]:  # Cap at 10 candidates
        content = candidate.get("content", "")
        category = candidate.get("category", "pattern")
        scope = candidate.get("scope", "project")
        base_confidence = candidate.get("confidence", 0.7)
        file_refs = candidate.get("file_references", [])

        # 3a. Codebase verification
        evidence_snippets: list[str] = []
        verified = False

        if body.verify and root_path:
            # Check referenced files
            for ref in file_refs[:3]:
                file_content = _safe_read_file(root_path, ref, max_chars=2000)
                if file_content:
                    evidence_snippets.append(f"[{ref}]:\n{file_content[:500]}")
                    verified = True
                    base_confidence = min(1.0, base_confidence + 0.1)

            # Smart search: extract key terms and grep
            if not verified:
                # Extract likely search terms from the learning
                words = content.split()
                search_terms = [w for w in words if len(w) > 4 and not w[0].islower() or "." in w][:3]
                for term in search_terms:
                    matched_files = _grep_project(root_path, term, max_results=3)
                    for mf in matched_files[:2]:
                        fc = _safe_read_file(root_path, mf, max_chars=1000)
                        if fc:
                            evidence_snippets.append(f"[{mf}]: contains '{term}'")
                            verified = True
                            base_confidence = min(1.0, base_confidence + 0.05)
                            break
                    if verified:
                        break

            if not verified and file_refs:
                # Referenced files don't exist - lower confidence
                base_confidence = max(0.3, base_confidence - 0.2)

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
        classification_input = f"""Candidate learning: "{content}"
Category: {category}
Scope: {scope}

File evidence:
{chr(10).join(evidence_snippets) if evidence_snippets else "No file evidence available"}

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

                proposals.append(SynthesizeProposal(
                    action=action,
                    content=final_content if action != "delete" else None,
                    category=category,
                    confidence=round(final_confidence, 2),
                    verified=is_verified,
                    scope=scope,
                    evidence=evidence_text,
                    reason=reason if action == "delete" else None,
                    related_existing=related_existing if action in ("update", "delete") else None,
                ))
            else:
                # Fallback: create proposal without classification
                proposals.append(SynthesizeProposal(
                    action="create",
                    content=content,
                    category=category,
                    confidence=round(base_confidence, 2),
                    verified=verified,
                    scope=scope,
                    evidence=evidence_snippets[0] if evidence_snippets else None,
                    related_existing=None,
                ))
        except Exception as e:
            logger.warning("Classification LLM call failed", error=str(e))
            # Still add as a create proposal
            proposals.append(SynthesizeProposal(
                action="create",
                content=content,
                category=category,
                confidence=round(base_confidence, 2),
                verified=verified,
                scope=scope,
                related_existing=None,
            ))

    await qdrant.disconnect()
    return SynthesizeResponse(proposals=proposals)
