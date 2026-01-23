"""
Circuit breaker implementation for external service calls.

Prevents cascade failures by temporarily blocking calls to
failing services with exponential backoff recovery.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from .logging import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking calls
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 10
    success_threshold: int = 2
    timeout: float = 60.0
    half_open_max_calls: int = 3
    half_open_failure_threshold: int = 2  # Failures in HALF_OPEN before re-opening
    max_timeout: float = 300.0  # Max backoff timeout (5 minutes)
    backoff_multiplier: float = 2.0  # Timeout multiplier on repeated opens


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for protecting external service calls.

    States:
    - CLOSED: Normal operation, tracking failures
    - OPEN: Blocking all calls, waiting for timeout
    - HALF_OPEN: Allowing limited calls to test recovery
    """

    name: str
    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0
    half_open_calls: int = 0
    half_open_failures: int = 0
    consecutive_opens: int = 0  # Tracks repeated opens for backoff
    _current_timeout: float = field(init=False, default=0)

    def __post_init__(self) -> None:
        self._current_timeout = self.config.timeout

    def _should_allow_request(self) -> bool:
        """Check if request should be allowed based on current state."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self._current_timeout:
                self._transition_to_half_open()
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.config.half_open_max_calls

        return False

    def _transition_to_half_open(self) -> None:
        """Transition to half-open state."""
        logger.info("Circuit breaker transitioning to half-open", name=self.name)
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        self.half_open_failures = 0
        self.success_count = 0

    def _record_success(self) -> None:
        """Record successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                logger.info("Circuit breaker closing", name=self.name)
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.consecutive_opens = 0
                self._current_timeout = self.config.timeout
        elif self.state == CircuitState.CLOSED:
            # Decay failure count on success
            self.failure_count = max(0, self.failure_count - 1)

    def _record_failure(self) -> None:
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.half_open_failures += 1
            if self.half_open_failures >= self.config.half_open_failure_threshold:
                self.consecutive_opens += 1
                self._current_timeout = min(
                    self.config.timeout * (self.config.backoff_multiplier ** self.consecutive_opens),
                    self.config.max_timeout,
                )
                logger.warning(
                    "Circuit breaker re-opening (half-open failures)",
                    name=self.name,
                    half_open_failures=self.half_open_failures,
                    next_timeout=self._current_timeout,
                )
                self.state = CircuitState.OPEN
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.consecutive_opens += 1
                self._current_timeout = min(
                    self.config.timeout * (self.config.backoff_multiplier ** (self.consecutive_opens - 1)),
                    self.config.max_timeout,
                )
                logger.warning(
                    "Circuit breaker opening",
                    name=self.name,
                    failures=self.failure_count,
                    timeout=self._current_timeout,
                )
                self.state = CircuitState.OPEN

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        logger.info("Circuit breaker manually reset", name=self.name)
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        self.half_open_failures = 0
        self.consecutive_opens = 0
        self._current_timeout = self.config.timeout

    async def call(self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        """
        Execute function with circuit breaker protection.

        Raises:
            CircuitOpenError: If circuit is open
        """
        if not self._should_allow_request():
            raise CircuitOpenError(f"Circuit breaker '{self.name}' is open")

        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            raise


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# Registry of circuit breakers
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    config: CircuitBreakerConfig | None = None,
) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            config=config or CircuitBreakerConfig(),
        )
    return _circuit_breakers[name]


def circuit_breaker(
    name: str,
    config: CircuitBreakerConfig | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to wrap function with circuit breaker.

    Usage:
        @circuit_breaker("external-api")
        async def call_external_api():
            ...
    """
    breaker = get_circuit_breaker(name, config)

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator


def reset_circuit_breaker(name: str) -> bool:
    """Reset a circuit breaker by name. Returns True if found and reset."""
    if name in _circuit_breakers:
        _circuit_breakers[name].reset()
        return True
    return False


def get_all_breaker_status() -> list[dict[str, Any]]:
    """Get status of all registered circuit breakers."""
    return [
        {
            "name": b.name,
            "state": b.state.value,
            "failure_count": b.failure_count,
            "consecutive_opens": b.consecutive_opens,
            "current_timeout": b._current_timeout,
            "last_failure_time": b.last_failure_time,
            "seconds_until_half_open": max(
                0, b._current_timeout - (time.time() - b.last_failure_time)
            ) if b.state == CircuitState.OPEN else 0,
        }
        for b in _circuit_breakers.values()
    ]
