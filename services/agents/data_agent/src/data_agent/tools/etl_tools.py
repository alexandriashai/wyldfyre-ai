"""
ETL (Extract, Transform, Load) tools for the Data Agent.
"""

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles
import asyncpg

from ai_core import get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Workspace directory for file operations
WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_DIR", "/app/workspace"))
DATA_DIR = WORKSPACE_DIR / "data"

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/ai_infrastructure",
)


def _validate_path(path: str) -> Path:
    """Validate and resolve a file path within data directory."""
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    data_resolved = DATA_DIR.resolve()
    resolved = (DATA_DIR / path).resolve()

    try:
        resolved.relative_to(data_resolved)
    except ValueError:
        raise ValueError(f"Path escapes data directory: {path}")

    return resolved


async def _get_connection() -> asyncpg.Connection:
    """Get a database connection."""
    return await asyncpg.connect(DATABASE_URL)


@tool(
    name="export_to_csv",
    description="Export query results to a CSV file",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "SQL SELECT query to export",
            },
            "filename": {
                "type": "string",
                "description": "Output filename (relative to data directory)",
            },
            "include_header": {
                "type": "boolean",
                "description": "Include column headers",
                "default": True,
            },
        },
        "required": ["query", "filename"],
    },
    permission_level=1,
)
async def export_to_csv(
    query: str,
    filename: str,
    include_header: bool = True,
) -> ToolResult:
    """Export query results to CSV."""
    try:
        # Validate query (must be SELECT)
        query_lower = query.lower().strip()
        if not query_lower.startswith("select"):
            return ToolResult.fail("Only SELECT queries can be exported")

        file_path = _validate_path(filename)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        conn = await _get_connection()
        try:
            rows = await conn.fetch(query)

            if not rows:
                return ToolResult.ok(
                    "No data to export",
                    rows=0,
                    file=str(file_path),
                )

            # Get column names from first row
            columns = list(rows[0].keys())

            async with aiofiles.open(file_path, "w") as f:
                # Write header
                if include_header:
                    await f.write(",".join(columns) + "\n")

                # Write data rows
                for row in rows:
                    values = []
                    for col in columns:
                        val = row[col]
                        if val is None:
                            values.append("")
                        elif isinstance(val, str):
                            # Escape quotes and wrap in quotes if needed
                            if "," in val or '"' in val or "\n" in val:
                                val = '"' + val.replace('"', '""') + '"'
                            values.append(val)
                        else:
                            values.append(str(val))
                    await f.write(",".join(values) + "\n")

            return ToolResult.ok(
                f"Exported {len(rows)} rows to {filename}",
                rows=len(rows),
                columns=columns,
                file=str(file_path),
            )

        finally:
            await conn.close()

    except ValueError as e:
        return ToolResult.fail(str(e))
    except asyncpg.PostgresError as e:
        logger.error("Export to CSV failed", query=query, error=str(e))
        return ToolResult.fail(f"SQL error: {e}")
    except Exception as e:
        logger.error("Export failed", error=str(e))
        return ToolResult.fail(f"Export failed: {e}")


@tool(
    name="export_to_json",
    description="Export query results to a JSON file",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "SQL SELECT query to export",
            },
            "filename": {
                "type": "string",
                "description": "Output filename (relative to data directory)",
            },
            "pretty": {
                "type": "boolean",
                "description": "Pretty print JSON",
                "default": True,
            },
        },
        "required": ["query", "filename"],
    },
    permission_level=1,
)
async def export_to_json(
    query: str,
    filename: str,
    pretty: bool = True,
) -> ToolResult:
    """Export query results to JSON."""
    try:
        # Validate query
        query_lower = query.lower().strip()
        if not query_lower.startswith("select"):
            return ToolResult.fail("Only SELECT queries can be exported")

        file_path = _validate_path(filename)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        conn = await _get_connection()
        try:
            rows = await conn.fetch(query)

            # Convert to list of dicts with JSON-serializable values
            data = []
            for row in rows:
                record = {}
                for key, value in dict(row).items():
                    if isinstance(value, datetime):
                        record[key] = value.isoformat()
                    elif isinstance(value, bytes):
                        record[key] = value.hex()
                    else:
                        record[key] = value
                data.append(record)

            # Write JSON
            indent = 2 if pretty else None
            json_content = json.dumps(data, indent=indent, default=str)

            async with aiofiles.open(file_path, "w") as f:
                await f.write(json_content)

            return ToolResult.ok(
                f"Exported {len(data)} records to {filename}",
                records=len(data),
                file=str(file_path),
            )

        finally:
            await conn.close()

    except ValueError as e:
        return ToolResult.fail(str(e))
    except asyncpg.PostgresError as e:
        logger.error("Export to JSON failed", query=query, error=str(e))
        return ToolResult.fail(f"SQL error: {e}")
    except Exception as e:
        logger.error("Export failed", error=str(e))
        return ToolResult.fail(f"Export failed: {e}")


@tool(
    name="import_from_csv",
    description="Import data from a CSV file (returns preview, does not insert)",
    parameters={
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "CSV filename (relative to data directory)",
            },
            "preview_rows": {
                "type": "integer",
                "description": "Number of rows to preview",
                "default": 10,
            },
        },
        "required": ["filename"],
    },
)
async def import_from_csv(
    filename: str,
    preview_rows: int = 10,
) -> ToolResult:
    """Preview CSV data for import."""
    try:
        file_path = _validate_path(filename)

        if not file_path.exists():
            return ToolResult.fail(f"File not found: {filename}")

        async with aiofiles.open(file_path, "r") as f:
            content = await f.read()

        # Parse CSV
        lines = content.strip().split("\n")
        if not lines:
            return ToolResult.fail("Empty CSV file")

        reader = csv.DictReader(lines)
        columns = reader.fieldnames or []

        rows = []
        total_rows = 0
        for row in reader:
            total_rows += 1
            if len(rows) < preview_rows:
                rows.append(dict(row))

        return ToolResult.ok(
            {
                "columns": columns,
                "preview": rows,
                "total_rows": total_rows,
            },
            file=str(file_path),
        )

    except ValueError as e:
        return ToolResult.fail(str(e))
    except csv.Error as e:
        logger.error("CSV parsing failed", filename=filename, error=str(e))
        return ToolResult.fail(f"CSV parsing error: {e}")
    except Exception as e:
        logger.error("Import preview failed", error=str(e))
        return ToolResult.fail(f"Import preview failed: {e}")


@tool(
    name="transform_data",
    description="Apply transformations to data and save result",
    parameters={
        "type": "object",
        "properties": {
            "input_file": {
                "type": "string",
                "description": "Input JSON file",
            },
            "output_file": {
                "type": "string",
                "description": "Output JSON file",
            },
            "transformations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["filter", "map", "select", "rename"],
                        },
                        "config": {
                            "type": "object",
                        },
                    },
                },
                "description": "List of transformations to apply",
            },
        },
        "required": ["input_file", "output_file", "transformations"],
    },
    permission_level=1,
)
async def transform_data(
    input_file: str,
    output_file: str,
    transformations: list[dict[str, Any]],
) -> ToolResult:
    """Apply transformations to JSON data."""
    try:
        input_path = _validate_path(input_file)
        output_path = _validate_path(output_file)

        if not input_path.exists():
            return ToolResult.fail(f"Input file not found: {input_file}")

        # Read input
        async with aiofiles.open(input_path, "r") as f:
            content = await f.read()
        data = json.loads(content)

        if not isinstance(data, list):
            return ToolResult.fail("Input must be a JSON array")

        original_count = len(data)

        # Apply transformations
        for transform in transformations:
            t_type = transform.get("type")
            config = transform.get("config", {})

            if t_type == "filter":
                # Filter records by field value
                field = config.get("field")
                value = config.get("value")
                operator = config.get("operator", "eq")

                if field:
                    if operator == "eq":
                        data = [r for r in data if r.get(field) == value]
                    elif operator == "ne":
                        data = [r for r in data if r.get(field) != value]
                    elif operator == "contains":
                        data = [
                            r for r in data if value in str(r.get(field, ""))
                        ]
                    elif operator == "gt":
                        data = [r for r in data if r.get(field, 0) > value]
                    elif operator == "lt":
                        data = [r for r in data if r.get(field, 0) < value]

            elif t_type == "select":
                # Select specific fields
                fields = config.get("fields", [])
                if fields:
                    data = [
                        {k: r.get(k) for k in fields if k in r} for r in data
                    ]

            elif t_type == "rename":
                # Rename fields
                mapping = config.get("mapping", {})
                if mapping:
                    for record in data:
                        for old_name, new_name in mapping.items():
                            if old_name in record:
                                record[new_name] = record.pop(old_name)

            elif t_type == "map":
                # Map field values
                field = config.get("field")
                mapping = config.get("mapping", {})
                if field and mapping:
                    for record in data:
                        if field in record:
                            old_val = str(record[field])
                            if old_val in mapping:
                                record[field] = mapping[old_val]

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        json_content = json.dumps(data, indent=2, default=str)

        async with aiofiles.open(output_path, "w") as f:
            await f.write(json_content)

        return ToolResult.ok(
            f"Transformed {original_count} -> {len(data)} records",
            input_count=original_count,
            output_count=len(data),
            output_file=str(output_path),
        )

    except ValueError as e:
        return ToolResult.fail(str(e))
    except json.JSONDecodeError as e:
        logger.error("JSON parsing failed", error=str(e))
        return ToolResult.fail(f"Invalid JSON: {e}")
    except Exception as e:
        logger.error("Transform failed", error=str(e))
        return ToolResult.fail(f"Transform failed: {e}")
