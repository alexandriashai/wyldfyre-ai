# Research Agent

The Research Agent is a specialized AI agent for information gathering, web research, documentation management, and knowledge synthesis within the Wyld Fyre AI Infrastructure.

## Capabilities

### Web Research
- **search_web** - Search the web using multiple search engines
- **fetch_url** - Fetch and extract content from URLs
- **summarize_page** - Summarize web pages with focus on specific topics

### Documentation Management
- **search_documentation** - Search through project documentation
- **read_documentation** - Read and extract sections from docs
- **create_documentation** - Create new documentation files
- **update_documentation** - Update existing documentation

### GitHub & Repository Research
- **search_github** - Search GitHub repositories
- **get_repository_info** - Get repository details and metadata
- **get_repository_readme** - Fetch repository README
- **list_trending_repos** - List trending repositories

### Package Registry Research
- **search_pypi** - Search Python Package Index
- **get_pypi_package** - Get package details and versions
- **search_npm** - Search NPM registry
- **get_npm_package** - Get NPM package details

### Information Synthesis
- **synthesize_findings** - Combine information from multiple sources
- **extract_insights** - Extract key insights and patterns
- **create_summary** - Create structured summaries

## Configuration

### Environment Variables
```bash
REDIS_HOST=redis
POSTGRES_HOST=postgres
QDRANT_HOST=qdrant
SERP_API_KEY=<key>           # Optional: for enhanced web search
GITHUB_TOKEN=<token>         # Optional: for GitHub API access
```

### Permission Level
The Research Agent operates at **Permission Level 1** (READ_WRITE), allowing it to:
- Search the web and fetch content
- Read and write documentation files
- Access public APIs (GitHub, PyPI, NPM)
- Store findings in memory

## Usage Examples

### Web Search
```json
{
  "tool": "search_web",
  "arguments": {
    "query": "FastAPI websocket authentication best practices",
    "num_results": 10
  }
}
```

### Fetch and Summarize
```json
{
  "tool": "fetch_url",
  "arguments": {
    "url": "https://fastapi.tiangolo.com/advanced/websockets/",
    "extract_text": true
  }
}
```

### Search GitHub
```json
{
  "tool": "search_github",
  "arguments": {
    "query": "fastapi websocket",
    "language": "python",
    "sort": "stars",
    "limit": 5
  }
}
```

### Search PyPI
```json
{
  "tool": "search_pypi",
  "arguments": {
    "query": "async websocket",
    "limit": 10
  }
}
```

### Create Documentation
```json
{
  "tool": "create_documentation",
  "arguments": {
    "path": "docs/guides/websocket-auth.md",
    "title": "WebSocket Authentication Guide",
    "content": "# WebSocket Authentication\n\n..."
  }
}
```

## Architecture

```
services/agents/research_agent/
├── src/
│   └── research_agent/
│       ├── __init__.py
│       ├── agent.py              # Main agent class
│       └── tools/
│           ├── __init__.py
│           ├── web_tools.py         # Web search and fetch
│           ├── documentation_tools.py # Doc management
│           ├── github_tools.py      # GitHub integration
│           ├── pypi_tools.py        # PyPI search
│           ├── npm_tools.py         # NPM search
│           └── synthesis_tools.py   # Information synthesis
├── pyproject.toml
└── README.md
```

## Documentation Format

The Research Agent creates documentation in Markdown with YAML frontmatter:

```markdown
---
title: "Document Title"
date: 2024-01-21
tags: [fastapi, websocket, authentication]
sources:
  - https://example.com/source1
  - https://example.com/source2
---

# Document Title

## Overview
...

## Key Findings
...

## Code Examples
...

## References
...
```

## Memory Integration

The Research Agent uses Qdrant vector database for:
- Storing research findings for future reference
- Semantic search over previous research
- Building knowledge bases from multiple sources

## Security

- Only accesses publicly available information
- Respects rate limits and terms of service
- Does not scrape private or protected content
- Properly attributes all sources

## Dependencies
- ai-core, ai-messaging, ai-memory, base-agent
- httpx - HTTP client
- beautifulsoup4 - HTML parsing
- markdown - Markdown processing

## Running

### With Docker Compose
```bash
docker compose up -d research-agent
```

### Standalone
```bash
python -m services.agents.research_agent.src.research_agent.agent
```

## Logs
Logs are written to `/home/wyld-data/logs/agents/research-agent.log`
