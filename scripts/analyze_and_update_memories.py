#!/usr/bin/env python3
"""
Memory Analysis and Metadata Update Script

Analyzes existing learnings in Qdrant and updates them with proper metadata
according to the PAI memory schema (phases, categories, utility scores, scopes).
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from collections import defaultdict

# Add package paths
sys.path.insert(0, "/home/wyld-core/packages/core/src")
sys.path.insert(0, "/home/wyld-core/packages/memory/src")

from qdrant_client import QdrantClient
from qdrant_client.http import models

# Configuration
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "EAp2zFPe2DFAWghiWxZZXXB2TkiY5Rm5")
COLLECTION_NAME = "agent_learnings"

# PAI Schema Constants
VALID_PHASES = ["OBSERVE", "THINK", "PLAN", "BUILD", "EXECUTE", "VERIFY", "LEARN"]
VALID_CATEGORIES = [
    "code_pattern",
    "debugging",
    "architecture",
    "testing",
    "documentation",
    "performance",
    "security",
    "tooling",
    "process",
    "domain_knowledge",
    "error_handling",
    "integration",
    "configuration",
    "user_preference",
    "general",
]

# Map old category values to new standard categories
CATEGORY_MAPPING = {
    "error": "error_handling",
    "extracted": "general",
    "success": "process",
    "pattern": "code_pattern",
    "fix": "debugging",
    "bug": "debugging",
    "feature": "architecture",
    "improvement": "process",
    "optimization": "performance",
    "refactor": "architecture",
    "test": "testing",
    "doc": "documentation",
    "config": "configuration",
    "tool": "tooling",
    "api": "integration",
    "auth": "security",
    # Domain-specific mappings
    "blackbook-reviews": "domain_knowledge",
    "reviews": "domain_knowledge",
    "insight": "general",
    "strategy": "process",
    "workflow": "process",
    "best-practice": "code_pattern",
    "best_practice": "code_pattern",
}

# Map old scope values to new standard scopes
SCOPE_MAPPING = {
    "domain": "project",
}
VALID_SCOPES = ["task", "session", "project", "global"]
DEFAULT_UTILITY_SCORE = 0.5


def connect_to_qdrant() -> QdrantClient:
    """Connect to Qdrant with authentication."""
    print(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}...")
    # Use URL format to explicitly specify HTTP (not HTTPS)
    client = QdrantClient(
        url=f"http://{QDRANT_HOST}:{QDRANT_PORT}",
        api_key=QDRANT_API_KEY,
        prefer_grpc=False,
    )
    # Test connection
    collections = client.get_collections()
    print(f"Connected successfully. Found {len(collections.collections)} collections.")
    return client


def get_all_learnings(client: QdrantClient, collection: str, batch_size: int = 100) -> list[dict]:
    """Retrieve all learnings from the collection."""
    print(f"\nRetrieving learnings from '{collection}'...")

    # Check if collection exists
    collections = [c.name for c in client.get_collections().collections]
    if collection not in collections:
        print(f"Collection '{collection}' not found. Available: {collections}")
        return []

    # Get collection info
    info = client.get_collection(collection)
    total_points = info.points_count
    print(f"Collection has {total_points} points")

    if total_points == 0:
        return []

    # Scroll through all points
    all_learnings = []
    offset = None

    while True:
        results = client.scroll(
            collection_name=collection,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        points, next_offset = results

        for point in points:
            learning = {
                "id": point.id,
                "payload": point.payload or {},
            }
            all_learnings.append(learning)

        if next_offset is None:
            break
        offset = next_offset

    print(f"Retrieved {len(all_learnings)} learnings")
    return all_learnings


def analyze_metadata(learnings: list[dict]) -> dict[str, Any]:
    """Analyze metadata distribution across learnings."""
    print("\n" + "=" * 60)
    print("METADATA ANALYSIS")
    print("=" * 60)

    analysis = {
        "total_learnings": len(learnings),
        "phases": defaultdict(int),
        "categories": defaultdict(int),
        "scopes": defaultdict(int),
        "utility_score_ranges": {
            "0.0-0.2": 0,
            "0.2-0.4": 0,
            "0.4-0.6": 0,
            "0.6-0.8": 0,
            "0.8-1.0": 0,
        },
        "missing_fields": {
            "phase": [],
            "category": [],
            "scope": [],
            "utility_score": [],
            "created_at": [],
            "content": [],
        },
        "invalid_values": {
            "phase": [],
            "category": [],
            "scope": [],
        },
        "has_embeddings": 0,
        "fields_present": defaultdict(int),
    }

    for learning in learnings:
        payload = learning["payload"]
        lid = learning["id"]

        # Count all fields present
        for field in payload.keys():
            analysis["fields_present"][field] += 1

        # Check phase (normalize case)
        phase = payload.get("phase")
        if not phase:
            analysis["missing_fields"]["phase"].append(lid)
        else:
            # Try uppercase normalization
            phase_upper = phase.upper()
            if phase_upper in VALID_PHASES:
                analysis["phases"][phase_upper] += 1
                if phase != phase_upper:
                    # Mark for normalization
                    analysis["invalid_values"]["phase"].append((lid, phase))
            else:
                analysis["invalid_values"]["phase"].append((lid, phase))

        # Check category (with mapping)
        category = payload.get("category")
        if not category:
            analysis["missing_fields"]["category"].append(lid)
        elif category in VALID_CATEGORIES:
            analysis["categories"][category] += 1
        elif category in CATEGORY_MAPPING:
            # Can be mapped
            mapped = CATEGORY_MAPPING[category]
            analysis["categories"][mapped] += 1
            analysis["invalid_values"]["category"].append((lid, category))
        else:
            analysis["invalid_values"]["category"].append((lid, category))

        # Check scope (with mapping)
        scope = payload.get("scope")
        if not scope:
            analysis["missing_fields"]["scope"].append(lid)
        elif scope in VALID_SCOPES:
            analysis["scopes"][scope] += 1
        elif scope in SCOPE_MAPPING:
            # Can be mapped
            mapped = SCOPE_MAPPING[scope]
            analysis["scopes"][mapped] += 1
            analysis["invalid_values"]["scope"].append((lid, scope))
        else:
            analysis["invalid_values"]["scope"].append((lid, scope))

        # Check utility_score
        utility = payload.get("utility_score")
        if utility is None:
            analysis["missing_fields"]["utility_score"].append(lid)
        else:
            try:
                u = float(utility)
                if u < 0.2:
                    analysis["utility_score_ranges"]["0.0-0.2"] += 1
                elif u < 0.4:
                    analysis["utility_score_ranges"]["0.2-0.4"] += 1
                elif u < 0.6:
                    analysis["utility_score_ranges"]["0.4-0.6"] += 1
                elif u < 0.8:
                    analysis["utility_score_ranges"]["0.6-0.8"] += 1
                else:
                    analysis["utility_score_ranges"]["0.8-1.0"] += 1
            except (TypeError, ValueError):
                analysis["missing_fields"]["utility_score"].append(lid)

        # Check created_at
        if not payload.get("created_at"):
            analysis["missing_fields"]["created_at"].append(lid)

        # Check content
        if not payload.get("content") and not payload.get("learning") and not payload.get("text"):
            analysis["missing_fields"]["content"].append(lid)

    # Print analysis
    print(f"\nTotal Learnings: {analysis['total_learnings']}")

    print("\n--- Phase Distribution ---")
    for phase in VALID_PHASES:
        count = analysis["phases"].get(phase, 0)
        pct = (count / len(learnings) * 100) if learnings else 0
        print(f"  {phase}: {count} ({pct:.1f}%)")

    print("\n--- Category Distribution ---")
    for cat, count in sorted(analysis["categories"].items(), key=lambda x: -x[1]):
        pct = (count / len(learnings) * 100) if learnings else 0
        print(f"  {cat}: {count} ({pct:.1f}%)")

    print("\n--- Scope Distribution ---")
    for scope in VALID_SCOPES:
        count = analysis["scopes"].get(scope, 0)
        pct = (count / len(learnings) * 100) if learnings else 0
        print(f"  {scope}: {count} ({pct:.1f}%)")

    print("\n--- Utility Score Distribution ---")
    for range_name, count in analysis["utility_score_ranges"].items():
        pct = (count / len(learnings) * 100) if learnings else 0
        print(f"  {range_name}: {count} ({pct:.1f}%)")

    print("\n--- Missing Fields ---")
    for field, ids in analysis["missing_fields"].items():
        print(f"  {field}: {len(ids)} learnings")

    print("\n--- Invalid Values ---")
    for field, items in analysis["invalid_values"].items():
        if items:
            print(f"  {field}: {len(items)} learnings with invalid values")
            for lid, val in items[:3]:
                print(f"    - ID {lid}: '{val}'")

    print("\n--- Fields Present ---")
    for field, count in sorted(analysis["fields_present"].items(), key=lambda x: -x[1]):
        pct = (count / len(learnings) * 100) if learnings else 0
        print(f"  {field}: {count} ({pct:.1f}%)")

    return analysis


def infer_phase_from_content(content: str) -> str:
    """Infer the phase from learning content."""
    content_lower = content.lower()

    # EXECUTE phase indicators
    execute_keywords = ["run", "execute", "command", "tool", "function call", "api call", "bash", "shell"]
    if any(kw in content_lower for kw in execute_keywords):
        return "EXECUTE"

    # VERIFY phase indicators
    verify_keywords = ["test", "verify", "check", "assert", "validate", "confirmed", "works", "passed"]
    if any(kw in content_lower for kw in verify_keywords):
        return "VERIFY"

    # BUILD phase indicators
    build_keywords = ["implement", "create", "build", "code", "write", "add", "function", "class", "method"]
    if any(kw in content_lower for kw in build_keywords):
        return "BUILD"

    # PLAN phase indicators
    plan_keywords = ["plan", "strategy", "approach", "design", "architecture", "structure"]
    if any(kw in content_lower for kw in plan_keywords):
        return "PLAN"

    # THINK phase indicators
    think_keywords = ["analyze", "consider", "think", "understand", "reason", "why", "because"]
    if any(kw in content_lower for kw in think_keywords):
        return "THINK"

    # OBSERVE phase indicators
    observe_keywords = ["observe", "notice", "see", "find", "discover", "read", "explore"]
    if any(kw in content_lower for kw in observe_keywords):
        return "OBSERVE"

    # Default to LEARN (it's a learning after all)
    return "LEARN"


def infer_category_from_content(content: str) -> str:
    """Infer the category from learning content."""
    content_lower = content.lower()

    # Code pattern indicators
    if any(kw in content_lower for kw in ["pattern", "syntax", "idiom", "convention", "style"]):
        return "code_pattern"

    # Debugging indicators
    if any(kw in content_lower for kw in ["error", "bug", "fix", "debug", "issue", "problem"]):
        return "debugging"

    # Architecture indicators
    if any(kw in content_lower for kw in ["architecture", "design", "structure", "module", "component", "system"]):
        return "architecture"

    # Testing indicators
    if any(kw in content_lower for kw in ["test", "unittest", "pytest", "assert", "mock"]):
        return "testing"

    # Documentation indicators
    if any(kw in content_lower for kw in ["document", "docstring", "readme", "comment", "explain"]):
        return "documentation"

    # Performance indicators
    if any(kw in content_lower for kw in ["performance", "optimize", "speed", "memory", "efficient", "cache"]):
        return "performance"

    # Security indicators
    if any(kw in content_lower for kw in ["security", "auth", "permission", "credential", "encrypt"]):
        return "security"

    # Tooling indicators
    if any(kw in content_lower for kw in ["tool", "cli", "command", "git", "docker", "npm"]):
        return "tooling"

    # Configuration indicators
    if any(kw in content_lower for kw in ["config", "setting", "environment", "yaml", "json", ".env"]):
        return "configuration"

    # Integration indicators
    if any(kw in content_lower for kw in ["api", "integrate", "connect", "service", "endpoint"]):
        return "integration"

    # Error handling indicators
    if any(kw in content_lower for kw in ["exception", "try", "catch", "raise", "handle"]):
        return "error_handling"

    # Process indicators
    if any(kw in content_lower for kw in ["workflow", "process", "pipeline", "step", "procedure"]):
        return "process"

    # Default
    return "general"


def infer_scope_from_payload(payload: dict) -> str:
    """Infer scope from payload metadata."""
    # If it has project_id, it's project-scoped
    if payload.get("project_id"):
        return "project"

    # If it has session_id but no project, it's session-scoped
    if payload.get("session_id"):
        return "session"

    # If it has task_id, it's task-scoped
    if payload.get("task_id"):
        return "task"

    # Default to global
    return "global"


def update_learning_metadata(
    client: QdrantClient,
    collection: str,
    learning: dict,
    dry_run: bool = True
) -> dict[str, Any]:
    """Update a single learning with normalized/inferred metadata."""
    lid = learning["id"]
    payload = learning["payload"]
    updates = {}

    # Get content field (could be named differently)
    content = payload.get("content") or payload.get("learning") or payload.get("text") or ""

    # Normalize phase to uppercase
    existing_phase = payload.get("phase")
    if existing_phase:
        phase_upper = existing_phase.upper()
        if phase_upper in VALID_PHASES:
            if existing_phase != phase_upper:
                updates["phase"] = phase_upper  # Normalize case
        else:
            # Invalid phase - infer from content
            updates["phase"] = infer_phase_from_content(content)
    else:
        # Missing phase - infer from content
        updates["phase"] = infer_phase_from_content(content)

    # Normalize/map category
    existing_category = payload.get("category")
    if existing_category:
        if existing_category in VALID_CATEGORIES:
            pass  # Already valid, no update needed
        elif existing_category in CATEGORY_MAPPING:
            updates["category"] = CATEGORY_MAPPING[existing_category]
        else:
            # Invalid category - infer from content
            updates["category"] = infer_category_from_content(content)
    else:
        # Missing category - infer from content
        updates["category"] = infer_category_from_content(content)

    # Validate/map scope
    existing_scope = payload.get("scope")
    if not existing_scope:
        updates["scope"] = infer_scope_from_payload(payload)
    elif existing_scope in VALID_SCOPES:
        pass  # Already valid
    elif existing_scope in SCOPE_MAPPING:
        updates["scope"] = SCOPE_MAPPING[existing_scope]
    else:
        updates["scope"] = infer_scope_from_payload(payload)

    # Set default utility score if missing
    # Start with 0.5 as baseline; the boost/decay system will adjust from there
    if payload.get("utility_score") is None:
        # Use confidence as a starting point if available
        confidence = payload.get("confidence")
        if confidence is not None:
            try:
                conf_val = float(confidence)
                # Map confidence (0-1) to utility starting point (0.4-0.7)
                updates["utility_score"] = 0.4 + (conf_val * 0.3)
            except (TypeError, ValueError):
                updates["utility_score"] = DEFAULT_UTILITY_SCORE
        else:
            updates["utility_score"] = DEFAULT_UTILITY_SCORE

    # Set created_at if missing
    if not payload.get("created_at"):
        updates["created_at"] = datetime.now(timezone.utc).isoformat()

    # Initialize boost/decay tracking
    if payload.get("boost_count") is None:
        updates["boost_count"] = 0
    if payload.get("decay_count") is None:
        updates["decay_count"] = 0
    if payload.get("usage_count") is None:
        updates["usage_count"] = 0

    # Add metadata_updated timestamp
    if updates:
        updates["metadata_updated_at"] = datetime.now(timezone.utc).isoformat()
        updates["metadata_version"] = "2.0"

    # Apply updates
    if updates and not dry_run:
        client.set_payload(
            collection_name=collection,
            payload=updates,
            points=[lid],
        )

    return updates


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Analyze and update PAI memory metadata")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Analyze only, don't update (default: True)")
    parser.add_argument("--update", action="store_true",
                        help="Actually update the metadata")
    parser.add_argument("--collection", default=COLLECTION_NAME,
                        help=f"Collection name (default: {COLLECTION_NAME})")
    args = parser.parse_args()

    dry_run = not args.update

    try:
        # Connect to Qdrant
        client = connect_to_qdrant()

        # Get all learnings
        learnings = get_all_learnings(client, args.collection)

        if not learnings:
            print("No learnings found. Exiting.")
            return

        # Analyze metadata
        analysis = analyze_metadata(learnings)

        # Calculate how many need updates
        needs_update = set()
        for field, ids in analysis["missing_fields"].items():
            if field != "content":  # Content is informational
                needs_update.update(ids)
        for field, items in analysis["invalid_values"].items():
            needs_update.update(lid for lid, _ in items)

        print(f"\n{'=' * 60}")
        print(f"LEARNINGS NEEDING METADATA UPDATE: {len(needs_update)}")
        print(f"{'=' * 60}")

        if not needs_update:
            print("All learnings have valid metadata. No updates needed.")
            return

        if dry_run:
            print("\n[DRY RUN MODE - No changes will be made]")
            print("Run with --update flag to apply changes.")
        else:
            print("\n[UPDATE MODE - Changes will be applied]")

        # Process updates
        updated_count = 0
        update_summary = defaultdict(int)

        for learning in learnings:
            if learning["id"] not in needs_update:
                continue

            updates = update_learning_metadata(client, args.collection, learning, dry_run)

            if updates:
                updated_count += 1
                for field in updates:
                    if field not in ("metadata_updated_at", "metadata_version"):
                        update_summary[field] += 1

                if updated_count <= 5:  # Show first 5 examples
                    print(f"\n  Learning {learning['id']}:")
                    content = learning["payload"].get("content") or learning["payload"].get("learning") or ""
                    print(f"    Content: {content[:80]}...")
                    for field, value in updates.items():
                        if field not in ("metadata_updated_at", "metadata_version"):
                            print(f"    + {field}: {value}")

        print(f"\n{'=' * 60}")
        print("UPDATE SUMMARY")
        print(f"{'=' * 60}")
        print(f"Total learnings updated: {updated_count}")
        print("\nFields updated:")
        for field, count in sorted(update_summary.items(), key=lambda x: -x[1]):
            print(f"  {field}: {count}")

        if dry_run:
            print("\n[DRY RUN COMPLETE - Run with --update to apply changes]")
        else:
            print("\n[UPDATES APPLIED SUCCESSFULLY]")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
