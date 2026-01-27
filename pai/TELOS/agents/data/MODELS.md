# Data Agent Mental Models

> Frameworks for reasoning about data flows, queries, and integrity (stack-agnostic).

## Data Flow Model

```
┌─────────────────────────────────────────────────────────┐
│                    DATA FLOW PIPELINE                    │
└─────────────────────────────────────────────────────────┘

  SOURCE          TRANSFORM        LOAD           VALIDATE
┌─────────┐     ┌───────────┐   ┌────────┐     ┌──────────┐
│ Files   │     │ Clean     │   │ Insert │     │ Schema   │
│ APIs    │ ──→ │ Enrich    │ ─→│ Upsert │ ──→ │ Counts   │
│ Streams │     │ Aggregate │   │ Update │     │ Quality  │
└─────────┘     └───────────┘   └────────┘     └──────────┘
     │                                               │
     │          ┌────────────────────────┐          │
     └──────────│    ERROR HANDLING      │──────────┘
                │ - Log failures         │
                │ - Dead letter queue    │
                │ - Retry with backoff   │
                └────────────────────────┘
```

**When to Use**: Any ETL operation, data migration
**Key Insight**: Never load without validation; never transform without backup.

---

## Query Optimization Model

```
Query Execution Order (SQL-like systems):
┌──────────────────────────────────────────────────────┐
│                                                      │
│   1. FROM    → Which tables/collections?            │
│   2. WHERE   → Filter records (use indexes here!)   │
│   3. GROUP   → Aggregate                            │
│   4. HAVING  → Filter groups                        │
│   5. SELECT  → Pick fields                          │
│   6. ORDER   → Sort (expensive without index)       │
│   7. LIMIT   → Truncate results                     │
│                                                      │
└──────────────────────────────────────────────────────┘

Index Decision:
┌─────────────────────────────────────────────────────┐
│  FIELD USAGE          │  INDEX?  │  REASON         │
├─────────────────────────────────────────────────────┤
│  Filter equality      │  YES     │  Fast lookups   │
│  Filter range         │  MAYBE   │  Depends on     │
│                       │          │  selectivity    │
│  Join/lookup key      │  YES     │  Required       │
│  Sort field           │  MAYBE   │  If large sets  │
│  Read-only field      │  NO      │  Waste of space │
└─────────────────────────────────────────────────────┘
```

**When to Use**: Writing or optimizing queries
**Key Insight**: Analyze query plan before running expensive queries.

---

## Backup Risk Model

```
Backup Decision Tree:

Is it a destructive operation? (DELETE, DROP, UPDATE)
    │
    ├── YES ──→ BACKUP REQUIRED
    │            │
    │            ├── Full table/collection? ──→ Full dump
    │            │
    │            └── Partial? ──→ Export affected records
    │
    └── NO ──→ Is it a large INSERT/UPDATE?
                 │
                 ├── YES ──→ Test on subset first
                 │            Use transaction if available
                 │
                 └── NO ──→ Proceed (with transaction if available)
```

**Restore Decision**:
```
Error Detected
    │
    ├── Within transaction? ──→ ROLLBACK
    │
    └── Committed? ──→ Restore from backup
                        │
                        ├── Recent backup? ──→ Restore directly
                        │
                        └── Old backup? ──→ Point-in-time recovery
                                            or manual repair
```

**When to Use**: Before any data modification
**Key Insight**: The question isn't IF you'll need the backup, but WHEN.

---

## Schema Evolution Model

```
Safe Migration Patterns:

ADDING (Safe):
┌──────────────────────────────────────────────────────┐
│  + Add field with DEFAULT      │  Zero downtime     │
│  + Add nullable field          │  Zero downtime     │
│  + Add new table/collection    │  Zero downtime     │
│  + Add index (background)      │  Zero downtime     │
└──────────────────────────────────────────────────────┘

MODIFYING (Caution):
┌──────────────────────────────────────────────────────┐
│  ~ Rename field   │  Break queries → use alias      │
│  ~ Change type    │  May fail → new field + migrate │
│  ~ Add NOT NULL   │  May fail → add default first   │
└──────────────────────────────────────────────────────┘

REMOVING (Dangerous):
┌──────────────────────────────────────────────────────┐
│  - Drop field   │  App may depend → deprecate first │
│  - Drop table   │  Data loss → backup + verify      │
│  - Drop index   │  Performance → test queries first │
└──────────────────────────────────────────────────────┘
```

**When to Use**: Database/schema migrations
**Key Insight**: Add is safe; modify is careful; remove is dangerous.

---

## Data Integrity Model

```
Validation Layers:

┌─────────────────────────────────────────────────────┐
│  LAYER           │  VALIDATES              │  WHEN │
├─────────────────────────────────────────────────────┤
│  Application     │  Business rules         │  Input│
│                  │  Format, ranges         │       │
├─────────────────────────────────────────────────────┤
│  Database        │  Constraints            │  Write│
│                  │  Foreign keys           │       │
│                  │  NOT NULL, UNIQUE       │       │
├─────────────────────────────────────────────────────┤
│  Post-load       │  Counts match           │  After│
│                  │  No orphans             │       │
│                  │  Quality metrics        │       │
└─────────────────────────────────────────────────────┘

Integrity Checks:
□ Row count matches expected
□ No NULL in required fields
□ Foreign keys all resolve
□ Unique constraints satisfied
□ Check constraints pass
□ Data quality score acceptable
```

**When to Use**: After any data load or migration
**Key Insight**: Trust but verify at every boundary.

---

*Last updated: 2026-01-26*
