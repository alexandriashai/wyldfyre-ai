# Mental Models

> Frameworks and models used for reasoning across the system.

## Active Models

### 7-Phase Learning Loop (PAI Algorithm)
```
OBSERVE → THINK → PLAN → BUILD → EXECUTE → VERIFY → LEARN
   ↑                                                    ↓
   └────────────────── Feedback ──────────────────────┘
```

**When to Use**: Every task execution
**Key Insight**: Each phase has specific context needs; phase memory retrieves relevant learnings for each phase.

### 3-Tier Memory Model
```
HOT (Redis)     → Real-time traces, 24h TTL
       ↓
WARM (Qdrant)   → Searchable learnings, 30d retention
       ↓
COLD (Files)    → Historical archive, 365d retention
```

**When to Use**: Memory storage and retrieval decisions
**Key Insight**: Learnings move from HOT to WARM to COLD based on age and utility.

### Utility Feedback Loop
```
Learning Created → utility_score: 0.5
                        ↓
         ┌──────────────┴──────────────┐
         ↓                              ↓
    Used + Success                 Used + Failure
    boost(+0.1)                    decay(-0.05)
         ↓                              ↓
    utility: 0.6                   utility: 0.45
```

**When to Use**: Learning lifecycle management
**Key Insight**: Successful learnings rise in utility, failed learnings decay.

### Permission Hierarchy
```
SUPERUSER (4)  → Full system access
ADMIN (3)      → Administrative operations
EXECUTE (2)    → Tool execution
READ_WRITE (1) → Standard operations
READ_ONLY (0)  → View only
```

**When to Use**: ACL decisions, tool registration
**Key Insight**: Higher permissions include lower; Supervisor (4) sees everything.

### Learning Scope Hierarchy
```
GLOBAL   → All projects, all agents
    ↓
PROJECT  → Single project only
    ↓
DOMAIN   → Specific domain/site
```

**When to Use**: Learning isolation decisions
**Key Insight**: Global learnings are patterns; Project learnings are conventions; Domain learnings are preferences.

## Decision Frameworks

### Should This Learning Be Global?
1. Is it a general programming pattern? → GLOBAL
2. Is it project-specific convention? → PROJECT
3. Is it domain/client preference? → DOMAIN
4. Is it temporary workaround? → Don't store

### Is This Task Multi-Step?
- 3+ tool calls → Extract strategy
- Complex coordination → Document pattern
- Repeated success → Increase confidence

---
*Last updated: 2026-01-26 00:00:00 UTC*
