# Development Guide

This guide covers setting up a local development environment for Wyld Fyre AI.

## Prerequisites

- Python 3.12+
- Node.js 22+
- Docker & Docker Compose
- Redis (via Docker)
- PostgreSQL (via Docker)

## Quick Start

```bash
# 1. Clone repository
git clone git@github.com:alexandriashai/wyldfyre-ai.git /home/wyld-core
cd /home/wyld-core

# 2. Copy environment file
cp .env.example .env
# Edit .env with your API keys

# 3. Install dependencies
make install

# 4. Start infrastructure
make dev

# 5. Start agents
make agents
```

## Development Workflow

### Running Services

```bash
# Start everything
make dev

# Start individual services
make dev-api    # API on :8000
make dev-web    # Web on :3000
```

### Code Quality

```bash
# Format code
make format

# Run linters
make lint

# Type checking
make typecheck

# Run tests
make test
```

### Database

```bash
# Run migrations
make db-migrate

# Reset database
make db-reset  # WARNING: Destroys data
```

## IDE Setup

### VS Code

Recommended extensions:
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- ESLint (dbaeumer.vscode-eslint)
- Prettier (esbenp.prettier-vscode)
- Tailwind CSS IntelliSense

Settings (`.vscode/settings.json`):
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.formatting.provider": "none",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  }
}
```

## Debugging

### API

```bash
# Run with debugger
cd services/api
python -m debugpy --listen 5678 --wait-for-client -m uvicorn src.api.main:app --reload
```

### Agents

Agent logs are written to `/home/wyld-data/logs/agents/`.

```bash
# Tail agent logs
make agent-logs

# View specific agent
tail -f /home/wyld-data/logs/agents/code_agent.log
```

## Common Issues

### Port Already in Use

```bash
# Find process using port
lsof -i :8000
# Kill it or use different port
```

### Docker Permission Denied

```bash
sudo usermod -aG docker $USER
# Log out and back in
```

### Redis Connection Failed

```bash
# Check Redis is running
docker-compose ps ai-redis
# Restart if needed
docker-compose restart ai-redis
```
