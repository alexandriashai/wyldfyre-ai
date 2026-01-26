# Learnings

> Top learnings synced from PAI Memory by utility score.

*Last synced: 2026-01-26 00:00:00 UTC*

## Top Learnings (by utility score)

1. **[0.95]** When modifying class attributes in Python, always create a copy first to avoid mutation bugs
   - Phase: EXECUTE
   - Source: Code review task

2. **[0.92]** Parallel async queries reduce latency by ~60% for memory retrieval operations
   - Phase: VERIFY
   - Source: PhaseMemoryManager implementation

3. **[0.89]** Use dataclasses with default_factory for mutable default arguments
   - Phase: BUILD
   - Source: TELOS implementation

4. **[0.87]** Hook priority ordering ensures deterministic execution sequence
   - Phase: PLAN
   - Source: Plugin system refactor

5. **[0.85]** Embedding-based deduplication catches semantic duplicates better than exact match
   - Phase: LEARN
   - Source: Memory optimization task

## Learning Categories

### Code Patterns
- Use `field(default_factory=list)` instead of `[]` in dataclass fields
- Prefer `async with aiofiles.open()` for async file operations
- Always validate user input before processing

### Architecture Decisions
- 3-tier memory provides good balance of speed and persistence
- Hook-based extensibility allows clean separation of concerns
- TELOS files work better as markdown for human readability

### Tool Usage
- Parallel tool execution improves throughput for read-only operations
- Sequential execution required for tools with side effects
- Always check tool permissions before execution

---
*Sync schedule: Session end or every 20 new learnings*
