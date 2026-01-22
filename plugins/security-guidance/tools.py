"""
Security Guidance Plugin Tools.

Provides security scanning and recommendations.
"""

import re
from typing import Any

# Security patterns organized by category
SECURITY_PATTERNS = {
    "injection": [
        (r"os\.system\s*\(", "Command injection via os.system", "critical"),
        (r"subprocess\..*shell\s*=\s*True", "Shell injection risk", "high"),
        (r"eval\s*\(", "Code injection via eval", "critical"),
        (r"exec\s*\(", "Code injection via exec", "critical"),
        (r"__import__\s*\(", "Dynamic import - potential injection", "medium"),
    ],
    "sql": [
        (r"f['\"].*SELECT.*{", "SQL injection via f-string", "critical"),
        (r"\.format\(.*SELECT", "SQL injection via format", "critical"),
        (r"\+.*SELECT.*\+", "SQL injection via concatenation", "high"),
        (r"cursor\.execute\([^,]+%", "SQL injection via % formatting", "high"),
    ],
    "xss": [
        (r"innerHTML\s*=", "XSS via innerHTML", "high"),
        (r"document\.write\s*\(", "XSS via document.write", "high"),
        (r"\.html\s*\([^)]*\+", "XSS via jQuery html()", "medium"),
    ],
    "secrets": [
        (r"password\s*=\s*['\"][^'\"]{3,}['\"]", "Hardcoded password", "critical"),
        (r"api[_-]?key\s*=\s*['\"][^'\"]{10,}['\"]", "Hardcoded API key", "critical"),
        (r"secret[_-]?key\s*=\s*['\"][^'\"]{10,}['\"]", "Hardcoded secret", "critical"),
        (r"bearer\s+[a-zA-Z0-9_-]{20,}", "Exposed bearer token", "critical"),
    ],
    "dangerous_commands": [
        (r"rm\s+-rf\s+/", "Dangerous rm -rf /", "critical"),
        (r"chmod\s+777", "Overly permissive chmod", "high"),
        (r"dd\s+if=.*of=/dev/", "Dangerous dd command", "critical"),
        (r">\s*/dev/sd[a-z]", "Writing to disk device", "critical"),
        (r"mkfs\.", "Filesystem format command", "critical"),
    ],
    "path_traversal": [
        (r"\.\.\/", "Path traversal attempt", "high"),
        (r"\.\.\\\\", "Path traversal attempt (Windows)", "high"),
    ],
}

DANGEROUS_OPERATIONS = [
    "rm -rf",
    "dd if=",
    "mkfs",
    "> /dev/",
    "chmod 777",
    "curl | sh",
    "wget | sh",
    "eval(",
    "exec(",
]


def security_scan(
    content: str,
    type: str = "code",
) -> dict[str, Any]:
    """
    Scan content for security issues.

    Args:
        content: Code, command, or config to scan
        type: Type of content

    Returns:
        Security scan results
    """
    findings = []
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    # Select patterns based on type
    patterns_to_check = []
    if type == "code":
        patterns_to_check = (
            SECURITY_PATTERNS["injection"] +
            SECURITY_PATTERNS["sql"] +
            SECURITY_PATTERNS["xss"] +
            SECURITY_PATTERNS["secrets"]
        )
    elif type == "command":
        patterns_to_check = SECURITY_PATTERNS["dangerous_commands"]
    else:
        # Check all patterns for config
        for category_patterns in SECURITY_PATTERNS.values():
            patterns_to_check.extend(category_patterns)

    # Scan for patterns
    for pattern, description, severity in patterns_to_check:
        matches = list(re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE))
        for match in matches:
            line_num = content[:match.start()].count("\n") + 1
            findings.append({
                "severity": severity,
                "description": description,
                "line": line_num,
                "match": match.group()[:100],
            })
            severity_counts[severity] += 1

    # Calculate risk score
    risk_score = (
        severity_counts["critical"] * 25 +
        severity_counts["high"] * 10 +
        severity_counts["medium"] * 3 +
        severity_counts["low"] * 1
    )

    return {
        "success": True,
        "scan_type": type,
        "findings": findings,
        "summary": {
            "total_issues": len(findings),
            "by_severity": severity_counts,
            "risk_score": min(risk_score, 100),
            "risk_level": (
                "critical" if severity_counts["critical"] > 0 else
                "high" if severity_counts["high"] > 0 else
                "medium" if severity_counts["medium"] > 0 else
                "low" if findings else "none"
            ),
        },
        "should_block": severity_counts["critical"] > 0,
    }


def get_security_recommendations(
    context: str,
    language: str | None = None,
) -> dict[str, Any]:
    """
    Get security recommendations for a context.

    Args:
        context: Task or context description
        language: Programming language

    Returns:
        Security recommendations
    """
    recommendations = []

    context_lower = context.lower()

    # Authentication related
    if any(word in context_lower for word in ["auth", "login", "password", "credential"]):
        recommendations.extend([
            {
                "category": "authentication",
                "recommendation": "Use bcrypt or argon2 for password hashing",
                "priority": "high",
            },
            {
                "category": "authentication",
                "recommendation": "Implement rate limiting on login endpoints",
                "priority": "high",
            },
            {
                "category": "authentication",
                "recommendation": "Use secure session management with httpOnly cookies",
                "priority": "high",
            },
        ])

    # API related
    if any(word in context_lower for word in ["api", "endpoint", "rest", "graphql"]):
        recommendations.extend([
            {
                "category": "api",
                "recommendation": "Validate and sanitize all input data",
                "priority": "critical",
            },
            {
                "category": "api",
                "recommendation": "Implement proper CORS configuration",
                "priority": "medium",
            },
            {
                "category": "api",
                "recommendation": "Use parameterized queries for database operations",
                "priority": "critical",
            },
        ])

    # Database related
    if any(word in context_lower for word in ["database", "sql", "query", "db"]):
        recommendations.extend([
            {
                "category": "database",
                "recommendation": "Never concatenate user input in SQL queries",
                "priority": "critical",
            },
            {
                "category": "database",
                "recommendation": "Use an ORM or query builder with parameterization",
                "priority": "high",
            },
            {
                "category": "database",
                "recommendation": "Apply principle of least privilege for DB users",
                "priority": "medium",
            },
        ])

    # File operations
    if any(word in context_lower for word in ["file", "upload", "download", "path"]):
        recommendations.extend([
            {
                "category": "file_handling",
                "recommendation": "Validate file types and sizes on upload",
                "priority": "high",
            },
            {
                "category": "file_handling",
                "recommendation": "Sanitize file names to prevent path traversal",
                "priority": "critical",
            },
            {
                "category": "file_handling",
                "recommendation": "Store uploads outside web root",
                "priority": "medium",
            },
        ])

    # Default recommendations
    if not recommendations:
        recommendations = [
            {
                "category": "general",
                "recommendation": "Follow the principle of least privilege",
                "priority": "high",
            },
            {
                "category": "general",
                "recommendation": "Keep dependencies updated",
                "priority": "medium",
            },
            {
                "category": "general",
                "recommendation": "Enable logging for security events",
                "priority": "medium",
            },
        ]

    return {
        "success": True,
        "context": context,
        "recommendations": recommendations,
        "resources": [
            "OWASP Top 10: https://owasp.org/Top10/",
            "CWE Top 25: https://cwe.mitre.org/top25/",
        ],
    }
