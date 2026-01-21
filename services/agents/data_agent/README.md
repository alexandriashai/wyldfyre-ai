# Data Agent

The Data Agent is a specialized AI agent for database operations, ETL processes, and backup management within the Wyld Fyre AI Infrastructure.

## Capabilities

### SQL Operations
- **execute_query** - Run read-only SQL queries (SELECT, WITH, EXPLAIN)
- **list_tables** - List all tables in the database
- **get_schema** - Get detailed schema for a table

### ETL Operations
- **export_to_csv** - Export query results to CSV files
- **export_to_json** - Export query results to JSON files
- **import_from_csv** - Preview and import CSV data
- **transform_data** - Apply transformations (filter, map, select)

### Backup Operations
- **create_backup** - Create PostgreSQL backups (custom, plain, directory)
- **list_backups** - List available backup files
- **restore_backup** - Restore from backup (with confirmation)

### Vector Database (Qdrant)
- **qdrant_create_collection** - Create vector collections
- **qdrant_delete_collection** - Delete collections
- **qdrant_describe_collection** - Get collection details
- **qdrant_batch_insert** - Batch insert embeddings
- **qdrant_advanced_search** - Semantic search with filters
- **qdrant_scroll** - Paginate through vectors
- **qdrant_delete_points** - Delete vectors by ID or filter

## Configuration

### Environment Variables
```bash
REDIS_HOST=redis
POSTGRES_HOST=postgres
POSTGRES_DB=ai_infrastructure
POSTGRES_USER=ai_infra
POSTGRES_PASSWORD=<secret>
QDRANT_HOST=qdrant
QDRANT_PORT=6333
```

### Permission Level
The Data Agent operates at **Permission Level 2** (READ_WRITE), allowing it to:
- Execute read-only SQL queries
- Export data to files
- Create and manage backups
- Manage vector collections

## Usage Examples

### Query Data
```json
{
  "tool": "execute_query",
  "arguments": {
    "query": "SELECT * FROM users WHERE created_at > NOW() - INTERVAL '7 days' LIMIT 100"
  }
}
```

### Export to CSV
```json
{
  "tool": "export_to_csv",
  "arguments": {
    "query": "SELECT id, email, created_at FROM users",
    "output_path": "/home/wyld-data/exports/users.csv"
  }
}
```

### Create Backup
```json
{
  "tool": "create_backup",
  "arguments": {
    "format": "custom",
    "compress": true
  }
}
```

### Vector Search
```json
{
  "tool": "qdrant_advanced_search",
  "arguments": {
    "collection_name": "documents",
    "query_vector": [0.1, 0.2, ...],
    "limit": 10,
    "filters": {
      "must": [{"key": "type", "match": {"value": "article"}}]
    }
  }
}
```

## Architecture

```
services/agents/data_agent/
├── src/
│   └── data_agent/
│       ├── __init__.py
│       ├── agent.py          # Main agent class
│       └── tools/
│           ├── __init__.py
│           ├── sql_tools.py     # SQL operations
│           ├── etl_tools.py     # Export/import/transform
│           ├── backup_tools.py  # Backup operations
│           └── qdrant_tools.py  # Vector database
├── pyproject.toml
└── README.md
```

## Security

- Only read-only SQL queries are allowed (SELECT, WITH, EXPLAIN)
- DROP, DELETE, UPDATE, INSERT are blocked
- Backups require confirmation for restore operations
- File paths are validated to prevent path traversal

## Dependencies
- ai-core, ai-messaging, ai-memory, base-agent
- asyncpg - PostgreSQL async driver
- qdrant-client - Qdrant vector database client

## Running

### With Docker Compose
```bash
docker compose up -d data-agent
```

### Standalone
```bash
python -m services.agents.data_agent.src.data_agent.agent
```

## Logs
Logs are written to `/home/wyld-data/logs/agents/data-agent.log`
