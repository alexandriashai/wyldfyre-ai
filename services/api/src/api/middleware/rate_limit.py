"""
Rate limiting middleware.
"""

import time
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ai_core import get_logger
from ai_messaging import RedisClient, get_redis_client

from ..config import get_api_config

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Token bucket rate limiting middleware.

    Uses Redis for distributed rate limiting across multiple API instances.

    Features:
    - Per-user rate limiting (by JWT user ID or IP)
    - Configurable requests per minute
    - Burst allowance
    - Redis-backed for distributed systems
    """

    def __init__(self, app, redis: RedisClient | None = None):
        super().__init__(app)
        self._redis = redis

    async def get_redis(self) -> RedisClient:
        """Get Redis client lazily."""
        if self._redis is None:
            self._redis = await get_redis_client()
        return self._redis

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        config = get_api_config()

        # Skip if rate limiting disabled
        if not config.rate_limit_enabled:
            return await call_next(request)

        # Skip rate limiting for health checks
        if request.url.path in ("/health/live", "/health/ready", "/metrics"):
            return await call_next(request)

        # Get identifier (user ID from auth or IP address)
        identifier = self._get_identifier(request)

        # Check rate limit
        is_allowed, remaining, reset_at = await self._check_rate_limit(
            identifier=identifier,
            limit=config.rate_limit_requests_per_minute,
            window=60,  # 1 minute window
            burst=config.rate_limit_burst,
        )

        if not is_allowed:
            logger.warning(
                "Rate limit exceeded",
                identifier=identifier,
                path=request.url.path,
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "detail": "Too many requests. Please try again later.",
                    "retry_after": reset_at,
                },
                headers={
                    "Retry-After": str(reset_at),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(
            config.rate_limit_requests_per_minute
        )
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_at)

        return response

    def _get_identifier(self, request: Request) -> str:
        """
        Get rate limit identifier from request.

        Priority:
        1. User ID from JWT (via request state)
        2. Client IP address
        """
        # Check for user ID in request state (set by auth middleware)
        if hasattr(request.state, "user_id"):
            return f"user:{request.state.user_id}"

        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

    async def _check_rate_limit(
        self,
        identifier: str,
        limit: int,
        window: int,
        burst: int,
    ) -> tuple[bool, int, int]:
        """
        Check and update rate limit using sliding window.

        Args:
            identifier: Unique identifier (user or IP)
            limit: Max requests per window
            window: Window size in seconds
            burst: Additional burst allowance

        Returns:
            Tuple of (is_allowed, remaining_requests, reset_timestamp)
        """
        redis = await self.get_redis()
        key = f"ratelimit:{identifier}"
        now = int(time.time())
        window_start = now - window

        try:
            # Use Redis pipeline for atomic operations
            async with redis.pipeline() as pipe:
                # Remove old entries
                await pipe.zremrangebyscore(key, 0, window_start)
                # Count current requests
                await pipe.zcard(key)
                # Add current request
                await pipe.zadd(key, {str(now): now})
                # Set expiry
                await pipe.expire(key, window * 2)
                # Execute
                results = await pipe.execute()

            current_count = results[1]
            effective_limit = limit + burst
            remaining = max(0, effective_limit - current_count - 1)
            reset_at = now + window

            is_allowed = current_count < effective_limit

            return is_allowed, remaining, reset_at

        except Exception as e:
            logger.error("Rate limit check failed", error=str(e))
            # Allow request on Redis failure (fail open)
            return True, limit, now + window
