# Agents - Specialized AI Workers

This directory contains the specialized agent implementations. Each agent has specific tools and capabilities.

## Agent Overview

| Agent | Directory | Permission | Tools | Purpose |
|-------|-----------|------------|-------|---------|
| Code | code/ | 2 | git, file ops, analysis | Development tasks |
| Data | data/ | 2 | SQL, ETL, backups | Data operations |
| Infra | infra/ | 2 | Docker, Nginx, SSL | Infrastructure |
| Research | research/ | 1 | web search, docs | Information gathering |
| QA | qa/ | 1 | testing, review | Quality assurance |

Permission levels (0-3):
- 0: Read-only
- 1: Limited write (research, testing)
- 2: Extended write (code, data, infra)
- 3: Full (Supervisor only)

## Agent Lifecycle

```
1. INITIALIZE
   └── Load configuration from config/agents.yaml
   └── Connect to Redis pub/sub
   └── Load context from memory

2. LISTEN
   └── Subscribe to agent:tasks channel
   └── Subscribe to agent:{name} channel
   └── Send heartbeat every 30s

3. RECEIVE TASK
   └── Parse task message
   └── Load relevant memory context
   └── Select appropriate tools

4. EXECUTE
   └── Run tools with Claude API
   └── Track execution trace
   └── Handle errors gracefully

5. RESPOND
   └── Publish result to agent:results
   └── Store learnings in memory
   └── Update metrics
```

## Creating a New Agent

1. **Copy template:**
```bash
cp -r agents/_template agents/my_agent
```

2. **Update configuration:**

Edit `config/agents.yaml`:
```yaml
agents:
  my_agent:
    name: "My Agent"
    description: "Description of what this agent does"
    permission_level: 1
    model: "claude-sonnet-4-20250514"
    tools:
      - my_tool_one
      - my_tool_two
```

3. **Implement agent:**

Edit `agents/my_agent/src/my_agent/agent.py`:
```python
from ai_agents import BaseAgent, Tool, ToolResult

class MyAgent(BaseAgent):
    def get_system_prompt(self) -> str:
        return """You are a specialized agent for..."""

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="my_tool",
                description="What this tool does",
                parameters={...},
                handler=self.my_tool_handler
            )
        ]

    async def my_tool_handler(self, **params) -> ToolResult:
        # Tool implementation
        return ToolResult(success=True, data={...})
```

4. **Install and test:**
```bash
make install
pytest agents/my_agent/tests/ -v
```

5. **Register with supervisor:**

Add routing logic to `services/supervisor/src/supervisor/agent.py`

## Tool Development

### Tool Structure

```python
Tool(
    name="unique_tool_name",
    description="Clear description for Claude",
    parameters={
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "..."},
            "param2": {"type": "integer", "default": 10}
        },
        "required": ["param1"]
    },
    handler=self.handler_function
)
```

### Tool Guidelines

1. **Single responsibility** - One tool, one purpose
2. **Clear descriptions** - Help Claude understand when to use
3. **Input validation** - Validate parameters before execution
4. **Error handling** - Return meaningful error messages
5. **Audit logging** - Log all tool executions

### Permission Checks

Tools should check permission levels:

```python
async def dangerous_tool_handler(self, **params) -> ToolResult:
    if self.permission_level < 2:
        return ToolResult(
            success=False,
            error="Insufficient permissions for this operation"
        )
    # Proceed with operation
```

## Agent Communication

### Direct Communication

Agents can communicate with each other:

```python
# Request help from another agent
response = await self.request_peer(
    agent="research",
    task="Find documentation for X"
)

# Escalate to supervisor
await self.escalate(
    reason="Need approval for destructive operation",
    context={...}
)
```

### Channels

| Channel | Direction | Purpose |
|---------|-----------|---------|
| `agent:tasks` | Supervisor → Agent | Task assignments |
| `agent:results` | Agent → API | Task completions |
| `agent:{name}` | Agent ↔ Agent | Direct messages |
| `agent:status` | Agent → Monitor | Heartbeats |

## Memory Integration

Agents should leverage the memory system:

```python
# Load context before responding
context = await self.memory.search(
    query=task.description,
    collection="learnings",
    limit=5
)

# Store learnings after execution
await self.memory.store(
    collection="learnings",
    text=f"Learned: {insight}",
    metadata={
        "agent": self.name,
        "task_id": task.id,
        "timestamp": datetime.now()
    }
)
```

## Testing Agents

### Unit Tests

```python
# tests/test_tools.py
async def test_my_tool():
    agent = MyAgent()
    result = await agent.my_tool_handler(param1="test")
    assert result.success
    assert "expected" in result.data
```

### Integration Tests

```python
# tests/test_integration.py
async def test_agent_task_flow():
    agent = MyAgent()
    await agent.start()

    # Simulate task
    await pubsub.publish("agent:tasks", task_message)

    # Wait for result
    result = await pubsub.wait_for("agent:results", timeout=30)
    assert result["status"] == "completed"
```

### Running Tests

```bash
# Test specific agent
pytest agents/code/tests/ -v

# Test all agents
pytest agents/*/tests/ -v
```

## Existing Agent Details

### Code Agent (code/)

Tools:
- `file_read` - Read file contents
- `file_write` - Write/create files
- `file_search` - Search code patterns
- `git_status` - Repository status
- `git_commit` - Commit changes
- `run_command` - Execute shell commands

### Data Agent (data/)

Tools:
- `sql_query` - Execute SQL queries
- `data_export` - Export data to files
- `backup_create` - Create database backups
- `qdrant_search` - Vector similarity search

### Infra Agent (infra/)

Tools:
- `docker_ps` - List containers
- `docker_logs` - View container logs
- `nginx_reload` - Reload nginx config
- `ssl_status` - Check SSL certificates
- `domain_add` - Add new domain

### Research Agent (research/)

Tools:
- `web_search` - Search the internet
- `fetch_url` - Fetch and parse URLs
- `summarize` - Summarize documents

### QA Agent (qa/)

Tools:
- `run_tests` - Execute test suites
- `code_review` - Review code changes
- `security_scan` - Security analysis
- `type_check` - Run type checker
