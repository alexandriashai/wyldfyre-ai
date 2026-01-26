# Supervisor Service (Wyld)

The Supervisor agent, codenamed **Wyld**, is the orchestration layer for the Wyld Fyre AI system. It manages user interactions and coordinates specialized agents.

## Overview

Wyld serves as:
- **User Interface**: Primary point of contact for all user interactions
- **Task Router**: Analyzes requests and delegates to appropriate agents
- **Orchestrator**: Coordinates multi-agent workflows
- **Memory Manager**: Maintains conversation context and learnings

## Capabilities

### Conversation Management

- Natural language understanding
- Context maintenance across sessions
- Multi-turn dialogue handling

### Task Routing

Intelligently routes tasks to specialized agents:

| Task Type | Agent | Example |
|-----------|-------|---------|
| Code operations | Code Agent | "Create a new API endpoint" |
| Data queries | Data Agent | "Show me yesterday's sales" |
| Infrastructure | Infra Agent | "Deploy to staging" |
| Research | Research Agent | "Find docs on React hooks" |
| Testing | QA Agent | "Run the test suite" |

### Multi-Agent Workflows

Coordinates complex tasks requiring multiple agents:

```
User: "Create a new feature with tests and deploy it"

Wyld orchestrates:
1. Code Agent → Write the feature
2. QA Agent → Write and run tests
3. Code Agent → Commit changes
4. Infra Agent → Deploy to staging
```

### Learning Integration

- Extracts insights from interactions
- Stores patterns in memory tiers
- Applies learnings to improve responses

## Architecture

```
┌─────────────────────────────────────────────┐
│              Supervisor (Wyld)              │
├─────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Router    │  │   Memory Manager    │  │
│  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Orchestrator│  │  TELOS Identity     │  │
│  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│            Agent Workers (Redis)            │
│  Code │ Data │ Infra │ Research │ QA       │
└─────────────────────────────────────────────┘
```

## Running

### Development

```bash
# From project root
make agents-start

# Or directly
python -m services.supervisor.main
```

### Production

The supervisor runs as part of the agent stack via tmux:

```bash
make agents-start
make agents-attach  # View tmux session
```

## Configuration

Environment variables:
- `ANTHROPIC_API_KEY`: Claude API key
- `SUPERVISOR_MODEL`: Model for supervisor (default: claude-sonnet)
- `REDIS_URL`: Redis for agent communication
- `DATABASE_URL`: PostgreSQL for persistence

## TELOS Configuration

Wyld's behavior is guided by its TELOS configuration in `pai/TELOS/`:
- Mission statement
- Core beliefs
- Strategic goals
- Behavioral guidelines

## Testing

```bash
cd services/supervisor
pytest tests/
```
