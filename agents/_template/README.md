# Agent Template

This is a template for creating new agents. Copy this directory and customize.

## Quick Start

```bash
# 1. Copy template
cp -r agents/_template agents/my_agent

# 2. Rename package
mv agents/my_agent/src/template_agent agents/my_agent/src/my_agent

# 3. Update files
# - pyproject.toml: Change name to "my_agent"
# - src/my_agent/__init__.py: Update imports
# - src/my_agent/agent.py: Implement your agent
# - tests/: Add tests

# 4. Configure
# Add to config/agents.yaml

# 5. Install and test
make install
pytest agents/my_agent/tests/ -v
```

## Directory Structure

```
my_agent/
├── src/
│   └── my_agent/
│       ├── __init__.py     # Package exports
│       ├── agent.py        # Agent implementation
│       └── tools/
│           ├── __init__.py # Tool exports
│           └── my_tools.py # Tool implementations
├── tests/
│   ├── __init__.py
│   └── test_agent.py       # Agent tests
├── pyproject.toml          # Package config
└── README.md               # This file
```

## Checklist

- [ ] Rename package directory
- [ ] Update pyproject.toml with correct name
- [ ] Implement agent class
- [ ] Define tools
- [ ] Write tests
- [ ] Add to config/agents.yaml
- [ ] Add routing in supervisor
- [ ] Document in agents/CLAUDE.md
