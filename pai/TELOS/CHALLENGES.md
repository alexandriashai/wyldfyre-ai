# Challenges & Blockers

> Track recurring issues and their resolutions.

## Active Challenges

*No active challenges recorded.*

## Resolved Challenges

### Memory Deduplication Performance
- **Issue**: Deduplication checks were slow on large learning sets
- **Resolution**: Implemented embedding-based similarity search with 0.92 threshold
- **Resolved**: 2026-01-20

### Hook Loading Order
- **Issue**: Hooks were loading in inconsistent order
- **Resolution**: Added priority field to PluginHook, sorted by priority descending
- **Resolved**: 2026-01-18

### Phase Context Cache Invalidation
- **Issue**: Cached phase contexts weren't invalidating on new learnings
- **Resolution**: Added 5-minute TTL per task with automatic cache refresh
- **Resolved**: 2026-01-22

## Common Patterns

### Import Errors
When encountering import errors in hooks:
1. Check if the module path is correct
2. Verify the ai_memory package is properly installed
3. Ensure __init__.py exports the required classes

### Memory Access Patterns
When memory queries return empty:
1. Verify Qdrant connection is active
2. Check permission levels match
3. Confirm scope filtering is appropriate (GLOBAL vs PROJECT)

---
*Last synced: 2026-01-26 00:00:00 UTC*
