"""
Code Review Plugin Tools.

Provides code review, security analysis, and improvement suggestions.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IssueCategory(str, Enum):
    SECURITY = "security"
    BUG = "bug"
    PERFORMANCE = "performance"
    STYLE = "style"
    BEST_PRACTICE = "best_practice"
    MAINTAINABILITY = "maintainability"


@dataclass
class ReviewIssue:
    """A code review issue."""
    category: IssueCategory
    severity: Severity
    message: str
    line: int | None = None
    file: str | None = None
    suggestion: str | None = None
    confidence: float = 0.8

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "line": self.line,
            "file": self.file,
            "suggestion": self.suggestion,
            "confidence": self.confidence,
        }


# Security patterns to detect
SECURITY_PATTERNS = [
    # SQL Injection
    (r"f['\"].*SELECT.*{.*}.*FROM", "Potential SQL injection via f-string", Severity.CRITICAL),
    (r"\.format\(.*\).*SELECT", "Potential SQL injection via string format", Severity.CRITICAL),
    (r"\+\s*['\"].*SELECT", "Potential SQL injection via string concatenation", Severity.HIGH),

    # Command Injection
    (r"os\.system\s*\(", "os.system() usage - potential command injection", Severity.CRITICAL),
    (r"subprocess\..*shell\s*=\s*True", "Shell=True in subprocess - potential command injection", Severity.HIGH),
    (r"eval\s*\(", "eval() usage - potential code injection", Severity.CRITICAL),
    (r"exec\s*\(", "exec() usage - potential code injection", Severity.CRITICAL),

    # XSS
    (r"innerHTML\s*=", "innerHTML assignment - potential XSS", Severity.HIGH),
    (r"document\.write\s*\(", "document.write() - potential XSS", Severity.HIGH),
    (r"dangerouslySetInnerHTML", "dangerouslySetInnerHTML usage - ensure sanitization", Severity.MEDIUM),

    # Secrets
    (r"password\s*=\s*['\"][^'\"]+['\"]", "Hardcoded password detected", Severity.CRITICAL),
    (r"api[_-]?key\s*=\s*['\"][^'\"]+['\"]", "Hardcoded API key detected", Severity.CRITICAL),
    (r"secret\s*=\s*['\"][^'\"]+['\"]", "Hardcoded secret detected", Severity.CRITICAL),

    # Unsafe deserialization
    (r"pickle\.load", "Unsafe pickle deserialization", Severity.HIGH),
    (r"yaml\.load\s*\([^)]*\)", "yaml.load() without Loader - use safe_load", Severity.MEDIUM),

    # Path traversal
    (r"open\s*\([^)]*\+[^)]*\)", "File open with concatenation - potential path traversal", Severity.MEDIUM),
]

# Code quality patterns
QUALITY_PATTERNS = [
    # Python
    (r"except\s*:", "Bare except clause - catches all exceptions", Severity.MEDIUM, IssueCategory.BEST_PRACTICE),
    (r"from\s+\S+\s+import\s+\*", "Wildcard import - be explicit", Severity.LOW, IssueCategory.STYLE),
    (r"global\s+\w+", "Global variable usage - consider alternatives", Severity.LOW, IssueCategory.MAINTAINABILITY),
    (r"#\s*TODO", "TODO comment found", Severity.INFO, IssueCategory.MAINTAINABILITY),
    (r"#\s*FIXME", "FIXME comment found", Severity.MEDIUM, IssueCategory.BUG),
    (r"#\s*HACK", "HACK comment found - needs cleanup", Severity.MEDIUM, IssueCategory.MAINTAINABILITY),

    # JavaScript/TypeScript
    (r"console\.log\s*\(", "console.log() left in code", Severity.LOW, IssueCategory.STYLE),
    (r"debugger;", "Debugger statement left in code", Severity.MEDIUM, IssueCategory.BUG),
    (r"==\s*null|null\s*==", "Use === for null comparison", Severity.LOW, IssueCategory.BEST_PRACTICE),
    (r"var\s+\w+", "Use let/const instead of var", Severity.LOW, IssueCategory.STYLE),
]


def review_code(
    diff: str,
    context: str | None = None,
    focus_areas: list[str] | None = None,
) -> dict[str, Any]:
    """
    Review code changes for issues.

    Args:
        diff: Git diff or code changes to review
        context: Additional context about the changes
        focus_areas: Specific areas to focus on

    Returns:
        Review results with issues found
    """
    issues: list[ReviewIssue] = []
    focus = set(focus_areas or [])

    # Extract added lines from diff
    added_lines = []
    current_file = None
    line_number = 0

    for line in diff.split("\n"):
        # Track current file
        if line.startswith("+++ b/"):
            current_file = line[6:]
            line_number = 0
        elif line.startswith("@@"):
            # Parse line number from hunk header
            match = re.search(r"\+(\d+)", line)
            if match:
                line_number = int(match.group(1)) - 1
        elif line.startswith("+") and not line.startswith("+++"):
            line_number += 1
            added_lines.append((current_file, line_number, line[1:]))
        elif not line.startswith("-"):
            line_number += 1

    # Check security patterns
    if not focus or "security" in focus:
        for file, line_num, content in added_lines:
            for pattern, message, severity in SECURITY_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    issues.append(ReviewIssue(
                        category=IssueCategory.SECURITY,
                        severity=severity,
                        message=message,
                        line=line_num,
                        file=file,
                        confidence=0.85,
                    ))

    # Check quality patterns
    if not focus or any(f in focus for f in ["style", "quality", "best_practice"]):
        for file, line_num, content in added_lines:
            for item in QUALITY_PATTERNS:
                pattern, message, severity, category = item
                if re.search(pattern, content):
                    issues.append(ReviewIssue(
                        category=category,
                        severity=severity,
                        message=message,
                        line=line_num,
                        file=file,
                        confidence=0.75,
                    ))

    # Group issues by severity
    by_severity = {s.value: [] for s in Severity}
    for issue in issues:
        by_severity[issue.severity.value].append(issue.to_dict())

    # Calculate summary
    total_issues = len(issues)
    critical_count = len(by_severity["critical"])
    high_count = len(by_severity["high"])

    return {
        "success": True,
        "summary": {
            "total_issues": total_issues,
            "by_severity": {k: len(v) for k, v in by_severity.items()},
            "needs_attention": critical_count > 0 or high_count > 0,
        },
        "issues": [i.to_dict() for i in issues],
        "recommendations": _generate_recommendations(issues),
    }


def suggest_improvements(
    code: str,
    language: str | None = None,
) -> dict[str, Any]:
    """
    Suggest code improvements and refactoring opportunities.

    Args:
        code: Code to analyze
        language: Programming language

    Returns:
        Improvement suggestions
    """
    suggestions = []

    # Detect long functions
    function_pattern = r"(def\s+\w+|function\s+\w+|const\s+\w+\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)"
    functions = re.findall(function_pattern, code)
    lines = code.split("\n")

    if len(lines) > 50:
        suggestions.append({
            "type": "refactoring",
            "message": "Consider breaking this into smaller functions",
            "reason": f"Code is {len(lines)} lines - aim for <50 lines per function",
        })

    # Detect repeated code patterns
    if code.count("if ") > 5:
        suggestions.append({
            "type": "refactoring",
            "message": "Multiple conditionals detected - consider using a mapping or strategy pattern",
            "reason": "Reduces cyclomatic complexity",
        })

    # Check for magic numbers
    magic_numbers = re.findall(r"(?<!['\"\w])\d{2,}(?!['\"\w])", code)
    if magic_numbers:
        suggestions.append({
            "type": "maintainability",
            "message": "Extract magic numbers into named constants",
            "reason": f"Found magic numbers: {magic_numbers[:5]}",
        })

    # Check for deep nesting
    max_indent = max((len(line) - len(line.lstrip()) for line in lines if line.strip()), default=0)
    if max_indent > 16:  # More than 4 levels
        suggestions.append({
            "type": "refactoring",
            "message": "Deep nesting detected - consider early returns or extracting methods",
            "reason": "Deep nesting reduces readability",
        })

    return {
        "success": True,
        "suggestions": suggestions,
        "metrics": {
            "total_lines": len(lines),
            "function_count": len(functions),
            "max_nesting": max_indent // 4,
        },
    }


def check_security(
    code: str,
    language: str | None = None,
) -> dict[str, Any]:
    """
    Check code for security vulnerabilities.

    Args:
        code: Code to analyze
        language: Programming language

    Returns:
        Security analysis results
    """
    vulnerabilities = []

    for pattern, message, severity in SECURITY_PATTERNS:
        matches = list(re.finditer(pattern, code, re.IGNORECASE | re.MULTILINE))
        for match in matches:
            # Find line number
            line_num = code[:match.start()].count("\n") + 1
            vulnerabilities.append({
                "severity": severity.value,
                "message": message,
                "line": line_num,
                "match": match.group()[:50],  # First 50 chars of match
            })

    # Calculate risk score
    severity_weights = {"critical": 10, "high": 5, "medium": 2, "low": 1}
    risk_score = sum(
        severity_weights.get(v["severity"], 0)
        for v in vulnerabilities
    )

    return {
        "success": True,
        "vulnerabilities": vulnerabilities,
        "risk_score": min(risk_score, 100),  # Cap at 100
        "risk_level": (
            "critical" if risk_score >= 20 else
            "high" if risk_score >= 10 else
            "medium" if risk_score >= 5 else
            "low"
        ),
        "recommendations": [
            "Review all critical and high severity issues before merging",
            "Consider using a SAST tool for continuous security scanning",
            "Ensure secrets are stored in environment variables or secret managers",
        ] if vulnerabilities else ["No obvious security issues detected"],
    }


def _generate_recommendations(issues: list[ReviewIssue]) -> list[str]:
    """Generate recommendations based on issues found."""
    recommendations = []

    categories = {i.category for i in issues}
    severities = {i.severity for i in issues}

    if IssueCategory.SECURITY in categories:
        recommendations.append("Address security issues before merging - they may expose vulnerabilities")

    if Severity.CRITICAL in severities:
        recommendations.append("Critical issues found - these should be fixed immediately")

    if IssueCategory.MAINTAINABILITY in categories:
        recommendations.append("Consider addressing maintainability issues to reduce technical debt")

    if not recommendations:
        recommendations.append("Code looks good! Consider getting a peer review for additional perspectives")

    return recommendations
