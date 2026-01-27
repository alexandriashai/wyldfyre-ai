# Data Agent Strategies

> Proven multi-step patterns for data operations (stack-agnostic).

## Safe Query Execution

**Success Rate**: 97%
**When to Use**: Any query that modifies data or could be expensive

**Pattern**:
```
1. EXPLAIN  → Analyze query plan first
2. LIMIT    → Test with small limit first
3. REVIEW   → Check plan for full scans
4. EXECUTE  → Run the actual query
5. VERIFY   → Confirm expected row counts
6. LOG      → Record what was done
```

**Red Flags in Query Plans**:
- Full table/collection scan on large data
- Nested loops with large outer set
- Sort without index
- Join on unindexed fields

---

## ETL Pipeline Pattern

**Success Rate**: 92%
**When to Use**: Moving data between systems

**Pattern**:
```
1. EXTRACT   → Pull data from source
              - Log record count
              - Capture extraction timestamp

2. VALIDATE  → Check extracted data
              - Schema matches expected
              - No critical nulls
              - Data types correct

3. TRANSFORM → Apply business logic
              - Clean: trim, normalize
              - Enrich: lookups, calculations
              - Aggregate: if needed

4. LOAD      → Insert into destination
              - Use batch inserts
              - Wrap in transaction if possible
              - Handle duplicates (upsert?)

5. VERIFY    → Post-load validation
              - Source count = destination count
              - Spot check sample records
              - Quality metrics acceptable
```

**Error Handling**:
- Log all failures with full context
- Consider dead-letter queue for failed rows
- Implement idempotency (re-runnable)

---

## Backup Before Modify

**Success Rate**: 99%
**When to Use**: Any UPDATE, DELETE, or schema change

**Pattern**:
```
1. BACKUP    → Create backup of affected data
              - Full table: export/dump
              - Partial: export affected records

2. VERIFY    → Confirm backup is complete
              - Row counts match
              - Sample data correct

3. MODIFY    → Execute the change
              - Wrap in transaction if possible
              - Use explicit WHERE clause

4. VALIDATE  → Check results
              - Expected rows affected?
              - Data looks correct?

5. ARCHIVE   → Keep backup for rollback period
              - Label with timestamp
              - Document what it's for
              - Set retention (7 days typical)
```

**Rollback Procedure**:
```
If something went wrong:
1. Stop application writes if needed
2. Truncate/clear target
3. Restore from backup
4. Verify data integrity
5. Resume operations
```

---

## Schema Migration Strategy

**Success Rate**: 94%
**When to Use**: Database/schema changes

**Pattern**:
```
1. PLAN      → Document the migration
              - What changes
              - Why it's needed
              - Rollback plan

2. BACKUP    → Full schema + data backup

3. TEST      → Run on staging/test first
              - Exact copy of production schema
              - Verify all queries still work

4. MIGRATE   → Execute migration
              - Prefer small, incremental changes
              - One change per migration file
              - Version control migrations

5. VALIDATE  → Confirm success
              - Schema matches expected
              - Application tests pass
              - No broken references

6. CLEANUP   → Remove deprecated items
              - After 1-2 release cycles
              - Confirm no dependencies remain
```

**Migration File Template**:
```
-- Migration: 001_add_user_email_index
-- Author: Data Agent
-- Date: YYYY-MM-DD
-- Description: Add index for email lookup performance

-- UP (apply)
[Create index or modify schema]

-- DOWN (rollback)
[Reverse the change]
```

---

## Data Export Pattern

**Success Rate**: 96%
**When to Use**: Exporting data for reports, transfers, backups

**Pattern**:
```
1. QUERY     → Build and test the query
              - Verify correct data
              - Optimize if large

2. VALIDATE  → Check data before export
              - Row count expected?
              - No PII exposed (if external)?
              - Correct date range?

3. FORMAT    → Choose appropriate format
              - CSV: Human readable, spreadsheet compatible
              - JSON: Nested data, API consumers
              - Binary: Large datasets, analytics

4. EXPORT    → Execute the export
              - Stream large datasets (don't load all in memory)
              - Add progress logging

5. CHECKSUM  → Verify export integrity
              - Record row count
              - Generate file hash
              - Store metadata
```

**Export Metadata Example**:
```
{
  "export_date": "2026-01-26T10:30:00Z",
  "source": "orders",
  "row_count": 150000,
  "file_size_bytes": 45000000,
  "checksum": "sha256:abc123...",
  "date_range": "2025-01-01 to 2025-12-31"
}
```

---

## Query Debugging Strategy

**Success Rate**: 87%
**When to Use**: Query returns unexpected results or is slow

**Pattern**:
```
1. ISOLATE   → Simplify the query
              - Remove joins one at a time
              - Comment out filters
              - Find minimal breaking case

2. EXPLAIN   → Analyze execution plan
              - Where is time spent?
              - Are indexes being used?
              - Any full scans?

3. SAMPLE    → Examine actual data
              - Look at small sample
              - Check data types
              - Look for NULLs, edge cases

4. COMPARE   → Expected vs actual
              - Manual count vs query count
              - Spot check specific records
              - Verify join conditions

5. FIX       → Address the issue
              - Add missing index
              - Fix join condition
              - Handle NULLs explicitly

6. TEST      → Verify fix works
              - Rerun query plan analysis
              - Check results
              - Performance acceptable?
```

---

*Last updated: 2026-01-26*
