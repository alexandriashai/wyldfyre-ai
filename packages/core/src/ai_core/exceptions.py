"""
Custom exceptions for AI Infrastructure.

Provides a hierarchy of exceptions for different error categories
with support for error codes, context, and user-friendly messages.
"""

from typing import Any


class AIInfraError(Exception):
    """Base exception for all AI Infrastructure errors."""

    error_code: str = "AI_INFRA_ERROR"
    status_code: int = 500

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        status_code: int | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message)
        self.message = message
        if error_code:
            self.error_code = error_code
        if status_code:
            self.status_code = status_code
        self.context = context or {}
        self.__cause__ = cause

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.error_code,
            "message": self.message,
            "context": self.context,
        }


# Configuration Errors
class ConfigurationError(AIInfraError):
    """Configuration-related errors."""
    error_code = "CONFIGURATION_ERROR"
    status_code = 500


class MissingConfigError(ConfigurationError):
    """Required configuration is missing."""
    error_code = "MISSING_CONFIG"


class InvalidConfigError(ConfigurationError):
    """Configuration value is invalid."""
    error_code = "INVALID_CONFIG"


# Database Errors
class DatabaseError(AIInfraError):
    """Database-related errors."""
    error_code = "DATABASE_ERROR"
    status_code = 500


class ConnectionError(DatabaseError):
    """Failed to connect to database."""
    error_code = "CONNECTION_ERROR"


class QueryError(DatabaseError):
    """Database query failed."""
    error_code = "QUERY_ERROR"


class NotFoundError(DatabaseError):
    """Requested resource not found."""
    error_code = "NOT_FOUND"
    status_code = 404


class DuplicateError(DatabaseError):
    """Resource already exists."""
    error_code = "DUPLICATE_ERROR"
    status_code = 409


# Agent Errors
class AgentError(AIInfraError):
    """Agent-related errors."""
    error_code = "AGENT_ERROR"
    status_code = 500


class AgentNotFoundError(AgentError):
    """Specified agent not found."""
    error_code = "AGENT_NOT_FOUND"
    status_code = 404


class AgentBusyError(AgentError):
    """Agent is busy with another task."""
    error_code = "AGENT_BUSY"
    status_code = 429


class AgentTimeoutError(AgentError):
    """Agent task timed out."""
    error_code = "AGENT_TIMEOUT"
    status_code = 504


class PermissionDeniedError(AgentError):
    """Agent lacks permission for this operation."""
    error_code = "PERMISSION_DENIED"
    status_code = 403


# External Service Errors
class ExternalServiceError(AIInfraError):
    """External service errors."""
    error_code = "EXTERNAL_SERVICE_ERROR"
    status_code = 502


class APIError(ExternalServiceError):
    """External API error."""
    error_code = "API_ERROR"


class RateLimitError(ExternalServiceError):
    """Rate limit exceeded."""
    error_code = "RATE_LIMIT"
    status_code = 429


class ServiceUnavailableError(ExternalServiceError):
    """External service unavailable."""
    error_code = "SERVICE_UNAVAILABLE"
    status_code = 503


# Authentication/Authorization Errors
class AuthError(AIInfraError):
    """Authentication/authorization errors."""
    error_code = "AUTH_ERROR"
    status_code = 401


class InvalidTokenError(AuthError):
    """Invalid or expired token."""
    error_code = "INVALID_TOKEN"


class UnauthorizedError(AuthError):
    """User not authorized for this action."""
    error_code = "UNAUTHORIZED"
    status_code = 403


# Validation Errors
class ValidationError(AIInfraError):
    """Input validation errors."""
    error_code = "VALIDATION_ERROR"
    status_code = 400


class InvalidInputError(ValidationError):
    """Invalid input provided."""
    error_code = "INVALID_INPUT"


# Task/Workflow Errors
class TaskError(AIInfraError):
    """Task execution errors."""
    error_code = "TASK_ERROR"
    status_code = 500


class TaskCancelledError(TaskError):
    """Task was cancelled."""
    error_code = "TASK_CANCELLED"


class TaskFailedError(TaskError):
    """Task execution failed."""
    error_code = "TASK_FAILED"


# Memory/Storage Errors
class MemoryError(AIInfraError):
    """Memory system errors."""
    error_code = "MEMORY_ERROR"
    status_code = 500


class EmbeddingError(MemoryError):
    """Failed to generate embeddings."""
    error_code = "EMBEDDING_ERROR"


class StorageError(MemoryError):
    """Storage operation failed."""
    error_code = "STORAGE_ERROR"
