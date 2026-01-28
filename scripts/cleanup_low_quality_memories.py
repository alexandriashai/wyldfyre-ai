#!/usr/bin/env python3
"""
Clean up low-quality memories from the Qdrant database.

This script identifies and removes memories that don't meet our quality standards:
- Too short (< 20 chars)
- Low alpha ratio (< 40% alphabetic characters)
- Generic/noise patterns
- Low utility with no access
"""

import asyncio
import re
from datetime import datetime, timezone

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

# Quality thresholds
MIN_CONTENT_LENGTH = 20
MIN_ALPHA_RATIO = 0.4
MIN_WORDS = 4

# Blocklist patterns for noise
BLOCKLIST_PATTERNS = [
    r"(?i)^(ok|okay|done|yes|no|sure|thanks|thank you|got it)[\.\s]*$",
    r"(?i)^(running|executing|processing|loading|starting|checking)\.{0,3}$",
    r"(?i)^(all \d+ tools? executed successfully)$",
    r"(?i)^(task completed?|completed successfully)[\.\s]*$",
    r"(?i)^(success|failed|error)[\.\s]*$",
    r"(?i)^[\d\.\s]+$",
    r"(?i)^[a-z_]+\s*=\s*[a-z0-9_]+$",
    r"(?i)console\.(log|error|warn|info)",
    r"(?i)^(null|undefined|none|true|false)$",
    r"(?i)^file (not found|exists|created|deleted|updated)$",
    r"(?i)^\[.*\]\s*$",
    r"(?i)^https?://",
    r"(?i)^/[^\s]+$",
]

def is_low_quality(text: str, metadata: dict) -> tuple[bool, str]:
    """
    Check if a memory is low quality.

    Returns (is_low_quality, reason)
    """
    if not text:
        return True, "empty content"

    text = text.strip()

    # Length check
    if len(text) < MIN_CONTENT_LENGTH:
        return True, f"too short ({len(text)} chars)"

    # Word count check
    words = text.split()
    if len(words) < MIN_WORDS:
        return True, f"too few words ({len(words)})"

    # Alpha ratio check
    alpha_count = sum(1 for c in text if c.isalpha())
    alpha_ratio = alpha_count / len(text)
    if alpha_ratio < MIN_ALPHA_RATIO:
        return True, f"low alpha ratio ({alpha_ratio:.2f})"

    # Blocklist check
    for pattern in BLOCKLIST_PATTERNS:
        if re.match(pattern, text):
            return True, f"matches blocklist pattern"

    # Check for generic success messages
    if re.match(r"(?i)^(all \d+ tools? executed|completed|success)", text):
        return True, "generic success message"

    # Low utility with no access (stale low-value)
    utility = metadata.get("utility_score", 0.5)
    access_count = metadata.get("access_count", 0)
    if utility < 0.3 and access_count == 0:
        return True, f"low utility ({utility:.2f}) with no access"

    return False, ""

async def cleanup_memories():
    """Main cleanup function."""
    print("=" * 60)
    print("PAI Memory Quality Cleanup")
    print("=" * 60)
    print()

    # Connect to Qdrant with API key (no HTTPS for local)
    import os
    from dotenv import load_dotenv
    load_dotenv("/home/wyld-core/.env")

    api_key = os.getenv("QDRANT_API_KEY")
    client = QdrantClient(
        host="localhost",
        port=6333,
        api_key=api_key,
        https=False,
    )
    collection_name = "agent_learnings"

    # Check if collection exists
    try:
        collection_info = client.get_collection(collection_name)
        total_points = collection_info.points_count
        print(f"Collection: {collection_name}")
        print(f"Total memories: {total_points}")
        print()
    except Exception as e:
        print(f"Error accessing collection: {e}")
        return

    # Scroll through all points
    low_quality_ids = []
    low_quality_reasons = {}

    offset = None
    batch_size = 100
    scanned = 0

    print("Scanning memories for quality issues...")
    print()

    while True:
        results = client.scroll(
            collection_name=collection_name,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        points, offset = results

        if not points:
            break

        for point in points:
            scanned += 1
            payload = point.payload or {}
            text = payload.get("text", "")

            is_low, reason = is_low_quality(text, payload)

            if is_low:
                low_quality_ids.append(point.id)
                low_quality_reasons[point.id] = {
                    "reason": reason,
                    "text": text[:100] + "..." if len(text) > 100 else text,
                    "category": payload.get("category", "unknown"),
                }

        if offset is None:
            break

    print(f"Scanned: {scanned} memories")
    print(f"Low quality: {len(low_quality_ids)} memories")
    print()

    if not low_quality_ids:
        print("No low-quality memories found. Database is clean!")
        return

    # Group by reason
    reason_counts = {}
    for info in low_quality_reasons.values():
        reason = info["reason"]
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    print("Breakdown by reason:")
    for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
        print(f"  - {reason}: {count}")
    print()

    # Show some examples
    print("Examples of low-quality memories:")
    for i, (point_id, info) in enumerate(list(low_quality_reasons.items())[:10]):
        print(f"  [{info['reason']}] ({info['category']}) {info['text']}")
    print()

    # Delete low-quality memories
    print(f"Deleting {len(low_quality_ids)} low-quality memories...")

    # Delete in batches
    batch_size = 100
    deleted = 0

    for i in range(0, len(low_quality_ids), batch_size):
        batch = low_quality_ids[i:i + batch_size]
        try:
            client.delete(
                collection_name=collection_name,
                points_selector=batch,
            )
            deleted += len(batch)
            print(f"  Deleted batch: {deleted}/{len(low_quality_ids)}")
        except Exception as e:
            print(f"  Error deleting batch: {e}")

    print()
    print(f"Cleanup complete!")
    print(f"  - Deleted: {deleted} low-quality memories")
    print(f"  - Remaining: {total_points - deleted} memories")
    print()

    # Verify
    try:
        collection_info = client.get_collection(collection_name)
        print(f"Verified remaining memories: {collection_info.points_count}")
    except Exception as e:
        print(f"Error verifying: {e}")

if __name__ == "__main__":
    asyncio.run(cleanup_memories())
