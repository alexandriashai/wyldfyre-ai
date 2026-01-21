# Packages - Shared Python Libraries

This directory contains the core Python packages that are shared across all services and agents.

## Package Overview

| Package | Import Name | Purpose |
|---------|-------------|---------|
| core/ | ai_core | Configuration, logging, exceptions, metrics |
| messaging/ | ai_messaging | Redis pub/sub, message bus, channels |
| memory/ | ai_memory | Qdrant vectors, embeddings, PAI memory |
| agents/ | ai_agents | Base agent class, tool framework |

## Installation

All packages are installed in development mode for local development:

```bash
# From /home/wyld-core
make install

# Or manually:
pip install -e packages/core
pip install -e packages/messaging
pip install -e packages/memory
pip install -e packages/agents
```

## Package Dependencies

```
ai_core (no dependencies)
    └── ai_messaging (depends on ai_core)
    └── ai_memory (depends on ai_core)
            └── ai_agents (depends on ai_core, ai_messaging, ai_memory)
```

## Development Guidelines

### Creating a New Package

1. Create directory structure:
```
packages/your_package/
├── src/
│   └── your_package/
│       ├── __init__.py
│       └── module.py
├── tests/
│   └── test_module.py
├── pyproject.toml
└── README.md
```

2. Configure `pyproject.toml`:
```toml
[project]
name = "ai_your_package"
version = "0.1.0"
dependencies = ["ai_core"]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

3. Export public API in `__init__.py`

### Conventions

- Use async/await for I/O operations
- Type hints on all public functions
- Structured logging via structlog
- Pydantic models for data validation
- Write tests for all public interfaces

### Testing

```bash
# Run all package tests
make test

# Run specific package tests
pytest packages/core/tests/ -v
```

## Package APIs

### ai_core

```python
from ai_core import Config, get_logger, AIException

# Configuration
config = Config()
api_key = config.ANTHROPIC_API_KEY

# Logging
logger = get_logger("my_module")
logger.info("message", key="value")
```

### ai_messaging

```python
from ai_messaging import PubSub, Message

# Publish/Subscribe
pubsub = PubSub()
await pubsub.publish("agent:tasks", message)
await pubsub.subscribe("agent:results", callback)
```

### ai_memory

```python
from ai_memory import QdrantClient, embed_text

# Vector search
client = QdrantClient()
embedding = await embed_text("search query")
results = await client.search("learnings", embedding, limit=5)
```

### ai_agents

```python
from ai_agents import BaseAgent, Tool, ToolResult

class MyAgent(BaseAgent):
    def get_tools(self) -> list[Tool]:
        return [my_tool]
```

## Modifying Packages

When modifying a package:

1. Run tests before and after changes
2. Update type hints if signatures change
3. Bump version in pyproject.toml for releases
4. Document breaking changes in CHANGELOG.md
