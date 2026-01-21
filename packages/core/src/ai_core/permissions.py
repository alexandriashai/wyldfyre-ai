"""
Permission management for AI Infrastructure agents.

Provides:
- PermissionContext: Tracks an agent's current permission state
- ElevationRequest: Represents a request for elevated permissions
- ElevationGrant: Represents an approved elevation
- ElevationManager: Manages the elevation workflow and tracking
"""

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .enums import AgentType, CapabilityCategory, ElevationReason, PermissionLevel
from .logging import get_logger

logger = get_logger(__name__)

# Configuration
MAX_AUTO_ELEVATION = 1  # Maximum levels an agent can auto-elevate
MAX_ELEVATIONS_PER_HOUR = 10  # Rate limit for auto-elevations
ELEVATION_TIMEOUT_SECONDS = 300  # How long an elevation grant is valid


@dataclass
class PermissionContext:
    """
    Tracks an agent's permission state.

    Attributes:
        agent_type: The type of agent
        base_level: The agent's configured base permission level
        current_level: The current effective permission level (may be elevated)
        allowed_capabilities: Set of capability categories the agent can access
        allowed_elevation_to: Maximum level the agent can be elevated to
        active_elevation: Currently active elevation grant, if any
    """

    agent_type: AgentType
    base_level: PermissionLevel
    allowed_capabilities: set[CapabilityCategory] = field(default_factory=set)
    allowed_elevation_to: PermissionLevel | None = None
    active_elevation: "ElevationGrant | None" = None

    @property
    def current_level(self) -> PermissionLevel:
        """Get the current effective permission level."""
        if self.active_elevation and self.active_elevation.is_valid():
            return self.active_elevation.granted_level
        return self.base_level

    def can_access_tool(
        self,
        required_level: PermissionLevel,
        capability: CapabilityCategory | None = None,
    ) -> bool:
        """
        Check if the agent can access a tool.

        Args:
            required_level: The permission level required by the tool
            capability: The capability category of the tool (optional)

        Returns:
            True if access is allowed
        """
        # Check permission level
        if self.current_level < required_level:
            return False

        # Check capability if specified
        if capability and self.allowed_capabilities:
            if capability not in self.allowed_capabilities:
                return False

        return True

    def can_auto_elevate_to(self, target_level: PermissionLevel) -> bool:
        """
        Check if the agent can auto-elevate to a target level.

        Args:
            target_level: The desired permission level

        Returns:
            True if auto-elevation is possible
        """
        elevation_needed = target_level.value - self.base_level.value

        # Check if within auto-elevation limit
        if elevation_needed > MAX_AUTO_ELEVATION:
            return False

        # Check if within allowed elevation ceiling
        if self.allowed_elevation_to is not None:
            if target_level > self.allowed_elevation_to:
                return False

        return True


@dataclass
class ElevationRequest:
    """
    Represents a request for elevated permissions.

    Created when an agent needs to perform an action above its base level.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    agent_type: AgentType = AgentType.CODE
    requesting_task_id: str = ""
    tool_name: str = ""
    current_level: PermissionLevel = PermissionLevel.READ_ONLY
    requested_level: PermissionLevel = PermissionLevel.READ_WRITE
    reason: ElevationReason = ElevationReason.TOOL_REQUIREMENT
    justification: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def elevation_delta(self) -> int:
        """How many levels of elevation are being requested."""
        return self.requested_level.value - self.current_level.value


@dataclass
class ElevationGrant:
    """
    Represents an approved elevation.

    Grants temporary elevated permissions to an agent.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    request_id: str = ""
    agent_type: AgentType = AgentType.CODE
    granted_level: PermissionLevel = PermissionLevel.READ_WRITE
    granted_by: str = ""  # "auto" or supervisor agent name
    granted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    reason: str = ""
    scope: str | None = None  # Optional scope limitation (e.g., specific tool)

    def __post_init__(self) -> None:
        """Set default expiration if not provided."""
        # If expires_at is the same as granted_at (default), set proper expiration
        if self.expires_at == self.granted_at:
            self.expires_at = datetime.fromtimestamp(
                self.granted_at.timestamp() + ELEVATION_TIMEOUT_SECONDS,
                tz=timezone.utc,
            )

    def is_valid(self) -> bool:
        """Check if the grant is still valid."""
        return datetime.now(timezone.utc) < self.expires_at


@dataclass
class ElevationRecord:
    """Record of an elevation event for audit logging."""

    timestamp: datetime
    agent_type: AgentType
    action: str  # "requested", "auto_approved", "supervisor_approved", "denied"
    from_level: PermissionLevel
    to_level: PermissionLevel
    tool_name: str | None
    reason: ElevationReason
    justification: str
    result: str  # "approved", "denied", "timeout"
    granted_by: str | None = None


class ElevationManager:
    """
    Manages permission elevations for agents.

    Responsibilities:
    - Process elevation requests
    - Auto-approve single-level elevations within rate limits
    - Forward multi-level elevations to supervisor
    - Track and audit all elevation events
    - Enforce rate limiting
    """

    def __init__(self) -> None:
        self._pending_requests: dict[str, ElevationRequest] = {}
        self._active_grants: dict[str, ElevationGrant] = {}
        self._elevation_history: list[ElevationRecord] = []
        self._rate_limiter: dict[AgentType, list[float]] = {}

    def request_elevation(
        self,
        context: PermissionContext,
        target_level: PermissionLevel,
        tool_name: str,
        task_id: str,
        reason: ElevationReason = ElevationReason.TOOL_REQUIREMENT,
        justification: str = "",
    ) -> tuple[bool, ElevationGrant | ElevationRequest | None]:
        """
        Request an elevation of permissions.

        Args:
            context: The agent's current permission context
            target_level: The desired permission level
            tool_name: The tool requiring elevation
            task_id: The current task ID
            reason: Why elevation is needed
            justification: Human-readable justification

        Returns:
            Tuple of (auto_approved, grant_or_request)
            - If auto-approved: (True, ElevationGrant)
            - If needs supervisor: (False, ElevationRequest)
            - If denied: (False, None)
        """
        elevation_delta = target_level.value - context.base_level.value

        logger.info(
            "Elevation requested",
            agent=context.agent_type.value,
            current_level=context.base_level.value,
            target_level=target_level.value,
            delta=elevation_delta,
            tool=tool_name,
        )

        # Check if within auto-elevation limit
        if elevation_delta <= MAX_AUTO_ELEVATION:
            # Check rate limit
            if not self._check_rate_limit(context.agent_type):
                logger.warning(
                    "Elevation rate limit exceeded",
                    agent=context.agent_type.value,
                )
                self._record_elevation(
                    context.agent_type,
                    "denied",
                    context.base_level,
                    target_level,
                    tool_name,
                    reason,
                    justification,
                    "rate_limited",
                )
                return False, None

            # Check if elevation is allowed
            if not context.can_auto_elevate_to(target_level):
                logger.warning(
                    "Elevation not allowed",
                    agent=context.agent_type.value,
                    target=target_level.value,
                    ceiling=context.allowed_elevation_to,
                )
                self._record_elevation(
                    context.agent_type,
                    "denied",
                    context.base_level,
                    target_level,
                    tool_name,
                    reason,
                    justification,
                    "ceiling_exceeded",
                )
                return False, None

            # Auto-approve
            grant = self._create_grant(
                context,
                target_level,
                tool_name,
                reason,
                "auto",
            )

            self._record_elevation(
                context.agent_type,
                "auto_approved",
                context.base_level,
                target_level,
                tool_name,
                reason,
                justification,
                "approved",
                "auto",
            )

            logger.info(
                "Elevation auto-approved",
                agent=context.agent_type.value,
                grant_id=grant.id,
                level=target_level.value,
            )

            return True, grant

        # Requires supervisor approval
        request = ElevationRequest(
            agent_type=context.agent_type,
            requesting_task_id=task_id,
            tool_name=tool_name,
            current_level=context.base_level,
            requested_level=target_level,
            reason=reason,
            justification=justification,
        )

        self._pending_requests[request.id] = request

        self._record_elevation(
            context.agent_type,
            "requested",
            context.base_level,
            target_level,
            tool_name,
            reason,
            justification,
            "pending",
        )

        logger.info(
            "Elevation requires supervisor approval",
            agent=context.agent_type.value,
            request_id=request.id,
            delta=elevation_delta,
        )

        return False, request

    def approve_elevation(
        self,
        request_id: str,
        approved_by: str,
        scope: str | None = None,
    ) -> ElevationGrant | None:
        """
        Approve a pending elevation request (called by supervisor).

        Args:
            request_id: The elevation request ID
            approved_by: Who approved (supervisor name)
            scope: Optional scope limitation

        Returns:
            ElevationGrant if approved, None if request not found
        """
        request = self._pending_requests.pop(request_id, None)
        if not request:
            logger.warning("Elevation request not found", request_id=request_id)
            return None

        grant = ElevationGrant(
            request_id=request_id,
            agent_type=request.agent_type,
            granted_level=request.requested_level,
            granted_by=approved_by,
            reason=request.justification,
            scope=scope,
        )

        self._active_grants[grant.id] = grant

        self._record_elevation(
            request.agent_type,
            "supervisor_approved",
            request.current_level,
            request.requested_level,
            request.tool_name,
            request.reason,
            request.justification,
            "approved",
            approved_by,
        )

        logger.info(
            "Elevation approved by supervisor",
            request_id=request_id,
            grant_id=grant.id,
            approved_by=approved_by,
        )

        return grant

    def deny_elevation(
        self,
        request_id: str,
        denied_by: str,
        reason: str = "",
    ) -> bool:
        """
        Deny a pending elevation request.

        Args:
            request_id: The elevation request ID
            denied_by: Who denied
            reason: Why it was denied

        Returns:
            True if request was found and denied
        """
        request = self._pending_requests.pop(request_id, None)
        if not request:
            logger.warning("Elevation request not found", request_id=request_id)
            return False

        self._record_elevation(
            request.agent_type,
            "denied",
            request.current_level,
            request.requested_level,
            request.tool_name,
            request.reason,
            reason or request.justification,
            "denied",
            denied_by,
        )

        logger.info(
            "Elevation denied",
            request_id=request_id,
            denied_by=denied_by,
            reason=reason,
        )

        return True

    def revoke_elevation(self, grant_id: str) -> bool:
        """
        Revoke an active elevation grant.

        Args:
            grant_id: The grant ID to revoke

        Returns:
            True if grant was found and revoked
        """
        grant = self._active_grants.pop(grant_id, None)
        if not grant:
            return False

        logger.info("Elevation revoked", grant_id=grant_id)
        return True

    def get_grant(self, grant_id: str) -> ElevationGrant | None:
        """Get an active grant by ID."""
        grant = self._active_grants.get(grant_id)
        if grant and grant.is_valid():
            return grant
        return None

    def get_pending_requests(
        self,
        agent_type: AgentType | None = None,
    ) -> list[ElevationRequest]:
        """Get all pending elevation requests, optionally filtered by agent."""
        requests = list(self._pending_requests.values())
        if agent_type:
            requests = [r for r in requests if r.agent_type == agent_type]
        return requests

    def get_elevation_history(
        self,
        agent_type: AgentType | None = None,
        limit: int = 100,
    ) -> list[ElevationRecord]:
        """Get elevation history, optionally filtered by agent."""
        history = self._elevation_history
        if agent_type:
            history = [r for r in history if r.agent_type == agent_type]
        return history[-limit:]

    def cleanup_expired(self) -> int:
        """Remove expired grants. Returns count of removed grants."""
        expired = [
            gid for gid, grant in self._active_grants.items() if not grant.is_valid()
        ]
        for gid in expired:
            del self._active_grants[gid]
        return len(expired)

    def _create_grant(
        self,
        context: PermissionContext,
        level: PermissionLevel,
        tool_name: str,
        reason: ElevationReason,
        granted_by: str,
    ) -> ElevationGrant:
        """Create and register an elevation grant."""
        grant = ElevationGrant(
            agent_type=context.agent_type,
            granted_level=level,
            granted_by=granted_by,
            reason=f"{reason.value}: {tool_name}",
            scope=tool_name,
        )
        self._active_grants[grant.id] = grant
        self._record_rate_limit(context.agent_type)
        return grant

    def _check_rate_limit(self, agent_type: AgentType) -> bool:
        """Check if agent is within rate limit for auto-elevations."""
        now = time.time()
        hour_ago = now - 3600

        # Get timestamps of elevations in the last hour
        timestamps = self._rate_limiter.get(agent_type, [])
        recent = [t for t in timestamps if t > hour_ago]
        self._rate_limiter[agent_type] = recent

        return len(recent) < MAX_ELEVATIONS_PER_HOUR

    def _record_rate_limit(self, agent_type: AgentType) -> None:
        """Record an elevation for rate limiting."""
        if agent_type not in self._rate_limiter:
            self._rate_limiter[agent_type] = []
        self._rate_limiter[agent_type].append(time.time())

    def _record_elevation(
        self,
        agent_type: AgentType,
        action: str,
        from_level: PermissionLevel,
        to_level: PermissionLevel,
        tool_name: str | None,
        reason: ElevationReason,
        justification: str,
        result: str,
        granted_by: str | None = None,
    ) -> None:
        """Record an elevation event for audit."""
        record = ElevationRecord(
            timestamp=datetime.now(timezone.utc),
            agent_type=agent_type,
            action=action,
            from_level=from_level,
            to_level=to_level,
            tool_name=tool_name,
            reason=reason,
            justification=justification,
            result=result,
            granted_by=granted_by,
        )
        self._elevation_history.append(record)

        # Trim history if too long
        if len(self._elevation_history) > 1000:
            self._elevation_history = self._elevation_history[-500:]


# Global elevation manager instance
_elevation_manager: ElevationManager | None = None
_elevation_lock = threading.Lock()


def get_elevation_manager() -> ElevationManager:
    """Get or create the global elevation manager (thread-safe)."""
    global _elevation_manager
    if _elevation_manager is None:
        with _elevation_lock:
            # Double-check locking pattern for thread safety
            if _elevation_manager is None:
                _elevation_manager = ElevationManager()
    return _elevation_manager
