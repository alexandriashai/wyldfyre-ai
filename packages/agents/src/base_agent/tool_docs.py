"""
Tool documentation module for agent prompts.

Provides shared tool documentation that can be injected into all agent system prompts.
This ensures agents know what tools they have access to.
"""

SHARED_TOOLS_DOCS = """
## Shared Tools (Available to All Agents)

You have access to the following shared tools in addition to your specialist tools:

### Memory Tools
- `search_memory(query, collection?, limit?, filter?)` - Semantic search of learnings and past experiences. Use before starting tasks to find relevant context.
- `store_memory(content, collection?, category?, tags?, scope?)` - Store new learnings, discoveries, or corrections. Scope: GLOBAL (system-wide), PROJECT (project-specific), or DOMAIN (domain-specific).
- `list_memory_collections()` - List available memory collections.
- `get_memory_stats()` - Get statistics about stored memories.
- `delete_memory(id)` - Delete a specific memory entry.

### Collaboration Tools
- `notify_user(message, level?)` - Send notification to user (info, warning, error).
- `request_agent_help(agent_type, task, context?)` - Request help from another specialist agent.
- `broadcast_status(status, message?)` - Broadcast status update to all listening agents.

### Subagent Tools
- `spawn_explore_agent(query, path?, thoroughness?)` - Launch a READ-ONLY code exploration agent. Use this for codebase understanding BEFORE making changes.
- `spawn_plan_agent(task, context?)` - Launch an architecture/design planning agent. Returns implementation plans.
- `spawn_subagent(task, max_iterations?)` - Execute a generic subtask in an isolated context.

### Code Editing (Advanced)
- `aider_code(instruction, files, root_path, model_tier?)` - AI-powered multi-file code editing. Use for complex refactoring across multiple files.

### System Tools
- `get_system_info()` - Get system information (OS, memory, CPU).
- `check_service_health(services?)` - Check health of system services.
- `resource_monitor()` - Monitor CPU/memory/disk usage.
- `shell_execute(command, timeout?)` - Execute shell commands (requires permission level 2+).

### Browser Tools (Shared)
- `browser_status()` - Get status of browser instances.
- `screenshot_url(url, viewport?)` - Take a screenshot of a URL.
- `page_content_fetch(url)` - Fetch and extract content from a URL.
- `visual_diff(url1, url2)` - Compare visual differences between two URLs.

IMPORTANT: Always use `search_memory` before starting complex tasks to leverage past learnings!
"""

LEARNING_FEEDBACK_DOCS = """
## Learning Feedback

When completing tasks, follow this learning protocol:

### Using Retrieved Learnings
- If a retrieved learning was USEFUL → The system auto-boosts its relevance score
- If a learning was MISLEADING or OUTDATED → Call `store_memory` with a correction

### Storing New Learnings
When you discover something important, store it for future reference:
1. Assess scope:
   - GLOBAL: Applies system-wide (e.g., "Always check nginx config before reload")
   - PROJECT: Applies to specific project (e.g., "This repo uses pnpm, not npm")
   - DOMAIN: Applies to a domain/technology (e.g., "Qdrant requires explicit collection creation")

2. Call `store_memory` with appropriate metadata:
   ```
   store_memory(
       content="Discovered learning...",
       scope="GLOBAL|PROJECT|DOMAIN",
       category="pattern|error|config|best_practice|tool_usage",
       tags=["relevant", "tags"]
   )
   ```

### What to Store
- Error resolutions and workarounds
- Configuration discoveries
- Tool usage patterns that worked well
- Common pitfalls to avoid
- Project-specific conventions
- Performance optimizations found
"""

DELEGATION_PROTOCOL_DOCS = """
## Delegation Protocol

When you need capabilities outside your specialty, use this protocol:

### Capability Matrix
| Agent | Domain | Use For |
|-------|--------|---------|
| CODE | Code & Git | File edits, git ops, code analysis |
| DATA | SQL & Data | DB queries, backups, ETL, vectors |
| INFRA | System | Docker, Nginx, SSL, domains, services |
| RESEARCH | Web | Documentation, web search, API research |
| QA | Testing | Tests, E2E automation, security scans |

### Before Delegating Complex Tasks
1. Use `spawn_explore_agent()` → Understand the codebase first
2. Use `spawn_plan_agent()` → Design the approach
3. Then delegate implementation to the appropriate specialist

### Patterns
- **Exploration-First**: Explore → Plan → Implement → Verify
- **Parallel Research**: Multiple `spawn_explore_agent` calls for different questions
- **Sequential Build**: Plan → Code changes → Tests → Deploy
"""


def get_shared_tools_prompt_section() -> str:
    """Get the complete shared tools documentation for injection into prompts."""
    return SHARED_TOOLS_DOCS + "\n" + LEARNING_FEEDBACK_DOCS


def get_supervisor_delegation_section() -> str:
    """Get the delegation protocol for supervisor prompt."""
    return DELEGATION_PROTOCOL_DOCS
