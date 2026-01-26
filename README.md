<div align="center">

```
██╗    ██╗██╗   ██╗██╗     ██████╗     ███████╗██╗   ██╗██████╗ ███████╗
██║    ██║╚██╗ ██╔╝██║     ██╔══██╗    ██╔════╝╚██╗ ██╔╝██╔══██╗██╔════╝
██║ █╗ ██║ ╚████╔╝ ██║     ██║  ██║    █████╗   ╚████╔╝ ██████╔╝█████╗
██║███╗██║  ╚██╔╝  ██║     ██║  ██║    ██╔══╝    ╚██╔╝  ██╔══██╗██╔══╝
╚███╔███╔╝   ██║   ███████╗██████╔╝    ██║        ██║   ██║  ██║███████╗
 ╚══╝╚══╝    ╚═╝   ╚══════╝╚═════╝     ╚═╝        ╚═╝   ╚═╝  ╚═╝╚══════╝
                            A I   I N F R A S T R U C T U R E
```

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://python.org)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://docker.com)

**Self-hosted multi-agent AI infrastructure that learns and improves itself**

[Features](#features) • [Quick Start](#quick-start) • [Architecture](#architecture) • [Documentation](#documentation) • [Contributing](#contributing)

</div>

---

## What is Wyld Fyre AI?

Wyld Fyre AI is a production-grade, self-hosted AI platform where specialized agents collaborate to manage infrastructure, write code, analyze data, and continuously learn from every interaction.

Talk to **Wyld**, your intelligent AI supervisor, and let the team of specialized agents handle the rest.

Built on the **[PAI (Personal AI Infrastructure)](https://github.com/danielmiessler/Personal_AI_Infrastructure)** framework by Daniel Miessler, it implements a 7-phase learning algorithm that extracts insights from every task and improves future performance.

## Features

### Multi-Agent System

Six specialized AI agents coordinated by the Supervisor:

| Agent | Role | Capabilities |
|-------|------|--------------|
| **Wyld** (Supervisor) | Orchestration & User Interface | Task routing, conversation management, agent coordination |
| **Code Agent** | Software Development | Git operations, file management, code analysis, refactoring |
| **Data Agent** | Data Operations | SQL queries, ETL pipelines, backups, data transformation |
| **Infra Agent** | Infrastructure | Docker, Nginx, SSL certificates, system monitoring |
| **Research Agent** | Information Gathering | Web research, documentation, knowledge synthesis |
| **QA Agent** | Quality Assurance | Testing, code review, security validation, linting |

### Continuous Learning (PAI Framework)

The PAI-powered memory system ensures your AI gets smarter with every interaction:

```
┌─────────────────────────────────────────────────────────────────┐
│                     3-TIER MEMORY SYSTEM                        │
├─────────────────────────────────────────────────────────────────┤
│  HOT (Redis)     │ Active context, session state, quick recall │
│  WARM (Qdrant)   │ Semantic search, vector embeddings, RAG     │
│  COLD (Files)    │ Long-term storage, patterns, learned prefs  │
└─────────────────────────────────────────────────────────────────┘
```

### Full-Featured Workspace

- **Code Editor**: Monaco-based editor with syntax highlighting
- **Integrated Terminal**: Full shell access with tmux integration
- **Git Integration**: Branch management, commits, diffs in the UI
- **Project Management**: Task tracking with agent assignments
- **Voice Interface**: Speech-to-text and text-to-speech

### Complete Observability

Built-in monitoring stack with Prometheus, Grafana, and Loki for full visibility into your AI infrastructure.

## Architecture

```
                              ┌─────────────────────┐
                              │    Web Interface    │
                              │    (Next.js 14)     │
                              └──────────┬──────────┘
                                         │
                              ┌──────────▼──────────┐
                              │     API Gateway     │
                              │     (FastAPI)       │
                              └──────────┬──────────┘
                                         │
           ┌─────────────────────────────┼─────────────────────────────┐
           │                             │                             │
           ▼                             ▼                             ▼
┌─────────────────────┐       ┌─────────────────────┐       ┌─────────────────────┐
│     Supervisor      │       │    Agent Workers    │       │   Memory System     │
│       (Wyld)        │◄─────►│  Code│Data│Infra   │       │  Redis│Qdrant│File  │
│                     │       │  Research│QA        │       │                     │
└─────────────────────┘       └─────────────────────┘       └─────────────────────┘
           │                             │                             │
           └─────────────────────────────┼─────────────────────────────┘
                                         │
                              ┌──────────▼──────────┐
                              │    PostgreSQL       │
                              │    (Persistence)    │
                              └─────────────────────┘
```

### Technology Stack

| Layer | Technologies |
|-------|--------------|
| **Frontend** | Next.js 14, React, TypeScript, Tailwind CSS, shadcn/ui |
| **Backend** | Python 3.12, FastAPI, SQLAlchemy (async), Pydantic |
| **AI** | Claude API (Anthropic), OpenAI (embeddings, voice) |
| **Data** | PostgreSQL, Qdrant (vectors), Redis (cache/messaging) |
| **Infrastructure** | Docker, Nginx, Let's Encrypt (SSL), Certbot |
| **Monitoring** | Prometheus, Grafana, Loki |

## Quick Start

### Prerequisites

- Docker 20.10+ and Docker Compose
- 16GB RAM minimum (64GB recommended for production)
- API keys: Anthropic (required), OpenAI (optional, for voice)

### Installation

```bash
# Clone the repository
git clone https://github.com/wyldfyre-ai/wyld-core.git
cd wyld-core

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys (ANTHROPIC_API_KEY required)

# Start all services
docker compose up -d

# Verify services are running
docker compose ps
```

### Access the Application

| Service | URL | Description |
|---------|-----|-------------|
| Web Portal | http://localhost:3000 | Main interface |
| API | http://localhost:8000 | Backend API |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Grafana | http://localhost:3001 | Monitoring dashboard |

### Start the Supervisor

```bash
# Start Wyld and all agent workers
make agents-start

# Check status
make agents-status

# View logs
make agents-attach
```

## Project Structure

```
wyld-core/
├── agents/              # Agent implementations (code, data, infra, qa, research)
├── packages/            # Shared libraries
│   ├── agents/          # Base agent framework
│   ├── core/            # Core utilities
│   └── memory/          # Memory system (HOT/WARM/COLD)
├── services/
│   ├── api/             # FastAPI backend
│   ├── supervisor/      # Wyld supervisor agent
│   └── voice/           # Voice I/O service
├── web/                 # Next.js frontend
├── pai/                 # PAI framework (TELOS, hooks)
├── infrastructure/      # Docker, Nginx, monitoring configs
└── docs/                # Additional documentation
```

## Documentation

- [Architecture Guide](ARCHITECTURE.md) - Detailed technical architecture
- [Development Guide](docs/DEVELOPMENT.md) - Local development setup
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions

## Development

```bash
# Install dependencies
make install

# Start development environment (hot reload)
make dev

# Run tests
make test

# Run linting
make lint

# Format code
make format
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## Port Reference

| Port | Service |
|------|---------|
| 3000 | Web Portal |
| 3001 | Grafana |
| 3100 | Loki |
| 5432 | PostgreSQL |
| 6333 | Qdrant |
| 6379 | Redis |
| 8000 | API |
| 8001 | Voice Service |
| 9090 | Prometheus |

## Install as PWA

Wyld Fyre AI is a Progressive Web App:

- **Desktop**: Click the install icon in your browser's address bar
- **iOS**: Share > Add to Home Screen
- **Android**: Menu > Install app

## PAI Framework & Wyld Fyre Enhancements

Wyld Fyre AI implements Daniel Miessler's **[PAI (Personal AI Infrastructure)](https://github.com/danielmiessler/Personal_AI_Infrastructure)** framework with significant enhancements for production use.

### What PAI Provides (Foundation)

| Component | Description |
|-----------|-------------|
| **TELOS** | Mission, beliefs, goals, and strategies for agent behavior |
| **7-Phase Learning** | Extract → Assess → Distill → Store → Retrieve → Apply → Refine |
| **Memory Tiers** | Conceptual Hot/Warm/Cold architecture |
| **Hooks System** | Lifecycle hooks for extending agent behavior |

### What Wyld Fyre Adds (Enhancements)

| Enhancement | PAI Concept | Wyld Fyre Implementation |
|-------------|-------------|--------------------------|
| **Multi-Agent Orchestration** | Single agent focus | 6 specialized agents + Supervisor with intelligent routing |
| **Memory Backend** | Conceptual tiers | Redis (HOT) + Qdrant vectors (WARM) + File system (COLD) |
| **Real-time Collaboration** | Async patterns | WebSocket streams, live agent status, task handoffs |
| **Full Web IDE** | CLI-based | Monaco editor, terminal, Git UI, project management |
| **Infrastructure Tools** | Manual setup | Docker, Nginx, SSL, domain management as agent capabilities |
| **Production Stack** | Development focus | Prometheus, Grafana, Loki monitoring out of the box |
| **Voice Interface** | Text-only | Speech-to-text and text-to-speech integration |
| **PWA Support** | Web interface | Installable app with offline capabilities |

### Architectural Differences

```
PAI (Conceptual)              Wyld Fyre (Production)
─────────────────             ──────────────────────
Single Agent        →         Multi-Agent Team
File-based Memory   →         Redis + Qdrant + PostgreSQL
Manual Orchestration →        Supervisor Auto-routing
CLI Interface       →         Full Web IDE + Voice
Development Tools   →         Production Monitoring Stack
```

Wyld Fyre AI takes PAI's powerful conceptual framework and transforms it into a complete, self-hosted production system with enterprise-grade tooling, multi-agent collaboration, and full observability

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development setup
- Code style guidelines
- Pull request process
- Issue reporting

## Security

Found a vulnerability? Please review our [Security Policy](SECURITY.md) for responsible disclosure guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

Copyright (c) 2026 Allie Eden

## Acknowledgments

- [Daniel Miessler](https://danielmiessler.com) for the PAI framework
- [Anthropic](https://anthropic.com) for Claude
- The open-source community

---

<div align="center">

**Built with Claude by Anthropic**

</div>
