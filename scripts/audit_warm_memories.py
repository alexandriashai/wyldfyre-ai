#!/usr/bin/env python3
"""
PAI Memory Audit Script
Audits all WARM tier memories for quality and metadata issues.
"""

import asyncio
import json
import re
import sys
from datetime import datetime
from collections import defaultdict
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Qdrant connection
QDRANT_URL = "http://localhost:6333"
QDRANT_API_KEY = "EAp2zFPe2DFAWghiWxZZXXB2TkiY5Rm5"
COLLECTION_NAME = "agent_learnings"

# Quality thresholds
MIN_CONTENT_LENGTH = 20
MIN_ALPHA_RATIO = 0.4

# Trivial patterns to detect noise
TRIVIAL_PATTERNS = [
    r'^ok$',
    r'^done$',
    r'^yes$',
    r'^no$',
    r'^completed?$',
    r'^started?$',
    r'^processing\.{0,3}$',
    r'^loading\.{0,3}$',
    r'^working\.{0,3}$',
    r'^thinking\.{0,3}$',
    r'^status:\s*(ok|done|complete)',
    r'^\s*$',
]

def alpha_ratio(text: str) -> float:
    """Calculate ratio of alphabetic characters."""
    if not text:
        return 0.0
    alpha_count = sum(1 for c in text if c.isalpha())
    return alpha_count / len(text)

def is_trivial(text: str) -> bool:
    """Check if content is trivial/noise."""
    text_lower = text.strip().lower()
    for pattern in TRIVIAL_PATTERNS:
        if re.match(pattern, text_lower):
            return True
    return False

def audit_memory(point_id: str, payload: dict) -> dict:
    """Audit a single memory and return issues."""
    issues = []
    text = payload.get("text", "")

    # Content quality checks
    if len(text) < MIN_CONTENT_LENGTH:
        issues.append("too_short")

    if alpha_ratio(text) < MIN_ALPHA_RATIO:
        issues.append("low_alpha")

    if is_trivial(text):
        issues.append("trivial")

    # Metadata checks
    if not payload.get("phase"):
        issues.append("missing_phase")

    if not payload.get("agent_type") and not payload.get("agent"):
        issues.append("missing_agent")

    if not payload.get("created_at"):
        issues.append("missing_created_at")

    if not payload.get("scope"):
        issues.append("missing_scope")

    # Category check
    if not payload.get("category"):
        issues.append("missing_category")

    return {
        "id": point_id,
        "text": text,
        "text_preview": text[:100] + "..." if len(text) > 100 else text,
        "issues": issues,
        "payload": payload,
        "should_delete": any(i in ["too_short", "low_alpha", "trivial"] for i in issues)
    }

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

    # Audit all memories
    audit_results = []
    issues_count = defaultdict(int)
    to_delete = []
    to_fix = []

    for point in all_points:
        result = audit_memory(str(point.id), point.payload)
        audit_results.append(result)

        for issue in result["issues"]:
            issues_count[issue] += 1

        if result["should_delete"]:
            to_delete.append(result)
        elif result["issues"]:
            to_fix.append(result)

    # Summary
    print("\n📊 AUDIT SUMMARY")
    print("=" * 80)
    print(f"Total memories: {len(all_points)}")
    print(f"Clean memories: {len(all_points) - len(to_delete) - len(to_fix)}")
    print(f"To delete: {len(to_delete)}")
    print(f"To fix: {len(to_fix)}")

    print("\n📋 ISSUE BREAKDOWN")
    print("-" * 40)
    for issue, count in sorted(issues_count.items(), key=lambda x: -x[1]):
        print(f"  {issue}: {count}")

    # Show memories to delete
    if to_delete:
        print("\n\n🗑️  MEMORIES TO DELETE")
        print("=" * 80)
        for i, result in enumerate(to_delete, 1):
            print(f"\n[{i}] ID: {result['id']}")
            print(f"    Issues: {result['issues']}")
            print(f"    Content: {result['text_preview']}")
            print(f"    Phase: {result['payload'].get('phase', 'N/A')}")
            print(f"    Category: {result['payload'].get('category', 'N/A')}")

    # Show memories to fix
    if to_fix:
        print("\n\n🔧 MEMORIES TO FIX")
        print("=" * 80)
        for i, result in enumerate(to_fix, 1):
            print(f"\n[{i}] ID: {result['id']}")
            print(f"    Issues: {result['issues']}")
            print(f"    Content: {result['text_preview']}")
            print(f"    Phase: {result['payload'].get('phase', 'N/A')}")
            print(f"    Category: {result['payload'].get('category', 'N/A')}")
            print(f"    Agent: {result['payload'].get('agent_type', result['payload'].get('agent', 'N/A'))}")

    # Stats by category
    print("\n\n📁 MEMORIES BY CATEGORY")
    print("=" * 80)
    by_category = defaultdict(int)
    for point in all_points:
        cat = point.payload.get("category", "unknown")
        by_category[cat] += 1
    for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    # Stats by phase
    print("\n\n🔄 MEMORIES BY PHASE")
    print("=" * 80)
    by_phase = defaultdict(int)
    for point in all_points:
        phase = point.payload.get("phase", "unknown")
        by_phase[phase] += 1
    for phase, count in sorted(by_phase.items(), key=lambda x: -x[1]):
        print(f"  {phase}: {count}")

    # Stats by agent
    print("\n\n🤖 MEMORIES BY AGENT")
    print("=" * 80)
    by_agent = defaultdict(int)
    for point in all_points:
        agent = point.payload.get("agent_type") or point.payload.get("agent") or "unknown"
        by_agent[agent] += 1
    for agent, count in sorted(by_agent.items(), key=lambda x: -x[1]):
        print(f"  {agent}: {count}")

    # Output IDs to delete as JSON for easy cleanup
    if to_delete:
        delete_ids = [r["id"] for r in to_delete]
        print("\n\n📝 DELETE IDS (for cleanup)")
        print("=" * 80)
        print(json.dumps(delete_ids, indent=2))

    # Save detailed report
    report = {
        "timestamp": datetime.now().isoformat(),
        "total": len(all_points),
        "clean": len(all_points) - len(to_delete) - len(to_fix),
        "to_delete_count": len(to_delete),
        "to_fix_count": len(to_fix),
        "issues": dict(issues_count),
        "by_category": dict(by_category),
        "by_phase": dict(by_phase),
        "by_agent": dict(by_agent),
        "to_delete": [{"id": r["id"], "issues": r["issues"], "text": r["text"][:200]} for r in to_delete],
        "to_fix": [{"id": r["id"], "issues": r["issues"], "text": r["text"][:200]} for r in to_fix]
    }

    with open("/home/wyld-core/scripts/memory_audit_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print("\n\n✅ Detailed report saved to: /home/wyld-core/scripts/memory_audit_report.json")

if __name__ == "__main__":
    main()
