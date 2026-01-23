"""
Security validation for Wyld Fyre AI agents.

Protects the AI infrastructure from self-modification while allowing
agents to work freely in approved directories.
"""

import os
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import yaml

from .logging import get_logger

logger = get_logger(__name__)


class SecurityAction(Enum):
    """Actions the security validator can take."""
    ALLOW = "allow"
    BLOCK = "block"
    WARN = "warn"


class ThreatLevel(Enum):
    """Severity levels for security threats."""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class SecurityViolation:
    """Records a security violation or check result."""
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    action: SecurityAction = SecurityAction.ALLOW
    threat_level: ThreatLevel = ThreatLevel.NONE
    rule_name: str = ""
    tool_name: str = ""
    input_summary: str = ""
    message: str = ""
    agent_name: str | None = None
    blocked: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "threat_level": self.threat_level.value,
            "rule_name": self.rule_name,
            "tool_name": self.tool_name,
            "input_summary": self.input_summary[:200],
            "message": self.message,
            "agent_name": self.agent_name,
            "blocked": self.blocked,
        }


@dataclass
class SecurityConfig:
    """Security configuration loaded from YAML."""
    
    protected_paths: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)
    dangerous_patterns: list[dict[str, Any]] = field(default_factory=list)
    protected_containers: list[str] = field(default_factory=list)
    protected_files: list[str] = field(default_factory=list)
    bypass_tools: list[str] = field(default_factory=list)
    agent_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    
    @classmethod
    def from_yaml(cls, path: str) -> "SecurityConfig":
        """Load configuration from YAML file."""
        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            
            return cls(
                protected_paths=data.get("protected_paths", []),
                allowed_paths=data.get("allowed_paths", []),
                dangerous_patterns=data.get("dangerous_patterns", []),
                protected_containers=data.get("protected_containers", []),
                protected_files=data.get("protected_files", []),
                bypass_tools=data.get("bypass_tools", []),
                agent_overrides=data.get("agent_overrides", {}),
            )
        except FileNotFoundError:
            logger.warning("Security config not found, using defaults", path=path)
            return cls.get_defaults()
        except Exception as e:
            logger.error("Failed to load security config", error=str(e), path=path)
            return cls.get_defaults()
    
    @classmethod
    def get_defaults(cls) -> "SecurityConfig":
        """Get default security configuration."""
        return cls(
            protected_paths=[
                "/home/wyld-core",
                "/home/wyld-web", 
                "/home/wyld-data",
                "/etc",
                "/var/lib",
                "/root",
            ],
            allowed_paths=[
                "/tmp",
                "/home/wyld-data/workspaces",
                "/home/wyld-data/uploads",
            ],
            dangerous_patterns=[
                {"pattern": r"rm\s+(-[rf]+\s+)*(/|/home|/etc|/var|/root)", "level": "critical", "message": "Catastrophic recursive deletion"},
                {"pattern": r">\s*/dev/sd[a-z]", "level": "critical", "message": "Direct disk write"},
                {"pattern": r"mkfs\.", "level": "critical", "message": "Filesystem format command"},
                {"pattern": r"dd\s+.*of=/dev/", "level": "critical", "message": "Direct disk overwrite"},
                {"pattern": r"chmod\s+777", "level": "high", "message": "Dangerous permission change"},
            ],
            protected_containers=[
                "ai-api", "ai-web", "ai-postgres", "ai-redis",
                "ai-qdrant", "ai-grafana", "ai-prometheus", "ai-loki", "ai-voice",
            ],
            protected_files=[
                ".env", "docker-compose.yml", "docker-compose.override.yml",
                "agents.yaml", "security.yaml",
            ],
            bypass_tools=[],
            agent_overrides={},
        )


class SecurityValidator:
    """Validates tool inputs against security rules."""
    
    def __init__(self, config: SecurityConfig | None = None, config_path: str | None = None):
        if config:
            self._config = config
        elif config_path:
            self._config = SecurityConfig.from_yaml(config_path)
        else:
            default_path = "/home/wyld-core/config/security.yaml"
            if os.path.exists(default_path):
                self._config = SecurityConfig.from_yaml(default_path)
            else:
                self._config = SecurityConfig.get_defaults()
        
        self._violations: list[SecurityViolation] = []
        self._compiled_patterns: list[tuple[re.Pattern[str], str, ThreatLevel]] = []
        self._compile_patterns()
        
        logger.info("Security validator initialized",
            protected_paths=len(self._config.protected_paths),
            allowed_paths=len(self._config.allowed_paths),
            patterns=len(self._config.dangerous_patterns))
    
    def _compile_patterns(self) -> None:
        level_map = {"low": ThreatLevel.LOW, "medium": ThreatLevel.MEDIUM,
                     "high": ThreatLevel.HIGH, "critical": ThreatLevel.CRITICAL}
        
        for pc in self._config.dangerous_patterns:
            try:
                compiled = re.compile(pc["pattern"], re.IGNORECASE)
                level = level_map.get(pc.get("level", "high"), ThreatLevel.HIGH)
                self._compiled_patterns.append((compiled, pc.get("message", "Dangerous pattern"), level))
            except re.error as e:
                logger.warning("Invalid regex", pattern=pc["pattern"], error=str(e))
    
    def _path_matches(self, path: str, prefix: str) -> bool:
        """Check if path is within prefix directory (proper boundary matching)."""
        # Ensure prefix ends with separator for proper matching
        # This prevents /home/wyld-core from matching /home/wyld-corefoo
        if not prefix.endswith(os.sep):
            prefix_with_sep = prefix + os.sep
        else:
            prefix_with_sep = prefix

        return path == prefix.rstrip(os.sep) or path.startswith(prefix_with_sep)

    def validate_path(self, path: str, operation: str = "access", agent_name: str | None = None) -> SecurityViolation:
        try:
            normalized = os.path.normpath(os.path.abspath(path))
        except Exception:
            normalized = path

        for allowed in self._config.allowed_paths:
            if self._path_matches(normalized, allowed):
                return SecurityViolation(action=SecurityAction.ALLOW, rule_name="allowed_path",
                    input_summary=f"{operation}: {path}", message=f"Path allowed: {allowed}",
                    agent_name=agent_name, blocked=False)

        for protected in self._config.protected_paths:
            if self._path_matches(normalized, protected):
                if operation == "read":
                    return SecurityViolation(action=SecurityAction.WARN, threat_level=ThreatLevel.LOW,
                        rule_name="protected_path_read", input_summary=f"{operation}: {path}",
                        message=f"Read on protected path: {protected}", agent_name=agent_name, blocked=False)
                
                violation = SecurityViolation(action=SecurityAction.BLOCK, threat_level=ThreatLevel.HIGH,
                    rule_name="protected_path", input_summary=f"{operation}: {path}",
                    message=f"Modification blocked on: {protected}", agent_name=agent_name, blocked=True)
                self._record_violation(violation)
                return violation
        
        filename = os.path.basename(normalized)
        if filename in self._config.protected_files and operation != "read":
            violation = SecurityViolation(action=SecurityAction.BLOCK, threat_level=ThreatLevel.HIGH,
                rule_name="protected_file", input_summary=f"{operation}: {path}",
                message=f"Protected file: {filename}", agent_name=agent_name, blocked=True)
            self._record_violation(violation)
            return violation
        
        return SecurityViolation(action=SecurityAction.ALLOW, rule_name="default_allow",
            input_summary=f"{operation}: {path}", message="Path not protected", agent_name=agent_name, blocked=False)
    
    def validate_command(self, command: str, agent_name: str | None = None) -> SecurityViolation:
        for pattern, message, level in self._compiled_patterns:
            if pattern.search(command):
                violation = SecurityViolation(action=SecurityAction.BLOCK, threat_level=level,
                    rule_name="dangerous_command", input_summary=command[:200],
                    message=message, agent_name=agent_name, blocked=True)
                self._record_violation(violation)
                return violation
        
        return SecurityViolation(action=SecurityAction.ALLOW, rule_name="command_safe",
            input_summary=command[:200], message="Command safe", agent_name=agent_name, blocked=False)
    
    def validate_docker_operation(self, operation: str, container: str | None = None, agent_name: str | None = None) -> SecurityViolation:
        dangerous_ops = {"rm", "stop", "kill", "down", "prune"}
        
        if operation in dangerous_ops and container:
            for protected in self._config.protected_containers:
                if protected in container:
                    violation = SecurityViolation(action=SecurityAction.BLOCK, threat_level=ThreatLevel.CRITICAL,
                        rule_name="protected_container", input_summary=f"docker {operation} {container}",
                        message=f"Protected container: {protected}", agent_name=agent_name, blocked=True)
                    self._record_violation(violation)
                    return violation
        
        if operation == "prune" and container is None:
            violation = SecurityViolation(action=SecurityAction.BLOCK, threat_level=ThreatLevel.HIGH,
                rule_name="docker_prune", input_summary=f"docker {operation}",
                message="System prune not allowed", agent_name=agent_name, blocked=True)
            self._record_violation(violation)
            return violation
        
        return SecurityViolation(action=SecurityAction.ALLOW, rule_name="docker_safe",
            input_summary=f"docker {operation} {container or ''}".strip(),
            message="Docker operation allowed", agent_name=agent_name, blocked=False)
    
    def validate_tool_input(self, tool_name: str, tool_input: dict[str, Any], agent_name: str | None = None) -> SecurityViolation:
        if tool_name in self._config.bypass_tools:
            return SecurityViolation(action=SecurityAction.ALLOW, rule_name="bypass_tool",
                tool_name=tool_name, input_summary=str(tool_input)[:200],
                message="Tool bypassed", agent_name=agent_name, blocked=False)
        
        file_tools = {"read_file", "file_read", "write_file", "file_write",
                      "delete_file", "file_delete", "directory_delete",
                      "file_move", "file_copy", "file_chown", "file_chmod"}
        
        if tool_name in file_tools:
            path = tool_input.get("path") or tool_input.get("file_path") or tool_input.get("source")
            if path:
                operation = "read" if "read" in tool_name else "write"
                if "delete" in tool_name:
                    operation = "delete"
                return self.validate_path(path, operation, agent_name)
        
        command_tools = {"bash", "shell", "execute", "run_command", "subprocess"}
        if tool_name in command_tools:
            command = tool_input.get("command") or tool_input.get("cmd") or tool_input.get("script")
            if command:
                return self.validate_command(command, agent_name)
        
        docker_tools = {"docker_stop", "docker_rm", "docker_kill", "docker_compose_down", "docker_system_prune"}
        if tool_name in docker_tools:
            container = tool_input.get("container") or tool_input.get("name")
            operation = tool_name.replace("docker_", "").replace("container_", "")
            return self.validate_docker_operation(operation, container, agent_name)
        
        return SecurityViolation(action=SecurityAction.ALLOW, rule_name="default_allow",
            tool_name=tool_name, input_summary=str(tool_input)[:200],
            message="Tool not in rules", agent_name=agent_name, blocked=False)
    
    def _record_violation(self, violation: SecurityViolation) -> None:
        self._violations.append(violation)
        if len(self._violations) > 1000:
            self._violations = self._violations[-500:]
        
        log_data = violation.to_dict()
        if violation.threat_level.value >= ThreatLevel.HIGH.value:
            logger.warning("Security violation", **log_data)
        else:
            logger.info("Security check", **log_data)
    
    def get_violations(self, limit: int = 100, blocked_only: bool = False) -> list[SecurityViolation]:
        violations = self._violations
        if blocked_only:
            violations = [v for v in violations if v.blocked]
        return violations[-limit:]
    
    def reload_config(self, config_path: str | None = None) -> None:
        path = config_path or "/home/wyld-core/config/security.yaml"
        self._config = SecurityConfig.from_yaml(path)
        self._compiled_patterns = []
        self._compile_patterns()
        logger.info("Security config reloaded", path=path)


_security_validator: SecurityValidator | None = None
_security_lock = threading.Lock()


def get_security_validator() -> SecurityValidator:
    """Get or create the global security validator (thread-safe)."""
    global _security_validator
    if _security_validator is None:
        with _security_lock:
            # Double-check locking pattern for thread safety
            if _security_validator is None:
                _security_validator = SecurityValidator()
    return _security_validator


def validate_tool(tool_name: str, tool_input: dict[str, Any], agent_name: str | None = None) -> tuple[bool, str]:
    """Convenience function to validate a tool call."""
    validator = get_security_validator()
    result = validator.validate_tool_input(tool_name, tool_input, agent_name)
    return not result.blocked, result.message
