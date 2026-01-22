"""
Security Guidance Plugin Hooks.

Monitors all operations for security issues.
"""

from typing import Any
from .tools import DANGEROUS_OPERATIONS, security_scan


def security_monitor(context: dict[str, Any]) -> dict[str, Any]:
    """
    Monitor all tool usage for security patterns.

    This hook runs before every tool use to check for dangerous operations.
    """
    tool_name = context.get("tool_name", "")
    tool_args = context.get("tool_args", {})

    violations = []

    # Check command execution tools
    if tool_name in ("bash", "run_command", "execute", "shell"):
        command = tool_args.get("command", "")

        # Check for dangerous operations
        for dangerous in DANGEROUS_OPERATIONS:
            if dangerous in command:
                violations.append({
                    "type": "dangerous_command",
                    "pattern": dangerous,
                    "severity": "critical",
                    "blocked": True,
                })

        # Run security scan on command
        scan_result = security_scan(command, type="command")
        if scan_result.get("should_block"):
            violations.extend([
                {
                    "type": "security_pattern",
                    "pattern": f["description"],
                    "severity": f["severity"],
                    "blocked": True,
                }
                for f in scan_result.get("findings", [])
            ])

    # Check file write operations
    if tool_name in ("write_file", "edit_file", "create_file"):
        content = tool_args.get("content", "")
        file_path = tool_args.get("file_path", tool_args.get("path", ""))

        # Check for writing to sensitive paths
        sensitive_paths = ["/etc/", "/root/", "/var/log/", ".ssh/", ".env"]
        for sensitive in sensitive_paths:
            if sensitive in file_path:
                violations.append({
                    "type": "sensitive_path",
                    "path": file_path,
                    "severity": "high",
                    "blocked": False,  # Warn but don't block
                    "warning": f"Writing to sensitive path: {sensitive}",
                })

        # Scan content for secrets
        scan_result = security_scan(content, type="code")
        for finding in scan_result.get("findings", []):
            if finding["severity"] == "critical" and "secret" in finding["description"].lower():
                violations.append({
                    "type": "secret_exposure",
                    "pattern": finding["description"],
                    "severity": "critical",
                    "blocked": True,
                })

    if violations:
        context["security_violations"] = violations
        context["security_blocked"] = any(v.get("blocked") for v in violations)

        if context["security_blocked"]:
            context["block_reason"] = "Security violation detected"
            context["block_details"] = [
                v for v in violations if v.get("blocked")
            ]

    return context


def init_security_context(context: dict[str, Any]) -> dict[str, Any]:
    """Initialize security context at session start."""
    context["security"] = {
        "monitoring_enabled": True,
        "violation_count": 0,
        "warnings": [],
    }
    return context
