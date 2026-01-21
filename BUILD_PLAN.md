# AI Infrastructure - Build Plan

This document provides specific, actionable steps for building the Multi-Agent AI Infrastructure. Use this as a reference during development to track progress and ensure all components are implemented correctly.

---

## Table of Contents

1. [Phase 1: Foundation](#phase-1-foundation)
2. [Phase 2: Agent Framework](#phase-2-agent-framework)
3. [Phase 3: Multi-Agent System](#phase-3-multi-agent-system)
4. [Phase 4: Infrastructure Agent Tools](#phase-4-infrastructure-agent-tools)
5. [Phase 5: API & Backend](#phase-5-api--backend)
6. [Phase 6: Web Portal](#phase-6-web-portal)
7. [Phase 7: Voice & Polish](#phase-7-voice--polish)

---

## Phase 1: Foundation

**Goal**: Set up project structure, Docker infrastructure, and core shared packages.

### Step 1.1: Project Structure Setup

Create the base directory structure:

```bash
mkdir -p packages/{core,messaging,memory,tmux_manager}/src
mkdir -p services/{api,supervisor,voice}/src
mkdir -p services/agents/{base,code_agent,data_agent,infra_agent,research_agent,qa_agent}/src
mkdir -p web/src/{app,components,hooks,lib,stores}
mkdir -p database/{migrations,seeds,models}
mkdir -p infrastructure/{docker,nginx,systemd,scripts}
mkdir -p config/{tmux,prompts}
mkdir -p pai/{.claude/commands,MEMORY/{Learning/{OBSERVE,THINK,PLAN,BUILD,EXECUTE,VERIFY,LEARN,ALGORITHM},Signals/{ratings,sentiment,behavioral,verification},Work/{active,archive}},TELOS,hooks}
mkdir -p tests/{unit,integration,e2e}
mkdir -p docs
```

- [ ] **1.1.1** Create root configuration files
  - `pyproject.toml` - Root Python project with workspace config
  - `.gitignore` - Python, Node, IDE, env files
  - `.env.example` - All environment variables documented
  - `Makefile` - Common commands (dev, build, test, lint)
  - `.pre-commit-config.yaml` - Code quality hooks

- [ ] **1.1.2** Create Docker Compose files
  - `docker-compose.yml` - Production configuration
  - `docker-compose.dev.yml` - Development overrides

### Step 1.2: Docker Infrastructure

- [ ] **1.2.1** Create `docker-compose.yml` with services:
  ```yaml
  services:
    postgres:     # Port 5432, 8GB memory limit
    qdrant:       # Port 6333, 8GB memory limit
    redis:        # Port 6379, 2GB memory limit (host install preferred)
    prometheus:   # Port 9090
    grafana:      # Port 3001
    loki:         # Port 3100
  ```

- [ ] **1.2.2** Create Dockerfiles in `infrastructure/docker/`:
  - `Dockerfile.api` - FastAPI service
  - `Dockerfile.agent` - Python agent runtime
  - `Dockerfile.web` - Next.js frontend
  - `Dockerfile.voice` - Voice service

- [ ] **1.2.3** Create Docker network configuration:
  - `ai-frontend` - Public-facing (Nginx, Next.js)
  - `ai-backend` - Internal (FastAPI, Redis, Agents)
  - `ai-data` - Database access (PostgreSQL, Qdrant)

- [ ] **1.2.4** Verify infrastructure starts correctly:
  ```bash
  docker-compose up -d postgres qdrant
  docker-compose ps  # All services healthy
  ```

### Step 1.3: Core Package (`packages/core`)

Location: `packages/core/src/ai_core/`

- [ ] **1.3.1** Create `packages/core/pyproject.toml`:
  ```toml
  [project]
  name = "ai-core"
  dependencies = [
    "pydantic>=2.0",
    "pydantic-settings",
    "structlog",
    "boto3",
    "prometheus-client",
    "opentelemetry-api",
    "opentelemetry-sdk",
    "opentelemetry-exporter-otlp"
  ]
  ```

- [ ] **1.3.2** Create `config.py`:
  - `Settings` class using pydantic-settings
  - Load from environment variables
  - AWS Secrets Manager integration for sensitive values
  - Validation for required API keys

- [ ] **1.3.3** Create `logging.py`:
  - Structured logging with structlog
  - JSON format for production
  - Console format for development
  - Correlation ID tracking
  - Log levels per component

- [ ] **1.3.4** Create `exceptions.py`:
  - `AIInfrastructureError` - Base exception
  - `ConfigurationError` - Missing/invalid config
  - `AgentError` - Agent-specific errors
  - `CommunicationError` - Inter-agent messaging
  - `MemoryError` - Vector DB/retrieval errors

- [ ] **1.3.5** Create `metrics.py`:
  - Prometheus metrics definitions
  - Agent task counters
  - API request histograms
  - LLM token/cost counters
  - Redis message counters

- [ ] **1.3.6** Create `tracing.py`:
  - OpenTelemetry setup
  - Tracer provider configuration
  - Span helpers for agents

- [ ] **1.3.7** Create `secrets.py`:
  - AWS Secrets Manager client
  - Secret retrieval with caching (`@lru_cache`)
  - `get_secret(name)` method
  - `get_api_keys()` for startup loading
  - Prefix-based secret organization

- [ ] **1.3.8** Create `circuit_breaker.py`:
  - `CircuitState` enum (CLOSED, OPEN, HALF_OPEN)
  - `CircuitBreaker` class
  - Failure threshold tracking
  - Automatic recovery with timeout
  - Half-open state testing

- [ ] **1.3.9** Create `__init__.py` files:
  - Export all public classes and functions
  - Version information

### Step 1.4: Messaging Package (`packages/messaging`)

Location: `packages/messaging/src/ai_messaging/`

- [ ] **1.4.1** Create `packages/messaging/pyproject.toml`:
  ```toml
  [project]
  name = "ai-messaging"
  dependencies = ["redis>=5.0", "tenacity", "ai-core"]
  ```

- [ ] **1.4.2** Create `protocols.py`:
  - `Message` dataclass with fields:
    - id, timestamp, source, target, type, priority, payload, pai
  - `MessageType` enum: task, result, handoff, query, heartbeat, learn
  - Message serialization/deserialization

- [ ] **1.4.3** Create `bus.py`:
  - `MessageBus` class
  - Redis connection management
  - Channel naming conventions
  - Connection pooling

- [ ] **1.4.4** Create `publisher.py`:
  - `Publisher` class
  - Publish to specific agent
  - Broadcast to all agents
  - Priority queue support
  - Message TTL handling

- [ ] **1.4.5** Create `subscriber.py`:
  - `Subscriber` class
  - Subscribe to agent-specific channel
  - Subscribe to broadcast channel
  - Message handler registration
  - Graceful unsubscribe

- [ ] **1.4.6** Create `streams.py`:
  - Redis Streams for task queues
  - Consumer groups for agent pools
  - Message acknowledgment
  - Dead letter queue integration

- [ ] **1.4.7** Create `retry.py`:
  - Retry strategies with tenacity
  - Exponential backoff configuration
  - Retry decorators for different operation types
  - Integration with circuit breaker from core package

- [ ] **1.4.8** Create `dlq.py`:
  - Dead letter queue management
  - Failed message storage
  - Replay functionality
  - Automatic cleanup

### Step 1.5: Memory Package (`packages/memory`)

Location: `packages/memory/src/ai_memory/`

- [ ] **1.5.1** Create `packages/memory/pyproject.toml`:
  ```toml
  [project]
  name = "ai-memory"
  dependencies = ["qdrant-client", "openai>=1.0", "aiofiles", "ai-core", "ai-messaging"]
  ```

- [ ] **1.5.2** Create `schemas.py`:
  - `MemoryEntry` dataclass
  - `MemoryTier` enum (hot, warm, cold)
  - `MemoryMetadata` with timestamps, scores
  - Collection schemas for Qdrant

- [ ] **1.5.3** Create `embeddings.py`:
  - `EmbeddingService` class
  - OpenAI text-embedding-3-small integration
  - Batch embedding for efficiency
  - Embedding cache (Redis-based)
  - Cost tracking per embedding

- [ ] **1.5.4** Create `qdrant_store.py`:
  - `QdrantStore` class
  - Collection creation/management
  - Vector upsert operations
  - Similarity search with filters
  - Scroll/pagination support

- [ ] **1.5.5** Create `retriever.py`:
  - `MemoryRetriever` class
  - Semantic search across collections
  - Hybrid search (vector + keyword)
  - Relevance scoring
  - Context assembly for agents

- [ ] **1.5.6** Create `lifecycle.py`:
  - `MemoryManager` class
  - Hot tier (Redis) management
  - Warm tier (Qdrant) promotion
  - Cold tier (file archive) demotion
  - Utility score calculation
  - Maintenance tasks

- [ ] **1.5.7** Create `signals.py`:
  - `SignalType` enum
  - `LearningSignal` dataclass
  - `SignalProcessor` class
  - Score updates from signals
  - Learning extraction

- [ ] **1.5.8** Create `pai_memory.py`:
  - PAI memory directory integration
  - Learning/ directory management
  - Signals/ directory management
  - Work/ active/archive handling
  - File-based memory persistence

### Step 1.6: Tmux Manager Package (`packages/tmux_manager`)

Location: `packages/tmux_manager/src/ai_tmux/`

- [ ] **1.6.1** Create `packages/tmux_manager/pyproject.toml`:
  ```toml
  [project]
  name = "ai-tmux"
  dependencies = ["libtmux", "tmuxp", "ai-core", "ai-messaging"]
  ```

- [ ] **1.6.2** Create `config.py`:
  - Tmux session configuration
  - Window layout definitions
  - Agent-to-window mapping

- [ ] **1.6.3** Create `session.py`:
  - `TmuxSession` class
  - Create session: `ai-infrastructure`
  - Window management (create, destroy)
  - Pane splitting if needed

- [ ] **1.6.4** Create `agent_runner.py`:
  - `AgentRunner` class
  - Start agent in tmux window
  - Send commands to agent window
  - Capture agent output
  - Graceful stop with SIGTERM

- [ ] **1.6.5** Create `monitor.py`:
  - `AgentWatchdog` class
  - Heartbeat monitoring
  - Crash detection
  - Automatic restart with backoff
  - Health status reporting

- [ ] **1.6.6** Create `recovery.py`:
  - Agent crash recovery logic
  - Restart attempt tracking
  - Backoff intervals (10s, 30s, 60s)
  - Max restart attempts (3)
  - Alert on recovery failure

- [ ] **1.6.7** Create `config/tmux/session.yaml`:
  - tmuxp configuration file
  - Window definitions for all 6 agents
  - Monitor and logs windows
  - Startup commands

### Step 1.7: PAI Structure Setup

- [ ] **1.7.1** Create PAI TELOS files:
  - `pai/TELOS/mission.md` - System mission statement
  - `pai/TELOS/vision.md` - Long-term vision
  - `pai/TELOS/values.md` - Core values and principles
  - `pai/TELOS/priorities.md` - Current priorities
  - `pai/TELOS/success.md` - Success metrics

- [ ] **1.7.2** Create PAI hook templates:
  - `pai/hooks/session_start.py`
  - `pai/hooks/session_end.py`
  - `pai/hooks/user_prompt.py`
  - `pai/hooks/task_complete.py`
  - `pai/hooks/tool_use.py`

- [ ] **1.7.3** Initialize memory directories with `.gitkeep`:
  - All `Learning/` subdirectories
  - All `Signals/` subdirectories
  - `Work/active/` and `Work/archive/`

### Step 1.8: Database Setup

- [ ] **1.8.1** Create initial PostgreSQL migrations:
  - `database/migrations/001_create_users.sql`
  - `database/migrations/002_create_conversations.sql`
  - `database/migrations/003_create_messages.sql`
  - `database/migrations/004_create_attachments.sql`
  - `database/migrations/005_create_tasks.sql`
  - `database/migrations/006_create_audit_logs.sql`
  - `database/migrations/007_create_domains.sql`

- [ ] **1.8.2** Create database models (SQLAlchemy):
  - `database/models/user.py`
  - `database/models/conversation.py`
  - `database/models/message.py`
  - `database/models/attachment.py`
  - `database/models/task.py`
  - `database/models/audit_log.py`
  - `database/models/domain.py`

- [ ] **1.8.3** Create seed data:
  - `database/seeds/admin_user.sql`
  - `database/seeds/default_domains.sql`

### Step 1.9: Phase 1 Verification

- [ ] **1.9.1** Write unit tests:
  - `tests/unit/test_core_config.py`
  - `tests/unit/test_messaging_protocols.py`
  - `tests/unit/test_memory_embeddings.py`

- [ ] **1.9.2** Integration test:
  - Docker services start and connect
  - Redis pub/sub works
  - Qdrant accepts vectors
  - PostgreSQL migrations run

---

## Phase 2: Agent Framework

**Goal**: Build the base agent class and implement Supervisor + Code Agent with communication.

### Step 2.1: Base Agent Class (`services/agents/base`)

Location: `services/agents/base/src/agent_base/`

- [ ] **2.1.1** Create `services/agents/base/pyproject.toml`:
  ```toml
  [project]
  name = "agent-base"
  dependencies = ["anthropic", "httpx", "ai-core", "ai-messaging", "ai-memory"]
  ```

- [ ] **2.1.2** Create `agent.py`:
  - `BaseAgent` abstract class
  - Agent lifecycle: init, start, stop
  - Claude API client initialization
  - System prompt loading from AGENT.md
  - Message loop with Redis subscription
  - Heartbeat publishing

- [ ] **2.1.3** Create `tools.py`:
  - `Tool` base class
  - Tool registration system
  - Tool execution with error handling
  - Tool result formatting
  - Permission level checking

- [ ] **2.1.4** Create `memory.py`:
  - Agent-specific memory interface
  - Context retrieval for prompts
  - Memory storage after responses
  - Relevance-based context assembly

- [ ] **2.1.5** Create `communication.py`:
  - `AgentCommunication` class
  - Send message to specific agent
  - Broadcast message
  - Wait for response with timeout
  - Handoff to another agent

- [ ] **2.1.6** Create `algorithm.py`:
  - PAI 7-phase algorithm implementation
  - Phase tracking per task
  - Phase transition logic
  - Failure traceback handling
  - Learning extraction triggers

### Step 2.2: Supervisor Agent (`services/supervisor`)

Location: `services/supervisor/src/supervisor/`

- [ ] **2.2.1** Create `services/supervisor/pyproject.toml`:
  ```toml
  [project]
  name = "supervisor-agent"
  dependencies = ["agent-base"]
  ```

- [ ] **2.2.2** Create `services/supervisor/AGENT.md`:
  - System prompt for supervisor
  - Role definition
  - Available tools
  - Communication protocols
  - Escalation procedures

- [ ] **2.2.3** Create `main.py`:
  - Supervisor agent entry point
  - Initialize with Level 3 permissions
  - Start message loop
  - User message handling

- [ ] **2.2.4** Create `router.py`:
  - `TaskRouter` class
  - Analyze incoming tasks
  - Determine best agent(s) for task
  - Route single or parallel tasks
  - Handle agent unavailability

- [ ] **2.2.5** Create `orchestrator.py`:
  - `Orchestrator` class
  - Sequential task execution
  - Parallel task execution
  - Result aggregation
  - Task dependency resolution

- [ ] **2.2.6** Create `aggregator.py`:
  - `ResultAggregator` class
  - Combine results from multiple agents
  - Conflict resolution
  - Summary generation for user

- [ ] **2.2.7** Create `algorithm.py`:
  - Supervisor-specific PAI algorithm
  - Task-level phase tracking
  - Verification criteria management
  - Learning signal collection

### Step 2.3: Code Agent (`services/agents/code_agent`)

Location: `services/agents/code_agent/src/code_agent/`

- [ ] **2.3.1** Create `services/agents/code_agent/pyproject.toml`

- [ ] **2.3.2** Create `services/agents/code_agent/AGENT.md`:
  - System prompt for code agent
  - Coding standards
  - Git workflow
  - Available tools
  - Security guidelines

- [ ] **2.3.3** Create `main.py`:
  - Code agent entry point
  - Level 1 permissions
  - Tool registration

- [ ] **2.3.4** Create `tools/git.py`:
  - Git clone, pull, push
  - Branch management
  - Commit with messages
  - Diff viewing
  - Status checking

- [ ] **2.3.5** Create `tools/file_ops.py`:
  - File read/write within workspace
  - Directory operations
  - Search (grep, find)
  - Permission validation

- [ ] **2.3.6** Create `tools/code_analysis.py`:
  - Syntax checking
  - Linting integration
  - Type checking
  - Dependency analysis

- [ ] **2.3.7** Create `tools/testing.py`:
  - Run pytest
  - Run npm test
  - Coverage reporting
  - Test result parsing

### Step 2.4: Inter-Agent Communication

- [ ] **2.4.1** Test supervisor → code_agent task routing:
  - User sends coding request
  - Supervisor routes to code_agent
  - Code agent executes
  - Result returns to supervisor
  - Supervisor responds to user

- [ ] **2.4.2** Implement handoff pattern:
  - Agent A delegates to Agent B
  - Ownership transfer
  - Result propagation

- [ ] **2.4.3** Implement broadcast pattern:
  - Knowledge sharing messages
  - All agents receive
  - Optional acknowledgment

### Step 2.5: Agent Configuration

- [ ] **2.5.1** Create `config/agents.yaml`:
  ```yaml
  agents:
    supervisor:
      permission_level: 3
      tools: [route, orchestrate, escalate]
    code_agent:
      permission_level: 1
      tools: [git, file_ops, code_analysis, testing]
    # ... other agents
  ```

- [ ] **2.5.2** Create `config/prompts/supervisor.md`
- [ ] **2.5.3** Create `config/prompts/code_agent.md`

### Step 2.6: Phase 2 Verification

- [ ] **2.6.1** Unit tests:
  - Base agent message handling
  - Router logic
  - Tool execution

- [ ] **2.6.2** Integration test:
  - Start supervisor in tmux
  - Start code_agent in tmux
  - Send task through Redis
  - Verify end-to-end flow

---

## Phase 3: Multi-Agent System

**Goal**: Implement remaining agents and complete orchestration patterns.

### Step 3.1: Data Agent (`services/agents/data_agent`)

- [ ] **3.1.1** Create `AGENT.md` with data agent system prompt
- [ ] **3.1.2** Create `main.py` with Level 1 permissions
- [ ] **3.1.3** Create `tools/sql.py`:
  - PostgreSQL query execution
  - Query validation (prevent destructive ops)
  - Result formatting
  - Parameterized queries only

- [ ] **3.1.4** Create `tools/analysis.py`:
  - Data profiling
  - Statistical summaries
  - Trend detection

- [ ] **3.1.5** Create `tools/etl.py`:
  - Data transformation
  - CSV/JSON import/export
  - Data validation

- [ ] **3.1.6** Create `tools/backup.py`:
  - Database backup triggers
  - Backup verification
  - Restore procedures

### Step 3.2: Infrastructure Agent (`services/agents/infra_agent`)

- [ ] **3.2.1** Create `AGENT.md` with infra agent system prompt
- [ ] **3.2.2** Create `main.py` with Level 2 permissions
- [ ] **3.2.3** Create `tools/nginx.py` (detailed in Phase 4)
- [ ] **3.2.4** Create `tools/docker.py` (detailed in Phase 4)
- [ ] **3.2.5** Create `tools/certbot.py` (detailed in Phase 4)
- [ ] **3.2.6** Create `tools/domains.py` (detailed in Phase 4)
- [ ] **3.2.7** Create `tools/systemd.py` (detailed in Phase 4)
- [ ] **3.2.8** Create `tools/cloudflare.py` (detailed in Phase 4)

### Step 3.3: Research Agent (`services/agents/research_agent`)

- [ ] **3.3.1** Create `AGENT.md` with research agent system prompt
- [ ] **3.3.2** Create `main.py` with Level 1 permissions
- [ ] **3.3.3** Create `tools/web_search.py`:
  - Search engine integration
  - Result parsing
  - Content extraction

- [ ] **3.3.4** Create `tools/documentation.py`:
  - API documentation fetching
  - Library documentation
  - Code examples extraction

- [ ] **3.3.5** Create `tools/synthesis.py`:
  - Information summarization
  - Knowledge compilation
  - Learning document creation

### Step 3.4: QA Agent (`services/agents/qa_agent`)

- [ ] **3.4.1** Create `AGENT.md` with QA agent system prompt
- [ ] **3.4.2** Create `main.py` with Level 1 permissions
- [ ] **3.4.3** Create `tools/testing.py`:
  - Test execution
  - Test coverage analysis
  - Test generation suggestions

- [ ] **3.4.4** Create `tools/review.py`:
  - Code review checklists
  - Best practice validation
  - Style guide compliance

- [ ] **3.4.5** Create `tools/security.py`:
  - Security scanning
  - Dependency vulnerability check
  - OWASP checklist validation

- [ ] **3.4.6** Create `tools/validation.py`:
  - Input/output validation
  - API contract testing
  - Schema validation

### Step 3.5: Agent Health Monitoring

- [ ] **3.5.1** Implement heartbeat system:
  - Each agent publishes heartbeat every 30s
  - Heartbeat contains: status, current_task, memory_usage
  - Redis key: `agent:{name}:heartbeat`

- [ ] **3.5.2** Implement watchdog:
  - Monitor all agent heartbeats
  - Detect stale heartbeats (>90s)
  - Trigger restart procedure
  - Alert on repeated failures

- [ ] **3.5.3** Create health dashboard data:
  - Agent status API endpoint
  - Current task visibility
  - Resource usage metrics

### Step 3.6: Task Orchestration Patterns

- [ ] **3.6.1** Implement sequential pattern:
  ```
  Supervisor → Agent A → Agent B → Supervisor
  ```
  - Task chain definition
  - Result passing between agents
  - Error propagation

- [ ] **3.6.2** Implement parallel pattern:
  ```
  Supervisor → [Agent A, Agent B, Agent C] → Supervisor
  ```
  - Concurrent task dispatch
  - Result collection with timeout
  - Partial result handling

- [ ] **3.6.3** Implement peer consultation:
  ```
  Agent A ←→ Agent B
  ```
  - Direct agent queries
  - Response timeout handling
  - No supervisor involvement

- [ ] **3.6.4** Implement escalation pattern:
  ```
  Agent → Supervisor → Human (if needed)
  ```
  - Escalation triggers
  - Human approval interface
  - Timeout and fallback

### Step 3.7: PAI Hook System

- [ ] **3.7.1** Implement SessionStart hook:
  - Load agent context
  - Restore active tasks
  - Initialize memory retrieval

- [ ] **3.7.2** Implement SessionEnd hook:
  - Persist agent state
  - Archive completed tasks
  - Cleanup resources

- [ ] **3.7.3** Implement UserPromptSubmit hook:
  - Capture user input
  - Route to supervisor
  - Start algorithm OBSERVE phase

- [ ] **3.7.4** Implement Stop (task complete) hook:
  - Trigger VERIFY phase
  - Collect learning signals
  - Store task outcome

- [ ] **3.7.5** Implement PreToolUse hook:
  - Validate tool permissions
  - Log tool intent
  - Check rate limits

- [ ] **3.7.6** Implement PostToolUse hook:
  - Capture tool result
  - Update memory
  - Track metrics

### Step 3.8: Learning Signal Capture

- [ ] **3.8.1** Implement explicit signals:
  - User rating capture (1-5)
  - User correction detection
  - User acceptance tracking

- [ ] **3.8.2** Implement implicit signals:
  - Task success/failure
  - Retry detection
  - Abandonment detection

- [ ] **3.8.3** Implement behavioral signals:
  - Response edit tracking
  - Follow-up question detection
  - Context switch detection

- [ ] **3.8.4** Signal processing:
  - Update memory utility scores
  - Store signals in PAI structure
  - Trigger learning extraction

### Step 3.9: Phase 3 Verification

- [ ] **3.9.1** All 6 agents start in tmux session
- [ ] **3.9.2** Inter-agent communication works
- [ ] **3.9.3** Orchestration patterns function
- [ ] **3.9.4** Health monitoring active
- [ ] **3.9.5** Learning signals captured

---

## Phase 4: Infrastructure Agent Tools

**Goal**: Complete Infrastructure Agent with domain, Nginx, SSL, and Docker management.

### Step 4.1: Nginx Configuration Tools

Location: `services/agents/infra_agent/src/infra_agent/tools/nginx.py`

- [ ] **4.1.1** Read Nginx configuration:
  - Parse `/etc/nginx/nginx.conf`
  - List sites-available
  - List sites-enabled
  - Get virtual host details

- [ ] **4.1.2** Create virtual host:
  - Template-based generation
  - Server block configuration
  - Location block setup
  - SSL configuration inclusion

- [ ] **4.1.3** Manage virtual hosts:
  - Enable site (symlink)
  - Disable site (remove symlink)
  - Delete site configuration
  - Backup before changes

- [ ] **4.1.4** Nginx operations:
  - Test configuration (`nginx -t`)
  - Reload (`systemctl reload nginx`)
  - View error logs
  - View access logs

### Step 4.2: SSL/Certbot Integration

Location: `services/agents/infra_agent/src/infra_agent/tools/certbot.py`

- [ ] **4.2.1** Certificate operations:
  - Request new certificate
  - List existing certificates
  - Check certificate expiry
  - Revoke certificate

- [ ] **4.2.2** Auto-renewal:
  - Check renewal status
  - Force renewal if needed
  - Verify post-renewal hooks

- [ ] **4.2.3** Certificate validation:
  - Verify cert matches domain
  - Check cert chain validity
  - Validate key permissions

### Step 4.3: Docker Management

Location: `services/agents/infra_agent/src/infra_agent/tools/docker.py`

- [ ] **4.3.1** Container operations:
  - List containers
  - Start/stop/restart container
  - View container logs
  - Inspect container

- [ ] **4.3.2** Image operations:
  - List images
  - Pull image
  - Build image
  - Remove unused images

- [ ] **4.3.3** Compose operations:
  - Start services
  - Stop services
  - View service status
  - Scale services

- [ ] **4.3.4** Health checks:
  - Container health status
  - Resource usage per container
  - Network connectivity

### Step 4.4: Domain Management

Location: `services/agents/infra_agent/src/infra_agent/tools/domains.py`

- [ ] **4.4.1** Add domain workflow:
  1. Create `/var/www/{domain}/` directory
  2. Set proper permissions (www-data)
  3. Create Nginx config from template
  4. Enable site (symlink)
  5. Request SSL certificate
  6. Reload Nginx
  7. Verify domain accessible

- [ ] **4.4.2** Remove domain workflow:
  1. Disable site (remove symlink)
  2. Archive web root to backup location
  3. Remove Nginx config
  4. Optionally revoke SSL cert
  5. Reload Nginx
  6. Update domains.yaml

- [ ] **4.4.3** Deploy to domain:
  1. Pull/copy new files to web root
  2. Set file permissions
  3. Clear any caches
  4. Verify deployment
  5. Rollback capability

- [ ] **4.4.4** Domain configuration:
  - Create `config/domains.yaml`:
    ```yaml
    domains:
      - name: example.com
        type: static
        webroot: /var/www/example
        ssl: true
      - name: api.example.com
        type: proxy
        upstream: localhost:8000
        ssl: true
    ```

### Step 4.5: Cloudflare Integration

Location: `services/agents/infra_agent/src/infra_agent/tools/cloudflare.py`

- [ ] **4.5.1** Zone management:
  - List all zones in account
  - Create new zone for domain
  - Get zone details
  - Cache zone ID mappings

- [ ] **4.5.2** DNS record management:
  - Add DNS record (A, CNAME, etc.)
  - Update existing records
  - Delete records
  - List records for zone

- [ ] **4.5.3** Cache operations:
  - Purge entire cache
  - Purge specific files
  - Development mode toggle

- [ ] **4.5.4** WAF/Security (paid features):
  - Create custom WAF rules
  - Manage firewall rules
  - Rate limiting configuration

### Step 4.6: Systemd Management

Location: `services/agents/infra_agent/src/infra_agent/tools/systemd.py`

- [ ] **4.6.1** Service operations:
  - Start/stop/restart service
  - Enable/disable service
  - View service status
  - View service logs (journalctl)

- [ ] **4.6.2** Service creation:
  - Create service unit file
  - Reload systemd daemon
  - Enable and start service

### Step 4.7: SSH Access Configuration

- [ ] **4.7.1** Create `infrastructure/scripts/setup-ssh.sh`:
  - SSH hardening configuration
  - Key-only authentication
  - Fail2ban setup
  - Allowed users whitelist

- [ ] **4.7.2** Document SSH access:
  - Connection instructions
  - Tmux attach command
  - Window navigation

### Step 4.8: Infrastructure Templates

- [ ] **4.8.1** Create `infrastructure/nginx/sites-available/template.conf`:
  - Static site template
  - Reverse proxy template
  - SSL configuration snippet

- [ ] **4.8.2** Create `infrastructure/nginx/snippets/`:
  - `ssl-params.conf`
  - `security-headers.conf`
  - `proxy-params.conf`

- [ ] **4.8.3** Create systemd unit templates:
  - `infrastructure/systemd/ai-infrastructure.service`
  - `infrastructure/systemd/ai-api.service`
  - `infrastructure/systemd/ai-agents.service`

### Step 4.9: Phase 4 Verification

- [ ] **4.9.1** Add test domain via infra agent
- [ ] **4.9.2** SSL certificate obtained
- [ ] **4.9.3** Domain accessible via HTTPS
- [ ] **4.9.4** Docker containers manageable
- [ ] **4.9.5** Cloudflare DNS configured
- [ ] **4.9.6** Remove domain cleans up properly

---

## Phase 5: API & Backend

**Goal**: Build FastAPI backend with authentication, WebSocket, and domain management API.

### Step 5.1: FastAPI Application Setup

Location: `services/api/src/api/`

- [ ] **5.1.1** Create `services/api/pyproject.toml`:
  ```toml
  [project]
  name = "ai-api"
  dependencies = [
    "fastapi", "uvicorn[standard]", "python-multipart",
    "python-jose[cryptography]", "passlib[bcrypt]",
    "sqlalchemy[asyncio]", "asyncpg",
    "ai-core", "ai-messaging", "ai-memory"
  ]
  ```

- [ ] **5.1.2** Create `main.py`:
  - FastAPI app initialization
  - CORS configuration
  - Middleware registration
  - Router inclusion
  - Lifespan handlers (startup/shutdown)

- [ ] **5.1.3** Create `config.py`:
  - API-specific settings
  - Database URL construction
  - JWT configuration
  - Rate limit settings

- [ ] **5.1.4** Create `dependencies.py`:
  - Database session dependency
  - Redis connection dependency
  - Current user dependency
  - Permission checking

### Step 5.2: Authentication System

- [ ] **5.2.1** Create `middleware/auth.py`:
  - JWT token validation
  - User extraction from token
  - Optional auth for public endpoints

- [ ] **5.2.2** Create `routes/auth.py`:
  - `POST /auth/register` - User registration
  - `POST /auth/login` - Login, return JWT
  - `POST /auth/logout` - Invalidate token
  - `POST /auth/refresh` - Refresh token
  - `GET /auth/me` - Current user info

- [ ] **5.2.3** Create `services/auth_service.py`:
  - Password hashing with bcrypt
  - JWT token generation
  - Token validation
  - User lookup and creation

- [ ] **5.2.4** OAuth integration (optional):
  - GitHub OAuth
  - Google OAuth
  - OAuth callback handling

### Step 5.3: WebSocket Real-Time Chat

- [ ] **5.3.1** Create `websocket/manager.py`:
  - `ConnectionManager` class
  - Connection tracking per user
  - Message broadcasting
  - Connection cleanup

- [ ] **5.3.2** Create `websocket/handlers.py`:
  - Message handler routing
  - Chat message handling
  - Agent status updates
  - Error handling

- [ ] **5.3.3** Create `routes/chat.py`:
  - `WS /ws/chat` - WebSocket endpoint
  - Authentication on connect
  - Message format validation
  - Redis subscription for agent responses

- [ ] **5.3.4** Implement streaming:
  - Token-by-token streaming from agents
  - Partial message updates
  - Typing indicators

### Step 5.4: Core API Routes

- [ ] **5.4.1** Create `routes/conversations.py`:
  - `GET /conversations` - List user conversations
  - `POST /conversations` - Create new conversation
  - `GET /conversations/{id}` - Get conversation history
  - `DELETE /conversations/{id}` - Delete conversation

- [ ] **5.4.2** Create `routes/agents.py`:
  - `GET /agents` - List all agents with status
  - `GET /agents/{name}` - Get agent details
  - `GET /agents/{name}/logs` - Get recent logs
  - `POST /agents/{name}/restart` - Restart agent (admin)

- [ ] **5.4.3** Create `routes/tasks.py`:
  - `GET /tasks` - List tasks
  - `GET /tasks/{id}` - Get task details
  - `POST /tasks/{id}/cancel` - Cancel task

- [ ] **5.4.4** Create `routes/memory.py`:
  - `GET /memory/search` - Semantic search
  - `GET /memory/learnings` - Browse learnings
  - `GET /memory/stats` - Memory statistics

### Step 5.5: Domain Management API

- [ ] **5.5.1** Create `routes/domains.py`:
  - `GET /domains` - List all domains
  - `POST /domains` - Add new domain
  - `GET /domains/{name}` - Get domain details
  - `PUT /domains/{name}` - Update domain config
  - `DELETE /domains/{name}` - Remove domain
  - `POST /domains/{name}/deploy` - Deploy to domain
  - `POST /domains/{name}/ssl/renew` - Force SSL renewal

- [ ] **5.5.2** Create `services/domain_service.py`:
  - Domain CRUD operations
  - Delegate to infra agent
  - Track domain status
  - Validate domain format

### Step 5.6: File Upload Handling

- [ ] **5.6.1** Create `routes/files.py`:
  - `POST /files/upload` - Upload files
  - `GET /files/{id}` - Download file
  - `DELETE /files/{id}` - Delete file

- [ ] **5.6.2** File handling:
  - Size limits
  - Type validation
  - Secure storage
  - Cleanup job

### Step 5.7: Health & Metrics

- [ ] **5.7.1** Create `routes/health.py`:
  - `GET /health/live` - Liveness probe
  - `GET /health/ready` - Readiness probe
  - `GET /health/agents` - Agent health summary

- [ ] **5.7.2** Prometheus metrics endpoint:
  - `GET /metrics` - Prometheus format

### Step 5.8: Middleware & Security

- [ ] **5.8.1** Create `middleware/rate_limit.py`:
  - Per-user rate limiting
  - Per-endpoint limits
  - Redis-backed counters

- [ ] **5.8.2** Create `middleware/logging.py`:
  - Request/response logging
  - Correlation ID injection
  - Timing metrics

- [ ] **5.8.3** Create `middleware/sanitization.py`:
  - Input sanitization
  - XSS prevention
  - SQL injection prevention

- [ ] **5.8.4** Audit logging:
  - Log all security events
  - Store in PostgreSQL
  - Include actor, action, outcome

### Step 5.9: Phase 5 Verification

- [ ] **5.9.1** API starts and health checks pass
- [ ] **5.9.2** User registration and login work
- [ ] **5.9.3** WebSocket chat connects
- [ ] **5.9.4** Messages route to supervisor
- [ ] **5.9.5** Domain API functions
- [ ] **5.9.6** Rate limiting active

---

## Phase 6: Web Portal

**Goal**: Build Next.js frontend with authentication, chat, and dashboard.

### Step 6.1: Next.js Project Setup

Location: `web/`

- [ ] **6.1.1** Initialize Next.js 14 project:
  ```bash
  npx create-next-app@14 web --typescript --tailwind --app --src-dir
  ```

- [ ] **6.1.2** Install dependencies:
  ```bash
  npm install @tanstack/react-query zustand socket.io-client
  npx shadcn-ui@latest init
  ```

- [ ] **6.1.3** Configure `next.config.js`:
  - API proxy configuration
  - WebSocket upgrade handling
  - Environment variables

- [ ] **6.1.4** Configure Tailwind with shadcn/ui theme

### Step 6.2: Authentication Pages

- [ ] **6.2.1** Create `src/app/(auth)/login/page.tsx`:
  - Login form
  - Error handling
  - Remember me option
  - Link to register

- [ ] **6.2.2** Create `src/app/(auth)/register/page.tsx`:
  - Registration form
  - Validation
  - Success redirect

- [ ] **6.2.3** Create `src/lib/auth.ts`:
  - Token storage (httpOnly cookie preferred)
  - Auth state management
  - Logout function
  - Token refresh

- [ ] **6.2.4** Create auth middleware:
  - Protected route wrapper
  - Redirect to login if unauthenticated

### Step 6.3: Layout Components

- [ ] **6.3.1** Create `src/app/(dashboard)/layout.tsx`:
  - Sidebar navigation
  - Header with user menu
  - Main content area

- [ ] **6.3.2** Create `src/components/ui/sidebar.tsx`:
  - Navigation items
  - Agent status indicators
  - Collapsible sections

- [ ] **6.3.3** Create `src/components/ui/header.tsx`:
  - Logo
  - User dropdown
  - Settings link
  - Logout

### Step 6.4: Chat Interface

- [ ] **6.4.1** Create `src/app/(dashboard)/chat/page.tsx`:
  - Main chat view
  - Conversation selector
  - Message history

- [ ] **6.4.2** Create `src/components/chat/message-list.tsx`:
  - Message bubbles
  - Agent identification
  - Timestamp display
  - Code block rendering

- [ ] **6.4.3** Create `src/components/chat/message-input.tsx`:
  - Text input with markdown support
  - File attachment button
  - Voice input button
  - Send button

- [ ] **6.4.4** Create `src/components/chat/agent-status.tsx`:
  - Current agent working
  - Progress indicator
  - Agent avatar

- [ ] **6.4.5** Create `src/hooks/useChat.ts`:
  - WebSocket connection
  - Message sending
  - Message receiving
  - Connection status

- [ ] **6.4.6** Implement streaming:
  - Real-time token display
  - Typing indicator
  - Partial message updates

### Step 6.5: Agent Dashboard

- [ ] **6.5.1** Create `src/app/(dashboard)/agents/page.tsx`:
  - Agent grid/list view
  - Status overview
  - Quick actions

- [ ] **6.5.2** Create `src/components/agents/agent-card.tsx`:
  - Agent name and icon
  - Status indicator (online/offline/busy)
  - Current task
  - Memory usage

- [ ] **6.5.3** Create `src/components/agents/agent-logs.tsx`:
  - Real-time log viewer
  - Log level filtering
  - Search functionality

- [ ] **6.5.4** Create `src/app/(dashboard)/agents/[name]/page.tsx`:
  - Agent detail view
  - Recent tasks
  - Performance metrics
  - Restart button (admin)

### Step 6.6: Domain Management UI

- [ ] **6.6.1** Create `src/app/(dashboard)/domains/page.tsx`:
  - Domain list table
  - Add domain button
  - Status indicators

- [ ] **6.6.2** Create `src/components/domains/domain-table.tsx`:
  - Domain name
  - Type (static/proxy)
  - SSL status
  - Actions (edit, delete, deploy)

- [ ] **6.6.3** Create `src/components/domains/add-domain-dialog.tsx`:
  - Domain name input
  - Type selection
  - Configuration options
  - Submit and validation

- [ ] **6.6.4** Create `src/components/domains/deploy-dialog.tsx`:
  - File upload option
  - Git repo option
  - Deploy button
  - Progress indicator

### Step 6.7: Memory Browser

- [ ] **6.7.1** Create `src/app/(dashboard)/memory/page.tsx`:
  - Search interface
  - Memory statistics
  - Learning browser

- [ ] **6.7.2** Create `src/components/memory/search.tsx`:
  - Semantic search input
  - Results display
  - Relevance scores

- [ ] **6.7.3** Create `src/components/memory/learnings.tsx`:
  - Browse by phase
  - View learning content
  - Filter by date

### Step 6.8: Settings Page

- [ ] **6.8.1** Create `src/app/(dashboard)/settings/page.tsx`:
  - User profile
  - API key display (masked)
  - Notification preferences

- [ ] **6.8.2** TELOS configuration (admin):
  - Edit mission/vision/values
  - Priority management
  - Success metrics

### Step 6.9: State Management

- [ ] **6.9.1** Create `src/stores/auth-store.ts`:
  - User state
  - Auth tokens
  - Login/logout actions

- [ ] **6.9.2** Create `src/stores/chat-store.ts`:
  - Conversations list
  - Current conversation
  - Message history
  - Pending messages

- [ ] **6.9.3** Create `src/stores/agent-store.ts`:
  - Agent list
  - Agent statuses
  - Selected agent

### Step 6.10: Phase 6 Verification

- [ ] **6.10.1** Login/register flow works
- [ ] **6.10.2** Chat sends and receives messages
- [ ] **6.10.3** Streaming responses display
- [ ] **6.10.4** Agent dashboard shows status
- [ ] **6.10.5** Domain management functions
- [ ] **6.10.6** Responsive on mobile

---

## Phase 7: Voice & Polish

**Goal**: Add voice capabilities, create installer, and finalize documentation.

### Step 7.1: Voice Service Setup

Location: `services/voice/src/voice_service/`

- [ ] **7.1.1** Create `services/voice/pyproject.toml`:
  ```toml
  [project]
  name = "voice-service"
  dependencies = ["fastapi", "openai>=1.0", "pydub", "python-multipart"]
  ```

- [ ] **7.1.2** Create `main.py`:
  - FastAPI app for voice
  - Port 8001
  - Health endpoint

### Step 7.2: Speech-to-Text (Whisper)

- [ ] **7.2.1** Create `transcription.py`:
  - OpenAI Whisper API client
  - Audio format handling
  - Streaming transcription
  - Language detection

- [ ] **7.2.2** Create `routes/transcribe.py`:
  - `POST /transcribe` - Audio file upload
  - `WS /transcribe/stream` - Streaming audio

- [ ] **7.2.3** Audio processing:
  - Format conversion (WebM, MP3, WAV)
  - Chunk handling for streaming
  - Noise reduction (optional)

- [ ] **7.2.4** Create `streaming.py`:
  - Real-time audio streaming handler
  - WebSocket audio chunk management
  - Buffering and batching for API calls
  - Stream state management

### Step 7.3: Text-to-Speech

- [ ] **7.3.1** Create `synthesis.py`:
  - OpenAI TTS API client
  - Voice selection
  - Speed control
  - Audio format output

- [ ] **7.3.2** Create `routes/synthesize.py`:
  - `POST /synthesize` - Text to audio
  - `GET /synthesize/stream` - Streaming audio

- [ ] **7.3.3** Voice options:
  - Multiple voices available
  - Speed adjustment
  - Format selection (mp3, opus, etc.)

### Step 7.4: Voice UI Components

- [ ] **7.4.1** Create `src/components/voice/voice-input.tsx`:
  - Push-to-talk button
  - Continuous listening toggle
  - Audio level indicator
  - Recording status

- [ ] **7.4.2** Create `src/components/voice/voice-output.tsx`:
  - Play/pause controls
  - Audio visualization
  - Download option

- [ ] **7.4.3** Create `src/hooks/useVoice.ts`:
  - Microphone access
  - Recording management
  - Transcription API calls
  - TTS playback

### Step 7.5: Installer Script

- [ ] **7.5.1** Create `install.sh`:
  ```bash
  #!/bin/bash
  # One-line installer for AI Infrastructure
  # curl -fsSL https://raw.githubusercontent.com/user/AI-Infrastructure/main/install.sh | bash
  ```
  - Check prerequisites (Docker, Python, Node)
  - Clone repository
  - Copy .env.example to .env
  - Prompt for API keys
  - Run docker-compose up
  - Initialize database
  - Start agents
  - Print access URLs

- [ ] **7.5.2** Create `scripts/setup.sh`:
  - Development environment setup
  - Python virtual environment
  - Node dependencies
  - Pre-commit hooks

- [ ] **7.5.3** Create `scripts/start-agents.sh`:
  - Create tmux session
  - Start all agents in windows
  - Start monitoring window

- [ ] **7.5.4** Create `scripts/backup.sh`:
  - Database backup
  - Memory backup
  - Configuration backup
  - Upload to GitHub

### Step 7.6: Documentation

- [ ] **7.6.1** Update `README.md`:
  - Project overview
  - Quick start guide
  - Feature list
  - Screenshots
  - Contributing guide

- [ ] **7.6.2** Create `docs/deployment.md`:
  - Server requirements
  - Installation steps
  - Configuration guide
  - SSL setup
  - Troubleshooting

- [ ] **7.6.3** Create `docs/agents.md`:
  - Agent descriptions
  - Capabilities
  - Communication patterns
  - Extending agents

- [ ] **7.6.4** Create `docs/api.md`:
  - API reference
  - Authentication
  - WebSocket protocol
  - Example requests

- [ ] **7.6.5** Create `docs/security.md`:
  - Security model
  - Permission levels
  - Best practices
  - Incident response

### Step 7.7: Testing & Quality

- [ ] **7.7.1** Complete unit test coverage:
  - All packages tested
  - Mock external APIs
  - Edge case handling

- [ ] **7.7.2** Integration tests:
  - End-to-end flows
  - API testing
  - WebSocket testing

- [ ] **7.7.3** E2E tests with Playwright:
  - Login flow
  - Chat interaction
  - Domain management

- [ ] **7.7.4** Load testing:
  - Multiple concurrent users
  - Message throughput
  - Memory under load

### Step 7.8: CI/CD Pipeline

- [ ] **7.8.1** Create `.github/workflows/ci.yml`:
  - Lint (ruff, eslint)
  - Type check (mypy, tsc)
  - Unit tests
  - Build Docker images

- [ ] **7.8.2** Create `.github/workflows/deploy.yml`:
  - Deploy to staging
  - Run E2E tests
  - Deploy to production (manual)

### Step 7.9: Final Polish

- [ ] **7.9.1** Performance optimization:
  - Database query optimization
  - Redis caching strategy
  - Frontend bundle size

- [ ] **7.9.2** Error handling review:
  - User-friendly error messages
  - Graceful degradation
  - Retry logic verification

- [ ] **7.9.3** Accessibility:
  - Keyboard navigation
  - Screen reader support
  - Color contrast

- [ ] **7.9.4** Mobile responsiveness:
  - Touch-friendly controls
  - Viewport handling
  - Voice input on mobile

### Step 7.10: Phase 7 Verification

- [ ] **7.10.1** Voice input works in chat
- [ ] **7.10.2** Voice output for responses
- [ ] **7.10.3** Installer runs successfully
- [ ] **7.10.4** Documentation complete
- [ ] **7.10.5** All tests pass
- [ ] **7.10.6** Ready for production deployment

---

## Appendix A: Quick Reference

### Key File Paths

| Component | Location |
|-----------|----------|
| Core Package | `packages/core/src/ai_core/` |
| Messaging Package | `packages/messaging/src/ai_messaging/` |
| Memory Package | `packages/memory/src/ai_memory/` |
| Tmux Manager | `packages/tmux_manager/src/ai_tmux/` |
| API Service | `services/api/src/api/` |
| Supervisor Agent | `services/supervisor/src/supervisor/` |
| Base Agent | `services/agents/base/src/agent_base/` |
| Code Agent | `services/agents/code_agent/src/code_agent/` |
| Data Agent | `services/agents/data_agent/src/data_agent/` |
| Infra Agent | `services/agents/infra_agent/src/infra_agent/` |
| Research Agent | `services/agents/research_agent/src/research_agent/` |
| QA Agent | `services/agents/qa_agent/src/qa_agent/` |
| Voice Service | `services/voice/src/voice_service/` |
| Web Portal | `web/src/` |
| PAI Memory | `pai/MEMORY/` |
| PAI TELOS | `pai/TELOS/` |

### Port Assignments

| Service | Port |
|---------|------|
| Next.js Frontend | 3000 |
| Grafana | 3001 |
| Loki | 3100 |
| PostgreSQL | 5432 |
| Qdrant | 6333 |
| Redis | 6379 |
| FastAPI Backend | 8000 |
| Voice Service | 8001 |
| Prometheus | 9090 |

### Agent Permissions

| Agent | Level | Key Capabilities |
|-------|-------|------------------|
| Supervisor | 3 | Full system access, orchestration |
| Code Agent | 1 | Git, file ops, testing |
| Data Agent | 1 | SQL, data analysis |
| Infra Agent | 2 | Docker, Nginx, SSL, Cloudflare |
| Research Agent | 1 | Web search, documentation |
| QA Agent | 1 | Testing, security scanning |

---

## Appendix B: Development Commands

```bash
# Start infrastructure
docker-compose up -d

# Start agents (after Phase 2)
./scripts/start-agents.sh

# Run API in development
cd services/api && uvicorn src.api.main:app --reload --port 8000

# Run web in development
cd web && npm run dev

# Run tests
pytest tests/
npm test --prefix web

# Lint and format
ruff check . --fix
npm run lint --prefix web

# Database migrations
alembic upgrade head

# Attach to agent tmux session
tmux attach -t ai-infrastructure
```

---

## Appendix C: Environment Variables Checklist

Before deployment, ensure all required environment variables are set:

- [ ] `ANTHROPIC_API_KEY` - Claude API
- [ ] `OPENAI_API_KEY` - Embeddings, Whisper, TTS
- [ ] `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` - Secrets Manager
- [ ] `CLOUDFLARE_API_KEY`, `CLOUDFLARE_EMAIL`, `CLOUDFLARE_ACCOUNT_ID` - Domain/DNS management
- [ ] `GITHUB_PAT` - Code backup
- [ ] `POSTGRES_PASSWORD` - Database
- [ ] `REDIS_PASSWORD` - Message bus
- [ ] `JWT_SECRET` - Authentication

---

*This build plan should be updated as implementation progresses. Mark items complete by changing `[ ]` to `[x]`.*
