# Services - Core Application Components

This directory contains the main application services that make up the Wyld Fyre AI system.

## Service Overview

| Service | Port | Purpose | Technology |
|---------|------|---------|------------|
| api/ | 8000 | REST API, WebSocket, authentication | FastAPI |
| web/ | 3000 | User interface, dashboards | Next.js |
| supervisor/ | - | Task routing, agent orchestration | Python |
| voice/ | 8001 | Speech-to-text, text-to-speech | FastAPI |

## Service Architecture

```
                    ┌──────────────┐
                    │   Browser    │
                    └──────┬───────┘
                           │ HTTP/WS
                    ┌──────▼───────┐
                    │    Nginx     │ (TLS termination)
                    └──────┬───────┘
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │     Web     │ │     API     │ │    Voice    │
    │   (Next.js) │ │  (FastAPI)  │ │  (FastAPI)  │
    └─────────────┘ └──────┬──────┘ └─────────────┘
                           │
                    ┌──────▼───────┐
                    │    Redis     │ (Pub/Sub)
                    └──────┬───────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │ Supervisor  │ │   Agents    │ │   Memory    │
    │   (Wyld)    │ │  (6 total)  │ │  (Qdrant)   │
    └─────────────┘ └─────────────┘ └─────────────┘
```

## Development

### Starting Services

```bash
# Start all services in dev mode
make dev

# Start individual services
make dev-api    # API on :8000
make dev-web    # Web on :3000
make dev-voice  # Voice on :8001
```

### API Service

The FastAPI backend handles:
- REST endpoints for CRUD operations
- WebSocket connections for real-time updates
- JWT authentication
- Task submission to agents via Redis

```bash
cd services/api
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Key files:
- `src/api/main.py` - Application entry point
- `src/api/routes/` - API route handlers
- `src/api/websocket/` - WebSocket handlers
- `src/api/middleware/` - Authentication, logging

### Web Service

The Next.js frontend provides:
- Chat interface with Wyld
- Agent status dashboard
- Memory browser
- Settings management

```bash
cd services/web
npm run dev
```

Key files:
- `src/app/` - Next.js App Router pages
- `src/components/` - React components
- `src/hooks/` - Custom React hooks
- `src/stores/` - Zustand state stores

### Supervisor Service

The Wyld supervisor agent:
- Routes tasks to appropriate agents
- Manages agent lifecycle
- Handles escalations
- Maintains conversation context

The supervisor runs as a specialized agent, not as an HTTP service.

### Voice Service

Optional voice capabilities:
- Whisper for speech-to-text
- OpenAI TTS for text-to-speech
- Real-time transcription

```bash
cd services/voice
uvicorn src.voice_service.main:app --reload --host 0.0.0.0 --port 8001
```

## Communication Patterns

### Request Flow

1. User submits request via Web UI
2. Web calls API endpoint
3. API publishes task to Redis `agent:tasks`
4. Supervisor receives and routes to agent(s)
5. Agent executes and publishes result
6. API receives result via Redis subscription
7. WebSocket pushes update to client

### Redis Channels

| Channel | Purpose |
|---------|---------|
| `agent:tasks` | Incoming task requests |
| `agent:results` | Task completion results |
| `agent:status` | Heartbeats, status updates |
| `agent:{name}` | Direct agent communication |

## Docker Deployment

Services run in Docker containers:

```yaml
# docker-compose.yml (simplified)
services:
  ai-api:
    build: ./services/api
    ports: ["8000:8000"]
    environment:
      - REDIS_HOST=ai-redis
      - POSTGRES_HOST=ai-db

  ai-web:
    build: ./services/web
    ports: ["3000:3000"]
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Adding a New Service

1. Create directory structure:
```
services/new_service/
├── src/
│   └── new_service/
│       ├── __init__.py
│       └── main.py
├── tests/
├── Dockerfile
├── pyproject.toml
└── README.md
```

2. Add to docker-compose.yml
3. Add nginx configuration if public-facing
4. Update infrastructure/scripts as needed

## Logging

All services use structured JSON logging:

```python
from ai_core import get_logger
logger = get_logger("api")

logger.info("request_received",
    method="POST",
    path="/tasks",
    user_id="123"
)
```

Logs are centralized in `/home/wyld-data/logs/`:
- `api/*.log` - API service logs
- `web/*.log` - Web service logs (via nginx)
- `agents/*.log` - Agent logs
