# Code Agent Strategies

> Proven multi-step patterns for code operations (stack-agnostic).

## Safe File Modification

**Success Rate**: High (prevents accidental data loss)
**When to Use**: Any file edit, especially configuration files

**Pattern**:
```
1. READ    → Read current file content
2. BACKUP  → Note original state (for revert)
3. EDIT    → Make targeted changes
4. VERIFY  → Check syntax/linting passes
5. COMMIT  → Atomic commit with clear message
```

**Anti-patterns to Avoid**:
- Editing without reading first
- Large multi-file edits in one commit
- Committing without running linter

---

## Feature Branch Workflow

**Success Rate**: 94%
**When to Use**: New features, significant changes

**Pattern**:
```
1. BRANCH   → git checkout -b feature/<name>
2. DEVELOP  → Write code in small, testable chunks
3. TEST     → Run tests after each significant change
4. LINT     → Ensure code passes all checks
5. COMMIT   → Atomic commits with context
6. PR       → Open PR with summary and test plan
7. MERGE    → Squash or merge based on project convention
```

**Commit Message Format**:
```
<type>(<scope>): <summary>

<body - why this change matters>

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

---

## Code Review Preparation

**Success Rate**: 89%
**When to Use**: Before requesting review

**Pattern**:
```
1. SELF-REVIEW  → Read diff as if you're the reviewer
2. LINT         → Run project linter, fix all issues
3. FORMAT       → Apply project formatter
4. TEST         → All tests pass
5. DOCUMENT     → Add/update comments where needed
6. COMMIT       → Clean commit history
7. PR-DESC      → Write clear summary + test plan
```

**Self-Review Checklist**:
- [ ] No debug code left in
- [ ] No hardcoded secrets
- [ ] Error handling present
- [ ] Edge cases considered
- [ ] Naming is clear

---

## Dependency Update Strategy

**Success Rate**: 85%
**When to Use**: Updating packages (any package manager)

**Pattern**:
```
1. CHECK    → List outdated packages
2. RESEARCH → Read changelogs for breaking changes
3. BRANCH   → Create update branch
4. UPDATE   → Update one package at a time
5. TEST     → Run full test suite
6. VERIFY   → Manual smoke test if critical
7. COMMIT   → Document what changed and why
```

**Risk Assessment**:
- **Patch version** (1.0.x): Low risk, batch together
- **Minor version** (1.x.0): Medium risk, update individually
- **Major version** (x.0.0): High risk, research first, test thoroughly

---

## Large Refactor Pattern

**Success Rate**: 91%
**When to Use**: Significant code restructuring

**Pattern**:
```
1. PLAN      → Define target state, identify steps
2. TESTS     → Ensure tests exist (add if missing)
3. BRANCH    → Create refactor branch
4. STEP      → Make ONE small change
5. VERIFY    → Tests still pass
6. COMMIT    → Commit with clear message
7. REPEAT    → Steps 4-6 until done
8. REVIEW    → Self-review full diff
9. PR        → Document before/after
```

**Small Step Examples**:
- Rename one variable
- Extract one function
- Move one file
- Split one class

**Key Rule**: Each commit should leave code working.

---

## Debug Investigation Flow

**Success Rate**: 88%
**When to Use**: Investigating bugs, unexpected behavior

**Pattern**:
```
1. REPRODUCE  → Confirm you can trigger the bug
2. ISOLATE    → Find minimum reproduction case
3. READ       → Study the relevant code path
4. HYPOTHESIS → Form theory about cause
5. VERIFY     → Add logging/debugging to confirm
6. FIX        → Implement the fix
7. TEST       → Confirm fix works
8. REGRESS    → Check nothing else broke
9. CLEANUP    → Remove debug code
```

**When Stuck**:
- Binary search: Comment out half the code
- Fresh eyes: Explain the problem out loud
- Walk away: Short break often helps

---

*Last updated: 2026-01-26*
