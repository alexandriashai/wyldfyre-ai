"""
Request/response logging middleware.
"""

import time
from typing import Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ai_core import (
    get_correlation_id,
    get_logger,
    http_request_duration_seconds,
    http_requests_in_progress,
    http_requests_total,
    set_correlation_id,
)

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for request/response logging and metrics.

    Features:
    - Correlation ID injection
    - Request/response logging
    - Request duration tracking
    - Prometheus metrics
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # Generate or extract correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
        set_correlation_id(correlation_id)

        # Extract request info
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"

        # Skip logging for health checks
        skip_logging = path in ("/health/live", "/health/ready", "/metrics")

        # Track in-progress requests
        http_requests_in_progress.labels(
            method=method,
            endpoint=path,
        ).inc()

        start_time = time.perf_counter()

        if not skip_logging:
            logger.info(
                "Request started",
                method=method,
                path=path,
                client_ip=client_ip,
                correlation_id=correlation_id,
            )

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration = time.perf_counter() - start_time

            # Add correlation ID to response
            response.headers["X-Correlation-ID"] = correlation_id

            # Record metrics
            http_requests_total.labels(
                method=method,
                endpoint=path,
                status_code=response.status_code,
            ).inc()

            http_request_duration_seconds.labels(
                method=method,
                endpoint=path,
            ).observe(duration)

            if not skip_logging:
                logger.info(
                    "Request completed",
                    method=method,
                    path=path,
                    status=response.status_code,
                    duration_ms=round(duration * 1000, 2),
                    correlation_id=correlation_id,
                )

            return response

        except Exception as e:
            duration = time.perf_counter() - start_time

            # Record error metrics
            http_requests_total.labels(
                method=method,
                endpoint=path,
                status_code=500,
            ).inc()

            http_request_duration_seconds.labels(
                method=method,
                endpoint=path,
            ).observe(duration)

            logger.error(
                "Request failed",
                method=method,
                path=path,
                error=str(e),
                duration_ms=round(duration * 1000, 2),
                correlation_id=correlation_id,
            )

            raise

        finally:
            # Decrement in-progress counter
            http_requests_in_progress.labels(
                method=method,
                endpoint=path,
            ).dec()
