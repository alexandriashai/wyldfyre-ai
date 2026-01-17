# Claude.md - Wyld Fyre AI Project Context

## Project Overview

Wyld Fyre AI is a self-hosted, installable multi-agent AI system that enables autonomous Claude agents to collaborate, learn, and manage server resources. The user-facing supervisor agent is named **Wyld**. It integrates Daniel Miessler's PAI (Personal AI Infrastructure) framework for continuous self-improvement through a 7-phase algorithmic cycle.

**Status**: Implementation phase

**License**: MIT (Copyright 2026 by Allie Eden)

## Architecture Summary

### Multi-Agent System

The system uses 6 specialized agents coordinated by a Supervisor:

| Agent | Purpose | Permission Level |
|-------|---------|------------------|
| Wyld (Supervisor) | Task routing, orchestration, user interaction | 3 (highest) |
| Code Agent | Git, file operations, code analysis, testing | 2 |
| Data Agent | SQL, data analysis, ETL, backups | 2 |
| Infra Agent | Docker, Nginx, SSL, domain management | 2 |
| Research Agent | Web search, documentation, synthesis | 1 |
| QA Agent | Testing, code review, security, validation | 1 |

### PAI Integration (The Algorithm)

```
OBSERVE → THINK → PLAN → BUILD → EXECUTE → VERIFY → LEARN
```

Each phase extracts learnings and stores them in the memory system.

### Memory System (3-Tier)

- **HOT** (Redis): Real-time task traces, 24-hour retention
- **WARM** (Qdrant): Synthesized learnings, 30-day retention, searchable
- **COLD** (File archive): Immutable historical reference, 365-day retention

## Technology Stack

### Backend (Python 3.12.3)
- FastAPI for REST API and WebSocket
- SQLAlchemy with async support
- Redis for messaging (Pub/Sub, Streams)
- Qdrant for vector storage (embeddings, RAG)
- PostgreSQL for relational data
- libtmux/tmuxp for agent process management

### Frontend (Node.js 22.19.0)
- Next.js 14 with App Router
- TypeScript
- shadcn/ui + Tailwind CSS
- Zustand for state management
- @tanstack/react-query for API calls
- socket.io-client for WebSocket

### Infrastructure
- Docker + Docker Compose
- Nginx 1.28.0 (TLS termination, domain routing)
- Let's Encrypt + Certbot for SSL
- Prometheus, Grafana, Loki for monitoring

### External Services (Paid)
- Anthropic Claude API (all agents)
- OpenAI (embeddings, Whisper, TTS)
- AWS Secrets Manager
- Cloudflare API
- GitHub

## Directory Structure (Planned)

```
AI-Infrastructure/
├── packages/                 # Shared Python libraries
│   ├── core/                # Config, logging, exceptions, metrics
│   ├── messaging/           # Redis pub/sub and message bus
│   ├── memory/              # Qdrant, embeddings, PAI memory
│   └── tmux_manager/        # Tmux session orchestration
├── services/
│   ├── api/                 # FastAPI backend
│   ├── supervisor/          # Supervisor agent
│   ├── agents/
│   │   ├── base/           # Base agent class
│   │   ├── code_agent/
│   │   ├── data_agent/
│   │   ├── infra_agent/
│   │   ├── research_agent/
│   │   └── qa_agent/
│   └── voice/              # Speech-to-text/text-to-speech
├── web/                     # Next.js frontend
├── database/                # PostgreSQL migrations, models, seeds
├── infrastructure/          # Docker, Nginx, systemd, scripts
├── pai/
│   ├── TELOS/              # Mission, vision, values
│   ├── MEMORY/             # Learning phases, signals
│   └── hooks/              # Event hooks
└── config/                  # Configuration files
```

## Key Documentation

- **ARCHITECTURE.md**: Comprehensive technical architecture (~3,775 lines)
- **BUILD_PLAN.md**: 7-phase implementation roadmap (~1,678 lines)
- **README.md**: Project entry point

## Port Assignments

| Service | Port |
|---------|------|
| Web Portal (Next.js) | 3000 |
| Grafana | 3001 |
| Loki | 3100 |
| PostgreSQL | 5432 |
| Qdrant | 6333 |
| Redis | 6379 |
| FastAPI | 8000 |
| Voice Service | 8001 |
| Prometheus | 9090 |

## Security Model

- **3 Docker Networks**: Frontend (public), Backend (agents), Data (databases)
- **Permission Levels**: 0-3 based on agent capabilities
- **JWT Authentication**: For API access
- **Input Validation**: All user inputs sanitized
- **Audit Logging**: All security-relevant events logged

## Development Guidelines

### Code Style
- Python: Follow PEP 8, use type hints, async/await patterns
- TypeScript: Strict mode, ESLint + Prettier
- Use structured JSON logging in production

### Communication Patterns
- Agents communicate exclusively via Redis (no shared memory)
- Each agent loads context from memory before responding
- Use correlation IDs to track requests across services

### Error Handling
- Implement circuit breakers for external API calls
- Use exponential backoff for retries
- Log all errors with full context

### Testing
- Unit tests for all business logic
- Integration tests for agent communication
- E2E tests for critical user flows

## Common Tasks

### Starting Development
```bash
# Start infrastructure services
docker-compose -f docker-compose.dev.yml up -d

# Start agents in tmux
./scripts/start-agents.sh
```

### Adding a New Agent
1. Create agent directory in `services/agents/`
2. Extend base agent class
3. Define tools and permissions
4. Add configuration in `config/agents.yaml`
5. Update Supervisor routing logic

### Adding a New Domain
1. Add entry to `config/domains.yaml`
2. Run domain provisioning via Infra Agent
3. Certbot will auto-provision SSL

## Environment Variables

Required environment variables (store in AWS Secrets Manager for production):

```
ANTHROPIC_API_KEY
OPENAI_API_KEY
AWS_REGION
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
CLOUDFLARE_API_KEY
CLOUDFLARE_EMAIL
CLOUDFLARE_ACCOUNT_ID
GITHUB_PAT
POSTGRES_PASSWORD
REDIS_PASSWORD
JWT_SECRET
```

## Key Patterns

### Task Flow
1. User sends request via Web Portal
2. FastAPI receives and publishes to Redis
3. Supervisor routes to appropriate agent(s)
4. Agent executes task using available tools
5. Results published back via Redis
6. WebSocket pushes response to client
7. Learning extracted and stored in memory

### Agent Communication
- **Sequential**: One agent after another
- **Parallel**: Multiple agents simultaneously
- **Peer Consultation**: Agent asks another for input
- **Escalation**: Agent escalates to Supervisor

## Resource Requirements

**Server**: 64GB RAM, 8 cores, NVMe RAID

| Component | RAM | Cores |
|-----------|-----|-------|
| PostgreSQL | 8GB | 2 |
| Qdrant | 8GB | 2 |
| Redis | 2GB | 1 |
| 6 Agents | 24GB | 6 |
| FastAPI | 4GB | 2 |
| Next.js | 2GB | 1 |
| Voice Service | 2GB | 1 |
| Monitoring | 2.5GB | 1.5 |

Note: Agents are I/O-bound (waiting on Claude API), not CPU-bound.

## Build Phases

1. **Foundation**: Docker, core packages (messaging, memory, tmux manager)
2. **Agent Framework**: Base agent, Supervisor, Code Agent
3. **Multi-Agent System**: Remaining agents, orchestration patterns
4. **Infrastructure Tools**: Nginx, SSL, Docker, Cloudflare management
5. **API & Backend**: FastAPI, authentication, WebSocket, domains API
6. **Web Portal**: Next.js frontend, chat, dashboards
7. **Voice & Polish**: Voice capabilities, installer, documentation
