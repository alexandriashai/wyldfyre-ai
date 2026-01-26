# Strategies

> Successful patterns extracted from task executions.

## Proven Strategies

### Multi-File Feature Implementation
**Success Rate**: 94% (17/18 tasks)
**Use Count**: 18

**Pattern**:
1. Read existing code structure first
2. Identify integration points
3. Create new files before modifying existing
4. Run syntax check after each file modification
5. Test integration before committing

**Best For**: New feature development, refactoring

### Bug Investigation Flow
**Success Rate**: 89% (8/9 tasks)
**Use Count**: 9

**Pattern**:
1. Reproduce the error
2. Read relevant code sections
3. Add diagnostic logging if needed
4. Form hypothesis
5. Implement fix
6. Verify fix resolves issue
7. Check for regressions

**Best For**: Debugging, error resolution

### Memory Integration Pattern
**Success Rate**: 100% (5/5 tasks)
**Use Count**: 5

**Pattern**:
1. Check existing memory patterns
2. Implement with proper ACL
3. Add to __init__.py exports
4. Test with different permission levels
5. Document in appropriate TELOS file

**Best For**: Memory system extensions

## Emerging Strategies

*New patterns with less than 5 uses will appear here for validation.*

---
*Last synced: 2026-01-26 00:00:00 UTC*
