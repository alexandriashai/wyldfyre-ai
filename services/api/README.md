# API Service

The FastAPI backend for Wyld Fyre AI, providing REST and WebSocket APIs for the web interface and agent communication.

## Overview

The API service is the central hub connecting:
- Web frontend (Next.js)
- Supervisor agent (Wyld)
- Specialized agents
- Memory system
- External services

## Endpoints

### Chat (`/api/chat`)

Real-time conversation with the AI system:
- `POST /api/chat/message` - Send a message
- `WS /api/chat/stream` - WebSocket for streaming responses

### Conversations (`/api/conversations`)

Conversation management:
- `GET /api/conversations` - List conversations
- `GET /api/conversations/{id}` - Get conversation
- `POST /api/conversations` - Create conversation
- `DELETE /api/conversations/{id}` - Delete conversation

### Projects (`/api/projects`)

Project and task management:
- `GET /api/projects` - List projects
- `POST /api/projects` - Create project
- `GET /api/projects/{id}/tasks` - Get project tasks

### Agents (`/api/agents`)

Agent status and control:
- `GET /api/agents/status` - Get all agent statuses
- `POST /api/agents/{name}/restart` - Restart an agent

### Files (`/api/files`)

File system operations:
- `GET /api/files/tree` - Get directory tree
- `GET /api/files/content` - Read file content
- `POST /api/files/content` - Write file content

### Memory (`/api/memory`)

Memory system access:
- `GET /api/memory/search` - Semantic search
- `POST /api/memory/store` - Store a memory
- `GET /api/memory/stats` - Memory statistics

## Running

### Development

```bash
# From project root
make dev-api

# Or directly
cd services/api
uvicorn src.api.main:app --reload --port 8000
```

### Production

```bash
docker compose up api
```

## Configuration

Environment variables:
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `QDRANT_URL`: Qdrant server URL
- `JWT_SECRET`: Secret for JWT tokens
- `CORS_ORIGINS`: Allowed CORS origins

## API Documentation

Interactive docs available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Testing

```bash
cd services/api
pytest tests/
```
