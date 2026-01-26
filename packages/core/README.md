# Core Package

Shared utilities and infrastructure for Wyld Fyre AI agents and services.

## Components

### LLM Client (`llm_client.py`)

Unified interface for AI model interactions:
- Claude API integration
- OpenAI API support
- Streaming responses
- Token counting and cost tracking

### Security (`security.py`, `security_policies.py`)

Permission and access control:
- Tool permission levels
- Action validation
- Security policy enforcement

### Circuit Breaker (`circuit_breaker.py`)

Fault tolerance for external services:
- Automatic failure detection
- Graceful degradation
- Recovery handling

### Cost Tracker (`cost_tracker.py`)

API usage monitoring:
- Token counting per model
- Cost calculation
- Usage reporting

### Content Router (`content_router.py`)

Intelligent message routing:
- Intent classification
- Agent selection
- Load balancing

### MCP Client (`mcp_client.py`)

Model Context Protocol integration:
- Tool discovery
- External tool execution
- Protocol handling

### Plugins (`plugins.py`, `plugin_integration.py`)

Plugin system for extensibility:
- Plugin loading
- Pack management
- Integration points

### Model Selector (`model_selector.py`)

Dynamic model selection:
- Task-based selection
- Cost optimization
- Capability matching

## Usage

```python
from ai_core import LLMClient, CostTracker, CircuitBreaker

# Initialize LLM client
client = LLMClient(
    provider="anthropic",
    model="claude-sonnet-4-20250514"
)

# Make a request with tracking
response = await client.chat(
    messages=[{"role": "user", "content": "Hello!"}],
    max_tokens=1000
)
```

## Configuration

Environment variables:
- `ANTHROPIC_API_KEY`: Claude API key
- `OPENAI_API_KEY`: OpenAI API key
- `DEFAULT_MODEL`: Default model to use
- `MAX_TOKENS`: Default max tokens

## Testing

```bash
cd packages/core
pytest tests/
```
