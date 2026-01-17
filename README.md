# Wyld Fyre AI

A self-hosted, multi-agent AI infrastructure system powered by Claude. Talk to **Wyld**, your intelligent AI supervisor, to manage tasks, infrastructure, and code.

## Features

- **Multi-Agent System**: 6 specialized AI agents coordinated by Wyld (the Supervisor)
- **PAI Integration**: Personal AI framework for continuous learning and improvement
- **Web Portal**: Modern Next.js interface for interacting with your AI team
- **Infrastructure Management**: Docker, Nginx, SSL, and domain management
- **Voice Interface**: Speech-to-text and text-to-speech capabilities
- **3-Tier Memory**: HOT (Redis), WARM (Qdrant), COLD (File) for persistent learning

## Quick Start

### One-Line Install

```bash
curl -fsSL https://raw.githubusercontent.com/alexandriashai/AI-Infrastructure/main/install.sh | bash
```

### Manual Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/alexandriashai/AI-Infrastructure.git
   cd AI-Infrastructure
   ```

2. **Copy and configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Start services**
   ```bash
   make docker-up
   ```

4. **Start agents**
   ```bash
   make agents-start
   ```

5. **Access the web portal**
   ```
   http://localhost:3000
   ```

## Architecture

### Agents

| Agent | Purpose | Permission Level |
|-------|---------|------------------|
| **Wyld** (Supervisor) | Task routing, orchestration, user interaction | 3 |
| Code Agent | Git, file operations, code analysis | 2 |
| Data Agent | SQL, data analysis, ETL, backups | 2 |
| Infra Agent | Docker, Nginx, SSL, domains | 2 |
| Research Agent | Web search, documentation | 1 |
| QA Agent | Testing, code review, security | 1 |

### Technology Stack

**Backend**
- Python 3.12.3
- FastAPI
- SQLAlchemy (async)
- Redis (messaging)
- Qdrant (vector storage)
- PostgreSQL

**Frontend**
- Next.js 14
- TypeScript
- Tailwind CSS
- shadcn/ui

**Infrastructure**
- Docker + Docker Compose
- Nginx
- Let's Encrypt (SSL)
- Prometheus + Grafana (monitoring)

## Port Assignments

| Service | Port |
|---------|------|
| Web Portal | 3000 |
| Grafana | 3001 |
| Loki | 3100 |
| PostgreSQL | 5432 |
| Qdrant | 6333 |
| Redis | 6379 |
| API | 8000 |
| Voice Service | 8001 |
| Prometheus | 9090 |

## Commands

```bash
# Development
make install       # Install all dependencies
make dev          # Start development environment
make dev-api      # Start API server
make dev-web      # Start web portal

# Agents
make agents-start  # Start all agents in tmux
make agents-stop   # Stop all agents
make agents-status # Check agent status
make agents-attach # Attach to tmux session

# Docker
make docker-up    # Start Docker services
make docker-down  # Stop Docker services
make docker-logs  # View logs

# Database
make db-migrate   # Run migrations
make db-seed      # Seed database
make db-reset     # Reset database

# Code Quality
make lint         # Run linters
make format       # Format code
make test         # Run tests
```

## Environment Variables

Required environment variables (set in `.env`):

```bash
# API Keys (Required)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Database
POSTGRES_PASSWORD=...
REDIS_PASSWORD=...

# Authentication
JWT_SECRET=...
```

See `.env.example` for all configuration options.

## Documentation

- [Architecture Guide](ARCHITECTURE.md) - Technical architecture details
- [Build Plan](BUILD_PLAN.md) - Implementation roadmap
- [Claude Guide](CLAUDE.md) - Development context

## Requirements

- **Server**: 64GB RAM, 8 cores recommended
- **Docker**: 20.10+
- **Node.js**: 22.x
- **Python**: 3.12+
- **tmux**: For agent management

## License

MIT License - Copyright 2026 by Allie Eden

## Contributing

Contributions are welcome! Please read the contributing guidelines before submitting PRs.

---

Built with Claude by Anthropic
