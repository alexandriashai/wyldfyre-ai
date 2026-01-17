"""
Backup tools for the Data Agent.
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path

from ai_core import get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Backup configuration
WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_DIR", "/app/workspace"))
BACKUP_DIR = WORKSPACE_DIR / "backups"

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/ai_infrastructure",
)


def _validate_backup_path(path: str) -> Path:
    """Validate and resolve a path within backup directory."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    backup_resolved = BACKUP_DIR.resolve()
    resolved = (BACKUP_DIR / path).resolve()

    try:
        resolved.relative_to(backup_resolved)
    except ValueError:
        raise ValueError(f"Path escapes backup directory: {path}")

    return resolved


def _parse_database_url(url: str) -> dict[str, str]:
    """Parse database URL into components."""
    # Format: postgresql://user:password@host:port/database
    url = url.replace("postgresql://", "")

    # Split user:password from host:port/database
    if "@" in url:
        auth, rest = url.split("@", 1)
        user, password = auth.split(":", 1) if ":" in auth else (auth, "")
    else:
        user, password = "", ""
        rest = url

    # Split host:port from database
    if "/" in rest:
        host_port, database = rest.split("/", 1)
    else:
        host_port, database = rest, ""

    # Split host from port
    if ":" in host_port:
        host, port = host_port.split(":", 1)
    else:
        host, port = host_port, "5432"

    return {
        "user": user,
        "password": password,
        "host": host,
        "port": port,
        "database": database,
    }


@tool(
    name="create_backup",
    description="Create a database backup using pg_dump",
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Backup name (optional, auto-generated if not provided)",
            },
            "tables": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific tables to backup (all if not specified)",
            },
            "format": {
                "type": "string",
                "enum": ["custom", "plain", "directory"],
                "description": "Backup format",
                "default": "custom",
            },
        },
    },
    permission_level=2,
)
async def create_backup(
    name: str | None = None,
    tables: list[str] | None = None,
    backup_format: str = "custom",
) -> ToolResult:
    """Create a database backup."""
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        # Generate backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if name:
            backup_name = f"{name}_{timestamp}"
        else:
            backup_name = f"backup_{timestamp}"

        # Determine extension based on format
        extensions = {
            "custom": ".dump",
            "plain": ".sql",
            "directory": "",
        }
        ext = extensions.get(backup_format, ".dump")
        backup_file = BACKUP_DIR / f"{backup_name}{ext}"

        # Parse database URL
        db_config = _parse_database_url(DATABASE_URL)

        # Build pg_dump command
        cmd = [
            "pg_dump",
            f"--host={db_config['host']}",
            f"--port={db_config['port']}",
            f"--username={db_config['user']}",
            f"--dbname={db_config['database']}",
            f"--format={backup_format[0]}",  # c, p, or d
            f"--file={backup_file}",
            "--no-password",
        ]

        # Add specific tables if requested
        if tables:
            for table in tables:
                cmd.extend(["--table", table])

        # Set password in environment
        env = os.environ.copy()
        env["PGPASSWORD"] = db_config["password"]

        # Run pg_dump
        process = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode().strip()
            logger.error("Backup failed", error=error_msg)
            return ToolResult.fail(f"Backup failed: {error_msg}")

        # Get backup size
        if backup_format == "directory":
            # Sum up directory contents
            size = sum(
                f.stat().st_size
                for f in backup_file.rglob("*")
                if f.is_file()
            )
        else:
            size = backup_file.stat().st_size

        return ToolResult.ok(
            f"Backup created: {backup_file.name}",
            file=str(backup_file),
            size=size,
            format=backup_format,
            tables=tables,
        )

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Backup creation failed", error=str(e))
        return ToolResult.fail(f"Backup creation failed: {e}")


@tool(
    name="list_backups",
    description="List available database backups",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Filter backups by name pattern",
            },
        },
    },
)
async def list_backups(pattern: str | None = None) -> ToolResult:
    """List available backups."""
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        backups = []

        # List all backup files
        for item in BACKUP_DIR.iterdir():
            name = item.name

            # Apply pattern filter
            if pattern and pattern.lower() not in name.lower():
                continue

            # Determine backup type
            if item.is_dir():
                backup_type = "directory"
                size = sum(
                    f.stat().st_size for f in item.rglob("*") if f.is_file()
                )
            elif name.endswith(".dump"):
                backup_type = "custom"
                size = item.stat().st_size
            elif name.endswith(".sql"):
                backup_type = "plain"
                size = item.stat().st_size
            else:
                continue  # Not a recognized backup

            # Get modification time
            mtime = datetime.fromtimestamp(item.stat().st_mtime)

            backups.append({
                "name": name,
                "type": backup_type,
                "size": size,
                "created": mtime.isoformat(),
                "path": str(item),
            })

        # Sort by creation time, newest first
        backups.sort(key=lambda x: x["created"], reverse=True)

        return ToolResult.ok(
            backups,
            count=len(backups),
            directory=str(BACKUP_DIR),
        )

    except Exception as e:
        logger.error("List backups failed", error=str(e))
        return ToolResult.fail(f"List backups failed: {e}")


@tool(
    name="restore_backup",
    description="Restore a database backup (requires confirmation)",
    parameters={
        "type": "object",
        "properties": {
            "backup_name": {
                "type": "string",
                "description": "Name of the backup file to restore",
            },
            "target_database": {
                "type": "string",
                "description": "Target database name (defaults to current)",
            },
        },
        "required": ["backup_name"],
    },
    permission_level=2,
    requires_confirmation=True,
)
async def restore_backup(
    backup_name: str,
    target_database: str | None = None,
) -> ToolResult:
    """Restore a database backup."""
    try:
        backup_path = _validate_backup_path(backup_name)

        if not backup_path.exists():
            return ToolResult.fail(f"Backup not found: {backup_name}")

        # Parse database URL
        db_config = _parse_database_url(DATABASE_URL)
        target_db = target_database or db_config["database"]

        # Determine restore command based on backup type
        if backup_path.is_dir() or backup_name.endswith(".dump"):
            # pg_restore for custom/directory format
            cmd = [
                "pg_restore",
                f"--host={db_config['host']}",
                f"--port={db_config['port']}",
                f"--username={db_config['user']}",
                f"--dbname={target_db}",
                "--no-password",
                "--clean",  # Drop objects before recreating
                "--if-exists",  # Don't error if objects don't exist
                str(backup_path),
            ]
        elif backup_name.endswith(".sql"):
            # psql for plain SQL format
            cmd = [
                "psql",
                f"--host={db_config['host']}",
                f"--port={db_config['port']}",
                f"--username={db_config['user']}",
                f"--dbname={target_db}",
                "--no-password",
                "-f",
                str(backup_path),
            ]
        else:
            return ToolResult.fail(f"Unrecognized backup format: {backup_name}")

        # Set password in environment
        env = os.environ.copy()
        env["PGPASSWORD"] = db_config["password"]

        # Run restore
        process = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode().strip()
            # pg_restore often has warnings that aren't fatal
            if "ERROR" in error_msg:
                logger.error("Restore failed", error=error_msg)
                return ToolResult.fail(f"Restore failed: {error_msg}")

        return ToolResult.ok(
            f"Restored backup: {backup_name} to {target_db}",
            backup=backup_name,
            database=target_db,
        )

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Restore failed", error=str(e))
        return ToolResult.fail(f"Restore failed: {e}")
