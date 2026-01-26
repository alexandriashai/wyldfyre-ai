#!/usr/bin/env python3
"""
Script to analyze and clean up Qdrant memories.
"""

import asyncio
import json
import os
import sys
from datetime import datetime

# Add packages to path
sys.path.insert(0, "/home/wyld-core/packages/memory/src")
sys.path.insert(0, "/home/wyld-core/packages/core/src")

from qdrant_client import AsyncQdrantClient


QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
COLLECTION_NAME = "agent_learnings"


async def get_all_memories():
    """Fetch all memories from Qdrant."""
    client = AsyncQdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_PORT,
        api_key=QDRANT_API_KEY if QDRANT_API_KEY else None,
        https=False,  # Use HTTP, not HTTPS
    )

    try:
        # Check if collection exists
        collections = await client.get_collections()
        collection_names = [c.name for c in collections.collections]
        print(f"Available collections: {collection_names}")

        if COLLECTION_NAME not in collection_names:
            print(f"Collection '{COLLECTION_NAME}' not found!")
            return []

        # Get collection info
        info = await client.get_collection(COLLECTION_NAME)
        print(f"\nCollection '{COLLECTION_NAME}' has {info.points_count} points")

        # Scroll through all documents
        all_docs = []
        offset = None

        while True:
            results, next_offset = await client.scroll(
                collection_name=COLLECTION_NAME,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            for point in results:
                doc = {
                    "id": str(point.id),
                    "text": point.payload.get("text", "") if point.payload else "",
                    "metadata": {k: v for k, v in (point.payload or {}).items() if k != "text"},
                }
                all_docs.append(doc)

            if not next_offset:
                break
            offset = next_offset

        return all_docs

    finally:
        await client.close()


def analyze_memories(memories):
    """Analyze memories and categorize them."""
    print(f"\n{'='*80}")
    print(f"MEMORY ANALYSIS - {len(memories)} total memories")
    print(f"{'='*80}\n")

    # Group by various attributes
    by_phase = {}
    by_category = {}
    by_agent = {}
    by_scope = {}
    missing_fields = []
    empty_content = []
    has_tags = []
    no_tags = []

    for mem in memories:
        meta = mem.get("metadata", {})
        text = mem.get("text", "")

        # Check for empty content
        if not text or len(text.strip()) < 10:
            empty_content.append(mem)

        # Check for missing critical fields
        missing = []
        if not meta.get("phase"):
            missing.append("phase")
        if not meta.get("category"):
            missing.append("category")
        if missing:
            missing_fields.append({"mem": mem, "missing": missing})

        # Group by phase
        phase = meta.get("phase", "UNKNOWN")
        by_phase.setdefault(phase, []).append(mem)

        # Group by category
        category = meta.get("category", "UNKNOWN")
        by_category.setdefault(category, []).append(mem)

        # Group by agent
        agent = meta.get("agent") or meta.get("agent_type") or "UNKNOWN"
        by_agent.setdefault(agent, []).append(mem)

        # Group by scope
        scope = meta.get("scope", "global")
        by_scope.setdefault(scope, []).append(mem)

        # Check tags
        tags = meta.get("tags", [])
        if tags:
            has_tags.append(mem)
        else:
            no_tags.append(mem)

    # Print summary
    print("BY PHASE:")
    for phase, mems in sorted(by_phase.items()):
        print(f"  {phase}: {len(mems)}")

    print("\nBY CATEGORY:")
    for cat, mems in sorted(by_category.items()):
        print(f"  {cat}: {len(mems)}")

    print("\nBY AGENT:")
    for agent, mems in sorted(by_agent.items()):
        print(f"  {agent}: {len(mems)}")

    print("\nBY SCOPE:")
    for scope, mems in sorted(by_scope.items()):
        print(f"  {scope}: {len(mems)}")

    print(f"\nTAGS:")
    print(f"  With tags: {len(has_tags)}")
    print(f"  Without tags: {len(no_tags)}")

    print(f"\nISSUES:")
    print(f"  Missing required fields: {len(missing_fields)}")
    print(f"  Empty/short content: {len(empty_content)}")

    return {
        "by_phase": by_phase,
        "by_category": by_category,
        "by_agent": by_agent,
        "by_scope": by_scope,
        "missing_fields": missing_fields,
        "empty_content": empty_content,
        "has_tags": has_tags,
        "no_tags": no_tags,
    }


def print_memories_detail(memories, limit=None):
    """Print detailed view of memories."""
    for i, mem in enumerate(memories[:limit] if limit else memories):
        print(f"\n{'─'*60}")
        print(f"ID: {mem['id']}")
        print(f"Text: {mem['text'][:200]}..." if len(mem['text']) > 200 else f"Text: {mem['text']}")
        meta = mem.get("metadata", {})
        print(f"Phase: {meta.get('phase', 'NONE')}")
        print(f"Category: {meta.get('category', 'NONE')}")
        print(f"Agent: {meta.get('agent') or meta.get('agent_type', 'NONE')}")
        print(f"Scope: {meta.get('scope', 'global')}")
        print(f"Tags: {meta.get('tags', [])}")
        print(f"Created: {meta.get('created_at', 'UNKNOWN')}")


async def main():
    print("Fetching memories from Qdrant...")
    memories = await get_all_memories()

    if not memories:
        print("No memories found!")
        return

    analysis = analyze_memories(memories)

    # Print details of problematic memories
    print(f"\n{'='*80}")
    print("MEMORIES WITH MISSING FIELDS:")
    print(f"{'='*80}")
    for item in analysis["missing_fields"][:20]:
        mem = item["mem"]
        missing = item["missing"]
        print(f"\n  ID: {mem['id']}")
        print(f"  Missing: {missing}")
        print(f"  Text: {mem['text'][:100]}...")

    print(f"\n{'='*80}")
    print("EMPTY/SHORT CONTENT:")
    print(f"{'='*80}")
    for mem in analysis["empty_content"][:10]:
        print(f"\n  ID: {mem['id']}")
        print(f"  Text: '{mem['text']}'")
        print(f"  Metadata: {mem['metadata']}")

    # Print all memories for review
    print(f"\n{'='*80}")
    print("ALL MEMORIES (first 50):")
    print(f"{'='*80}")
    print_memories_detail(memories, limit=50)

    # Output JSON for further processing
    output_file = "/tmp/qdrant_memories.json"
    with open(output_file, "w") as f:
        json.dump(memories, f, indent=2, default=str)
    print(f"\n\nFull data saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
