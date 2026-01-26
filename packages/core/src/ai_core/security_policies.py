"""
Enhanced Security Policies for PAI Infrastructure.

Extends the base security system with:
- JSON policy file support (.pai-protected.json)
- Attack tier classification (catastrophic, dangerous, suspicious)
- Pattern-matching validation against commands
- AllowList enforcement (explicit permission required)
- Confirmation-required patterns
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .logging import get_logger
from .security import SecurityValidator, SecurityViolation, ThreatLevel, SecurityAction

logger = get_logger(__name__)


class AttackTier(str, Enum):
    """Classification of attack severity."""
    CATASTROPHIC = "catastrophic"  # System destruction, data loss
    DANGEROUS = "dangerous"        # Security bypass, privilege escalation
    SUSPICIOUS = "suspicious"      # Potentially malicious, needs review
    BENIGN = "benign"              # Normal operation


@dataclass
class PolicyRule:
    """A security policy rule."""
    pattern: str
    tier: AttackTier
    action: str  # "block", "confirm", "warn", "allow"
    message: str
    category: str  # "command", "path", "docker", "network"
    compiled: re.Pattern[str] | None = None

    def __post_init__(self) -> None:
        """Compile the regex pattern."""
        try:
            self.compiled = re.compile(self.pattern, re.IGNORECASE)
        except re.error as e:
            logger.warning(f"Invalid policy pattern: {self.pattern}", error=str(e))
            self.compiled = None


@dataclass
class SecurityPolicies:
    """
    Security policies loaded from .pai-protected.json.

    Structure:
    {
        "version": "1.0",
        "system": {
            "blocked_patterns": [...],      # Catastrophic - always block
            "require_confirmation": [...],  # Dangerous - needs confirmation
            "warn_patterns": [...]          # Suspicious - log warning
        },
        "user": {
            "allowed_directories": [...],   # Explicit allow list
            "blocked_commands": [...],      # User-defined blocks
            "allowed_commands": [...]       # User-defined allows (override blocks)
        },
        "rules": [
            {
                "pattern": "...",
                "tier": "catastrophic|dangerous|suspicious",
                "action": "block|confirm|warn|allow",
                "message": "...",
                "category": "command|path|docker|network"
            }
        ]
    }
    """

    version: str = "1.0"
    blocked_patterns: list[str] = field(default_factory=list)
    require_confirmation: list[str] = field(default_factory=list)
    warn_patterns: list[str] = field(default_factory=list)
    allowed_directories: list[str] = field(default_factory=list)
    blocked_commands: list[str] = field(default_factory=list)
    allowed_commands: list[str] = field(default_factory=list)
    rules: list[PolicyRule] = field(default_factory=list)

    # Compiled patterns for performance
    _blocked_compiled: list[re.Pattern[str]] = field(default_factory=list)
    _confirm_compiled: list[re.Pattern[str]] = field(default_factory=list)
    _warn_compiled: list[re.Pattern[str]] = field(default_factory=list)
    _allowed_compiled: list[re.Pattern[str]] = field(default_factory=list)
    _user_blocked_compiled: list[re.Pattern[str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Compile all patterns."""
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for performance."""
        def compile_list(patterns: list[str]) -> list[re.Pattern[str]]:
            compiled = []
            for p in patterns:
                try:
                    compiled.append(re.compile(p, re.IGNORECASE))
                except re.error:
                    logger.warning(f"Invalid pattern skipped: {p}")
            return compiled

        self._blocked_compiled = compile_list(self.blocked_patterns)
        self._confirm_compiled = compile_list(self.require_confirmation)
        self._warn_compiled = compile_list(self.warn_patterns)
        self._allowed_compiled = compile_list(self.allowed_commands)
        self._user_blocked_compiled = compile_list(self.blocked_commands)

    @classmethod
    def from_json(cls, path: str | Path) -> "SecurityPolicies":
        """Load policies from JSON file."""
        try:
            with open(path) as f:
                data = json.load(f)

            system = data.get("system", {})
            user = data.get("user", {})

            # Parse rules
            rules = []
            for rule_data in data.get("rules", []):
                rules.append(PolicyRule(
                    pattern=rule_data["pattern"],
                    tier=AttackTier(rule_data.get("tier", "suspicious")),
                    action=rule_data.get("action", "warn"),
                    message=rule_data.get("message", "Security rule triggered"),
                    category=rule_data.get("category", "command"),
                ))

            return cls(
                version=data.get("version", "1.0"),
                blocked_patterns=system.get("blocked_patterns", []),
                require_confirmation=system.get("require_confirmation", []),
                warn_patterns=system.get("warn_patterns", []),
                allowed_directories=user.get("allowed_directories", []),
                blocked_commands=user.get("blocked_commands", []),
                allowed_commands=user.get("allowed_commands", []),
                rules=rules,
            )
        except FileNotFoundError:
            logger.warning("Policy file not found, using defaults", path=str(path))
            return cls.get_defaults()
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in policy file", error=str(e), path=str(path))
            return cls.get_defaults()
        except Exception as e:
            logger.error("Failed to load policy file", error=str(e), path=str(path))
            return cls.get_defaults()

    @classmethod
    def get_defaults(cls) -> "SecurityPolicies":
        """Get default security policies."""
        return cls(
            version="1.0",
            blocked_patterns=[
                # Catastrophic patterns - always block
                r"rm\s+(-[rf]+\s+)*[/]$",           # rm -rf /
                r"rm\s+(-[rf]+\s+)*[/]\s*$",        # rm -rf / (with trailing space)
                r":\(\)\s*{\s*:\s*\|\s*:&\s*}\s*;", # Fork bomb
                r"dd\s+if=/dev/zero\s+of=/dev/sd",  # Disk wipe
                r"chmod\s+(-R\s+)?777\s+/",         # Recursive 777 on root
                r"mkfs\.[a-z]+\s+/dev/sd",          # Format disk
                r">\s*/dev/sd[a-z]",                # Overwrite disk
                r"cat\s+/dev/urandom\s*>\s*/dev/sd", # Random to disk
            ],
            require_confirmation=[
                # Dangerous patterns - need confirmation
                r"git\s+push\s+--force",
                r"docker\s+system\s+prune",
                r"DROP\s+TABLE",
                r"DELETE\s+FROM\s+\w+\s*;?\s*$",    # DELETE without WHERE
                r"TRUNCATE\s+TABLE",
                r"rm\s+(-[rf]+\s+)*~",              # Delete home
                r"chmod\s+(-R\s+)?[0-7]{3}\s+/",    # Chmod on root paths
                r"chown\s+(-R\s+)?\w+:\w+\s+/",     # Chown on root paths
            ],
            warn_patterns=[
                # Suspicious patterns - log warning
                r"curl\s+.*\|\s*sh",                # Pipe curl to shell
                r"wget\s+.*\|\s*sh",
                r"eval\s+\$\(",                     # Eval command substitution
                r"base64\s+-d\s*\|",                # Decode and pipe
                r"nc\s+-[el]",                      # Netcat listener
            ],
            allowed_directories=[
                "/home/wyld-core",
                "/tmp",
                "/home/wyld-data/workspaces",
            ],
            blocked_commands=[],
            allowed_commands=[],
            rules=[
                PolicyRule(
                    pattern=r"pkill\s+-9",
                    tier=AttackTier.DANGEROUS,
                    action="confirm",
                    message="Force kill process",
                    category="command",
                ),
                PolicyRule(
                    pattern=r"iptables\s+-F",
                    tier=AttackTier.DANGEROUS,
                    action="confirm",
                    message="Flush firewall rules",
                    category="network",
                ),
            ],
        )


@dataclass
class PolicyValidationResult:
    """Result of policy validation."""
    allowed: bool
    tier: AttackTier
    action: str
    message: str
    rule_name: str = ""
    requires_confirmation: bool = False
    patterns_matched: list[str] = field(default_factory=list)

    def to_security_violation(
        self,
        tool_name: str = "",
        input_summary: str = "",
        agent_name: str | None = None,
    ) -> SecurityViolation:
        """Convert to SecurityViolation for integration with existing system."""
        tier_to_threat = {
            AttackTier.CATASTROPHIC: ThreatLevel.CRITICAL,
            AttackTier.DANGEROUS: ThreatLevel.HIGH,
            AttackTier.SUSPICIOUS: ThreatLevel.MEDIUM,
            AttackTier.BENIGN: ThreatLevel.NONE,
        }

        action_map = {
            "block": SecurityAction.BLOCK,
            "confirm": SecurityAction.WARN,
            "warn": SecurityAction.WARN,
            "allow": SecurityAction.ALLOW,
        }

        return SecurityViolation(
            timestamp=datetime.now(timezone.utc),
            action=action_map.get(self.action, SecurityAction.ALLOW),
            threat_level=tier_to_threat.get(self.tier, ThreatLevel.NONE),
            rule_name=self.rule_name,
            tool_name=tool_name,
            input_summary=input_summary[:200],
            message=self.message,
            agent_name=agent_name,
            blocked=not self.allowed,
        )


class SecurityPolicyValidator:
    """
    Enhanced security validator with policy file support.

    Works alongside the existing SecurityValidator, providing
    additional policy-based validation.
    """

    def __init__(
        self,
        policies: SecurityPolicies | None = None,
        policy_path: str | Path = "/home/wyld-core/.pai-protected.json",
    ):
        if policies:
            self._policies = policies
        else:
            path = Path(policy_path)
            if path.exists():
                self._policies = SecurityPolicies.from_json(path)
            else:
                self._policies = SecurityPolicies.get_defaults()

        logger.info(
            "Security policy validator initialized",
            version=self._policies.version,
            blocked_patterns=len(self._policies.blocked_patterns),
            confirm_patterns=len(self._policies.require_confirmation),
            rules=len(self._policies.rules),
        )

    def validate_command(self, command: str) -> PolicyValidationResult:
        """
        Validate a command against security policies.

        Checks in order:
        1. Allowed commands (explicit allow list)
        2. Blocked patterns (catastrophic - always block)
        3. User blocked commands
        4. Confirmation required patterns (dangerous)
        5. Warning patterns (suspicious)
        6. Custom rules
        """
        # 1. Check allowed commands first (whitelist)
        for pattern in self._policies._allowed_compiled:
            if pattern.search(command):
                return PolicyValidationResult(
                    allowed=True,
                    tier=AttackTier.BENIGN,
                    action="allow",
                    message="Command in allow list",
                    rule_name="allowed_command",
                )

        # 2. Check blocked patterns (catastrophic)
        for i, pattern in enumerate(self._policies._blocked_compiled):
            if pattern.search(command):
                return PolicyValidationResult(
                    allowed=False,
                    tier=AttackTier.CATASTROPHIC,
                    action="block",
                    message=f"Catastrophic pattern matched: {self._policies.blocked_patterns[i]}",
                    rule_name="blocked_pattern",
                    patterns_matched=[self._policies.blocked_patterns[i]],
                )

        # 3. Check user blocked commands
        for i, pattern in enumerate(self._policies._user_blocked_compiled):
            if pattern.search(command):
                return PolicyValidationResult(
                    allowed=False,
                    tier=AttackTier.DANGEROUS,
                    action="block",
                    message=f"User blocked: {self._policies.blocked_commands[i]}",
                    rule_name="user_blocked",
                    patterns_matched=[self._policies.blocked_commands[i]],
                )

        # 4. Check confirmation required patterns
        for i, pattern in enumerate(self._policies._confirm_compiled):
            if pattern.search(command):
                return PolicyValidationResult(
                    allowed=True,  # Allowed but needs confirmation
                    tier=AttackTier.DANGEROUS,
                    action="confirm",
                    message=f"Confirmation required: {self._policies.require_confirmation[i]}",
                    rule_name="require_confirmation",
                    requires_confirmation=True,
                    patterns_matched=[self._policies.require_confirmation[i]],
                )

        # 5. Check warning patterns
        for i, pattern in enumerate(self._policies._warn_compiled):
            if pattern.search(command):
                return PolicyValidationResult(
                    allowed=True,  # Allowed with warning
                    tier=AttackTier.SUSPICIOUS,
                    action="warn",
                    message=f"Suspicious pattern: {self._policies.warn_patterns[i]}",
                    rule_name="warn_pattern",
                    patterns_matched=[self._policies.warn_patterns[i]],
                )

        # 6. Check custom rules
        for rule in self._policies.rules:
            if rule.compiled and rule.compiled.search(command):
                return PolicyValidationResult(
                    allowed=rule.action != "block",
                    tier=rule.tier,
                    action=rule.action,
                    message=rule.message,
                    rule_name=f"custom_rule:{rule.category}",
                    requires_confirmation=rule.action == "confirm",
                    patterns_matched=[rule.pattern],
                )

        # Default: allow
        return PolicyValidationResult(
            allowed=True,
            tier=AttackTier.BENIGN,
            action="allow",
            message="No policy violations",
            rule_name="default_allow",
        )

    def validate_path(self, path: str, operation: str = "access") -> PolicyValidationResult:
        """
        Validate a path against allowed directories.

        Args:
            path: Path to validate
            operation: Type of operation (read, write, delete)
        """
        import os
        try:
            normalized = os.path.normpath(os.path.abspath(path))
        except Exception:
            normalized = path

        # Check if path is in allowed directories
        for allowed in self._policies.allowed_directories:
            if normalized.startswith(allowed):
                return PolicyValidationResult(
                    allowed=True,
                    tier=AttackTier.BENIGN,
                    action="allow",
                    message=f"Path in allowed directory: {allowed}",
                    rule_name="allowed_directory",
                )

        # Path not in allowed list
        if operation in ("write", "delete"):
            return PolicyValidationResult(
                allowed=False,
                tier=AttackTier.DANGEROUS,
                action="block",
                message=f"Path not in allowed directories: {path}",
                rule_name="path_not_allowed",
            )

        # Read operations are generally allowed
        return PolicyValidationResult(
            allowed=True,
            tier=AttackTier.BENIGN,
            action="allow",
            message="Read operation allowed",
            rule_name="read_allowed",
        )

    def reload_policies(self, path: str | Path = "/home/wyld-core/.pai-protected.json") -> None:
        """Reload policies from file."""
        self._policies = SecurityPolicies.from_json(path)
        logger.info("Security policies reloaded", path=str(path))


# Global instance
_policy_validator: SecurityPolicyValidator | None = None


def get_policy_validator() -> SecurityPolicyValidator:
    """Get the global security policy validator."""
    global _policy_validator
    if _policy_validator is None:
        _policy_validator = SecurityPolicyValidator()
    return _policy_validator


def validate_with_policies(
    command: str | None = None,
    path: str | None = None,
    operation: str = "access",
) -> PolicyValidationResult:
    """
    Convenience function to validate against security policies.

    Args:
        command: Command to validate (optional)
        path: Path to validate (optional)
        operation: Operation type for path validation

    Returns:
        PolicyValidationResult with validation outcome
    """
    validator = get_policy_validator()

    if command:
        result = validator.validate_command(command)
        if not result.allowed or result.requires_confirmation:
            return result

    if path:
        result = validator.validate_path(path, operation)
        if not result.allowed:
            return result

    return PolicyValidationResult(
        allowed=True,
        tier=AttackTier.BENIGN,
        action="allow",
        message="Validation passed",
        rule_name="all_passed",
    )
