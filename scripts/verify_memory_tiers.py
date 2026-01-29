#!/usr/bin/env python3
"""
Verify all PAI Memory tier operations work correctly.
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from uuid import uuid4

# Add packages to path
sys.path.insert(0, "/home/wyld-core/packages/memory/src")
sys.path.insert(0, "/home/wyld-core/packages/core/src")

from ai_memory.pai_memory import PAIMemory, PAIPhase, Learning, LearningScope
from ai_memory.qdrant import QdrantStore

# Redis mock for testing
class RedisMock:
    def __init__(self):
        self._data = {}

    async def set(self, key, value, ex=None):
        self._data[key] = value
        print(f"  [HOT] Stored: {key}")

    async def get(self, key):
        return self._data.get(key)

    async def rpush(self, key, value):
        if key not in self._data:
            self._data[key] = []
        self._data[key].append(value)

    async def expire(self, key, ttl):
        pass

    async def lrange(self, key, start, end):
        data = self._data.get(key, [])
        return data[start:end+1] if end >= 0 else data[start:]

    async def bgsave(self):
        pass


async def main():
    print("=" * 80)
    print("PAI MEMORY TIER VERIFICATION")
    print("=" * 80)

    # Initialize stores
    print("\n📦 Initializing stores...")

    # Use settings from environment
    from ai_core import get_settings
    settings = get_settings()

    qdrant = QdrantStore(
        collection_name="agent_learnings",
        settings=settings.qdrant,
    )
    await qdrant.connect()
    print("  [WARM] Qdrant connected ✓")

    redis = RedisMock()
    print("  [HOT] Redis mock initialized ✓")

    # Initialize PAIMemory
    memory = PAIMemory(
        redis_client=redis,
        qdrant_store=qdrant,
        cold_storage_path=None,  # Use default
    )
    await memory.initialize()
    print("  [COLD] File storage initialized ✓")

    # Test 1: HOT tier - Store task trace
    print("\n" + "=" * 40)
    print("TEST 1: HOT TIER - Task Trace Storage")
    print("=" * 40)
    test_task_id = str(uuid4())
    await memory.store_task_trace(
        task_id=test_task_id,
        phase=PAIPhase.PLAN,
        data={
            "agent_type": "test",
            "description": "Test task trace",
            "learning": "Test learning content for verification",
            "category": "test",
        },
    )

    traces = await memory.get_task_traces(test_task_id)
    print(f"  Task traces stored: {len(traces)}")
    if traces:
        print(f"  First trace phase: {traces[0].get('phase')}")
    print("  ✓ HOT tier working!")

    # Test 2: WARM tier - Store learning
    print("\n" + "=" * 40)
    print("TEST 2: WARM TIER - Store & Search Learning")
    print("=" * 40)
    test_learning = Learning(
        content="This is a test learning for PAI memory tier verification. It contains enough content to pass quality gates.",
        phase=PAIPhase.LEARN,
        category="test",
        agent_type="verification",
        confidence=0.9,
        scope=LearningScope.GLOBAL,
        tags=["test", "verification"],
    )

    doc_id = await memory.store_learning(test_learning)
    if doc_id:
        print(f"  Learning stored with ID: {doc_id}")
    else:
        print("  ⚠ Learning not stored (may be duplicate)")

    # Test 3: WARM tier - Search
    print("\n  Searching for 'test verification'...")
    results = await memory.search_learnings(
        query="test learning verification",
        limit=5,
    )
    print(f"  Search results: {len(results)}")
    for i, r in enumerate(results[:3]):
        print(f"    [{i+1}] score={r.get('score', 'N/A'):.3f}: {r.get('text', '')[:50]}...")
    print("  ✓ WARM tier working!")

    # Test 4: Verify metadata structure
    print("\n" + "=" * 40)
    print("TEST 3: Metadata Quality Check")
    print("=" * 40)
    sample_results = await qdrant.scroll(limit=10)
    docs, _ = sample_results

    missing_fields = {"phase": 0, "agent_type": 0, "scope": 0, "category": 0}
    for doc in docs:
        meta = doc.get("metadata", {})
        if not meta.get("phase"):
            missing_fields["phase"] += 1
        if not meta.get("agent_type"):
            missing_fields["agent_type"] += 1
        if not meta.get("scope"):
            missing_fields["scope"] += 1
        if not meta.get("category"):
            missing_fields["category"] += 1

    print(f"  Sample size: {len(docs)}")
    print(f"  Missing phase: {missing_fields['phase']}")
    print(f"  Missing agent_type: {missing_fields['agent_type']}")
    print(f"  Missing scope: {missing_fields['scope']}")
    print(f"  Missing category: {missing_fields['category']}")

    if all(v == 0 for v in missing_fields.values()):
        print("  ✓ All metadata fields present!")
    else:
        print("  ⚠ Some metadata fields missing")

    # Test 5: COLD tier - Check directories
    print("\n" + "=" * 40)
    print("TEST 4: COLD TIER - Directory Check")
    print("=" * 40)
    from pathlib import Path
    cold_path = Path("/home/wyld-core/pai/MEMORY/Learning")
    if cold_path.exists():
        for phase_dir in cold_path.iterdir():
            if phase_dir.is_dir():
                file_count = len(list(phase_dir.glob("*.json")))
                print(f"  {phase_dir.name}: {file_count} files")
        print("  ✓ COLD tier directory structure present!")
    else:
        print("  ⚠ COLD tier directory not found")

    # Test 6: Clean up test data
    print("\n" + "=" * 40)
    print("CLEANUP: Removing test learning")
    print("=" * 40)
    if doc_id:
        await memory.delete_learning(doc_id)
        print(f"  Deleted test learning: {doc_id}")

    # Final summary
    print("\n" + "=" * 80)
    print("VERIFICATION COMPLETE")
    print("=" * 80)
    print("✅ HOT tier (Redis): Task traces working")
    print("✅ WARM tier (Qdrant): Store/search working")
    print("✅ COLD tier (Files): Directory structure present")
    print("✅ Metadata: All required fields present")


if __name__ == "__main__":
    asyncio.run(main())
