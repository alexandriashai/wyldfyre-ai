"""
SQL operation tools for the Data Agent.
"""

import os
from typing import Any

import asyncpg

from ai_core import get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Database connection configuration
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/ai_infrastructure",
)

# Maximum rows to return to prevent memory issues
MAX_QUERY_ROWS = 1000

# Dangerous SQL patterns (case-insensitive)
DANGEROUS_PATTERNS = [
    "drop database",
    "drop schema",
    "truncate",
    "delete from",
    "update ",
    "insert into",
    "alter table",
    "create table",
    "drop table",
    "grant ",
    "revoke ",
]


def _is_safe_query(query: str) -> tuple[bool, str]:
    """Check if a query is safe (read-only)."""
    query_lower = query.lower().strip()

    for pattern in DANGEROUS_PATTERNS:
        if pattern in query_lower:
            return False, f"Query contains dangerous pattern: {pattern}"

    # Must start with SELECT, WITH, or EXPLAIN
    if not any(
        query_lower.startswith(prefix)
        for prefix in ["select", "with", "explain", "show"]
    ):
        return False, "Query must be a SELECT, WITH, EXPLAIN, or SHOW statement"

    return True, ""


async def _get_connection() -> asyncpg.Connection:
    """Get a database connection."""
    return await asyncpg.connect(DATABASE_URL)


@tool(
    name="execute_query",
    description="Execute a read-only SQL query against the database",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "SQL SELECT query to execute",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum rows to return",
                "default": 100,
            },
        },
        "required": ["query"],
    },
)
async def execute_query(
    query: str,
    limit: int = 100,
) -> ToolResult:
    """Execute a read-only SQL query."""
    try:
        # Validate query safety
        is_safe, reason = _is_safe_query(query)
        if not is_safe:
            return ToolResult.fail(f"Unsafe query rejected: {reason}")

        # Apply row limit
        effective_limit = min(limit, MAX_QUERY_ROWS)

        # Add LIMIT if not present
        query_lower = query.lower().strip()
        if "limit" not in query_lower:
            query = f"{query.rstrip(';')} LIMIT {effective_limit}"

        conn = await _get_connection()
        try:
            rows = await conn.fetch(query)

            # Convert to list of dicts
            results = [dict(row) for row in rows]

            return ToolResult.ok(
                results,
                row_count=len(results),
                query=query,
            )

        finally:
            await conn.close()

    except asyncpg.PostgresError as e:
        logger.error("SQL query failed", query=query, error=str(e))
        return ToolResult.fail(f"SQL error: {e}")
    except Exception as e:
        logger.error("Query execution failed", error=str(e))
        return ToolResult.fail(f"Query failed: {e}")


@tool(
    name="list_tables",
    description="List all tables in the database",
    parameters={
        "type": "object",
        "properties": {
            "schema": {
                "type": "string",
                "description": "Schema to list tables from",
                "default": "public",
            },
        },
    },
)
async def list_tables(schema: str = "public") -> ToolResult:
    """List all tables in a schema."""
    try:
        conn = await _get_connection()
        try:
            query = """
                SELECT
                    table_name,
                    table_type
                FROM information_schema.tables
                WHERE table_schema = $1
                ORDER BY table_name
            """
            rows = await conn.fetch(query, schema)

            tables = [
                {
                    "name": row["table_name"],
                    "type": row["table_type"],
                }
                for row in rows
            ]

            return ToolResult.ok(
                tables,
                schema=schema,
                count=len(tables),
            )

        finally:
            await conn.close()

    except asyncpg.PostgresError as e:
        logger.error("Failed to list tables", schema=schema, error=str(e))
        return ToolResult.fail(f"Failed to list tables: {e}")
    except Exception as e:
        logger.error("List tables failed", error=str(e))
        return ToolResult.fail(f"List tables failed: {e}")


@tool(
    name="get_schema",
    description="Get the schema (columns and types) of a table",
    parameters={
        "type": "object",
        "properties": {
            "table": {
                "type": "string",
                "description": "Table name",
            },
            "schema": {
                "type": "string",
                "description": "Schema name",
                "default": "public",
            },
        },
        "required": ["table"],
    },
)
async def get_schema(table: str, schema: str = "public") -> ToolResult:
    """Get the schema of a table."""
    try:
        conn = await _get_connection()
        try:
            # Get columns
            columns_query = """
                SELECT
                    column_name,
                    data_type,
                    character_maximum_length,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = $1 AND table_name = $2
                ORDER BY ordinal_position
            """
            columns = await conn.fetch(columns_query, schema, table)

            if not columns:
                return ToolResult.fail(f"Table not found: {schema}.{table}")

            # Get primary key
            pk_query = """
                SELECT c.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage AS ccu
                    USING (constraint_schema, constraint_name)
                JOIN information_schema.columns AS c
                    ON c.table_schema = tc.constraint_schema
                    AND tc.table_name = c.table_name
                    AND ccu.column_name = c.column_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                    AND tc.table_schema = $1
                    AND tc.table_name = $2
            """
            pk_rows = await conn.fetch(pk_query, schema, table)
            primary_keys = [row["column_name"] for row in pk_rows]

            # Get foreign keys
            fk_query = """
                SELECT
                    kcu.column_name,
                    ccu.table_name AS foreign_table,
                    ccu.column_name AS foreign_column
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = $1
                    AND tc.table_name = $2
            """
            fk_rows = await conn.fetch(fk_query, schema, table)
            foreign_keys = [
                {
                    "column": row["column_name"],
                    "references": f"{row['foreign_table']}.{row['foreign_column']}",
                }
                for row in fk_rows
            ]

            # Get indexes
            idx_query = """
                SELECT
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE schemaname = $1 AND tablename = $2
            """
            idx_rows = await conn.fetch(idx_query, schema, table)
            indexes = [
                {
                    "name": row["indexname"],
                    "definition": row["indexdef"],
                }
                for row in idx_rows
            ]

            result = {
                "table": f"{schema}.{table}",
                "columns": [
                    {
                        "name": col["column_name"],
                        "type": col["data_type"],
                        "max_length": col["character_maximum_length"],
                        "nullable": col["is_nullable"] == "YES",
                        "default": col["column_default"],
                        "primary_key": col["column_name"] in primary_keys,
                    }
                    for col in columns
                ],
                "primary_keys": primary_keys,
                "foreign_keys": foreign_keys,
                "indexes": indexes,
            }

            return ToolResult.ok(result)

        finally:
            await conn.close()

    except asyncpg.PostgresError as e:
        logger.error("Failed to get schema", table=table, error=str(e))
        return ToolResult.fail(f"Failed to get schema: {e}")
    except Exception as e:
        logger.error("Get schema failed", error=str(e))
        return ToolResult.fail(f"Get schema failed: {e}")
