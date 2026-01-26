# Memory Package

The memory system for Wyld Fyre AI, implementing the PAI (Personal AI Infrastructure) 3-tier memory architecture.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Memory System                        │
├─────────────────────────────────────────────────────────┤
│  HOT (Redis)    │ Session state, active context        │
│  WARM (Qdrant)  │ Vector embeddings, semantic search   │
│  COLD (Files)   │ Long-term patterns, learned prefs    │
└─────────────────────────────────────────────────────────┘
```

## Components

### PAI Memory (`pai_memory.py`)

Core memory manager implementing the 7-phase learning cycle:
- **Extract**: Pull insights from interactions
- **Assess**: Evaluate relevance and importance
- **Distill**: Compress into learnable patterns
- **Store**: Persist to appropriate tier
- **Retrieve**: Fetch relevant context
- **Apply**: Use in current interaction
- **Refine**: Improve based on outcomes

### TELOS (`telos.py`)

Agent identity and behavior configuration:
- Mission statements
- Core beliefs
- Strategic goals
- Behavioral guidelines

### Embeddings (`embeddings.py`)

Vector embedding generation for semantic search:
- OpenAI embeddings integration
- Embedding cache for performance
- Batch processing support

### Qdrant Client (`qdrant.py`)

Vector database interface:
- Collection management
- Semantic search
- Similarity scoring

### Skill Library (`skill_library.py`)

Learned capabilities storage:
- Skill indexing and retrieval
- Capability matching
- Usage tracking

## Usage

```python
from ai_memory import PAIMemory, TELOS

# Initialize memory
memory = PAIMemory(
    redis_url="redis://localhost:6379",
    qdrant_url="http://localhost:6333",
    cold_storage_path="/data/cold"
)

# Store a learning
await memory.store_learning(
    content="User prefers TypeScript over JavaScript",
    category="preferences",
    importance=0.8
)

# Retrieve relevant context
context = await memory.retrieve_context(
    query="What language should I use?",
    limit=5
)
```

## Configuration

Environment variables:
- `REDIS_URL`: Redis connection string
- `QDRANT_URL`: Qdrant server URL
- `COLD_STORAGE_PATH`: Path for cold tier files
- `OPENAI_API_KEY`: For embeddings generation

## Testing

```bash
cd packages/memory
pytest tests/
```
