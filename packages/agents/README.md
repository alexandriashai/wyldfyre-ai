# Agents Package

Base agent framework for Wyld Fyre AI specialized agents.

## Overview

This package provides the foundation for building AI agents that can:
- Execute tools and capabilities
- Communicate via the messaging system
- Maintain conversation state
- Integrate with the PAI memory system

## Base Agent

The `BaseAgent` class provides:

### Core Features

- **Tool Registration**: Define and register agent capabilities
- **Message Handling**: Process incoming requests and send responses
- **State Management**: Maintain conversation and task state
- **Memory Integration**: Access HOT/WARM/COLD memory tiers
- **Error Handling**: Graceful failure and recovery

### Lifecycle Methods

```python
class BaseAgent:
    async def initialize(self) -> None:
        """Setup agent resources"""

    async def process_message(self, message: Message) -> Response:
        """Handle incoming messages"""

    async def execute_tool(self, tool: str, params: dict) -> Result:
        """Execute a registered tool"""

    async def shutdown(self) -> None:
        """Cleanup resources"""
```

## Creating an Agent

```python
from base_agent import BaseAgent, tool

class MyAgent(BaseAgent):
    name = "my_agent"
    description = "Does something useful"

    @tool(description="Greet a user")
    async def greet(self, name: str) -> str:
        return f"Hello, {name}!"

# Run the agent
agent = MyAgent()
await agent.run()
```

## Tool Decorator

Register capabilities with the `@tool` decorator:

```python
@tool(
    description="Tool description for the LLM",
    permission_level=2,  # 1=read, 2=write, 3=admin
    requires_approval=False
)
async def my_tool(self, param: str) -> str:
    return result
```

## Agent Communication

Agents communicate via Redis pub/sub:

```python
# Send to another agent
await self.send_message(
    target="code_agent",
    action="review_code",
    payload={"file": "main.py"}
)

# Broadcast to all agents
await self.broadcast(
    action="status_update",
    payload={"status": "ready"}
)
```

## Specialized Agents

Built on this framework:
- **Code Agent**: File operations, Git, code analysis
- **Data Agent**: SQL, ETL, backups
- **Infra Agent**: Docker, Nginx, system ops
- **Research Agent**: Web search, documentation
- **QA Agent**: Testing, code review, security

## Testing

```bash
cd packages/agents
pytest tests/
```
