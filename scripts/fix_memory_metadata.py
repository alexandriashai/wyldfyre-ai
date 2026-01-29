#!/usr/bin/env python3
"""
Fix metadata issues in WARM tier memories.
- Normalize phase names to lowercase
- Populate missing agent_type based on content analysis
"""

import json
import re
from datetime import datetime
from collections import defaultdict
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Qdrant connection
QDRANT_URL = "http://localhost:6333"
QDRANT_API_KEY = "EAp2zFPe2DFAWghiWxZZXXB2TkiY5Rm5"
COLLECTION_NAME = "agent_learnings"

# Phase normalization map
PHASE_MAP = {
    "LEARN": "learn",
    "PLAN": "plan",
    "EXECUTE": "execute",
    "VERIFY": "verify",
    "BUILD": "build",
    "OBSERVE": "observe",
    "THINK": "think",
}

# Agent inference rules based on category/content
def infer_agent(payload: dict) -> str:
    """Infer agent type from payload content."""
    text = payload.get("text", "").lower()
    category = payload.get("category", "").lower()
    tags = [t.lower() for t in payload.get("tags", [])]
    created_by = payload.get("created_by_agent", "")

    # If created_by_agent is set, use it
    if created_by and created_by != "unknown":
        return created_by

    # Infrastructure related
    if any(kw in text for kw in ["docker", "nginx", "redis", "qdrant", "deploy", "server", "systemd", "service"]):
        return "infra"
    if category in ["infrastructure", "devops", "deployment", "nginx"]:
        return "infra"
    if "infra" in tags:
        return "infra"

    # Code related
    if any(kw in text for kw in ["function", "class", "method", "variable", "import", "async", "await"]):
        return "code"
    if category in ["code_pattern", "file_pattern", "debugging", "error_handling", "error_pattern"]:
        return "code"

    # Research/architecture
    if category in ["domain_knowledge", "architecture", "pattern"]:
        return "research"

    # Testing
    if category in ["testing", "test"]:
        return "code"

    # Plan related
    if category in ["plan_creation", "plan_completion", "plan_extracted"]:
        return "supervisor"

    # Execution related
    if category in ["execution_success", "execution_outcome", "execution_warning"]:
        return "supervisor"

    # General technique/gotcha
    if category in ["technique", "gotcha", "preference"]:
        return "supervisor"

    # Quality/performance
    if category in ["quality_insight", "performance"]:
        return "research"

    # Default to supervisor for learnings
    return "supervisor"


def main():
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

    # Fetch all points
    all_points = []
    offset = None

    print("Fetching all memories from Qdrant...")
    while True:
        result = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )
        points, offset = result
        all_points.extend(points)
        print(f"  Fetched {len(all_points)} points...", end='\r')
        if offset is None:
            break

    print(f"\nTotal memories: {len(all_points)}")
    print("=" * 80)

    # Track changes
    changes = {
        "phase_normalized": 0,
        "agent_added": 0,
        "scope_added": 0,
    }
    updates = []

    for point in all_points:
        payload = dict(point.payload)
        point_id = str(point.id)
        updated = False
        update_payload = {}

        # Normalize phase
        phase = payload.get("phase", "")
        if phase in PHASE_MAP:
            update_payload["phase"] = PHASE_MAP[phase]
            changes["phase_normalized"] += 1
            updated = True

        # Add missing agent_type
        agent = payload.get("agent_type") or payload.get("agent")
        if not agent or agent == "unknown" or agent == "None":
            inferred = infer_agent(payload)
            update_payload["agent_type"] = inferred
            changes["agent_added"] += 1
            updated = True

        # Add missing scope
        if not payload.get("scope"):
            update_payload["scope"] = "global"
            changes["scope_added"] += 1
            updated = True

        if updated:
            updates.append({
                "id": point_id,
                "payload": update_payload
            })

    print(f"\n📊 CHANGES TO MAKE")
    print("=" * 80)
    print(f"  Phase normalized: {changes['phase_normalized']}")
    print(f"  Agent type added: {changes['agent_added']}")
    print(f"  Scope added: {changes['scope_added']}")
    print(f"  Total records to update: {len(updates)}")

    if not updates:
        print("\n✅ No updates needed!")
        return

    # Apply updates
    print(f"\n🔧 Applying {len(updates)} updates...")

    # Batch updates
    batch_size = 50
    for i in range(0, len(updates), batch_size):
        batch = updates[i:i+batch_size]

        for update in batch:
            # Use set_payload to update specific fields
            client.set_payload(
                collection_name=COLLECTION_NAME,
                payload=update["payload"],
                points=[update["id"]]
            )

        print(f"  Updated {min(i + batch_size, len(updates))}/{len(updates)}", end='\r')

    print(f"\n\n✅ Successfully updated {len(updates)} memories!")

    # Verify
    print("\n📊 POST-UPDATE VERIFICATION")
    print("=" * 80)

    # Re-fetch and verify
    all_points = []
    offset = None
    while True:
        result = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )
        points, offset = result
        all_points.extend(points)
        if offset is None:
            break

    # Check for remaining issues
    issues_remaining = {
        "uppercase_phase": 0,
        "missing_agent": 0,
        "missing_scope": 0,
    }

    for point in all_points:
        payload = point.payload
        phase = payload.get("phase", "")
        if phase and phase.isupper():
            issues_remaining["uppercase_phase"] += 1
        if not payload.get("agent_type") and not payload.get("agent"):
            issues_remaining["missing_agent"] += 1
        if not payload.get("scope"):
            issues_remaining["missing_scope"] += 1

    print(f"  Total memories: {len(all_points)}")
    print(f"  Uppercase phases remaining: {issues_remaining['uppercase_phase']}")
    print(f"  Missing agent remaining: {issues_remaining['missing_agent']}")
    print(f"  Missing scope remaining: {issues_remaining['missing_scope']}")


if __name__ == "__main__":
    main()
