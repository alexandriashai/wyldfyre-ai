# Multi-Agent AI Infrastructure - Architecture Plan

## Overview

A self-hosted, installable AI infrastructure enabling multiple autonomous Claude agents to collaborate, learn, and manage server resources. Integrates Daniel Miessler's PAI (Personal AI Infrastructure) for self-improvement capabilities.

## Cost Constraints

| Category | Service | Cost |
|----------|---------|------|
| **Paid** | Claude API/Account | Per-usage |
| **Paid** | OpenAI API (Embeddings, Whisper STT, TTS) | Per-usage |
| **Paid** | AWS Secrets Manager | Per-usage (minimal) |
| **Paid** | Cloudflare API (Pro/Business) | Account subscription |
| **Free** | GitHub (with PAT) | Free |
| **Free** | Everything else | $0 |

### External Service Integrations

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      EXTERNAL SERVICE INTEGRATIONS                          │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│   AWS SECRETS MGR   │  │    CLOUDFLARE API   │  │      GITHUB         │
│   ─────────────────  │  │   ─────────────────  │  │   ─────────────────  │
│                     │  │                     │  │                     │
│ • API keys storage  │  │ • DNS management    │  │ • Code backup       │
│ • DB credentials    │  │ • CDN caching       │  │ • Version control   │
│ • JWT secrets       │  │ • DDoS protection   │  │ • Config sync       │
│ • Rotation support  │  │ • SSL certificates  │  │ • Memory archival   │
│ • IAM integration   │  │ • Firewall rules    │  │ • Agent prompts     │
│                     │  │ • Analytics         │  │ • Collaboration     │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │   AI INFRASTRUCTURE       │
                    │   (Your Server)           │
                    └───────────────────────────┘
```

---

## Server Hardware Requirements

This infrastructure is designed to run on a dedicated server with the following specifications:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TARGET SERVER SPECIFICATIONS                         │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  HARDWARE                                                                    │
├──────────────┬───────────────────────────────────────────────────────────────┤
│  CPU         │  AMD EPYC 4344P (8 cores / 16 threads @ 3.8GHz base)          │
│  RAM         │  64 GB DDR5 ECC                                               │
│  Storage     │  2× Micron 7450 NVMe 960GB (RAID-1) - ~900GB usable           │
│  Network     │  1 Gbps dedicated                                             │
└──────────────┴───────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  OPERATING SYSTEM                                                            │
├──────────────┬───────────────────────────────────────────────────────────────┤
│  OS          │  Ubuntu 24.04.3 LTS (Noble Numbat)                            │
│  Kernel      │  6.8.0-88-generic                                             │
└──────────────┴───────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  PRE-INSTALLED SOFTWARE (Available on Host)                                  │
├──────────────┬───────────────────────────────────────────────────────────────┤
│  Nginx       │  1.28.0 (reverse proxy, TLS termination)                      │
│  Redis       │  7.0.15 (message bus, caching)                                │
│  Docker      │  29.1.4 (container orchestration)                             │
│  Python      │  3.12.3 (agent runtime)                                       │
│  Node.js     │  22.19.0 (web portal)                                         │
│  Bun         │  1.3.6 (fast JS runtime, optional)                            │
└──────────────┴───────────────────────────────────────────────────────────────┘
```

### Resource Allocation

With 64GB RAM and 8 cores, resources are allocated as follows:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          RESOURCE ALLOCATION                                 │
└─────────────────────────────────────────────────────────────────────────────┘

SERVICE                    CPU LIMIT    MEMORY LIMIT    MEMORY RESERVED
─────────────────────────────────────────────────────────────────────────────
Infrastructure Services:
├── PostgreSQL             2 cores      8 GB            4 GB
├── Qdrant (Vector DB)     2 cores      8 GB            4 GB
├── Redis (Host)           1 core       2 GB            1 GB
└── Nginx (Host)           0.5 core     512 MB          256 MB

Application Services:
├── FastAPI Backend        2 cores      4 GB            2 GB
├── Next.js Frontend       1 core       2 GB            1 GB
└── Voice Service          1 core       2 GB            1 GB

Agent Processes (tmux):
├── Supervisor Agent       1 core       4 GB            2 GB
├── Code Agent             1 core       4 GB            2 GB
├── Data Agent             1 core       4 GB            2 GB
├── Infra Agent            1 core       4 GB            2 GB
├── Research Agent         1 core       4 GB            2 GB
└── QA Agent               1 core       4 GB            2 GB

Monitoring & Observability:
├── Prometheus             0.5 core     1 GB            512 MB
├── Grafana                0.5 core     512 MB          256 MB
└── Loki (Logs)            0.5 core     1 GB            512 MB
─────────────────────────────────────────────────────────────────────────────
TOTAL RESERVED:            ~16 cores*   ~54 GB          ~26 GB

* CPU overcommit is acceptable; agents are I/O bound waiting on API responses
```

**Scaling Notes:**
- Agents are **I/O bound** (waiting on Claude API), not CPU bound
- Peak memory occurs during parallel agent execution (~40GB)
- 24GB headroom for OS, file cache, and burst operations
- NVMe RAID provides ~500K IOPS for database operations

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        MULTI-AGENT AI INFRASTRUCTURE                            │
│                         with PAI Integration                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

                                 INTERNET
                                     │
                     ┌───────────────┴───────────────┐
                     │     NGINX (TLS + Reverse      │
                     │        Proxy + Domains)       │
                     │   ┌─────────────────────┐     │
                     │   │ domain1.com → /www1 │     │
                     │   │ domain2.com → /www2 │     │
                     │   │ portal.ai   → :3000 │     │
                     │   └─────────────────────┘     │
                     └───────────────┬───────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
         ▼                           ▼                           ▼
┌─────────────────┐      ┌─────────────────────┐      ┌─────────────────┐
│   WEB PORTAL    │      │    API GATEWAY      │      │  VOICE SERVICE  │
│   (Next.js)     │      │    (FastAPI)        │      │  (Whisper+TTS)  │
│   Port: 3000    │      │    Port: 8000       │      │  Port: 8001     │
│   [MIT]         │      │    [MIT]            │      │  [OpenAI API]   │
└────────┬────────┘      └─────────┬───────────┘      └────────┬────────┘
         │                         │                           │
         └─────────────────────────┼───────────────────────────┘
                                   │
                     ┌─────────────▼─────────────┐
                     │      REDIS MESSAGE BUS    │
                     │   Pub/Sub + Streams       │
                     │   Port: 6379 [BSD]        │
                     └─────────────┬─────────────┘
                                   │
┌──────────────────────────────────┼──────────────────────────────────┐
│                    TMUX SESSION: ai-infrastructure                  │
│  ┌───────────────────────────────┴───────────────────────────────┐  │
│  │                                                               │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐             │  │
│  │  │ SUPERVISOR  │ │ CODE AGENT  │ │ DATA AGENT  │             │  │
│  │  │   Window 0  │ │  Window 1   │ │  Window 2   │             │  │
│  │  │  (Claude)   │ │  (Claude)   │ │  (Claude)   │  ...        │  │
│  │  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘             │  │
│  │         │               │               │                     │  │
│  │         └───────────────┼───────────────┘                     │  │
│  │                         │                                     │  │
│  │              PAI INTEGRATION LAYER                            │  │
│  │         ┌───────────────┼───────────────┐                     │  │
│  │         │   THE ALGORITHM (7-Phase)     │                     │  │
│  │         │ OBSERVE→THINK→PLAN→BUILD→     │                     │  │
│  │         │ EXECUTE→VERIFY→LEARN          │                     │  │
│  │         └───────────────────────────────┘                     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  SSH ACCESS: ssh root@server → tmux attach -t ai-infrastructure     │
└──────────────────────────────────────────────────────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────────┐
         │                         │                             │
         ▼                         ▼                             ▼
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│     QDRANT      │    │    POSTGRESQL       │    │    PAI MEMORY       │
│  Vector Store   │    │   Conversations     │    │   (File-based)      │
│  Port: 6333     │    │   Users, Tasks      │    │                     │
│  [Apache 2.0]   │    │   Port: 5432 [BSD]  │    │   MEMORY/           │
│                 │    │                     │    │   ├── Learning/     │
│  - Embeddings   │    │                     │    │   ├── Signals/      │
│  - RAG Memory   │    │                     │    │   └── Work/         │
│  - Knowledge    │    │                     │    │                     │
└─────────────────┘    └─────────────────────┘    └─────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                           SERVER MANAGEMENT LAYER                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  DOMAIN MANAGEMENT          WEB ROOTS              SERVICES                     │
│  ┌────────────────┐        ┌────────────────┐     ┌────────────────┐           │
│  │ /etc/nginx/    │        │ /var/www/      │     │ systemd units  │           │
│  │   sites-avail/ │        │   domain1/     │     │ docker         │           │
│  │   sites-enable/│        │   domain2/     │     │ certbot        │           │
│  │   ssl/         │        │   portal/      │     │ fail2ban       │           │
│  └────────────────┘        └────────────────┘     └────────────────┘           │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

                              EXTERNAL APIs (Paid)
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ┌─────────────────────┐              ┌─────────────────────┐                   │
│  │    ANTHROPIC        │              │      OPENAI         │                   │
│  │    Claude API       │              │  - Embeddings       │                   │
│  │    (All Agents)     │              │  - Whisper (STT)    │                   │
│  │                     │              │  - TTS              │                   │
│  └─────────────────────┘              └─────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack (All Free/Open Source except APIs)

### Core Infrastructure

| Component | Technology | License | Purpose |
|-----------|------------|---------|---------|
| Message Bus | Redis | BSD-3 | Pub/Sub, Streams, Caching |
| Vector DB | Qdrant | Apache 2.0 | Embeddings, RAG, Knowledge |
| Relational DB | PostgreSQL | PostgreSQL License | Users, Tasks, Conversations |
| Reverse Proxy | Nginx | BSD-2 | TLS, Domains, Load Balancing |
| SSL Certs | Let's Encrypt + Certbot | Free | TLS Certificates |
| Containers | Docker + Compose | Apache 2.0 | Isolation, Deployment |

### Application Layer

| Component | Technology | License | Purpose |
|-----------|------------|---------|---------|
| API Server | FastAPI | MIT | REST + WebSocket API |
| Frontend | Next.js 14 | MIT | Web Portal |
| UI Components | shadcn/ui + Tailwind | MIT | Component Library |
| Tmux Control | libtmux | MIT | Agent Process Management |
| Session Manager | tmuxp | MIT | Tmux Configuration |

### AI Services (Paid)

| Service | Provider | Purpose |
|---------|----------|---------|
| Agent LLM | Claude API | All agent intelligence |
| Embeddings | OpenAI text-embedding-3-small | Vector embeddings |
| Speech-to-Text | OpenAI Whisper | Voice transcription |
| Text-to-Speech | OpenAI TTS | Voice synthesis |

### PAI Integration

| Component | Source | Purpose |
|-----------|--------|---------|
| The Algorithm | PAI | 7-phase improvement cycle |
| Memory System | PAI | Hot/Warm/Cold learning |
| Hook System | PAI | Event-driven automation |
| TELOS Config | PAI | Goal/value alignment |

---

## Agent Architecture

### Agent Types & Responsibilities

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AGENT HIERARCHY                                   │
└─────────────────────────────────────────────────────────────────────────────┘

                        ┌─────────────────────┐
                        │   SUPERVISOR AGENT  │
                        │   ─────────────────  │
                        │   • Task routing    │
                        │   • Orchestration   │
                        │   • User interface  │
                        │   • Conflict res.   │
                        │   • PAI Algorithm   │
                        └──────────┬──────────┘
                                   │
        ┌──────────────┬───────────┼───────────┬──────────────┐
        │              │           │           │              │
        ▼              ▼           ▼           ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  CODE AGENT  │ │  DATA AGENT  │ │ INFRA AGENT  │ │RESEARCH AGENT│ │   QA AGENT   │
│  ──────────  │ │  ──────────  │ │  ──────────  │ │  ──────────  │ │  ──────────  │
│ • Git ops    │ │ • SQL/DB     │ │ • Docker     │ │ • Web search │ │ • Testing    │
│ • Coding     │ │ • Analysis   │ │ • Nginx      │ │ • Docs       │ │ • Review     │
│ • Refactor   │ │ • ETL        │ │ • Domains    │ │ • Synthesis  │ │ • Security   │
│ • Debug      │ │ • Backups    │ │ • SSL/TLS    │ │ • Learning   │ │ • Validation │
│              │ │              │ │ • Monitoring │ │              │ │              │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

### Agent Communication Protocol

```python
# Message Schema
{
    "id": "uuid",
    "timestamp": "ISO-8601",
    "source": "supervisor",
    "target": "code_agent",  # or "*" for broadcast
    "type": "task|result|handoff|query|heartbeat|learn",
    "priority": 1-10,
    "payload": {
        "task_id": "uuid",
        "action": "implement_feature",
        "context": {...},
        "memory_refs": ["qdrant_id_1", "qdrant_id_2"]
    },
    "pai": {
        "algorithm_phase": "EXECUTE",
        "verification_criteria": [...],
        "learning_signals": []
    }
}
```

### Inter-Agent Patterns

```
SEQUENTIAL:     Supervisor → Agent A → Agent B → Supervisor
PARALLEL:       Supervisor → [Agent A, Agent B, Agent C] → Supervisor
PEER CONSULT:   Agent A ←→ Agent B (direct query/response)
BROADCAST:      Agent A → Redis Pub/Sub → All Agents (knowledge share)
HANDOFF:        Agent A → Agent B (transfer ownership)
```

---

## PAI Integration

### The Algorithm (7-Phase Improvement Cycle)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         THE ALGORITHM                                       │
│                   (Continuous Improvement Engine)                           │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
    │ OBSERVE  │────▶│  THINK   │────▶│   PLAN   │────▶│  BUILD   │
    │          │     │          │     │          │     │          │
    │ Gather   │     │ Generate │     │ Select   │     │ Define   │
    │ context  │     │ options  │     │ approach │     │ criteria │
    └──────────┘     └──────────┘     └──────────┘     └────┬─────┘
                                                            │
    ┌───────────────────────────────────────────────────────┘
    │
    ▼
    ┌──────────┐     ┌──────────┐     ┌──────────┐
    │ EXECUTE  │────▶│  VERIFY  │────▶│  LEARN   │
    │          │     │          │     │          │
    │ Perform  │     │ Test vs  │     │ Extract  │───────┐
    │ work     │     │ criteria │     │ insights │       │
    └──────────┘     └──────────┘     └──────────┘       │
                           │                              │
                           │ FAIL                         │
                           ▼                              │
                    ┌──────────────┐                     │
                    │ Trace back   │                     │
                    │ to failing   │                     │
                    │ phase        │                     │
                    └──────────────┘                     │
                                                         │
    ┌────────────────────────────────────────────────────┘
    │
    ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                      MEMORY SYSTEM                                      │
    │  ┌─────────────┐  ┌─────────────────┐  ┌──────────────────────┐        │
    │  │    HOT      │  │      WARM       │  │        COLD          │        │
    │  │  (CAPTURE)  │  │   (SYNTHESIS)   │  │   (APPLICATION)      │        │
    │  │             │  │                 │  │                      │        │
    │  │ Real-time   │  │ Learnings by    │  │ Immutable archive    │        │
    │  │ task traces │  │ algorithm phase │  │ Historical reference │        │
    │  └─────────────┘  └─────────────────┘  └──────────────────────┘        │
    └─────────────────────────────────────────────────────────────────────────┘
```

### PAI Memory Structure

```
MEMORY/
├── Learning/
│   ├── OBSERVE/           # Context gathering improvements
│   ├── THINK/             # Solution generation patterns
│   ├── PLAN/              # Planning improvements
│   ├── BUILD/             # Criteria definition learnings
│   ├── EXECUTE/           # Execution optimizations
│   ├── VERIFY/            # Verification improvements
│   ├── LEARN/             # Meta-learnings
│   └── ALGORITHM/         # Algorithm self-improvements
│
├── Signals/
│   ├── ratings/           # Explicit user ratings
│   ├── sentiment/         # Implicit tone analysis
│   ├── behavioral/        # Loopbacks, retries, abandons
│   └── verification/      # Objective pass/fail
│
└── Work/
    ├── active/            # Current task contexts
    └── archive/           # Completed task records
```

### Memory Lifecycle & Retention

```python
# packages/memory/src/ai_memory/lifecycle.py
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

class MemoryTier(Enum):
    HOT = "hot"      # Real-time, in-memory + Redis
    WARM = "warm"    # Recent, in Qdrant with full vectors
    COLD = "cold"    # Archived, compressed, file-based

@dataclass
class MemoryConfig:
    """Memory lifecycle configuration."""

    # Tier transitions
    HOT_TO_WARM_THRESHOLD = timedelta(hours=24)
    WARM_TO_COLD_THRESHOLD = timedelta(days=30)

    # Size limits
    HOT_MAX_ITEMS = 1000           # Per agent
    WARM_MAX_ITEMS = 50000         # Total in Qdrant
    COLD_MAX_SIZE_GB = 100         # On disk

    # Embedding configuration
    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS = 1536
    BATCH_SIZE = 100               # For cost optimization

    # Similarity thresholds
    DUPLICATE_THRESHOLD = 0.95     # Skip if too similar
    RELEVANCE_THRESHOLD = 0.7      # Minimum for retrieval

    # Retention policies
    RETENTION = {
        "hot": {
            "max_age": timedelta(hours=24),
            "max_items": 1000,
            "eviction": "lru"      # Least recently used
        },
        "warm": {
            "max_age": timedelta(days=30),
            "max_items": 50000,
            "eviction": "score"    # Lowest utility score
        },
        "cold": {
            "max_age": timedelta(days=365),
            "max_size_gb": 100,
            "compression": True,
            "eviction": "fifo"     # First in, first out
        }
    }

class MemoryManager:
    """Manage memory across tiers with automatic promotion/demotion."""

    async def process_new_memory(self, content: str, metadata: dict) -> str:
        """Store new memory in HOT tier."""
        # Check for duplicates
        if await self._is_duplicate(content):
            return None

        # Store in Redis (HOT)
        memory_id = str(uuid.uuid4())
        await self.redis.hset(f"memory:hot:{memory_id}", mapping={
            "content": content,
            "metadata": json.dumps(metadata),
            "created_at": datetime.utcnow().isoformat(),
            "access_count": 0,
            "utility_score": 0.5
        })

        return memory_id

    async def promote_to_warm(self, memory_id: str):
        """Promote from HOT to WARM (Redis → Qdrant)."""
        hot_data = await self.redis.hgetall(f"memory:hot:{memory_id}")
        if not hot_data:
            return

        # Generate embedding
        embedding = await self.embedding_cache.get_embedding(hot_data["content"])

        # Store in Qdrant
        await self.qdrant.upsert(
            collection_name="memories",
            points=[{
                "id": memory_id,
                "vector": embedding,
                "payload": {
                    **json.loads(hot_data["metadata"]),
                    "content": hot_data["content"],
                    "tier": "warm",
                    "promoted_at": datetime.utcnow().isoformat(),
                    "utility_score": float(hot_data.get("utility_score", 0.5))
                }
            }]
        )

        # Remove from Redis
        await self.redis.delete(f"memory:hot:{memory_id}")

    async def demote_to_cold(self, memory_ids: list[str]):
        """Demote from WARM to COLD (Qdrant → File archive)."""
        # Fetch from Qdrant
        points = await self.qdrant.retrieve(
            collection_name="memories",
            ids=memory_ids,
            with_vectors=False  # Don't store vectors in cold
        )

        # Compress and archive
        archive_path = self._get_archive_path()
        async with aiofiles.open(archive_path, 'a') as f:
            for point in points:
                await f.write(json.dumps({
                    "id": point.id,
                    "payload": point.payload,
                    "archived_at": datetime.utcnow().isoformat()
                }) + "\n")

        # Remove from Qdrant
        await self.qdrant.delete(
            collection_name="memories",
            points_selector=memory_ids
        )

    async def calculate_utility_score(self, memory_id: str) -> float:
        """Calculate utility score based on usage patterns."""
        metrics = await self._get_memory_metrics(memory_id)

        # Weighted scoring
        score = (
            0.3 * min(metrics["access_count"] / 10, 1.0) +  # Access frequency
            0.3 * min(metrics["retrieval_rank"] / 5, 1.0) +  # Retrieval position
            0.2 * metrics["recency_score"] +                  # How recent
            0.2 * metrics["feedback_score"]                   # User ratings
        )

        return score

    async def run_maintenance(self):
        """Periodic maintenance: tier transitions, cleanup, optimization."""
        # Promote hot → warm
        hot_keys = await self.redis.keys("memory:hot:*")
        for key in hot_keys:
            created = await self.redis.hget(key, "created_at")
            if self._age(created) > MemoryConfig.HOT_TO_WARM_THRESHOLD:
                await self.promote_to_warm(key.split(":")[-1])

        # Demote warm → cold
        old_warm = await self.qdrant.scroll(
            collection_name="memories",
            scroll_filter={
                "must": [{
                    "key": "promoted_at",
                    "range": {"lt": (datetime.utcnow() - MemoryConfig.WARM_TO_COLD_THRESHOLD).isoformat()}
                }]
            },
            limit=1000
        )
        if old_warm:
            await self.demote_to_cold([p.id for p in old_warm])

        # Enforce size limits
        await self._enforce_limits()
```

### Memory Signals & Learning

```python
# packages/memory/src/ai_memory/signals.py
from enum import Enum, auto

class SignalType(Enum):
    # Explicit signals
    USER_RATING = auto()        # 1-5 star rating
    USER_CORRECTION = auto()    # User corrects output
    USER_ACCEPTANCE = auto()    # User accepts suggestion

    # Implicit signals
    TASK_SUCCESS = auto()       # Task completed successfully
    TASK_FAILURE = auto()       # Task failed
    TASK_RETRY = auto()         # User asked to retry
    TASK_ABANDON = auto()       # User abandoned task

    # Behavioral signals
    RESPONSE_EDIT = auto()      # User edited response before using
    FOLLOW_UP = auto()          # User asked follow-up (unclear?)
    CONTEXT_SWITCH = auto()     # User changed topic abruptly

@dataclass
class LearningSignal:
    type: SignalType
    weight: float              # -1.0 to 1.0
    context: dict             # Related task/memory info
    timestamp: datetime

class SignalProcessor:
    """Process signals and update memory utility scores."""

    SIGNAL_WEIGHTS = {
        SignalType.USER_RATING: 1.0,
        SignalType.USER_CORRECTION: -0.5,
        SignalType.USER_ACCEPTANCE: 0.8,
        SignalType.TASK_SUCCESS: 0.6,
        SignalType.TASK_FAILURE: -0.4,
        SignalType.TASK_RETRY: -0.3,
        SignalType.TASK_ABANDON: -0.6,
        SignalType.RESPONSE_EDIT: -0.2,
        SignalType.FOLLOW_UP: -0.1,
        SignalType.CONTEXT_SWITCH: -0.2,
    }

    async def process_signal(self, signal: LearningSignal):
        """Update memory scores based on signal."""
        base_weight = self.SIGNAL_WEIGHTS.get(signal.type, 0)
        final_weight = base_weight * signal.weight

        # Find related memories
        related_memories = await self._find_related_memories(signal.context)

        for memory_id in related_memories:
            # Update utility score
            current_score = await self._get_utility_score(memory_id)
            new_score = max(0, min(1, current_score + final_weight * 0.1))
            await self._set_utility_score(memory_id, new_score)

        # Store signal for analysis
        await self._store_signal(signal)

    async def extract_learning(self, algorithm_phase: str, context: dict):
        """Extract and store learnings from completed tasks."""
        learning = {
            "phase": algorithm_phase,
            "context_summary": await self._summarize_context(context),
            "outcome": context.get("outcome"),
            "signals": context.get("signals", []),
            "extracted_at": datetime.utcnow().isoformat()
        }

        # Store in phase-specific directory
        learning_path = f"pai/MEMORY/Learning/{algorithm_phase}/{uuid.uuid4()}.json"
        async with aiofiles.open(learning_path, 'w') as f:
            await f.write(json.dumps(learning, indent=2))

        # Also embed and store in Qdrant for retrieval
        embedding = await self.embedding_cache.get_embedding(
            f"{algorithm_phase}: {learning['context_summary']}"
        )
        await self.qdrant.upsert(
            collection_name="learnings",
            points=[{
                "id": str(uuid.uuid4()),
                "vector": embedding,
                "payload": learning
            }]
        )
```

### Hook System Events

```python
HOOKS = {
    "SessionStart":     "Initialize agent, load context",
    "SessionEnd":       "Persist state, cleanup",
    "UserPromptSubmit": "Capture input, route to supervisor",
    "Stop":             "Task completion, trigger VERIFY",
    "SubagentStop":     "Child agent completed, aggregate",
    "PreToolUse":       "Validate tool call, log intent",
    "PostToolUse":      "Capture result, update memory",
    "PreCompact":       "Context optimization checkpoint"
}
```

---

## SSH & Tmux Access

### Remote Access Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SSH ACCESS ARCHITECTURE                              │
└─────────────────────────────────────────────────────────────────────────────┘

    Admin Workstation
          │
          │ SSH (Port 22, Key Auth)
          ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                         SERVER                                          │
    │  ┌───────────────────────────────────────────────────────────────────┐  │
    │  │                    TMUX SESSION: ai-infrastructure                │  │
    │  │                                                                   │  │
    │  │  Window 0: supervisor    │ Window 1: code     │ Window 2: data   │  │
    │  │  ┌─────────────────────┐ │ ┌─────────────────┐│ ┌───────────────┐│  │
    │  │  │ $ claude            │ │ │ $ claude        ││ │ $ claude      ││  │
    │  │  │ [Supervisor Agent]  │ │ │ [Code Agent]    ││ │ [Data Agent]  ││  │
    │  │  │                     │ │ │                 ││ │               ││  │
    │  │  │ Listening on Redis  │ │ │ Listening...    ││ │ Listening...  ││  │
    │  │  └─────────────────────┘ │ └─────────────────┘│ └───────────────┘│  │
    │  │                          │                    │                   │  │
    │  │  Window 3: infra         │ Window 4: research │ Window 5: qa     │  │
    │  │  ┌─────────────────────┐ │ ┌─────────────────┐│ ┌───────────────┐│  │
    │  │  │ $ claude            │ │ │ $ claude        ││ │ $ claude      ││  │
    │  │  │ [Infra Agent]       │ │ │ [Research Agent]││ │ [QA Agent]    ││  │
    │  │  └─────────────────────┘ │ └─────────────────┘│ └───────────────┘│  │
    │  │                                                                   │  │
    │  │  Window 6: monitor       │ Window 7: logs                        │  │
    │  │  ┌─────────────────────┐ │ ┌─────────────────────────────────────┐│  │
    │  │  │ $ htop / btop       │ │ │ $ tail -f /var/log/ai-infra/*.log  ││  │
    │  │  └─────────────────────┘ │ └─────────────────────────────────────┘│  │
    │  └───────────────────────────────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────────────────────────────┘

    COMMANDS:
    ─────────
    ssh root@server                           # Connect to server
    tmux attach -t ai-infrastructure          # Attach to agent session
    tmux select-window -t ai-infrastructure:0 # Switch to supervisor
    tmux select-window -t ai-infrastructure:1 # Switch to code agent
    Ctrl+b d                                  # Detach from session
    Ctrl+b n                                  # Next window
    Ctrl+b p                                  # Previous window
```

### SSH Security Configuration

```bash
# /etc/ssh/sshd_config additions
PermitRootLogin prohibit-password    # Key-only root access
PasswordAuthentication no            # No password auth
PubkeyAuthentication yes             # Key auth enabled
AllowUsers root admin                # Whitelist users
MaxAuthTries 3                       # Limit attempts
ClientAliveInterval 300              # Keep-alive
ClientAliveCountMax 2                # Disconnect on timeout
```

---

## Multi-Domain Management

### Domain Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      MULTI-DOMAIN ARCHITECTURE                              │
└─────────────────────────────────────────────────────────────────────────────┘

                              INTERNET
                                  │
                                  ▼
              ┌───────────────────────────────────────┐
              │              NGINX                    │
              │         (Reverse Proxy)               │
              │                                       │
              │  ┌─────────────────────────────────┐  │
              │  │     TLS TERMINATION             │  │
              │  │  - Let's Encrypt Certificates   │  │
              │  │  - Auto-renewal via Certbot     │  │
              │  └─────────────────────────────────┘  │
              │                                       │
              │  ┌─────────────────────────────────┐  │
              │  │     VIRTUAL HOSTS               │  │
              │  │                                 │  │
              │  │  api.example.com    → :8000     │  │
              │  │  portal.example.com → :3000     │  │
              │  │  app1.example.com   → /var/www/app1  │
              │  │  app2.example.com   → /var/www/app2  │
              │  │  blog.example.com   → /var/www/blog  │
              │  └─────────────────────────────────┘  │
              └───────────────────────────────────────┘
                     │         │         │
         ┌───────────┘         │         └───────────┐
         ▼                     ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  /var/www/app1  │  │  /var/www/app2  │  │  /var/www/blog  │
│  ─────────────  │  │  ─────────────  │  │  ─────────────  │
│  index.html     │  │  index.html     │  │  index.html     │
│  assets/        │  │  assets/        │  │  posts/         │
│  .htaccess      │  │  api/           │  │  themes/        │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Nginx Configuration Structure

```
/etc/nginx/
├── nginx.conf                 # Main config
├── sites-available/
│   ├── default
│   ├── api.example.com       # API server
│   ├── portal.example.com    # Web portal
│   ├── app1.example.com      # Static site 1
│   ├── app2.example.com      # Static site 2
│   └── template.conf         # Template for new domains
├── sites-enabled/            # Symlinks to active sites
├── ssl/
│   └── dhparam.pem          # DH parameters
├── snippets/
│   ├── ssl-params.conf      # SSL settings
│   ├── security-headers.conf # Security headers
│   └── proxy-params.conf    # Proxy settings
└── conf.d/
    ├── rate-limiting.conf   # Rate limiting rules
    └── gzip.conf            # Compression settings
```

### Infrastructure Agent Domain Commands

```python
# Commands the Infrastructure Agent can execute
DOMAIN_COMMANDS = {
    "add_domain": {
        "steps": [
            "Create /var/www/{domain}",
            "Create nginx config from template",
            "Enable site (symlink)",
            "Request SSL cert via certbot",
            "Reload nginx",
            "Verify domain accessible"
        ]
    },
    "remove_domain": {
        "steps": [
            "Disable site (remove symlink)",
            "Archive web root",
            "Remove nginx config",
            "Revoke SSL cert (optional)",
            "Reload nginx"
        ]
    },
    "update_ssl": {
        "steps": [
            "Run certbot renew",
            "Verify cert validity",
            "Reload nginx if renewed"
        ]
    },
    "deploy_site": {
        "steps": [
            "Pull/copy new files to web root",
            "Set permissions",
            "Clear cache if applicable",
            "Verify deployment"
        ]
    }
}
```

---

## Directory Structure

```
/home/user/AI-Infrastructure/
├── README.md
├── LICENSE (MIT)
├── .env.example
├── .gitignore
├── docker-compose.yml
├── docker-compose.prod.yml
├── Makefile
├── install.sh                    # One-line installer
│
├── docs/
│   ├── architecture.md
│   ├── deployment.md
│   ├── agents.md
│   ├── api.md
│   └── security.md
│
├── pai/                          # PAI Integration
│   ├── .claude/                  # Claude configurations
│   │   ├── settings.json
│   │   └── commands/
│   ├── MEMORY/                   # PAI Memory System
│   │   ├── Learning/
│   │   │   ├── OBSERVE/
│   │   │   ├── THINK/
│   │   │   ├── PLAN/
│   │   │   ├── BUILD/
│   │   │   ├── EXECUTE/
│   │   │   ├── VERIFY/
│   │   │   ├── LEARN/
│   │   │   └── ALGORITHM/
│   │   ├── Signals/
│   │   │   ├── ratings/
│   │   │   ├── sentiment/
│   │   │   ├── behavioral/
│   │   │   └── verification/
│   │   └── Work/
│   │       ├── active/
│   │       └── archive/
│   ├── TELOS/                    # Goal Configuration
│   │   ├── mission.md
│   │   ├── vision.md
│   │   ├── values.md
│   │   ├── priorities.md
│   │   └── success.md
│   └── hooks/                    # Event Hooks
│       ├── session_start.py
│       ├── session_end.py
│       ├── user_prompt.py
│       ├── task_complete.py
│       └── tool_use.py
│
├── packages/
│   ├── core/                     # Shared utilities
│   │   ├── pyproject.toml
│   │   └── src/ai_core/
│   │       ├── __init__.py
│   │       ├── config.py
│   │       ├── logging.py
│   │       └── exceptions.py
│   │
│   ├── messaging/                # Redis messaging
│   │   ├── pyproject.toml
│   │   └── src/ai_messaging/
│   │       ├── __init__.py
│   │       ├── bus.py
│   │       ├── publisher.py
│   │       ├── subscriber.py
│   │       ├── streams.py
│   │       └── protocols.py
│   │
│   ├── memory/                   # Vector DB + PAI memory
│   │   ├── pyproject.toml
│   │   └── src/ai_memory/
│   │       ├── __init__.py
│   │       ├── embeddings.py     # OpenAI embeddings
│   │       ├── qdrant_store.py
│   │       ├── retriever.py
│   │       ├── pai_memory.py     # PAI integration
│   │       └── schemas.py
│   │
│   └── tmux_manager/             # Tmux orchestration
│       ├── pyproject.toml
│       └── src/ai_tmux/
│           ├── __init__.py
│           ├── session.py
│           ├── agent_runner.py
│           ├── monitor.py
│           └── config.py
│
├── services/
│   ├── api/                      # FastAPI backend
│   │   ├── pyproject.toml
│   │   └── src/api/
│   │       ├── __init__.py
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── dependencies.py
│   │       ├── middleware/
│   │       │   ├── auth.py
│   │       │   ├── rate_limit.py
│   │       │   └── logging.py
│   │       ├── routes/
│   │       │   ├── auth.py
│   │       │   ├── chat.py
│   │       │   ├── agents.py
│   │       │   ├── tasks.py
│   │       │   ├── memory.py
│   │       │   ├── domains.py    # Domain management
│   │       │   └── voice.py
│   │       ├── websocket/
│   │       │   ├── manager.py
│   │       │   └── handlers.py
│   │       └── services/
│   │           ├── auth_service.py
│   │           ├── chat_service.py
│   │           ├── agent_service.py
│   │           └── domain_service.py
│   │
│   ├── supervisor/               # Supervisor agent
│   │   ├── pyproject.toml
│   │   ├── AGENT.md              # System prompt
│   │   └── src/supervisor/
│   │       ├── __init__.py
│   │       ├── main.py
│   │       ├── orchestrator.py
│   │       ├── router.py
│   │       ├── aggregator.py
│   │       ├── algorithm.py      # PAI Algorithm
│   │       └── prompts/
│   │
│   ├── agents/
│   │   ├── base/                 # Base agent class
│   │   │   ├── pyproject.toml
│   │   │   └── src/agent_base/
│   │   │       ├── __init__.py
│   │   │       ├── agent.py
│   │   │       ├── tools.py
│   │   │       ├── memory.py
│   │   │       └── communication.py
│   │   │
│   │   ├── code_agent/
│   │   │   ├── AGENT.md
│   │   │   └── src/code_agent/
│   │   │       ├── main.py
│   │   │       └── tools/
│   │   │
│   │   ├── data_agent/
│   │   │   ├── AGENT.md
│   │   │   └── src/data_agent/
│   │   │       ├── main.py
│   │   │       └── tools/
│   │   │
│   │   ├── infra_agent/          # Server/domain management
│   │   │   ├── AGENT.md
│   │   │   └── src/infra_agent/
│   │   │       ├── main.py
│   │   │       └── tools/
│   │   │           ├── nginx.py
│   │   │           ├── certbot.py
│   │   │           ├── docker.py
│   │   │           ├── systemd.py
│   │   │           └── domains.py
│   │   │
│   │   ├── research_agent/
│   │   │   ├── AGENT.md
│   │   │   └── src/research_agent/
│   │   │       ├── main.py
│   │   │       └── tools/
│   │   │
│   │   └── qa_agent/
│   │       ├── AGENT.md
│   │       └── src/qa_agent/
│   │           ├── main.py
│   │           └── tools/
│   │
│   └── voice/                    # Voice processing
│       ├── pyproject.toml
│       └── src/voice_service/
│           ├── __init__.py
│           ├── main.py
│           ├── transcription.py  # OpenAI Whisper
│           ├── synthesis.py      # OpenAI TTS
│           └── streaming.py
│
├── web/                          # Next.js frontend
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   └── src/
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── page.tsx
│       │   ├── (auth)/
│       │   │   ├── login/
│       │   │   └── register/
│       │   └── (dashboard)/
│       │       ├── chat/
│       │       ├── agents/
│       │       ├── domains/      # Domain management UI
│       │       ├── memory/
│       │       └── settings/
│       ├── components/
│       │   ├── ui/               # shadcn/ui
│       │   ├── chat/
│       │   ├── agents/
│       │   ├── domains/
│       │   └── voice/
│       ├── hooks/
│       ├── lib/
│       └── stores/
│
├── database/
│   ├── migrations/
│   ├── seeds/
│   └── models/
│
├── infrastructure/
│   ├── docker/
│   │   ├── Dockerfile.api
│   │   ├── Dockerfile.agent
│   │   ├── Dockerfile.web
│   │   └── Dockerfile.voice
│   ├── nginx/
│   │   ├── nginx.conf
│   │   ├── sites-available/
│   │   │   └── template.conf
│   │   └── snippets/
│   ├── systemd/
│   │   ├── ai-infrastructure.service
│   │   ├── ai-api.service
│   │   └── ai-agents.service
│   └── scripts/
│       ├── setup.sh
│       ├── start-agents.sh
│       ├── add-domain.sh
│       └── backup.sh
│
├── config/
│   ├── agents.yaml               # Agent definitions
│   ├── domains.yaml              # Domain configurations
│   ├── tmux/
│   │   └── session.yaml          # tmuxp config
│   └── prompts/
│       ├── supervisor.md
│       ├── code_agent.md
│       ├── data_agent.md
│       ├── infra_agent.md
│       ├── research_agent.md
│       └── qa_agent.md
│
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

---

## User Interface

### Web Portal Features

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           WEB PORTAL LAYOUT                                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  ┌─────┐  AI Infrastructure                    [User] ▼  [Settings]  [Logout]│
│  │ ◉◉◉ │                                                                    │
│  └─────┘                                                                    │
├─────────────┬───────────────────────────────────────────────────────────────┤
│             │                                                               │
│   SIDEBAR   │                    MAIN CONTENT                               │
│             │                                                               │
│  ┌────────┐ │  ┌─────────────────────────────────────────────────────────┐ │
│  │💬 Chat │ │  │                                                         │ │
│  └────────┘ │  │  ┌─────────────────────────────────────────────────┐   │ │
│  ┌────────┐ │  │  │ [Supervisor] Today at 2:30 PM                   │   │ │
│  │🤖 Agents│ │  │  │ I've analyzed your request. Here's my plan:    │   │ │
│  └────────┘ │  │  │ 1. Code Agent will implement the API            │   │ │
│  ┌────────┐ │  │  │ 2. Data Agent will set up the database         │   │ │
│  │🌐 Domain│ │  │  │ 3. QA Agent will write tests                   │   │ │
│  └────────┘ │  │  └─────────────────────────────────────────────────┘   │ │
│  ┌────────┐ │  │                                                         │ │
│  │🧠 Memory│ │  │  ┌─────────────────────────────────────────────────┐   │ │
│  └────────┘ │  │  │ [Code Agent] Working...                         │   │ │
│  ┌────────┐ │  │  │ ████████████░░░░░░░░ 60%                        │   │ │
│  │⚙️ Settings│ │  │  │ Currently implementing user authentication...   │   │ │
│  └────────┘ │  │  └─────────────────────────────────────────────────┘   │ │
│             │  │                                                         │ │
│  ─────────  │  └─────────────────────────────────────────────────────────┘ │
│             │                                                               │
│  AGENTS     │  ┌─────────────────────────────────────────────────────────┐ │
│  ┌────────┐ │  │                                                         │ │
│  │◉ Super │ │  │  ┌──────────────────────────────────────────┐ ┌──┐ ┌──┐│ │
│  │◉ Code  │ │  │  │ Type your message...                     │ │📎│ │🎤││ │
│  │◉ Data  │ │  │  └──────────────────────────────────────────┘ └──┘ └──┘│ │
│  │◉ Infra │ │  │        [Attach Files]        [Voice Input]    [Send ➤] │ │
│  │◉ Research│ │  └─────────────────────────────────────────────────────────┘ │
│  │◉ QA    │ │                                                               │
│  └────────┘ │                                                               │
│             │                                                               │
└─────────────┴───────────────────────────────────────────────────────────────┘

PAGES:
─────
/chat        - Main chat interface with supervisor
/agents      - Agent status, logs, controls
/domains     - Domain management (add/remove/deploy)
/memory      - Browse vector DB, view learnings
/settings    - API keys, preferences, TELOS config
```

### Chat Features

- **Text Input**: Markdown support, code blocks
- **File Upload**: Images, documents, code files
- **Voice Input**: Push-to-talk, continuous listening
- **Voice Output**: TTS for agent responses
- **Streaming**: Real-time response streaming
- **Agent Status**: Live indicator of which agents are working

---

## Security Architecture

### Permission Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PERMISSION LEVELS                                   │
└─────────────────────────────────────────────────────────────────────────────┘

LEVEL 0: RESTRICTED (Default)
├── Read: /workspace only
├── Write: None
├── Network: None
└── Execute: None

LEVEL 1: STANDARD (Code/Data/Research/QA Agents)
├── Read: /workspace, /var/www (read-only)
├── Write: /workspace
├── Network: HTTPS to allowlist (github.com, pypi.org, npm.js)
└── Execute: git, npm, pip, pytest, approved tools

LEVEL 2: ELEVATED (Infrastructure Agent)
├── Read: /workspace, /var/www, /etc/nginx, system logs
├── Write: /workspace, /var/www, /etc/nginx/sites-available
├── Network: Full outbound HTTPS
└── Execute: docker, nginx, certbot, systemctl (limited)

LEVEL 3: PRIVILEGED (Supervisor + Human Approval)
├── Read: Full system
├── Write: Full system (with audit)
├── Network: Full
└── Execute: All (with confirmation for destructive ops)

ESCALATION:
Agent requests elevated permission → Supervisor evaluates →
Auto-approve (within policy) OR Human approval required
All actions logged to audit trail
```

### Authentication Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  User    │────▶│  Portal  │────▶│   API    │────▶│  Redis   │
│          │     │          │     │          │     │          │
│ 1. Login │     │ 2. OAuth/│     │ 3. Issue │     │ 4. Store │
│    form  │     │    Creds │     │    JWT   │     │  session │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                                         │
                                         ▼
                                  ┌──────────┐
                                  │ WebSocket│
                                  │ Connect  │
                                  │ w/ JWT   │
                                  └──────────┘
```

### Network Segmentation

Docker networks isolate services and control inter-service communication:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DOCKER NETWORK TOPOLOGY                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  NETWORK: ai-frontend (bridge)                                              │
│  Purpose: Public-facing services only                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐                                        │
│  │   Nginx     │◄──►│  Next.js    │                                        │
│  │  (host)     │    │   :3000     │                                        │
│  └──────┬──────┘    └─────────────┘                                        │
└─────────┼───────────────────────────────────────────────────────────────────┘
          │
┌─────────┼───────────────────────────────────────────────────────────────────┐
│  NETWORK: ai-backend (bridge, internal)                                     │
│  Purpose: API and agent communication                                       │
├─────────┼───────────────────────────────────────────────────────────────────┤
│         ▼                                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │  FastAPI    │◄──►│   Redis     │◄──►│   Agents    │                     │
│  │   :8000     │    │   :6379     │    │  (tmux)     │                     │
│  └──────┬──────┘    └─────────────┘    └─────────────┘                     │
└─────────┼───────────────────────────────────────────────────────────────────┘
          │
┌─────────┼───────────────────────────────────────────────────────────────────┐
│  NETWORK: ai-data (bridge, internal)                                        │
│  Purpose: Database access only                                              │
├─────────┼───────────────────────────────────────────────────────────────────┤
│         ▼                                                                   │
│  ┌─────────────┐    ┌─────────────┐                                        │
│  │ PostgreSQL  │    │   Qdrant    │                                        │
│  │   :5432     │    │   :6333     │                                        │
│  └─────────────┘    └─────────────┘                                        │
└─────────────────────────────────────────────────────────────────────────────┘

ISOLATION RULES:
─────────────────
• Frontend containers cannot access databases directly
• Agents communicate only via Redis message bus
• Database ports are not exposed to host
• External API calls route through dedicated egress proxy
```

### Audit Logging

All security-relevant events are logged to a structured audit trail:

```python
# Audit Event Schema
{
    "id": "uuid",
    "timestamp": "ISO-8601",
    "event_type": "auth|access|action|escalation|error",
    "actor": {
        "type": "user|agent|system",
        "id": "user_id or agent_name",
        "ip": "source IP if applicable"
    },
    "resource": {
        "type": "file|endpoint|service|command",
        "path": "/path/or/endpoint"
    },
    "action": "read|write|execute|delete|login|logout|escalate",
    "outcome": "success|failure|denied",
    "details": {
        "reason": "optional failure reason",
        "changes": "optional diff or summary"
    },
    "risk_level": "low|medium|high|critical"
}
```

**Audit Log Storage:**
```sql
-- PostgreSQL audit_logs table
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(20) NOT NULL,
    actor_type VARCHAR(20) NOT NULL,
    actor_id VARCHAR(100) NOT NULL,
    actor_ip INET,
    resource_type VARCHAR(50),
    resource_path TEXT,
    action VARCHAR(20) NOT NULL,
    outcome VARCHAR(20) NOT NULL,
    details JSONB,
    risk_level VARCHAR(20) DEFAULT 'low'
) PARTITION BY RANGE (timestamp);

-- Indexes for common queries (created separately - inline INDEX syntax is not valid PostgreSQL)
CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX idx_audit_actor ON audit_logs(actor_type, actor_id);
CREATE INDEX idx_audit_risk ON audit_logs(risk_level, timestamp DESC);

-- Retention: Partition by month, retain 12 months
CREATE TABLE audit_logs_y2025m01 PARTITION OF audit_logs
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
```

### Input Sanitization

All user inputs are sanitized before processing:

```python
# services/api/src/api/middleware/sanitization.py
from pydantic import BaseModel, field_validator
import bleach
import re

class UserPromptInput(BaseModel):
    message: str
    attachments: list[str] = []

    @field_validator('message')
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        # Remove potential injection patterns
        v = bleach.clean(v, tags=[], strip=True)

        # Block shell injection attempts
        dangerous_patterns = [
            r'\$\([^)]+\)',      # $(command)
            r'`[^`]+`',          # `command`
            r'\|\s*\w+',         # | pipe
            r';\s*\w+',          # ; command chain
            r'&&\s*\w+',         # && chain
            r'\|\|\s*\w+',       # || chain
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, v):
                raise ValueError('Input contains potentially dangerous patterns')

        # Limit length
        if len(v) > 50000:
            raise ValueError('Message too long (max 50000 chars)')

        return v.strip()

    @field_validator('attachments')
    @classmethod
    def validate_attachments(cls, v: list[str]) -> list[str]:
        allowed_extensions = {'.txt', '.md', '.py', '.js', '.ts', '.json', '.yaml', '.yml'}
        for path in v:
            ext = Path(path).suffix.lower()
            if ext not in allowed_extensions:
                raise ValueError(f'File type {ext} not allowed')
        return v
```

### Rate Limiting

Multi-layer rate limiting protects against abuse:

```python
# Rate limit configuration
RATE_LIMITS = {
    "api": {
        "anonymous": "10/minute",
        "authenticated": "100/minute",
        "premium": "1000/minute"
    },
    "websocket": {
        "messages": "30/minute",
        "connections": "5/user"
    },
    "agents": {
        "inter_agent_messages": "100/minute/agent",
        "tool_calls": "50/minute/agent",
        "escalations": "5/minute/agent"
    },
    "auth": {
        "login_attempts": "5/15minutes/ip",
        "password_reset": "3/hour/email"
    }
}
```

```nginx
# /etc/nginx/conf.d/rate-limiting.conf
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=ws_limit:10m rate=2r/s;
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;

server {
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        limit_conn conn_limit 10;
    }

    location /ws/ {
        limit_req zone=ws_limit burst=5;
        limit_conn conn_limit 5;
    }
}
```

---

## Observability & Monitoring

### Metrics Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        OBSERVABILITY STACK                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    METRICS      │     │     LOGS        │     │    TRACES       │
│   (Prometheus)  │     │    (Loki)       │     │   (Tempo)       │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │        GRAFANA          │
                    │    (Visualization)      │
                    │    Port: 3001           │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │      ALERTMANAGER       │
                    │   (Slack, PagerDuty)    │
                    └─────────────────────────┘
```

### Key Metrics

```python
# packages/core/src/ai_core/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Agent Metrics
agent_tasks_total = Counter(
    'agent_tasks_total',
    'Total tasks processed by agent',
    ['agent', 'status']  # agent=code|data|infra, status=success|failure
)

agent_task_duration = Histogram(
    'agent_task_duration_seconds',
    'Task processing time',
    ['agent', 'task_type'],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]
)

agent_active_tasks = Gauge(
    'agent_active_tasks',
    'Currently processing tasks',
    ['agent']
)

# API Metrics
api_requests_total = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status_code']
)

api_request_duration = Histogram(
    'api_request_duration_seconds',
    'API request latency',
    ['method', 'endpoint']
)

# LLM Metrics
llm_tokens_total = Counter(
    'llm_tokens_total',
    'Total tokens consumed',
    ['provider', 'model', 'direction']  # direction=input|output
)

llm_request_duration = Histogram(
    'llm_request_duration_seconds',
    'LLM API call latency',
    ['provider', 'model']
)

llm_cost_total = Counter(
    'llm_cost_dollars_total',
    'Cumulative API cost in dollars',
    ['provider', 'model']
)

# Message Bus Metrics
redis_messages_total = Counter(
    'redis_messages_total',
    'Messages published to Redis',
    ['channel', 'message_type']
)

redis_queue_depth = Gauge(
    'redis_queue_depth',
    'Pending messages in queue',
    ['queue']
)
```

### Distributed Tracing

OpenTelemetry traces task execution across agents:

```python
# packages/core/src/ai_core/tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Initialize tracer
provider = TracerProvider()
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="http://tempo:4317"))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("ai-infrastructure")

# Usage in agent
class BaseAgent:
    async def process_task(self, task: Task):
        with tracer.start_as_current_span(
            f"agent.{self.name}.process_task",
            attributes={
                "task.id": task.id,
                "task.type": task.type,
                "agent.name": self.name
            }
        ) as span:
            try:
                result = await self._execute(task)
                span.set_attribute("task.status", "success")
                return result
            except Exception as e:
                span.set_attribute("task.status", "error")
                span.record_exception(e)
                raise
```

### Alerting Rules

```yaml
# infrastructure/prometheus/alerts.yml
groups:
  - name: agent_alerts
    rules:
      - alert: AgentUnresponsive
        expr: up{job="agents"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Agent {{ $labels.agent }} is unresponsive"

      - alert: AgentHighErrorRate
        expr: rate(agent_tasks_total{status="failure"}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Agent {{ $labels.agent }} error rate > 10%"

      - alert: TaskQueueBacklog
        expr: redis_queue_depth > 100
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Task queue {{ $labels.queue }} has {{ $value }} pending"

      - alert: HighAPILatency
        expr: histogram_quantile(0.95, api_request_duration_seconds_bucket) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "API p95 latency > 5s"

      - alert: LLMCostSpike
        expr: increase(llm_cost_dollars_total[1h]) > 10
        labels:
          severity: warning
        annotations:
          summary: "LLM costs exceeded $10 in the last hour"

      - alert: DiskSpaceLow
        expr: node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes < 0.15
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Disk space below 15%"
```

### Health Check Endpoints

```python
# services/api/src/api/routes/health.py
from fastapi import APIRouter, Response
from datetime import datetime
import asyncio

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/live")
async def liveness():
    """Kubernetes liveness probe - is the process running?"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@router.get("/ready")
async def readiness():
    """Kubernetes readiness probe - can we serve traffic?"""
    checks = await asyncio.gather(
        check_redis(),
        check_postgres(),
        check_qdrant(),
        return_exceptions=True
    )

    results = {
        "redis": "ok" if not isinstance(checks[0], Exception) else str(checks[0]),
        "postgres": "ok" if not isinstance(checks[1], Exception) else str(checks[1]),
        "qdrant": "ok" if not isinstance(checks[2], Exception) else str(checks[2]),
    }

    all_ok = all(v == "ok" for v in results.values())
    return Response(
        content=json.dumps({"status": "ok" if all_ok else "degraded", "checks": results}),
        status_code=200 if all_ok else 503,
        media_type="application/json"
    )

@router.get("/agents")
async def agent_health():
    """Check status of all agents."""
    agents = ["supervisor", "code", "data", "infra", "research", "qa"]
    statuses = {}

    for agent in agents:
        last_heartbeat = await redis.get(f"agent:{agent}:heartbeat")
        if last_heartbeat:
            age = datetime.utcnow() - datetime.fromisoformat(last_heartbeat)
            statuses[agent] = "ok" if age.seconds < 60 else "stale"
        else:
            statuses[agent] = "unknown"

    return {"agents": statuses}
```

---

## Resilience & Fault Tolerance

### Retry Strategies

```python
# packages/messaging/src/ai_messaging/retry.py
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import asyncio

class RetryConfig:
    """Configurable retry policies for different operations."""

    # Agent-to-agent communication
    AGENT_MESSAGE = {
        "max_attempts": 3,
        "wait_min": 1,
        "wait_max": 10,
        "wait_multiplier": 2
    }

    # LLM API calls
    LLM_API = {
        "max_attempts": 5,
        "wait_min": 2,
        "wait_max": 60,
        "wait_multiplier": 2,
        "retry_on": [429, 500, 502, 503, 504]  # Rate limit + server errors
    }

    # Database operations
    DATABASE = {
        "max_attempts": 3,
        "wait_min": 0.5,
        "wait_max": 5,
        "wait_multiplier": 2
    }

def with_retry(config_name: str):
    """Decorator factory for retry policies."""
    config = getattr(RetryConfig, config_name)

    return retry(
        stop=stop_after_attempt(config["max_attempts"]),
        wait=wait_exponential(
            multiplier=config["wait_multiplier"],
            min=config["wait_min"],
            max=config["wait_max"]
        ),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Retry {retry_state.attempt_number}/{config['max_attempts']}"
        )
    )

# Usage
@with_retry("LLM_API")
async def call_claude(prompt: str) -> str:
    ...
```

### Dead Letter Queue

Failed messages are preserved for debugging and replay:

```python
# packages/messaging/src/ai_messaging/dlq.py
from datetime import datetime
import json

class DeadLetterQueue:
    """Handle messages that fail processing after all retries."""

    DLQ_PREFIX = "ai:dlq:"
    MAX_RETENTION_DAYS = 7

    async def send_to_dlq(
        self,
        original_message: dict,
        error: Exception,
        source_queue: str,
        attempts: int
    ):
        """Move failed message to dead letter queue."""
        dlq_entry = {
            "id": str(uuid.uuid4()),
            "original_message": original_message,
            "source_queue": source_queue,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "attempts": attempts,
            "failed_at": datetime.utcnow().isoformat(),
            "stack_trace": traceback.format_exc()
        }

        dlq_key = f"{self.DLQ_PREFIX}{source_queue}"
        await self.redis.xadd(
            dlq_key,
            {"data": json.dumps(dlq_entry)},
            maxlen=10000  # Keep last 10k failures per queue
        )

        # Alert on DLQ threshold
        dlq_size = await self.redis.xlen(dlq_key)
        if dlq_size > 100:
            await self.alert_manager.send(
                severity="warning",
                title=f"DLQ {source_queue} has {dlq_size} entries",
                message="Review failed messages and consider replay"
            )

    async def replay_message(self, dlq_entry_id: str, target_queue: str):
        """Replay a message from DLQ to original queue."""
        ...

    async def purge_expired(self):
        """Remove DLQ entries older than retention period."""
        ...
```

### Circuit Breaker

Prevent cascade failures when downstream services are unhealthy:

```python
# packages/core/src/ai_core/circuit_breaker.py
from enum import Enum
from datetime import datetime, timedelta
import asyncio

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered

class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 3,
        timeout: timedelta = timedelta(seconds=30)
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout

        self.state = CircuitState.CLOSED
        self.failures = 0
        self.successes = 0
        self.last_failure_time: datetime = None

    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if datetime.utcnow() - self.last_failure_time > self.timeout:
                self.state = CircuitState.HALF_OPEN
                self.successes = 0
            else:
                raise CircuitOpenError(f"Circuit {self.name} is open")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.successes += 1
            if self.successes >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.failures = 0

    def _on_failure(self):
        self.failures += 1
        self.last_failure_time = datetime.utcnow()

        if self.failures >= self.failure_threshold:
            self.state = CircuitState.OPEN

# Usage
claude_circuit = CircuitBreaker("claude_api", failure_threshold=5, timeout=timedelta(minutes=1))

async def call_claude(prompt):
    return await claude_circuit.call(_raw_claude_call, prompt)
```

### Agent Recovery

Automatic recovery when agents crash:

```python
# packages/tmux_manager/src/ai_tmux/recovery.py
import asyncio
from datetime import datetime, timedelta

class AgentWatchdog:
    """Monitor and restart crashed agents."""

    HEARTBEAT_INTERVAL = 30  # seconds
    MAX_RESTART_ATTEMPTS = 3
    RESTART_BACKOFF = [10, 30, 60]  # seconds

    def __init__(self, tmux_manager, redis):
        self.tmux = tmux_manager
        self.redis = redis
        self.restart_counts: dict[str, int] = {}

    async def monitor_loop(self):
        """Continuously monitor agent health."""
        while True:
            await self.check_all_agents()
            await asyncio.sleep(self.HEARTBEAT_INTERVAL)

    async def check_all_agents(self):
        agents = ["supervisor", "code", "data", "infra", "research", "qa"]

        for agent in agents:
            heartbeat = await self.redis.get(f"agent:{agent}:heartbeat")

            if not heartbeat:
                await self.handle_missing_agent(agent)
                continue

            last_beat = datetime.fromisoformat(heartbeat)
            if datetime.utcnow() - last_beat > timedelta(seconds=90):
                await self.handle_stale_agent(agent, last_beat)

    async def handle_missing_agent(self, agent: str):
        """Agent never started or crashed without cleanup."""
        logger.error(f"Agent {agent} has no heartbeat - attempting restart")
        await self.restart_agent(agent)

    async def handle_stale_agent(self, agent: str, last_heartbeat: datetime):
        """Agent stopped sending heartbeats."""
        logger.warning(f"Agent {agent} heartbeat stale since {last_heartbeat}")

        # Check if tmux window is responsive
        if not await self.tmux.is_window_alive(agent):
            await self.restart_agent(agent)

    async def restart_agent(self, agent: str):
        """Restart an agent with backoff."""
        attempts = self.restart_counts.get(agent, 0)

        if attempts >= self.MAX_RESTART_ATTEMPTS:
            logger.critical(f"Agent {agent} exceeded max restart attempts")
            await self.alert_critical(agent)
            return

        backoff = self.RESTART_BACKOFF[min(attempts, len(self.RESTART_BACKOFF) - 1)]
        logger.info(f"Restarting {agent} (attempt {attempts + 1}) after {backoff}s")

        await asyncio.sleep(backoff)
        await self.tmux.restart_window(agent)
        self.restart_counts[agent] = attempts + 1

        # Reset counter after successful 5-minute uptime
        asyncio.create_task(self._reset_counter_after_stable(agent))

    async def _reset_counter_after_stable(self, agent: str):
        await asyncio.sleep(300)  # 5 minutes
        heartbeat = await self.redis.get(f"agent:{agent}:heartbeat")
        if heartbeat:
            self.restart_counts[agent] = 0
```

### Graceful Shutdown

Proper cleanup when stopping services:

```python
# services/supervisor/src/supervisor/shutdown.py
import signal
import asyncio

class GracefulShutdown:
    def __init__(self):
        self.shutdown_event = asyncio.Event()
        self.active_tasks: set[asyncio.Task] = set()

    def setup_handlers(self):
        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_event_loop().add_signal_handler(
                sig, lambda: asyncio.create_task(self.shutdown())
            )

    async def shutdown(self):
        logger.info("Shutdown signal received, draining tasks...")

        # Stop accepting new tasks
        self.shutdown_event.set()

        # Wait for active tasks (with timeout)
        if self.active_tasks:
            logger.info(f"Waiting for {len(self.active_tasks)} active tasks")
            done, pending = await asyncio.wait(
                self.active_tasks,
                timeout=30
            )

            if pending:
                logger.warning(f"Cancelling {len(pending)} tasks after timeout")
                for task in pending:
                    task.cancel()

        # Persist state
        await self.save_state()

        # Send final heartbeat
        await self.redis.set(
            f"agent:{self.name}:shutdown",
            datetime.utcnow().isoformat()
        )

        logger.info("Shutdown complete")
```

---

## Cost Optimization

### Token Usage Tracking

```python
# packages/core/src/ai_core/cost_tracking.py
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal

@dataclass
class TokenPricing:
    """Current pricing per 1M tokens (as of 2025)."""
    CLAUDE_OPUS_INPUT = Decimal("15.00")
    CLAUDE_OPUS_OUTPUT = Decimal("75.00")
    CLAUDE_SONNET_INPUT = Decimal("3.00")
    CLAUDE_SONNET_OUTPUT = Decimal("15.00")
    OPENAI_EMBEDDING = Decimal("0.02")
    OPENAI_WHISPER = Decimal("0.006")  # per minute
    OPENAI_TTS = Decimal("15.00")  # per 1M chars

class CostTracker:
    def __init__(self, db, budget_alert_threshold: Decimal = Decimal("100")):
        self.db = db
        self.budget_threshold = budget_alert_threshold

    async def record_usage(
        self,
        agent: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ):
        """Record API usage and calculate cost."""
        cost = self._calculate_cost(provider, model, input_tokens, output_tokens)

        await self.db.execute("""
            INSERT INTO api_usage (agent, provider, model, input_tokens, output_tokens, cost_usd, timestamp)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
        """, agent, provider, model, input_tokens, output_tokens, float(cost))

        # Update Prometheus metrics
        llm_tokens_total.labels(provider=provider, model=model, direction="input").inc(input_tokens)
        llm_tokens_total.labels(provider=provider, model=model, direction="output").inc(output_tokens)
        llm_cost_total.labels(provider=provider, model=model).inc(float(cost))

        # Check daily budget
        await self._check_budget_alert()

    async def get_daily_summary(self, target_date: date = None) -> dict:
        """Get usage summary for a specific day."""
        target_date = target_date or date.today()

        result = await self.db.fetch("""
            SELECT
                provider,
                model,
                SUM(input_tokens) as total_input,
                SUM(output_tokens) as total_output,
                SUM(cost_usd) as total_cost
            FROM api_usage
            WHERE DATE(timestamp) = $1
            GROUP BY provider, model
        """, target_date)

        return {
            "date": target_date.isoformat(),
            "breakdown": [dict(r) for r in result],
            "total_cost": sum(r["total_cost"] for r in result)
        }

    async def _check_budget_alert(self):
        """Alert if daily spending exceeds threshold."""
        today_cost = await self.db.fetchval("""
            SELECT COALESCE(SUM(cost_usd), 0)
            FROM api_usage
            WHERE DATE(timestamp) = CURRENT_DATE
        """)

        if Decimal(str(today_cost)) > self.budget_threshold:
            await self.alert_manager.send(
                severity="warning",
                title="Daily API Budget Exceeded",
                message=f"Today's spending: ${today_cost:.2f} (threshold: ${self.budget_threshold})"
            )
```

### Embedding Cache

Avoid re-embedding identical content:

```python
# packages/memory/src/ai_memory/embedding_cache.py
import hashlib
from typing import Optional

class EmbeddingCache:
    """Cache embeddings to reduce API calls."""

    CACHE_PREFIX = "embedding:"
    TTL = 86400 * 30  # 30 days

    def __init__(self, redis, openai_client):
        self.redis = redis
        self.openai = openai_client
        self.stats = {"hits": 0, "misses": 0}

    def _hash_content(self, text: str) -> str:
        """Create deterministic hash of content."""
        return hashlib.sha256(text.encode()).hexdigest()[:32]

    async def get_embedding(self, text: str, model: str = "text-embedding-3-small") -> list[float]:
        """Get embedding from cache or API."""
        cache_key = f"{self.CACHE_PREFIX}{model}:{self._hash_content(text)}"

        # Check cache
        cached = await self.redis.get(cache_key)
        if cached:
            self.stats["hits"] += 1
            return json.loads(cached)

        # Call API
        self.stats["misses"] += 1
        response = await self.openai.embeddings.create(
            input=text,
            model=model
        )
        embedding = response.data[0].embedding

        # Cache result
        await self.redis.setex(
            cache_key,
            self.TTL,
            json.dumps(embedding)
        )

        return embedding

    async def get_embeddings_batch(self, texts: list[str], model: str = "text-embedding-3-small") -> list[list[float]]:
        """Batch embedding with partial cache hits."""
        results = [None] * len(texts)
        uncached_indices = []
        uncached_texts = []

        # Check cache for each
        for i, text in enumerate(texts):
            cache_key = f"{self.CACHE_PREFIX}{model}:{self._hash_content(text)}"
            cached = await self.redis.get(cache_key)
            if cached:
                results[i] = json.loads(cached)
                self.stats["hits"] += 1
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)
                self.stats["misses"] += 1

        # Batch API call for uncached
        if uncached_texts:
            response = await self.openai.embeddings.create(
                input=uncached_texts,
                model=model
            )

            for i, (idx, embedding_data) in enumerate(zip(uncached_indices, response.data)):
                embedding = embedding_data.embedding
                results[idx] = embedding

                # Cache (use enumerate index to avoid O(n²) lookup)
                cache_key = f"{self.CACHE_PREFIX}{model}:{self._hash_content(uncached_texts[i])}"
                await self.redis.setex(cache_key, self.TTL, json.dumps(embedding))

        return results

    def get_hit_rate(self) -> float:
        total = self.stats["hits"] + self.stats["misses"]
        return self.stats["hits"] / total if total > 0 else 0.0
```

### Budget Controls

```yaml
# config/budgets.yaml
budgets:
  daily:
    warning_threshold: 50.00   # USD
    hard_limit: 100.00         # USD - pause non-critical operations
    critical_limit: 200.00     # USD - emergency shutdown

  monthly:
    warning_threshold: 1000.00
    hard_limit: 2000.00

  per_agent:
    supervisor: 30.00/day
    code: 25.00/day
    data: 15.00/day
    infra: 10.00/day
    research: 20.00/day
    qa: 15.00/day

actions:
  on_warning:
    - send_alert
    - log_detailed_usage

  on_hard_limit:
    - pause_research_agent      # Lowest priority
    - reduce_context_windows
    - switch_to_smaller_models  # Sonnet instead of Opus

  on_critical_limit:
    - pause_all_non_essential
    - alert_admin_urgent
    - require_manual_override
```

---

## External Service Integrations

### AWS Secrets Manager

All sensitive credentials are stored in AWS Secrets Manager for secure, centralized management.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AWS SECRETS MANAGER INTEGRATION                        │
└─────────────────────────────────────────────────────────────────────────────┘

    AWS Secrets Manager                         AI Infrastructure
    ──────────────────                         ──────────────────

    ai-infrastructure/                         Application Startup
    ├── anthropic-api-key      ───────────▶    │
    ├── openai-api-key         ───────────▶    │ Secrets loaded
    ├── postgres-credentials   ───────────▶    │ into memory
    ├── redis-password         ───────────▶    │ (not env files)
    ├── qdrant-api-key         ───────────▶    │
    ├── jwt-secret             ───────────▶    │
    ├── cloudflare-token       ───────────▶    │
    └── github-pat             ───────────▶    ▼

    FEATURES:
    ─────────
    • Automatic rotation support
    • IAM-based access control
    • Audit logging via CloudTrail
    • No secrets in code or .env files
    • Secrets cached locally for performance
```

**Secret Structure:**
```json
{
  "ai-infrastructure/anthropic-api-key": "sk-ant-...",
  "ai-infrastructure/openai-api-key": "sk-...",
  "ai-infrastructure/postgres": {
    "username": "ai_infra",
    "password": "...",
    "host": "localhost",
    "port": 5432,
    "database": "ai_infrastructure"
  },
  "ai-infrastructure/redis-password": "...",
  "ai-infrastructure/jwt-secret": "...",
  "ai-infrastructure/cloudflare-token": "...",
  "ai-infrastructure/github-pat": "ghp_..."
}
```

**Python Integration:**
```python
# packages/core/src/ai_core/secrets.py
import boto3
from functools import lru_cache

class SecretsManager:
    def __init__(self, region: str = "us-east-1", prefix: str = "ai-infrastructure/"):
        self.client = boto3.client("secretsmanager", region_name=region)
        self.prefix = prefix

    @lru_cache(maxsize=100)
    def get_secret(self, name: str) -> str:
        """Retrieve secret with caching."""
        response = self.client.get_secret_value(SecretId=f"{self.prefix}{name}")
        return response["SecretString"]

    def get_api_keys(self) -> dict:
        """Load all API keys at startup."""
        return {
            "anthropic": self.get_secret("anthropic-api-key"),
            "openai": self.get_secret("openai-api-key"),
            "cloudflare": self.get_secret("cloudflare-token"),
            "github": self.get_secret("github-pat"),
        }
```

### Cloudflare Integration (Paid Account)

Cloudflare provides DNS management, CDN, DDoS protection, SSL certificates, and advanced features with your paid account.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CLOUDFLARE INTEGRATION                               │
└─────────────────────────────────────────────────────────────────────────────┘

                              INTERNET
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │       CLOUDFLARE        │
                    │                         │
                    │  ┌───────────────────┐  │
                    │  │   DNS MANAGEMENT  │  │
                    │  │  ─────────────────│  │
                    │  │  A     → Server IP│  │
                    │  │  CNAME → Aliases  │  │
                    │  │  MX    → Mail     │  │
                    │  │  TXT   → Verify   │  │
                    │  └───────────────────┘  │
                    │                         │
                    │  ┌───────────────────┐  │
                    │  │   CDN / CACHING   │  │
                    │  │  ─────────────────│  │
                    │  │  Static assets    │  │
                    │  │  Edge locations   │  │
                    │  │  Compression      │  │
                    │  └───────────────────┘  │
                    │                         │
                    │  ┌───────────────────┐  │
                    │  │  SECURITY LAYER   │  │
                    │  │  ─────────────────│  │
                    │  │  DDoS protection  │  │
                    │  │  WAF rules        │  │
                    │  │  Bot management   │  │
                    │  │  Rate limiting    │  │
                    │  └───────────────────┘  │
                    │                         │
                    │  ┌───────────────────┐  │
                    │  │   SSL/TLS         │  │
                    │  │  ─────────────────│  │
                    │  │  Free certificates│  │
                    │  │  Full (strict)    │  │
                    │  │  Auto-renewal     │  │
                    │  └───────────────────┘  │
                    └────────────┬────────────┘
                                 │
                                 ▼
                         YOUR SERVER
```

**Infrastructure Agent Cloudflare Tools:**
```python
# services/agents/infra_agent/src/infra_agent/tools/cloudflare.py
import httpx
from typing import Optional

class CloudflareTools:
    """Cloudflare API client using Global API Key (paid account)."""
    BASE_URL = "https://api.cloudflare.com/client/v4"

    def __init__(self, api_key: str, email: str, account_id: str):
        self.headers = {
            "X-Auth-Key": api_key,
            "X-Auth-Email": email,
            "Content-Type": "application/json"
        }
        self.account_id = account_id
        self._zones: dict[str, str] = {}  # domain -> zone_id mapping

    async def list_zones(self) -> list[dict]:
        """List all zones in the account."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/zones",
                headers=self.headers,
                params={"account.id": self.account_id}
            )
            data = response.json()
            for zone in data.get("result", []):
                self._zones[zone["name"]] = zone["id"]
            return data["result"]

    async def add_dns_record(self, zone_id: str, name: str, content: str,
                            type: str = "A", proxied: bool = True, ttl: int = 1):
        """Add a DNS record for a new domain."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/zones/{zone_id}/dns_records",
                headers=self.headers,
                json={
                    "type": type, "name": name, "content": content,
                    "proxied": proxied, "ttl": ttl
                }
            )
            return response.json()

    async def create_zone(self, domain: str) -> dict:
        """Add a new domain/zone to the account."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/zones",
                headers=self.headers,
                json={"name": domain, "account": {"id": self.account_id}}
            )
            return response.json()

    async def purge_cache(self, zone_id: str, files: list[str] = None):
        """Purge CDN cache for specific files or entire zone."""
        payload = {"purge_everything": True} if not files else {"files": files}
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/zones/{zone_id}/purge_cache",
                headers=self.headers,
                json=payload
            )
            return response.json()

    async def create_waf_rule(self, zone_id: str, expression: str,
                              action: str = "block", description: str = ""):
        """Create a WAF custom rule (paid feature)."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/zones/{zone_id}/rulesets/phases/http_request_firewall_custom/entrypoint",
                headers=self.headers,
                json={
                    "rules": [{
                        "expression": expression,
                        "action": action,
                        "description": description
                    }]
                }
            )
            return response.json()

    async def get_analytics(self, zone_id: str, since: str = "-1440"):
        """Get traffic analytics for the zone."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/zones/{zone_id}/analytics/dashboard",
                headers=self.headers,
                params={"since": since}
            )
            return response.json()

    async def update_ssl_settings(self, zone_id: str, mode: str = "full"):
        """Update SSL/TLS encryption mode (off, flexible, full, strict)."""
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.BASE_URL}/zones/{zone_id}/settings/ssl",
                headers=self.headers,
                json={"value": mode}
            )
            return response.json()

    async def enable_always_https(self, zone_id: str, enabled: bool = True):
        """Enable Always Use HTTPS."""
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.BASE_URL}/zones/{zone_id}/settings/always_use_https",
                headers=self.headers,
                json={"value": "on" if enabled else "off"}
            )
            return response.json()
```

**Agent Commands via Cloudflare (Paid Features):**
- Create new zones/domains in account
- Add/remove DNS records (A, AAAA, CNAME, MX, TXT)
- Purge CDN cache after deployments
- Enable/disable proxying for maintenance
- Create WAF custom rules for security
- Configure SSL/TLS modes (Full Strict recommended)
- Enable Always HTTPS redirect
- Set up Page Rules for URL routing
- Monitor traffic analytics and threats
- Configure rate limiting rules
- Manage Workers (serverless functions)
- Set up Load Balancing (if subscribed)

### GitHub Integration

GitHub provides version control, backup, and collaboration through PAT (Personal Access Token).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GITHUB INTEGRATION                                  │
└─────────────────────────────────────────────────────────────────────────────┘

    AI INFRASTRUCTURE                              GITHUB
    ──────────────────                            ────────

    ┌─────────────────────┐                 ┌─────────────────────┐
    │   /workspace        │   git push      │  Main Repository    │
    │   (Active code)     │ ───────────────▶│  AI-Infrastructure  │
    │                     │                 │                     │
    │   - Services        │                 │  - Full codebase    │
    │   - Packages        │                 │  - Agent prompts    │
    │   - Config          │                 │  - Configurations   │
    └─────────────────────┘                 └─────────────────────┘

    ┌─────────────────────┐                 ┌─────────────────────┐
    │   PAI MEMORY        │   Scheduled     │  Backup Repository  │
    │   ──────────────    │   Backup        │  ai-infra-backup    │
    │                     │ ───────────────▶│                     │
    │   - Learning/       │   (Daily)       │  - Memory snapshots │
    │   - Signals/        │                 │  - Learning history │
    │   - Work/           │                 │  - Configuration    │
    └─────────────────────┘                 └─────────────────────┘

    ┌─────────────────────┐                 ┌─────────────────────┐
    │   CONFIGURATIONS    │   Sync          │  Config Repository  │
    │   ──────────────    │ ◀──────────────▶│  ai-infra-config    │
    │                     │                 │                     │
    │   - agents.yaml     │                 │  - Versioned config │
    │   - domains.yaml    │                 │  - Change tracking  │
    │   - TELOS/          │                 │  - Rollback support │
    └─────────────────────┘                 └─────────────────────┘

USE CASES:
──────────
1. CODE BACKUP:     Daily automated backup of all code changes
2. MEMORY BACKUP:   Weekly backup of PAI memory and learnings
3. CONFIG SYNC:     Bi-directional sync of configurations
4. AGENT PROMPTS:   Version control for agent system prompts
5. COLLABORATION:   Multiple users can contribute improvements
6. ROLLBACK:        Restore previous versions if issues occur
```

**GitHub Tools for Agents:**
```python
# packages/core/src/ai_core/github.py
import httpx
import base64
from datetime import datetime

class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str, owner: str, repo: str):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.owner = owner
        self.repo = repo

    async def backup_file(self, path: str, content: str, message: str = None):
        """Backup a file to GitHub repository."""
        message = message or f"Backup: {path} at {datetime.utcnow().isoformat()}"
        encoded = base64.b64encode(content.encode()).decode()

        # Get current file SHA if exists (for update)
        sha = await self._get_file_sha(path)

        payload = {
            "message": message,
            "content": encoded,
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.BASE_URL}/repos/{self.owner}/{self.repo}/contents/{path}",
                headers=self.headers,
                json=payload
            )
            return response.json()

    async def backup_memory(self, memory_dir: str):
        """Backup entire PAI memory directory."""
        # Tar and upload memory directory
        pass

    async def create_release(self, tag: str, name: str, body: str):
        """Create a release for version tracking."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/repos/{self.owner}/{self.repo}/releases",
                headers=self.headers,
                json={"tag_name": tag, "name": name, "body": body}
            )
            return response.json()

    async def sync_config(self, local_path: str, remote_path: str):
        """Bi-directional sync of configuration files."""
        pass
```

**Automated Backup Schedule:**
```yaml
# config/backup.yaml
schedules:
  code_backup:
    cron: "0 2 * * *"        # Daily at 2 AM
    type: full
    target: AI-Infrastructure

  memory_backup:
    cron: "0 3 * * 0"        # Weekly on Sunday at 3 AM
    type: incremental
    target: ai-infra-backup
    paths:
      - pai/MEMORY/Learning
      - pai/MEMORY/Signals

  config_sync:
    cron: "*/30 * * * *"     # Every 30 minutes
    type: bidirectional
    target: ai-infra-config
    paths:
      - config/agents.yaml
      - config/domains.yaml
      - pai/TELOS/
```

---

## Database Schema

### PostgreSQL Schema

```sql
-- database/migrations/001_initial_schema.sql

-- ============================================================================
-- USERS & AUTHENTICATION
-- ============================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    display_name VARCHAR(100),
    avatar_url TEXT,
    role VARCHAR(20) DEFAULT 'user' CHECK (role IN ('user', 'admin', 'system')),
    oauth_provider VARCHAR(50),
    oauth_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_oauth ON users(oauth_provider, oauth_id);

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    ip_address INET,
    user_agent TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);

-- ============================================================================
-- CONVERSATIONS & MESSAGES
-- ============================================================================

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_conversations_user ON conversations(user_id, status);
CREATE INDEX idx_conversations_updated ON conversations(updated_at DESC);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    agent VARCHAR(50),  -- Which agent sent this
    parent_message_id UUID REFERENCES messages(id),
    token_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);
CREATE INDEX idx_messages_agent ON messages(agent);

CREATE TABLE attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100),
    size_bytes BIGINT,
    storage_path TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- TASKS & AGENT WORK
-- ============================================================================

CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id),
    parent_task_id UUID REFERENCES tasks(id),
    assigned_agent VARCHAR(50) NOT NULL,
    type VARCHAR(50) NOT NULL,
    priority INTEGER DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    status VARCHAR(20) DEFAULT 'pending'
        CHECK (status IN ('pending', 'assigned', 'in_progress', 'waiting', 'completed', 'failed', 'cancelled')),
    input JSONB NOT NULL,
    output JSONB,
    error TEXT,
    pai_phase VARCHAR(20),  -- Current PAI algorithm phase
    verification_criteria JSONB,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tasks_status ON tasks(status, priority DESC);
CREATE INDEX idx_tasks_agent ON tasks(assigned_agent, status);
CREATE INDEX idx_tasks_conversation ON tasks(conversation_id);
CREATE INDEX idx_tasks_parent ON tasks(parent_task_id);

CREATE TABLE task_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES tasks(id) ON DELETE CASCADE,
    level VARCHAR(10) CHECK (level IN ('debug', 'info', 'warning', 'error')),
    message TEXT NOT NULL,
    data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_task_logs_task ON task_logs(task_id, created_at);

-- ============================================================================
-- API USAGE & COST TRACKING
-- ============================================================================

CREATE TABLE api_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent VARCHAR(50) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd DECIMAL(10, 6) NOT NULL,
    task_id UUID REFERENCES tasks(id),
    latency_ms INTEGER,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_api_usage_timestamp ON api_usage(timestamp DESC);
CREATE INDEX idx_api_usage_agent ON api_usage(agent, timestamp DESC);
CREATE INDEX idx_api_usage_daily ON api_usage(DATE(timestamp), provider);

-- Daily summary view
CREATE MATERIALIZED VIEW api_usage_daily AS
SELECT
    DATE(timestamp) as date,
    agent,
    provider,
    model,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(cost_usd) as total_cost,
    COUNT(*) as request_count,
    AVG(latency_ms) as avg_latency_ms
FROM api_usage
GROUP BY DATE(timestamp), agent, provider, model;

-- ============================================================================
-- AUDIT LOGS
-- ============================================================================

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(20) NOT NULL,
    actor_type VARCHAR(20) NOT NULL,
    actor_id VARCHAR(100) NOT NULL,
    actor_ip INET,
    resource_type VARCHAR(50),
    resource_path TEXT,
    action VARCHAR(20) NOT NULL,
    outcome VARCHAR(20) NOT NULL,
    details JSONB,
    risk_level VARCHAR(20) DEFAULT 'low'
) PARTITION BY RANGE (timestamp);

CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX idx_audit_actor ON audit_logs(actor_type, actor_id);
CREATE INDEX idx_audit_risk ON audit_logs(risk_level, timestamp DESC);

-- ============================================================================
-- DOMAIN MANAGEMENT
-- ============================================================================

CREATE TABLE domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_name VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending'
        CHECK (status IN ('pending', 'active', 'suspended', 'deleted')),
    ssl_status VARCHAR(20) DEFAULT 'none'
        CHECK (ssl_status IN ('none', 'pending', 'active', 'expired', 'failed')),
    ssl_expires_at TIMESTAMPTZ,
    webroot_path TEXT,
    nginx_config_path TEXT,
    cloudflare_zone_id VARCHAR(100),
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_domains_status ON domains(status);
CREATE INDEX idx_domains_ssl_expires ON domains(ssl_expires_at);

-- ============================================================================
-- AGENT HEARTBEATS & STATUS
-- ============================================================================

CREATE TABLE agent_heartbeats (
    agent_name VARCHAR(50) PRIMARY KEY,
    status VARCHAR(20) DEFAULT 'unknown'
        CHECK (status IN ('starting', 'running', 'idle', 'busy', 'stopping', 'stopped', 'error', 'unknown')),
    last_heartbeat TIMESTAMPTZ,
    current_task_id UUID REFERENCES tasks(id),
    metrics JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Qdrant Collections

```python
# Vector database collections configuration

QDRANT_COLLECTIONS = {
    "memories": {
        "vector_size": 1536,
        "distance": "Cosine",
        "on_disk_payload": True,
        "indexes": {
            "tier": "keyword",
            "agent": "keyword",
            "created_at": "datetime",
            "utility_score": "float"
        }
    },
    "learnings": {
        "vector_size": 1536,
        "distance": "Cosine",
        "indexes": {
            "phase": "keyword",     # OBSERVE, THINK, PLAN, etc.
            "outcome": "keyword",   # success, failure
            "extracted_at": "datetime"
        }
    },
    "conversations": {
        "vector_size": 1536,
        "distance": "Cosine",
        "indexes": {
            "conversation_id": "keyword",
            "user_id": "keyword",
            "created_at": "datetime"
        }
    },
    "knowledge": {
        "vector_size": 1536,
        "distance": "Cosine",
        "indexes": {
            "source": "keyword",    # documentation, research, etc.
            "domain": "keyword",    # code, data, infra, etc.
            "updated_at": "datetime"
        }
    }
}
```

---

## API Specification

### REST Endpoints

```yaml
# OpenAPI 3.0 specification (summary)
openapi: "3.0.3"
info:
  title: AI Infrastructure API
  version: "1.0.0"

paths:
  # Authentication
  /api/auth/login:
    post:
      summary: Login with credentials
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                email: { type: string }
                password: { type: string }
      responses:
        200:
          description: JWT token
          content:
            application/json:
              schema:
                type: object
                properties:
                  token: { type: string }
                  expires_at: { type: string, format: date-time }

  /api/auth/oauth/{provider}:
    get:
      summary: OAuth login redirect
      parameters:
        - name: provider
          in: path
          schema: { type: string, enum: [google, github] }

  # Conversations
  /api/conversations:
    get:
      summary: List user conversations
      parameters:
        - name: status
          in: query
          schema: { type: string, enum: [active, archived] }
        - name: limit
          in: query
          schema: { type: integer, default: 20 }
        - name: cursor
          in: query
          schema: { type: string }
    post:
      summary: Create new conversation
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                title: { type: string }

  /api/conversations/{id}:
    get:
      summary: Get conversation with messages
    delete:
      summary: Archive conversation

  /api/conversations/{id}/messages:
    get:
      summary: Get messages in conversation
      parameters:
        - name: limit
          in: query
          schema: { type: integer, default: 50 }
        - name: before
          in: query
          schema: { type: string, format: uuid }
    post:
      summary: Send message to conversation
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                content: { type: string }
                attachments: { type: array, items: { type: string } }

  # Agents
  /api/agents:
    get:
      summary: List all agents with status

  /api/agents/{name}:
    get:
      summary: Get agent details and current task

  /api/agents/{name}/restart:
    post:
      summary: Restart agent (admin only)

  # Tasks
  /api/tasks:
    get:
      summary: List tasks
      parameters:
        - name: status
          in: query
          schema: { type: string }
        - name: agent
          in: query
          schema: { type: string }

  /api/tasks/{id}:
    get:
      summary: Get task details with logs

  # Domains
  /api/domains:
    get:
      summary: List managed domains
    post:
      summary: Add new domain
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                domain_name: { type: string }
                setup_ssl: { type: boolean, default: true }

  /api/domains/{id}:
    get:
      summary: Get domain details
    delete:
      summary: Remove domain

  /api/domains/{id}/deploy:
    post:
      summary: Deploy files to domain
      requestBody:
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                files: { type: array, items: { type: string, format: binary } }

  # Memory
  /api/memory/search:
    post:
      summary: Search vector memory
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                query: { type: string }
                limit: { type: integer, default: 10 }
                filters:
                  type: object
                  properties:
                    tier: { type: string }
                    agent: { type: string }

  /api/memory/learnings:
    get:
      summary: Get recent learnings
      parameters:
        - name: phase
          in: query
          schema: { type: string }

  # Health
  /api/health/live:
    get:
      summary: Liveness check

  /api/health/ready:
    get:
      summary: Readiness check

  /api/health/agents:
    get:
      summary: Agent health status

  # Usage & Costs
  /api/usage/daily:
    get:
      summary: Get daily usage summary
      parameters:
        - name: date
          in: query
          schema: { type: string, format: date }

  /api/usage/budget:
    get:
      summary: Get budget status and alerts
```

### WebSocket Protocol

```typescript
// WebSocket message types for real-time communication

// Client → Server
interface ClientMessage {
  type: "subscribe" | "unsubscribe" | "send_message" | "ping";
  payload: {
    // For subscribe/unsubscribe
    channel?: "conversation" | "agents" | "tasks";
    conversation_id?: string;

    // For send_message
    content?: string;
    attachments?: string[];
  };
  id: string;  // For request/response correlation
}

// Server → Client
interface ServerMessage {
  type:
    | "subscribed"
    | "message"
    | "message_chunk"      // Streaming response
    | "message_complete"
    | "agent_status"
    | "task_update"
    | "error"
    | "pong";
  payload: MessagePayload | AgentStatusPayload | TaskUpdatePayload | ErrorPayload;
  id?: string;  // Correlates with client request
  timestamp: string;
}

interface MessagePayload {
  message_id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  agent?: string;
  is_complete: boolean;
}

interface AgentStatusPayload {
  agent: string;
  status: "idle" | "busy" | "error" | "offline";
  current_task?: {
    id: string;
    type: string;
    progress?: number;
  };
}

interface TaskUpdatePayload {
  task_id: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  agent: string;
  progress?: number;
  output?: any;
}

interface ErrorPayload {
  code: string;
  message: string;
  details?: any;
}

// Example WebSocket flow:
// 1. Client connects with JWT in query param or header
// 2. Server validates and sends: { type: "connected", payload: { user_id: "..." } }
// 3. Client subscribes: { type: "subscribe", payload: { channel: "conversation", conversation_id: "..." } }
// 4. Server confirms: { type: "subscribed", payload: { channel: "conversation" } }
// 5. Client sends message: { type: "send_message", payload: { content: "Hello" } }
// 6. Server streams response: { type: "message_chunk", payload: { content: "Hi", is_complete: false } }
// 7. Server completes: { type: "message_complete", payload: { message_id: "...", content: "Hi there!" } }
```

---

## Developer Experience

### Local Development Setup

```bash
#!/bin/bash
# scripts/dev-setup.sh

set -e

echo "=== AI Infrastructure Development Setup ==="

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "Docker required"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Python 3.12+ required"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js 22+ required"; exit 1; }

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -e packages/core
pip install -e packages/messaging
pip install -e packages/memory
pip install -e packages/tmux_manager
pip install -e services/api
pip install -e services/supervisor
pip install -e services/agents/base

# Install development tools
pip install pytest pytest-asyncio pytest-cov black ruff mypy pre-commit

# Setup pre-commit hooks
pre-commit install

# Install frontend dependencies
cd web && npm install && cd ..

# Copy environment template
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env - please add your API keys"
fi

# Start infrastructure services
docker-compose -f docker-compose.dev.yml up -d

# Wait for services
echo "Waiting for services to be ready..."
sleep 10

# Run database migrations
python scripts/migrate.py

echo "=== Setup Complete ==="
echo "Start API: uvicorn services.api.src.api.main:app --reload"
echo "Start Web: cd web && npm run dev"
echo "Start Agents: python scripts/start-agents-dev.py"
```

### Docker Compose for Development

```yaml
# docker-compose.dev.yml
# Note: 'version' key is omitted as it's deprecated in Docker Compose v2.0+

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ai_infra
      POSTGRES_PASSWORD: dev_password
      POSTGRES_DB: ai_infrastructure
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/migrations:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ai_infra"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      QDRANT__SERVICE__GRPC_PORT: 6334

  # Mock LLM server for testing without API costs
  mock-llm:
    image: mockoon/cli:latest
    ports:
      - "8080:8080"
    volumes:
      - ./tests/mocks/llm-mock.json:/data/llm-mock.json
    command: ["--data", "/data/llm-mock.json", "--port", "8080"]

  # Observability stack (optional for dev)
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./infrastructure/prometheus:/etc/prometheus
    profiles: ["observability"]

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
    volumes:
      - ./infrastructure/grafana/dashboards:/etc/grafana/provisioning/dashboards
    profiles: ["observability"]

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
```

### Pre-commit Configuration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
        args: ['--maxkb=1000']
      - id: detect-private-key
      - id: check-merge-conflict

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies:
          - types-redis
          - types-aiofiles
        args: [--ignore-missing-imports]

  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: pytest tests/unit -x -q
        language: system
        pass_filenames: false
        always_run: true
        stages: [commit]
```

### CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: "3.12"
  NODE_VERSION: "22"

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: |
          pip install ruff mypy

      - name: Run ruff
        run: ruff check .

      - name: Run mypy
        run: mypy packages/ services/ --ignore-missing-imports

  test-python:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: |
          pip install -e packages/core
          pip install -e packages/messaging
          pip install -e packages/memory
          pip install pytest pytest-asyncio pytest-cov

      - name: Run tests
        run: |
          pytest tests/ -v --cov=packages --cov=services --cov-report=xml
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/test
          REDIS_URL: redis://localhost:6379

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'
          cache-dependency-path: web/package-lock.json

      - name: Install dependencies
        run: cd web && npm ci

      - name: Run linter
        run: cd web && npm run lint

      - name: Run tests
        run: cd web && npm test

      - name: Build
        run: cd web && npm run build

  docker-build:
    runs-on: ubuntu-latest
    needs: [lint, test-python, test-frontend]
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build API image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: infrastructure/docker/Dockerfile.api
          push: false
          tags: ai-infrastructure/api:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Build Web image
        uses: docker/build-push-action@v5
        with:
          context: ./web
          file: infrastructure/docker/Dockerfile.web
          push: false
          tags: ai-infrastructure/web:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Testing Strategy

```python
# tests/conftest.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def mock_redis():
    """Mock Redis client for unit tests."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.hset = AsyncMock(return_value=True)
    redis.hgetall = AsyncMock(return_value={})
    redis.publish = AsyncMock(return_value=1)
    return redis

@pytest.fixture
async def mock_qdrant():
    """Mock Qdrant client for unit tests."""
    qdrant = AsyncMock()
    qdrant.search = AsyncMock(return_value=[])
    qdrant.upsert = AsyncMock(return_value=None)
    return qdrant

@pytest.fixture
async def mock_claude():
    """Mock Claude API for unit tests."""
    claude = AsyncMock()
    claude.messages.create = AsyncMock(return_value=MagicMock(
        content=[MagicMock(text="Mock response")],
        usage=MagicMock(input_tokens=100, output_tokens=50)
    ))
    return claude

@pytest.fixture
def mock_openai_embeddings():
    """Mock OpenAI embeddings for unit tests."""
    mock = AsyncMock()
    mock.embeddings.create = AsyncMock(return_value=MagicMock(
        data=[MagicMock(embedding=[0.1] * 1536)]
    ))
    return mock


# Example test structure:
# tests/
# ├── unit/
# │   ├── packages/
# │   │   ├── test_messaging.py
# │   │   ├── test_memory.py
# │   │   └── test_core.py
# │   └── services/
# │       ├── test_api.py
# │       └── test_agents.py
# ├── integration/
# │   ├── test_agent_communication.py
# │   ├── test_memory_lifecycle.py
# │   └── test_api_endpoints.py
# └── e2e/
#     ├── test_conversation_flow.py
#     └── test_domain_management.py
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Project setup, Docker Compose (Redis, Qdrant, PostgreSQL)
- [ ] Core packages: config, logging, messaging
- [ ] Memory package with OpenAI embeddings + Qdrant
- [ ] PAI memory structure setup
- [ ] Basic tmux manager

### Phase 2: Agent Framework (Week 3-4)
- [ ] Base agent class with Claude integration
- [ ] Supervisor agent with routing logic
- [ ] First domain agent (code_agent)
- [ ] Inter-agent communication via Redis
- [ ] PAI Algorithm integration

### Phase 3: Multi-Agent System (Week 5-6)
- [ ] Remaining agents (data, infra, research, qa)
- [ ] Agent health monitoring
- [ ] Task orchestration patterns
- [ ] PAI hook system
- [ ] Learning signal capture

### Phase 4: Infrastructure Agent (Week 7)
- [ ] Nginx configuration tools
- [ ] Domain management (add/remove)
- [ ] SSL/Certbot integration
- [ ] Docker management tools
- [ ] SSH access setup

### Phase 5: API & Backend (Week 8-9)
- [ ] FastAPI application setup
- [ ] Authentication (JWT + OAuth)
- [ ] WebSocket real-time chat
- [ ] File upload handling
- [ ] Domain management API

### Phase 6: Web Portal (Week 10-11)
- [ ] Next.js setup with shadcn/ui
- [ ] Authentication pages
- [ ] Chat interface with streaming
- [ ] Agent dashboard
- [ ] Domain management UI

### Phase 7: Voice & Polish (Week 12)
- [ ] OpenAI Whisper integration (STT)
- [ ] OpenAI TTS integration
- [ ] Voice UI components
- [ ] Installer script
- [ ] Documentation

---

## Environment Variables

```bash
# .env.example

# === PAID API SERVICES ===
ANTHROPIC_API_KEY=sk-ant-...           # Claude API
OPENAI_API_KEY=sk-...                   # Embeddings, Whisper, TTS

# === AWS SECRETS MANAGER ===
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_SECRETS_PREFIX=ai-infrastructure/  # Prefix for all secrets

# === CLOUDFLARE (Paid Account) ===
CLOUDFLARE_API_KEY=...                 # Global API Key (Account Settings)
CLOUDFLARE_EMAIL=your@email.com        # Account email
CLOUDFLARE_ACCOUNT_ID=...              # Account ID
CLOUDFLARE_ZONE_IDS=zone1,zone2,...    # Comma-separated Zone IDs for managed domains

# === GITHUB ===
GITHUB_PAT=ghp_...                     # Personal Access Token
GITHUB_OWNER=your-username             # GitHub username or org
GITHUB_REPO=ai-infrastructure-backup   # Backup repository
GITHUB_BRANCH=main                     # Branch for backups

# === FREE INFRASTRUCTURE ===
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=ai_infra
POSTGRES_PASSWORD=<from-aws-secrets>
POSTGRES_DB=ai_infrastructure

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=<from-aws-secrets>

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=<from-aws-secrets>

# === APPLICATION ===
JWT_SECRET=<from-aws-secrets>
JWT_ALGORITHM=HS256
JWT_EXPIRY_HOURS=24

# === DOMAINS ===
PRIMARY_DOMAIN=portal.example.com
API_DOMAIN=api.example.com
WEBROOT_BASE=/var/www

# === SSH ===
SSH_PORT=22
SSH_ALLOWED_USERS=root,admin
```

---

## Quick Start (After Implementation)

```bash
# One-line install
curl -fsSL https://raw.githubusercontent.com/user/AI-Infrastructure/main/install.sh | bash

# Or manual setup
git clone https://github.com/user/AI-Infrastructure.git
cd AI-Infrastructure
cp .env.example .env
# Edit .env with your API keys

# Start infrastructure
docker-compose up -d

# Start agents
./scripts/start-agents.sh

# Access
# Web Portal: https://portal.your-domain.com
# SSH: ssh root@your-server then `tmux attach -t ai-infrastructure`
```

---

## Next Steps

1. **Review this plan** - Does this architecture meet your needs?
2. **Clarify requirements** - Any specific features to add/remove?
3. **Begin implementation** - Start with Phase 1 foundation

Ready to proceed when you approve this plan.
