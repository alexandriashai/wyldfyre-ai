#!/usr/bin/env python3
"""
Script to clean up and categorize Qdrant memories.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models


QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
COLLECTION_NAME = "agent_learnings"

# IDs to delete (unhelpful error patterns, duplicate content)
IDS_TO_DELETE = [
    # Error patterns that are just "hit max iterations" - not useful learnings
    "0215d99a-3a34-4d29-82cf-5ba233143d70",  # ERROR: hit max iterations
    "03df7734-a172-4f0b-b885-a5bfa42503ea",  # ERROR: hit max iterations
    "5b3dfba2-86e3-4089-8da4-2e830295d42c",  # ERROR: hit max iterations
    "5f44066d-506a-4e2e-a55b-bab475ddc336",  # ERROR: hit max iterations
    "7b490ac4-4192-4028-9a58-3c7eb2c406fd",  # ERROR: hit max iterations
    "9bd7a5cd-a670-437a-9f56-63a4b0e18e42",  # ERROR: hit max iterations

    # Quality insights that are just "no file changes" - not useful
    "082dd1eb-7a96-4b28-a52c-7a0b500ad8ef",  # step completed without file changes
    "4aaa80d7-ab28-4db5-89d7-16e83799a01a",  # step completed without file changes
    "7cfd26d1-7926-4651-b44a-fcbf20ffbf51",  # step completed without file changes

    # Duplicate blackbook-reviews entries (keeping the more detailed ones)
    # These are duplicates with less info
    "6f397785-5537-482b-9fe4-659ec4e7156b",  # Architecture Pattern duplicate (less detailed)
    "9113c232-fb42-4d86-9fdb-f9ef951b4c5b",  # Tech Stack duplicate (incorrect - says Laravel when it's Slim)
    "930be393-3e56-4b4c-8eee-3dea57b256f5",  # Frontend Architecture duplicate (incorrect - says React SPA)
]

# Tag mappings based on category and content
CATEGORY_TAGS = {
    "blackbook-reviews": ["blackbook", "documentation", "architecture"],
    "technique": ["pattern", "implementation", "technique"],
    "file_pattern": ["files", "naming-convention"],
    "error_pattern": ["error", "debugging", "troubleshooting"],
    "quality_insight": ["quality", "review", "insight"],
    "plan_creation": ["planning", "workflow"],
    "plan_completion": ["planning", "completed"],
    "plan_execution": ["planning", "execution"],
    "project_paths": ["paths", "infrastructure"],
    "project-requirements": ["requirements", "specs"],
    "project_structure": ["structure", "organization"],
    "extracted": ["learned", "extracted"],
}

# Memories that need phase set to "learn"
MEMORIES_MISSING_PHASE = [
    "10b4ac84-5ac0-40ee-a5a8-afa47122d27f",
    "16aef8d3-daac-43b6-aef1-3a1a63f62312",
    "198d4b2e-0fb7-4d9c-b562-a2379d3293d0",
    "2ccf97b8-31a4-4216-a995-cbe09310ffdd",
    "3481997a-0368-459d-81f9-d709c7007583",
    "399720c7-9c44-4f10-a81a-69b0e897da86",
    "40106fde-5be0-4d51-b7b4-afc3b0fdc972",
    "4176f05d-b2a3-457f-9147-974612e74ab2",
    "5917ff5a-caaf-4c57-9927-bdfc04902bf8",
    "7077c42b-da9b-4b6e-a85f-759e11c3779d",
    "8ffe547c-13d0-4634-8e41-cde440bc4ffc",
    "9e2bc1ee-d8c0-406a-9ae2-e9d191abeb76",
    "b9cbbffd-5aa3-4e4d-a17f-7187d3153708",
    "ca822c1f-7720-4ee7-8500-465406c89d09",
    "cfd8e2f9-669d-46a4-8fed-bd4983d1d936",
    "d2451f73-ce41-472a-ab9e-f67a716fdd22",
    "d3703648-a0f7-453f-9e0d-72fe25b85ad9",
    "ea9bf501-79ae-4abb-9334-8cf095a21ced",
]


async def get_client():
    """Get connected Qdrant client."""
    return AsyncQdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_PORT,
        api_key=QDRANT_API_KEY if QDRANT_API_KEY else None,
        https=False,
    )


async def delete_memories(client, ids):
    """Delete memories by IDs."""
    if not ids:
        return 0

    print(f"\nDeleting {len(ids)} memories...")
    try:
        await client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.PointIdsList(points=ids),
        )
        print(f"  ✓ Deleted {len(ids)} memories")
        return len(ids)
    except Exception as e:
        print(f"  ✗ Delete failed: {e}")
        return 0


async def fix_missing_phases(client, ids):
    """Add phase=learn to memories missing it."""
    if not ids:
        return 0

    print(f"\nFixing phase for {len(ids)} memories...")
    fixed = 0
    for mem_id in ids:
        try:
            # Get current payload
            results = await client.retrieve(
                collection_name=COLLECTION_NAME,
                ids=[mem_id],
            )
            if not results:
                print(f"  - {mem_id}: not found")
                continue

            point = results[0]
            payload = point.payload or {}

            # Add phase if missing
            if not payload.get("phase"):
                payload["phase"] = "learn"
                payload["updated_at"] = datetime.now(timezone.utc).isoformat()

                await client.set_payload(
                    collection_name=COLLECTION_NAME,
                    payload=payload,
                    points=[mem_id],
                )
                print(f"  ✓ {mem_id}: phase set to 'learn'")
                fixed += 1
            else:
                print(f"  - {mem_id}: already has phase '{payload.get('phase')}'")
        except Exception as e:
            print(f"  ✗ {mem_id}: {e}")

    return fixed


async def add_tags_to_memories(client):
    """Add tags to memories that don't have them based on category."""
    print("\nAdding tags to memories without them...")

    # Get all memories
    all_mems = []
    offset = None
    while True:
        results, next_offset = await client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            offset=offset,
            with_payload=True,
        )
        all_mems.extend(results)
        if not next_offset:
            break
        offset = next_offset

    updated = 0
    for point in all_mems:
        payload = point.payload or {}
        existing_tags = payload.get("tags", [])

        # Skip if already has tags
        if existing_tags:
            continue

        category = payload.get("category", "")
        text = payload.get("text", "")

        # Build tags based on category
        new_tags = list(CATEGORY_TAGS.get(category, []))

        # Add content-based tags
        text_lower = text.lower()
        if "bootstrap" in text_lower:
            new_tags.append("bootstrap")
        if "css" in text_lower:
            new_tags.append("css")
        if "javascript" in text_lower or ".js" in text_lower:
            new_tags.append("javascript")
        if "html" in text_lower:
            new_tags.append("html")
        if "canvas" in text_lower:
            new_tags.append("canvas")
        if "particle" in text_lower:
            new_tags.append("animation")
        if "responsive" in text_lower:
            new_tags.append("responsive")
        if "trans" in text_lower and "pride" in text_lower:
            new_tags.append("trans-pride")
        if "ddd" in text_lower or "domain-driven" in text_lower:
            new_tags.append("ddd")
        if "php" in text_lower:
            new_tags.append("php")
        if "twig" in text_lower:
            new_tags.append("twig")
        if "typescript" in text_lower:
            new_tags.append("typescript")
        if "git" in text_lower:
            new_tags.append("git")
        if "test" in text_lower:
            new_tags.append("testing")

        # Dedupe
        new_tags = list(set(new_tags))

        if not new_tags:
            continue

        try:
            payload["tags"] = new_tags
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()

            await client.set_payload(
                collection_name=COLLECTION_NAME,
                payload=payload,
                points=[str(point.id)],
            )
            print(f"  ✓ {point.id}: added tags {new_tags}")
            updated += 1
        except Exception as e:
            print(f"  ✗ {point.id}: {e}")

    return updated


async def set_missing_agents(client):
    """Set agent_type for memories missing it."""
    print("\nSetting agent_type for memories missing it...")

    # Get all memories
    all_mems = []
    offset = None
    while True:
        results, next_offset = await client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            offset=offset,
            with_payload=True,
        )
        all_mems.extend(results)
        if not next_offset:
            break
        offset = next_offset

    updated = 0
    for point in all_mems:
        payload = point.payload or {}
        agent = payload.get("agent") or payload.get("agent_type")

        if agent and agent != "None" and agent != "NONE":
            continue

        # Determine agent based on content/category
        category = payload.get("category", "")
        text = payload.get("text", "")

        # Default to supervisor for most learnings
        new_agent = "supervisor"

        # Categorize based on content
        if "blackbook" in category:
            new_agent = "research"
        elif category in ("technique", "file_pattern"):
            new_agent = "code"
        elif "plan" in category:
            new_agent = "supervisor"
        elif "error" in category:
            new_agent = "supervisor"

        try:
            payload["agent_type"] = new_agent
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()

            await client.set_payload(
                collection_name=COLLECTION_NAME,
                payload=payload,
                points=[str(point.id)],
            )
            print(f"  ✓ {point.id}: agent_type set to '{new_agent}'")
            updated += 1
        except Exception as e:
            print(f"  ✗ {point.id}: {e}")

    return updated


async def main():
    print("=" * 60)
    print("QDRANT MEMORY CLEANUP")
    print("=" * 60)

    client = await get_client()

    try:
        # 1. Delete unhelpful memories
        deleted = await delete_memories(client, IDS_TO_DELETE)

        # 2. Fix missing phases
        fixed_phases = await fix_missing_phases(client, MEMORIES_MISSING_PHASE)

        # 3. Add tags to tagless memories
        tagged = await add_tags_to_memories(client)

        # 4. Set missing agents
        agents_set = await set_missing_agents(client)

        # Summary
        print("\n" + "=" * 60)
        print("CLEANUP SUMMARY")
        print("=" * 60)
        print(f"  Deleted:       {deleted}")
        print(f"  Phases fixed:  {fixed_phases}")
        print(f"  Tags added:    {tagged}")
        print(f"  Agents set:    {agents_set}")

        # Get final count
        info = await client.get_collection(COLLECTION_NAME)
        print(f"\n  Total memories remaining: {info.points_count}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
