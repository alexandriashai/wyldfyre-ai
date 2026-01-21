"""
Security validation tools for the QA Agent.
"""

import asyncio
import os
import re
from pathlib import Path
from typing import Any

import aiofiles

from ai_core import get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Workspace configuration
WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_DIR", "/app/workspace"))

# Patterns for secret detection
SECRET_PATTERNS = [
    (r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"]?([a-zA-Z0-9_-]{20,})['\"]?", "API Key"),
    (r"(?i)(secret[_-]?key|secretkey)\s*[=:]\s*['\"]?([a-zA-Z0-9_-]{20,})['\"]?", "Secret Key"),
    (r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"]([^'\"]+)['\"]", "Password"),
    (r"(?i)(aws[_-]?access[_-]?key[_-]?id)\s*[=:]\s*['\"]?(AKIA[A-Z0-9]{16})['\"]?", "AWS Access Key"),
    (r"(?i)(aws[_-]?secret[_-]?access[_-]?key)\s*[=:]\s*['\"]?([a-zA-Z0-9/+=]{40})['\"]?", "AWS Secret Key"),
    (r"-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----", "Private Key"),
    (r"(?i)(token|bearer)\s*[=:]\s*['\"]?([a-zA-Z0-9_-]{20,})['\"]?", "Token"),
    (r"(?i)ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
    (r"(?i)gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
    (r"(?i)sk-[a-zA-Z0-9]{48}", "OpenAI API Key"),
    (r"(?i)sk-ant-[a-zA-Z0-9-]{95}", "Anthropic API Key"),
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "Email Address"),
]

# Files to skip
SKIP_PATTERNS = [
    r"\.git/",
    r"node_modules/",
    r"__pycache__/",
    r"\.pyc$",
    r"\.min\.js$",
    r"\.min\.css$",
    r"package-lock\.json$",
    r"\.lock$",
]


def _validate_workspace_path(path: str) -> Path:
    """Validate and resolve a path within workspace."""
    workspace_resolved = WORKSPACE_DIR.resolve()
    resolved = (WORKSPACE_DIR / path).resolve()

    try:
        resolved.relative_to(workspace_resolved)
    except ValueError:
        raise ValueError(f"Path escapes workspace: {path}")

    return resolved


def _should_skip_file(path: Path) -> bool:
    """Check if file should be skipped."""
    path_str = str(path)
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, path_str):
            return True
    return False


@tool(
    name="check_secrets",
    description="Scan files for hardcoded secrets and credentials",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to scan",
                "default": ".",
            },
            "file_pattern": {
                "type": "string",
                "description": "File pattern to match",
                "default": "**/*",
            },
            "include_env_files": {
                "type": "boolean",
                "description": "Include .env files in scan",
                "default": True,
            },
        },
    },
)
async def check_secrets(
    path: str = ".",
    file_pattern: str = "**/*",
    include_env_files: bool = True,
) -> ToolResult:
    """Scan for hardcoded secrets."""
    try:
        scan_path = _validate_workspace_path(path)

        if not scan_path.exists():
            return ToolResult.fail(f"Path not found: {path}")

        findings: list[dict[str, Any]] = []
        files_scanned = 0

        # Collect files
        if scan_path.is_file():
            files = [scan_path]
        else:
            files = list(scan_path.glob(file_pattern))

        for file_path in files:
            if not file_path.is_file():
                continue

            if _should_skip_file(file_path):
                continue

            # Skip .env files if not requested
            if not include_env_files and file_path.name.startswith(".env"):
                continue

            # Skip binary files
            try:
                async with aiofiles.open(file_path, "r", errors="ignore") as f:
                    content = await f.read()
            except Exception:
                continue

            files_scanned += 1

            rel_path = str(file_path.relative_to(WORKSPACE_DIR))

            for line_num, line in enumerate(content.splitlines(), 1):
                for pattern, secret_type in SECRET_PATTERNS:
                    matches = re.finditer(pattern, line)
                    for match in matches:
                        # Don't report if it looks like an example or placeholder
                        value = match.group(0)
                        if any(
                            placeholder in value.lower()
                            for placeholder in [
                                "example",
                                "placeholder",
                                "your_",
                                "xxx",
                                "changeme",
                                "${",
                                "{{",
                            ]
                        ):
                            continue

                        findings.append({
                            "file": rel_path,
                            "line": line_num,
                            "type": secret_type,
                            "match": value[:50] + "..." if len(value) > 50 else value,
                            "severity": "high" if "key" in secret_type.lower() else "medium",
                        })

        # Categorize findings
        by_severity = {"high": 0, "medium": 0, "low": 0}
        for finding in findings:
            sev = finding.get("severity", "medium")
            by_severity[sev] = by_severity.get(sev, 0) + 1

        result = {
            "files_scanned": files_scanned,
            "findings": findings[:50],  # Limit output
            "finding_count": len(findings),
            "by_severity": by_severity,
            "has_critical": by_severity.get("high", 0) > 0,
        }

        return ToolResult.ok(result)

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Check secrets failed", path=path, error=str(e))
        return ToolResult.fail(f"Check secrets failed: {e}")


@tool(
    name="scan_dependencies",
    description="Scan dependencies for known vulnerabilities",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to requirements.txt or pyproject.toml",
            },
        },
        "required": ["path"],
    },
)
async def scan_dependencies(path: str) -> ToolResult:
    """Scan dependencies for vulnerabilities using pip-audit."""
    try:
        file_path = _validate_workspace_path(path)

        if not file_path.exists():
            return ToolResult.fail(f"File not found: {path}")

        # Run pip-audit
        cmd = ["python", "-m", "pip_audit"]

        if path.endswith(".txt"):
            cmd.extend(["-r", str(file_path)])
        else:
            cmd.extend(["--desc", "on"])

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=WORKSPACE_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=300,
        )

        output = stdout.decode().strip()
        errors = stderr.decode().strip()

        # Parse output
        vulnerabilities: list[dict[str, str]] = []

        for line in output.splitlines():
            # Look for vulnerability entries
            if "PYSEC-" in line or "CVE-" in line or "GHSA-" in line:
                parts = line.split()
                if len(parts) >= 3:
                    vulnerabilities.append({
                        "package": parts[0],
                        "version": parts[1],
                        "vulnerability_id": parts[2],
                        "severity": "unknown",
                    })

        # Check if pip-audit succeeded
        if process.returncode != 0 and "No known vulnerabilities found" not in output:
            if "pip_audit" in errors.lower() or "no module" in errors.lower():
                return ToolResult.fail(
                    "pip-audit not installed. Install with: pip install pip-audit"
                )

        result = {
            "file": path,
            "vulnerabilities": vulnerabilities,
            "vulnerability_count": len(vulnerabilities),
            "secure": len(vulnerabilities) == 0,
            "output": output[:2000],
        }

        return ToolResult.ok(result)

    except asyncio.TimeoutError:
        return ToolResult.fail("Dependency scan timed out")
    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Scan dependencies failed", path=path, error=str(e))
        return ToolResult.fail(f"Scan dependencies failed: {e}")


@tool(
    name="validate_permissions",
    description="Check file and directory permissions for security issues",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to check",
                "default": ".",
            },
            "check_sensitive": {
                "type": "boolean",
                "description": "Focus on sensitive files (keys, configs)",
                "default": True,
            },
        },
    },
)
async def validate_permissions(
    path: str = ".",
    check_sensitive: bool = True,
) -> ToolResult:
    """Validate file permissions."""
    try:
        check_path = _validate_workspace_path(path)

        if not check_path.exists():
            return ToolResult.fail(f"Path not found: {path}")

        issues: list[dict[str, Any]] = []
        files_checked = 0

        # Sensitive file patterns
        sensitive_patterns = [
            r"\.env",
            r"\.pem$",
            r"\.key$",
            r"id_rsa",
            r"id_dsa",
            r"id_ed25519",
            r"\.p12$",
            r"\.pfx$",
            r"credentials",
            r"secrets",
            r"config.*\.json$",
            r"config.*\.yaml$",
            r"config.*\.yml$",
        ]

        def is_sensitive(file_path: Path) -> bool:
            name = file_path.name.lower()
            path_str = str(file_path).lower()
            return any(
                re.search(pattern, path_str, re.IGNORECASE)
                for pattern in sensitive_patterns
            )

        # Walk directory
        if check_path.is_file():
            files = [check_path]
        else:
            files = list(check_path.rglob("*"))

        for file_path in files:
            if not file_path.exists():
                continue

            if _should_skip_file(file_path):
                continue

            # Skip if only checking sensitive and file isn't sensitive
            if check_sensitive and not is_sensitive(file_path):
                continue

            files_checked += 1

            try:
                stat = file_path.stat()
                mode = stat.st_mode
                rel_path = str(file_path.relative_to(WORKSPACE_DIR))

                # Check for world-readable sensitive files
                if is_sensitive(file_path):
                    # World readable (o+r)
                    if mode & 0o004:
                        issues.append({
                            "file": rel_path,
                            "issue": "Sensitive file is world-readable",
                            "severity": "high",
                            "current_mode": oct(mode)[-3:],
                            "recommended_mode": "600",
                        })

                    # World writable (o+w)
                    if mode & 0o002:
                        issues.append({
                            "file": rel_path,
                            "issue": "File is world-writable",
                            "severity": "critical",
                            "current_mode": oct(mode)[-3:],
                            "recommended_mode": "600",
                        })

                # Check for executable scripts without proper permissions
                if file_path.suffix in (".sh", ".py") and file_path.is_file():
                    # Check if file has shebang
                    try:
                        with open(file_path, "rb") as f:
                            first_line = f.readline()
                        if first_line.startswith(b"#!"):
                            # Should be executable
                            if not (mode & 0o100):
                                issues.append({
                                    "file": rel_path,
                                    "issue": "Script with shebang is not executable",
                                    "severity": "info",
                                    "current_mode": oct(mode)[-3:],
                                })
                    except Exception:
                        pass

            except OSError as e:
                logger.warning(f"Error checking {file_path}: {e}")

        # Categorize by severity
        by_severity: dict[str, int] = {}
        for issue in issues:
            sev = issue.get("severity", "medium")
            by_severity[sev] = by_severity.get(sev, 0) + 1

        result = {
            "files_checked": files_checked,
            "issues": issues[:50],
            "issue_count": len(issues),
            "by_severity": by_severity,
            "has_critical": by_severity.get("critical", 0) > 0,
        }

        return ToolResult.ok(result)

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Validate permissions failed", path=path, error=str(e))
        return ToolResult.fail(f"Validate permissions failed: {e}")
