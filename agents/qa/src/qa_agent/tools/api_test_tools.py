"""
API testing tools for the QA Agent.

These tools provide API testing capabilities:
- HTTP endpoint testing
- Request/response validation
- Performance testing
- Schema validation
"""

import asyncio
import json
import time
from typing import Any

from ai_core import CapabilityCategory, get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)


@tool(
    name="test_api_endpoint",
    description="""Test an HTTP API endpoint with various methods and parameters.
    Returns response details including status, headers, and timing.""",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Full URL to test",
            },
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                "description": "HTTP method",
                "default": "GET",
            },
            "headers": {
                "type": "object",
                "description": "Request headers",
            },
            "body": {
                "type": "object",
                "description": "Request body (JSON)",
            },
            "timeout": {
                "type": "number",
                "description": "Request timeout in seconds",
                "default": 30,
            },
            "expected_status": {
                "type": "integer",
                "description": "Expected HTTP status code",
            },
        },
        "required": ["url"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def test_api_endpoint(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = 30,
    expected_status: int | None = None,
) -> ToolResult:
    """Test an API endpoint."""
    try:
        import aiohttp

        start_time = time.time()

        request_headers = {
            "User-Agent": "AI-Infrastructure-QA-Agent",
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers=request_headers,
        ) as session:
            request_kwargs = {}
            if body:
                request_kwargs["json"] = body

            async with session.request(method, url, **request_kwargs) as response:
                elapsed = time.time() - start_time

                # Get response body
                try:
                    response_body = await response.json()
                    body_type = "json"
                except (json.JSONDecodeError, aiohttp.ContentTypeError):
                    response_body = await response.text()
                    body_type = "text"
                    if len(response_body) > 1000:
                        response_body = response_body[:1000] + "... (truncated)"

                # Check expected status
                status_match = True
                if expected_status is not None:
                    status_match = response.status == expected_status

                result = {
                    "url": url,
                    "method": method,
                    "status_code": response.status,
                    "response_time_ms": round(elapsed * 1000, 2),
                    "headers": dict(response.headers),
                    "body": response_body,
                    "body_type": body_type,
                    "success": response.ok,
                }

                if expected_status is not None:
                    result["expected_status"] = expected_status
                    result["status_match"] = status_match

                if status_match and response.ok:
                    return ToolResult.ok({
                        "message": f"API test passed: {method} {url} returned {response.status} in {elapsed*1000:.0f}ms",
                        **result,
                    })
                else:
                    return ToolResult.ok({
                        "message": f"API test {'failed status check' if not status_match else 'returned error'}: {method} {url} returned {response.status}",
                        **result,
                    })

    except asyncio.TimeoutError:
        return ToolResult.fail(f"Request timed out after {timeout}s")
    except Exception as e:
        logger.error("API test failed", url=url, error=str(e))
        return ToolResult.fail(f"API test failed: {e}")


@tool(
    name="test_api_batch",
    description="""Run multiple API tests in sequence and report results.
    Useful for testing multiple endpoints at once.""",
    parameters={
        "type": "object",
        "properties": {
            "tests": {
                "type": "array",
                "description": "Array of test cases",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Test name"},
                        "url": {"type": "string", "description": "URL to test"},
                        "method": {"type": "string", "description": "HTTP method"},
                        "headers": {"type": "object", "description": "Request headers"},
                        "body": {"type": "object", "description": "Request body"},
                        "expected_status": {"type": "integer", "description": "Expected status code"},
                    },
                    "required": ["name", "url"],
                },
            },
        },
        "required": ["tests"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def test_api_batch(tests: list[dict[str, Any]]) -> ToolResult:
    """Run multiple API tests."""
    try:
        import aiohttp

        results = []
        passed = 0
        failed = 0
        total_time = 0

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                "User-Agent": "AI-Infrastructure-QA-Agent",
                "Accept": "application/json",
            },
        ) as session:
            for test in tests:
                name = test.get("name", "unnamed")
                url = test.get("url")
                method = test.get("method", "GET")
                headers = test.get("headers", {})
                body = test.get("body")
                expected_status = test.get("expected_status")

                start_time = time.time()
                result = {
                    "name": name,
                    "url": url,
                    "method": method,
                }

                try:
                    request_kwargs = {"headers": headers}
                    if body:
                        request_kwargs["json"] = body

                    async with session.request(method, url, **request_kwargs) as response:
                        elapsed = time.time() - start_time
                        total_time += elapsed

                        result["status_code"] = response.status
                        result["response_time_ms"] = round(elapsed * 1000, 2)

                        # Check expected status
                        if expected_status is not None:
                            result["expected_status"] = expected_status
                            result["passed"] = response.status == expected_status
                        else:
                            result["passed"] = response.ok

                        if result["passed"]:
                            passed += 1
                        else:
                            failed += 1

                except Exception as e:
                    result["error"] = str(e)
                    result["passed"] = False
                    failed += 1

                results.append(result)

        return ToolResult.ok({
            "message": f"Batch test complete: {passed} passed, {failed} failed",
            "summary": {
                "total": len(tests),
                "passed": passed,
                "failed": failed,
                "total_time_ms": round(total_time * 1000, 2),
            },
            "results": results,
        })

    except Exception as e:
        logger.error("Batch API test failed", error=str(e))
        return ToolResult.fail(f"Batch API test failed: {e}")


@tool(
    name="validate_json_schema",
    description="""Validate JSON data against a JSON Schema.""",
    parameters={
        "type": "object",
        "properties": {
            "data": {
                "type": "object",
                "description": "JSON data to validate",
            },
            "schema": {
                "type": "object",
                "description": "JSON Schema to validate against",
            },
        },
        "required": ["data", "schema"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.CODE,
)
async def validate_json_schema(
    data: dict[str, Any],
    schema: dict[str, Any],
) -> ToolResult:
    """Validate JSON against a schema."""
    try:
        import jsonschema
        from jsonschema import Draft7Validator, ValidationError

        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(data))

        if not errors:
            return ToolResult.ok({
                "message": "JSON data is valid against schema",
                "valid": True,
                "errors": [],
            })

        formatted_errors = []
        for error in errors[:20]:  # Limit errors
            formatted_errors.append({
                "path": "/".join(str(p) for p in error.absolute_path) or "/",
                "message": error.message,
                "validator": error.validator,
            })

        return ToolResult.ok({
            "message": f"JSON validation failed with {len(errors)} errors",
            "valid": False,
            "errors": formatted_errors,
            "error_count": len(errors),
        })

    except ImportError:
        return ToolResult.fail("jsonschema is not installed. Install with: pip install jsonschema")
    except Exception as e:
        logger.error("JSON schema validation failed", error=str(e))
        return ToolResult.fail(f"JSON schema validation failed: {e}")


@tool(
    name="measure_api_performance",
    description="""Measure API endpoint performance with multiple requests.
    Returns statistics like min, max, avg response times.""",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to test",
            },
            "method": {
                "type": "string",
                "enum": ["GET", "POST"],
                "description": "HTTP method",
                "default": "GET",
            },
            "requests": {
                "type": "integer",
                "description": "Number of requests to make",
                "default": 10,
            },
            "concurrent": {
                "type": "integer",
                "description": "Number of concurrent requests",
                "default": 1,
            },
            "headers": {
                "type": "object",
                "description": "Request headers",
            },
            "body": {
                "type": "object",
                "description": "Request body (for POST)",
            },
        },
        "required": ["url"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def measure_api_performance(
    url: str,
    method: str = "GET",
    requests: int = 10,
    concurrent: int = 1,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> ToolResult:
    """Measure API performance."""
    try:
        import aiohttp

        # Limit requests
        requests = min(requests, 100)
        concurrent = min(concurrent, 10)

        request_headers = {
            "User-Agent": "AI-Infrastructure-QA-Agent",
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)

        response_times = []
        errors = []
        status_codes = {}

        async def make_request(session: aiohttp.ClientSession) -> None:
            start_time = time.time()
            try:
                request_kwargs = {}
                if body:
                    request_kwargs["json"] = body

                async with session.request(method, url, **request_kwargs) as response:
                    elapsed = (time.time() - start_time) * 1000  # Convert to ms
                    response_times.append(elapsed)

                    status = response.status
                    status_codes[status] = status_codes.get(status, 0) + 1

            except Exception as e:
                errors.append(str(e))

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers=request_headers,
        ) as session:
            # Create request batches
            for i in range(0, requests, concurrent):
                batch_size = min(concurrent, requests - i)
                await asyncio.gather(
                    *[make_request(session) for _ in range(batch_size)]
                )

        # Calculate statistics
        if response_times:
            sorted_times = sorted(response_times)
            stats = {
                "min_ms": round(min(response_times), 2),
                "max_ms": round(max(response_times), 2),
                "avg_ms": round(sum(response_times) / len(response_times), 2),
                "median_ms": round(sorted_times[len(sorted_times) // 2], 2),
                "p95_ms": round(sorted_times[int(len(sorted_times) * 0.95)], 2) if len(sorted_times) >= 20 else None,
                "p99_ms": round(sorted_times[int(len(sorted_times) * 0.99)], 2) if len(sorted_times) >= 100 else None,
            }
        else:
            stats = {}

        return ToolResult.ok({
            "message": f"Performance test complete: {len(response_times)} successful, {len(errors)} failed",
            "url": url,
            "method": method,
            "total_requests": requests,
            "successful_requests": len(response_times),
            "failed_requests": len(errors),
            "concurrent": concurrent,
            "statistics": stats,
            "status_codes": status_codes,
            "errors": errors[:10] if errors else [],
        })

    except Exception as e:
        logger.error("Performance test failed", url=url, error=str(e))
        return ToolResult.fail(f"Performance test failed: {e}")


@tool(
    name="check_api_health",
    description="""Check health of multiple API endpoints at once.
    Returns status of each endpoint.""",
    parameters={
        "type": "object",
        "properties": {
            "endpoints": {
                "type": "array",
                "description": "List of endpoint URLs to check",
                "items": {"type": "string"},
            },
            "timeout": {
                "type": "number",
                "description": "Timeout for each request",
                "default": 10,
            },
        },
        "required": ["endpoints"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def check_api_health(
    endpoints: list[str],
    timeout: float = 10,
) -> ToolResult:
    """Check health of multiple endpoints."""
    try:
        import aiohttp

        results = []
        healthy = 0
        unhealthy = 0

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers={
                "User-Agent": "AI-Infrastructure-QA-Agent",
                "Accept": "application/json",
            },
        ) as session:
            async def check_endpoint(url: str) -> dict:
                start_time = time.time()
                try:
                    async with session.get(url) as response:
                        elapsed = (time.time() - start_time) * 1000
                        return {
                            "url": url,
                            "status": "healthy" if response.ok else "unhealthy",
                            "status_code": response.status,
                            "response_time_ms": round(elapsed, 2),
                        }
                except asyncio.TimeoutError:
                    return {
                        "url": url,
                        "status": "timeout",
                        "error": f"Timeout after {timeout}s",
                    }
                except Exception as e:
                    return {
                        "url": url,
                        "status": "error",
                        "error": str(e),
                    }

            # Check all endpoints concurrently
            results = await asyncio.gather(
                *[check_endpoint(url) for url in endpoints]
            )

        # Count results
        for r in results:
            if r.get("status") == "healthy":
                healthy += 1
            else:
                unhealthy += 1

        overall_status = "healthy" if unhealthy == 0 else "degraded" if healthy > 0 else "down"

        return ToolResult.ok({
            "message": f"Health check: {healthy} healthy, {unhealthy} unhealthy",
            "status": overall_status,
            "summary": {
                "total": len(endpoints),
                "healthy": healthy,
                "unhealthy": unhealthy,
            },
            "endpoints": results,
        })

    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return ToolResult.fail(f"Health check failed: {e}")
