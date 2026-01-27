# TELOS - AI Goal & Knowledge System

TELOS (from Greek τέλος, meaning "purpose" or "end goal") is the goal management and knowledge framework that guides agent behavior. It provides mission alignment, mental models, and proven strategies that agents use to make decisions and solve problems effectively.

## Directory Structure

```
TELOS/
├── README.md              # This file
├── MISSION.md             # Organization's core purpose
├── BELIEFS.md             # Values and guiding principles
├── NARRATIVES.md          # Context and organizational story
├── GOALS.md               # Active goals and progress tracking
├── CHALLENGES.md          # Known issues and blockers
├── IDEAS.md               # Captured ideas for future work
├── LEARNED.md             # Top learnings (synced from memory)
├── MODELS.md              # Global mental models (Supervisor)
├── STRATEGIES.md          # Global proven strategies (Supervisor)
├── projects/              # Project-specific TELOS
│   └── <project-id>/
│       ├── GOALS.md
│       ├── LEARNED.md
│       └── STRATEGIES.md
└── agents/                # Agent-specific knowledge
    ├── code/
    │   ├── MODELS.md      # Code agent mental models
    │   └── STRATEGIES.md  # Code agent strategies
    ├── data/
    │   ├── MODELS.md      # Data agent mental models
    │   └── STRATEGIES.md  # Data agent strategies
    ├── infra/
    │   ├── MODELS.md      # Infra agent mental models
    │   └── STRATEGIES.md  # Infra agent strategies
    ├── research/
    │   ├── MODELS.md      # Research agent mental models
    │   └── STRATEGIES.md  # Research agent strategies
    └── qa/
        ├── MODELS.md      # QA agent mental models
        └── STRATEGIES.md  # QA agent strategies
```

## Understanding MODELS vs STRATEGIES

| Component | Purpose | Example |
|-----------|---------|---------|
| **MODELS** | Mental frameworks for reasoning about problems | "Code Change Impact Model" - how to assess ripple effects of changes |
| **STRATEGIES** | Proven multi-step patterns for accomplishing tasks | "Safe File Modification" - read → backup → edit → verify → commit |

### MODELS (Mental Frameworks)

MODELS provide conceptual frameworks that help agents reason about problems. They answer questions like:
- How should I think about this type of problem?
- What factors should I consider?
- What are the relationships between components?

Example from Code Agent MODELS:

```
Code Quality Hierarchy:
┌────────────────────────────────────────────┐
│ 1. SECURITY      ← Non-negotiable          │
│ 2. CORRECTNESS   ← Must work               │
│ 3. READABILITY   ← Must understand         │
│ 4. MAINTAINABILITY ← Must evolve           │
│ 5. PERFORMANCE   ← Should be fast          │
└────────────────────────────────────────────┘

Trade-off Rule: Never sacrifice a higher priority for a lower one.
```

### STRATEGIES (Proven Patterns)

STRATEGIES are step-by-step procedures that have proven successful. They provide:
- Concrete action sequences
- Success rates from past execution
- Anti-patterns to avoid
- When to use each strategy

Example from Data Agent STRATEGIES:

```
Safe Query Execution (97% success rate)

1. EXPLAIN  → Analyze query plan first
2. LIMIT    → Test with small limit first
3. REVIEW   → Check plan for full scans
4. EXECUTE  → Run the actual query
5. VERIFY   → Confirm expected row counts
6. LOG      → Record what was done
```

## Global vs Agent-Specific TELOS

### Global TELOS (Root Level)

The root-level TELOS files apply to the **Supervisor (Wyld)** and provide organization-wide context:

- `MISSION.md` - Why the organization exists
- `BELIEFS.md` - Core values and principles
- `NARRATIVES.md` - Context about the organization
- `MODELS.md` - Supervisor-level mental models
- `STRATEGIES.md` - Supervisor-level strategies

### Agent-Specific TELOS (`agents/` subdirectory)

Each specialized agent has its own MODELS and STRATEGIES optimized for their domain:

| Agent | Focus Area |
|-------|------------|
| **code** | Git workflows, code quality, refactoring safety, dependency management |
| **data** | Query optimization, ETL pipelines, schema evolution, data integrity |
| **infra** | Service dependencies, resource allocation, SSL/security, disaster recovery |
| **research** | Source credibility, search strategies, knowledge synthesis, documentation |
| **qa** | Test pyramid, bug severity, code review, security scanning |

All agent TELOS content is **stack-agnostic** - it focuses on universal patterns that apply regardless of specific technologies.

## How TELOS is Loaded

When an agent starts a session, the `TelosManager` loads:

1. **Global Context** - Mission, beliefs, narratives (if relevant to task type)
2. **Agent-Specific Context** - MODELS and STRATEGIES for the agent's type
3. **Project Context** - Project-specific learnings and goals (if applicable)

This context is injected into the agent's prompt to guide decision-making.

```python
# Example: Loading context for Code Agent
context = await telos.get_context_for_task(
    task_type="coding",
    project_id="my-project",
    agent_type="code",  # Loads code agent MODELS/STRATEGIES
)
```

## File Format

TELOS files use Markdown with specific conventions:

### MODELS.md Format

```markdown
# [Agent] Mental Models

> Brief description of what these models are for.

## Model Name

[ASCII diagram or structured representation]

**When to Use**: Context for when to apply this model
**Key Insight**: The most important takeaway
```

### STRATEGIES.md Format

```markdown
# [Agent] Strategies

> Brief description of what these strategies are for.

## Strategy Name

**Success Rate**: XX%
**When to Use**: Context for when to apply

**Pattern**:
1. STEP_NAME → Description
2. STEP_NAME → Description
...

**Anti-patterns to Avoid**:
- What not to do
```

## Extending TELOS

### Adding a New Strategy

1. Identify a successful multi-step pattern
2. Document it in the appropriate `STRATEGIES.md`
3. Include success rate, when to use, and steps
4. Add anti-patterns from lessons learned

### Adding a New Model

1. Identify a useful mental framework
2. Create a visual representation (ASCII diagrams work well)
3. Document when to use it and the key insight
4. Add to the appropriate `MODELS.md`

## Integration with PAI Memory

TELOS integrates with the PAI memory system:

- **LEARNED.md** is synced from high-utility learnings in memory
- Successful task patterns can be extracted into STRATEGIES
- Challenges and resolutions are tracked in CHALLENGES.md
- Ideas from conversations are captured in IDEAS.md

The `TelosManager` in `packages/memory/src/ai_memory/telos.py` handles all TELOS operations.

---

*Part of the [PAI (Personal AI Infrastructure)](https://github.com/danielmiessler/Personal_AI_Infrastructure) implementation*
