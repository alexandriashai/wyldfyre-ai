# Code Agent Mental Models

> Frameworks for reasoning about code changes, dependencies, and quality.

## Code Change Impact Model

```
Change Scope Assessment:
┌─────────────────────────────────────────────────────────┐
│  CHANGE TYPE          │  RIPPLE EFFECT  │  ACTION      │
├─────────────────────────────────────────────────────────┤
│  Interface change     │  HIGH           │  Find all    │
│  (params, returns)    │                 │  callers     │
├─────────────────────────────────────────────────────────┤
│  Internal refactor    │  LOW            │  Test same   │
│  (no API change)      │                 │  file only   │
├─────────────────────────────────────────────────────────┤
│  Dependency update    │  MEDIUM         │  Check       │
│  (imports/versions)   │                 │  consumers   │
├─────────────────────────────────────────────────────────┤
│  New addition         │  NONE           │  Test new    │
│  (no existing deps)   │                 │  code only   │
└─────────────────────────────────────────────────────────┘
```

**When to Use**: Before any code modification
**Key Insight**: Map the blast radius before making changes.

---

## Dependency Graph Model

```
                    ┌─────────────────┐
                    │   Entry Point   │
                    │   (main, app)   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │  Router  │  │  Config  │  │  Logger  │
        └────┬─────┘  └────┬─────┘  └──────────┘
             │              │
        ┌────┴────┐    (shared)
        ▼         ▼
   ┌─────────┐ ┌─────────┐
   │ Handler │ │ Service │
   └────┬────┘ └────┬────┘
        │           │
        └─────┬─────┘
              ▼
         ┌─────────┐
         │  Model  │  ← Base layer (fewest deps)
         └─────────┘
```

**Levels**:
- **Core/Utils**: No internal dependencies (safe to change)
- **Services**: Depend on core, models
- **API/Routes**: Depend on services, models
- **Entry**: Depend on everything

**When to Use**: Understanding import chains, circular dependency detection
**Key Insight**: Change flows UP the graph; errors flow DOWN.

---

## Git Workflow Model

```
Feature Development:
main ─────────────────────────────────────────→
        \                              /
         └── feature/xyz ─────────────┘
              commit → commit → commit

Bug Fix (Urgent):
main ─────────────────────────────────────────→
        \              /
         └── hotfix ──┘
             1 commit

Exploration:
main ─────────────────────────────────────────→
        \
         └── spike/experiment (may be abandoned)
```

**Branch Decision Tree**:
1. Is it a new feature? → `feature/<name>`
2. Is it a bug fix? → `fix/<issue>` or `hotfix/<issue>`
3. Is it exploration? → `spike/<topic>`
4. Is it cleanup? → `chore/<description>`

**When to Use**: Starting any git operation
**Key Insight**: Branch naming communicates intent; commit messages explain why.

---

## Refactoring Safety Model

```
Safe to Refactor?
┌────────────────────────────────────────────────────┐
│                                                    │
│  ┌──────────────┐    YES     ┌───────────────┐   │
│  │ Tests exist? │──────────→│ Refactor with │   │
│  └──────┬───────┘            │ confidence    │   │
│         │ NO                 └───────────────┘   │
│         ▼                                        │
│  ┌──────────────┐    YES     ┌───────────────┐   │
│  │ Can add tests│──────────→│ Add tests     │   │
│  │ first?       │            │ THEN refactor │   │
│  └──────┬───────┘            └───────────────┘   │
│         │ NO                                     │
│         ▼                                        │
│  ┌──────────────────────────────────────────┐   │
│  │ Small steps with manual verification     │   │
│  │ - Change one thing at a time             │   │
│  │ - Run app after each change              │   │
│  │ - Keep commits atomic (revert-friendly)  │   │
│  └──────────────────────────────────────────┘   │
│                                                    │
└────────────────────────────────────────────────────┘
```

**When to Use**: Before any refactoring task
**Key Insight**: No tests = small steps = fast rollback capability.

---

## Code Quality Hierarchy

```
Priority Stack (most to least critical):

┌────────────────────────────────────────────┐
│ 1. SECURITY                                │  ← Non-negotiable
│    No vulnerabilities, secrets, injection  │
├────────────────────────────────────────────┤
│ 2. CORRECTNESS                             │  ← Must work
│    Passes tests, handles edge cases        │
├────────────────────────────────────────────┤
│ 3. READABILITY                             │  ← Must understand
│    Clear names, simple logic, documented   │
├────────────────────────────────────────────┤
│ 4. MAINTAINABILITY                         │  ← Must evolve
│    Single responsibility, loose coupling   │
├────────────────────────────────────────────┤
│ 5. PERFORMANCE                             │  ← Should be fast
│    Optimize only proven bottlenecks        │
└────────────────────────────────────────────┘
```

**Trade-off Rule**: Never sacrifice a higher priority for a lower one.

**When to Use**: Code review, implementation decisions
**Key Insight**: Readable code is usually correct; correct code isn't always readable.

---

*Last updated: 2026-01-26*
