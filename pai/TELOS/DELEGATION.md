# Delegation Protocol

This document defines the formal protocol for task delegation between agents in the Wyld Fyre AI Infrastructure.

## Agent Capability Matrix

| Agent | Permission | Domain | Delegate For |
|-------|------------|--------|--------------|
| WYLD (Supervisor) | SUPERUSER(4) | Coordination | Routing, conversations, orchestration |
| CODE | EXECUTE(2) | Code & Git | File edits, git ops, code analysis, aider_code |
| DATA | EXECUTE(2) | SQL & ETL | DB queries, backups, ETL, vector operations |
| INFRA | ADMIN(3) | System | Docker, Nginx, SSL, domains, systemd |
| RESEARCH | READ_WRITE(1) | Web | Documentation, web search, API research |
| QA | EXECUTE(2) | Testing | Tests, E2E browser, security scans |

## Decision Tree

```
User Request
    │
    ├─ Conversation/question only? → Respond directly (DON'T delegate)
    │
    └─ Tool execution needed?
        │
        ├─ Code/Git/Files? ────────────→ CODE agent
        │   • File read/write/search
        │   • Git operations (commit, push, branch)
        │   • Code analysis (find definitions, references)
        │   • Multi-file refactoring (aider_code)
        │
        ├─ Database/SQL? ──────────────→ DATA agent
        │   • SQL query execution
        │   • Database backups/restores
        │   • ETL operations
        │   • Qdrant vector operations
        │
        ├─ Docker/Nginx/SSL/System? ───→ INFRA agent
        │   • Container management
        │   • Nginx configuration
        │   • SSL certificates
        │   • Domain provisioning
        │   • Systemd services
        │   • System commands
        │
        ├─ Web research/docs? ─────────→ RESEARCH agent
        │   • Web searches
        │   • Documentation lookup
        │   • GitHub/PyPI/NPM research
        │   • Information synthesis
        │
        ├─ Testing/E2E/Security? ──────→ QA agent
        │   • Run pytest tests
        │   • E2E browser automation
        │   • Security scanning
        │   • Code quality analysis
        │
        └─ Complex/Multi-step? ────────→ Break into subtasks
            1. spawn_explore_agent (understand first)
            2. spawn_plan_agent (design approach)
            3. Delegate to appropriate specialists
```

## Recommended Patterns

### 1. Exploration-First Pattern
Use for unfamiliar codebases or complex changes:
```
1. spawn_explore_agent(query, path, thoroughness="thorough")
   → Understand codebase structure, patterns, dependencies

2. spawn_plan_agent(task, context=exploration_results)
   → Design implementation approach

3. delegate_task(CODE, implementation_plan)
   → Execute the implementation

4. delegate_task(QA, verification_task)
   → Verify the changes work correctly
```

### 2. Parallel Research Pattern
Use when gathering information from multiple sources:
```
Parallel:
  - spawn_explore_agent("find authentication logic")
  - spawn_explore_agent("find API routes")
  - delegate_task(RESEARCH, "search best practices")

Then: Synthesize results and delegate implementation
```

### 3. Sequential Build Pattern
Use for new feature development:
```
1. RESEARCH: Gather requirements and best practices
2. CODE: Implement core functionality
3. QA: Write and run tests
4. INFRA: Deploy if needed
```

### 4. Verification Pattern
Use when uncertain about system state:
```
1. search_memory("relevant past learnings")
2. delegate_task(INFRA, "check current state")
3. Only then make claims or take action
```

## Anti-Patterns (Avoid)

1. **Over-delegation**: Don't delegate simple conversations or explanations
2. **Blind delegation**: Always explore/plan before delegating complex tasks
3. **Missing verification**: Always verify results after delegation
4. **Assumption-based claims**: Never claim system state without verification
5. **Sequential when parallel**: Use parallel delegation when tasks are independent

## Shared Tools All Agents Have

Every agent has access to these shared capabilities:

### Memory
- `search_memory` - Find relevant past learnings
- `store_memory` - Save new discoveries
- `list_memory_collections` - List memory collections
- `get_memory_stats` - Memory statistics

### Collaboration
- `notify_user` - Send user notifications
- `request_agent_help` - Request help from specialists
- `broadcast_status` - Broadcast status updates

### Exploration
- `spawn_explore_agent` - READ-ONLY codebase exploration
- `spawn_plan_agent` - Architecture/design planning
- `spawn_subagent` - Generic subtask execution

### Code Editing
- `aider_code` - AI-powered multi-file editing

### System (Level 2+)
- `shell_execute` - Execute shell commands
- `resource_monitor` - Monitor system resources
- `check_service_health` - Check service health

## Permission Escalation

When a task requires higher permissions:

1. Agent requests elevation via `request_agent_help` or direct supervisor routing
2. Supervisor evaluates and routes to appropriate higher-permission agent
3. Higher-permission agent executes with its capabilities
4. Results flow back through the chain

## Error Handling

When delegation fails:
1. Report the SPECIFIC error message (not vague excuses)
2. Check if alternative approach exists
3. If blocked, escalate to user with clear explanation
4. Store the error as a learning for future reference
