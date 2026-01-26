#!/usr/bin/env python3
"""
Migrate learnings from pai_learnings to agent_learnings collection.

This script:
1. Reads all points from pai_learnings
2. Checks for duplicates in agent_learnings (by content hash)
3. Inserts non-duplicate points into agent_learnings
4. Optionally deletes the pai_learnings collection
"""

import asyncio
import hashlib
import os
import sys
from typing import Any

# Add package paths
sys.path.insert(0, "/home/wyld-core/packages/core/src")
sys.path.insert(0, "/home/wyld-core/packages/memory/src")

from qdrant_client import QdrantClient
from qdrant_client.http import models

# Configuration
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "EAp2zFPe2DFAWghiWxZZXXB2TkiY5Rm5")

SOURCE_COLLECTION = "pai_learnings"
TARGET_COLLECTION = "agent_learnings"


def connect_to_qdrant() -> QdrantClient:
    """Connect to Qdrant."""
    print(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}...")
    client = QdrantClient(
        url=f"http://{QDRANT_HOST}:{QDRANT_PORT}",
        api_key=QDRANT_API_KEY,
        prefer_grpc=False,
    )
    collections = client.get_collections()
    print(f"Connected. Found {len(collections.collections)} collections.")
    return client


def get_content_hash(payload: dict) -> str:
    """Get hash of content for deduplication."""
    content = payload.get("text") or payload.get("content") or payload.get("learning") or ""
    return hashlib.md5(content.encode()).hexdigest()


def get_all_points(client: QdrantClient, collection: str) -> list[dict]:
    """Get all points from a collection."""
    all_points = []
    offset = None

    while True:
        results = client.scroll(
            collection_name=collection,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=True,  # Need vectors for migration
        )

        points, next_offset = results

        for point in points:
            all_points.append({
                "id": point.id,
                "payload": point.payload or {},
                "vector": point.vector,
            })

        if next_offset is None:
            break
        offset = next_offset

    return all_points


def migrate_points(
    client: QdrantClient,
    source_points: list[dict],
    target_hashes: set[str],
) -> tuple[int, int]:
    """Migrate points to target collection, skipping duplicates."""
    migrated = 0
    skipped = 0

    points_to_insert = []

    for point in source_points:
        content_hash = get_content_hash(point["payload"])

        if content_hash in target_hashes:
            skipped += 1
            continue

        # Prepare point for insertion
        points_to_insert.append(models.PointStruct(
            id=point["id"],
            payload=point["payload"],
            vector=point["vector"],
        ))
        target_hashes.add(content_hash)
        migrated += 1

    # Batch insert
    if points_to_insert:
        batch_size = 50
        for i in range(0, len(points_to_insert), batch_size):
            batch = points_to_insert[i:i + batch_size]
            client.upsert(
                collection_name=TARGET_COLLECTION,
                points=batch,
            )
            print(f"  Inserted batch {i // batch_size + 1} ({len(batch)} points)")

    return migrated, skipped


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Migrate pai_learnings to agent_learnings")
    parser.add_argument("--delete-source", action="store_true",
                        help="Delete pai_learnings collection after migration")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be migrated without doing it")
    args = parser.parse_args()

    try:
        client = connect_to_qdrant()

        # Check collections exist
        collections = [c.name for c in client.get_collections().collections]

        if SOURCE_COLLECTION not in collections:
            print(f"Source collection '{SOURCE_COLLECTION}' not found. Nothing to migrate.")
            return

        if TARGET_COLLECTION not in collections:
            print(f"Target collection '{TARGET_COLLECTION}' not found!")
            return

        # Get source points
        print(f"\nReading from '{SOURCE_COLLECTION}'...")
        source_points = get_all_points(client, SOURCE_COLLECTION)
        print(f"Found {len(source_points)} points in source collection")

        # Get target hashes for deduplication
        print(f"\nReading from '{TARGET_COLLECTION}' for deduplication...")
        target_points = get_all_points(client, TARGET_COLLECTION)
        target_hashes = {get_content_hash(p["payload"]) for p in target_points}
        print(f"Found {len(target_points)} existing points in target collection")

        # Calculate what would be migrated
        to_migrate = []
        to_skip = []
        for point in source_points:
            content_hash = get_content_hash(point["payload"])
            if content_hash in target_hashes:
                to_skip.append(point)
            else:
                to_migrate.append(point)

        print(f"\n{'=' * 60}")
        print("MIGRATION SUMMARY")
        print(f"{'=' * 60}")
        print(f"Points to migrate: {len(to_migrate)}")
        print(f"Duplicates to skip: {len(to_skip)}")

        if args.dry_run:
            print("\n[DRY RUN - No changes made]")
            if to_migrate:
                print("\nSample points to migrate:")
                for p in to_migrate[:3]:
                    content = p["payload"].get("text", "")[:60]
                    print(f"  - {p['id']}: {content}...")
            return

        if not to_migrate:
            print("\nNo new points to migrate.")
        else:
            # Perform migration
            print(f"\nMigrating {len(to_migrate)} points...")
            migrated, skipped = migrate_points(client, source_points, target_hashes)
            print(f"\nMigration complete: {migrated} migrated, {skipped} skipped")

        # Verify target count
        target_info = client.get_collection(TARGET_COLLECTION)
        print(f"\nTarget collection now has {target_info.points_count} points")

        # Optionally delete source
        if args.delete_source:
            print(f"\nDeleting source collection '{SOURCE_COLLECTION}'...")
            client.delete_collection(SOURCE_COLLECTION)
            print("Source collection deleted.")
        else:
            print(f"\nSource collection '{SOURCE_COLLECTION}' preserved.")
            print("Run with --delete-source to remove it.")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
