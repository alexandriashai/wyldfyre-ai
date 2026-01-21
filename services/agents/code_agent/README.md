# Code Agent

The Code Agent is a specialized AI agent for file operations, Git management, and code analysis within the Wyld Fyre AI Infrastructure.

## Capabilities

### File Operations
- **Read files** - Read content from any file in the workspace
- **Write files** - Create or update files with new content
- **List directories** - Browse directory structures
- **Search files** - Find files by name pattern or content
- **Delete files** - Remove files (with confirmation)

### Git Operations
- **git status** - Check repository status and staged changes
- **git diff** - View changes between commits or working directory
- **git log** - Browse commit history with filters
- **git add** - Stage files for commit
- **git commit** - Create commits with messages
- **git branch** - List, create, or delete branches
- **git checkout** - Switch branches or restore files
- **git pull** - Fetch and merge remote changes
- **git push** - Push commits to remote repository

### Code Analysis
- **code_search** - Search code using ripgrep patterns
- **find_definition** - Locate symbol definitions
- **find_references** - Find all references to a symbol
- **get_python_imports** - Extract import statements
- **get_package_dependencies** - Analyze project dependencies
- **count_lines** - Count lines of code by language

## Configuration

### Environment Variables
```bash
REDIS_HOST=redis          # Redis connection for messaging
REDIS_PORT=6379
POSTGRES_HOST=postgres    # Database connection
QDRANT_HOST=qdrant       # Vector database for memory
```

### Permission Level
The Code Agent operates at **Permission Level 2** (READ_WRITE), allowing it to:
- Read and write files in the workspace
- Execute Git operations
- Analyze code structure

## Usage Examples

### Reading a File
```json
{
  "tool": "read_file",
  "arguments": {
    "path": "/home/wyld-core/services/api/src/api/main.py"
  }
}
```

### Committing Changes
```json
{
  "tool": "git_commit",
  "arguments": {
    "message": "feat: Add new API endpoint for user preferences",
    "files": ["src/api/routes/preferences.py"]
  }
}
```

### Searching Code
```json
{
  "tool": "code_search",
  "arguments": {
    "pattern": "async def.*endpoint",
    "path": "/home/wyld-core/services/api",
    "file_pattern": "*.py"
  }
}
```

## Architecture

```
services/agents/code_agent/
├── src/
│   └── code_agent/
│       ├── __init__.py
│       ├── agent.py          # Main agent class
│       └── tools/
│           ├── __init__.py
│           ├── file_tools.py    # File operations
│           ├── git_tools.py     # Git operations
│           └── code_tools.py    # Code analysis
├── pyproject.toml
└── README.md
```

## Dependencies
- ai-core - Core utilities and logging
- ai-messaging - Redis pub/sub communication
- ai-memory - Vector database memory
- base-agent - Base agent framework
- GitPython - Git operations

## Running

### With Docker Compose
```bash
docker compose up -d code-agent
```

### Standalone
```bash
python -m services.agents.code_agent.src.code_agent.agent
```

## Logs
Logs are written to `/home/wyld-data/logs/agents/code-agent.log`
