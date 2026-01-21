"""
Browser network tools for the QA Agent.

Provides tools for network interception and mocking:
- Request interception
- Response mocking
- URL blocking
- Request capture and analysis
"""

import json
import re
from typing import Any

from ai_core import CapabilityCategory, get_logger
from base_agent import ToolResult, tool
from playwright.async_api import Route, Request

from ..browser_config import NETWORK_MOCK_DEFAULTS
from ..browser_manager import get_browser_manager

logger = get_logger(__name__)


# Track network interception state
_interception_handlers: dict[str, dict[str, Any]] = {}
_captured_requests: dict[str, list[dict[str, Any]]] = {}


# ============================================================================
# Request Interception
# ============================================================================


@tool(
    name="network_intercept_enable",
    description="Enable request interception for a page. Allows mocking and blocking requests.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "url_pattern": {
                "type": "string",
                "description": "URL pattern to intercept (regex or glob)",
                "default": "**/*",
            },
            "capture_requests": {
                "type": "boolean",
                "description": "Capture request details for later analysis",
                "default": True,
            },
        },
        "required": ["page_id"],
    },
    permission_level=2,
    capability_category=CapabilityCategory.WEB,
)
async def network_intercept_enable(
    page_id: str,
    url_pattern: str = "**/*",
    capture_requests: bool = True,
) -> ToolResult:
    """Enable request interception."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        # Initialize capture storage
        if capture_requests:
            _captured_requests[page_id] = []

        async def handle_route(route: Route, request: Request) -> None:
            # Capture request if enabled
            if capture_requests and page_id in _captured_requests:
                _captured_requests[page_id].append({
                    "url": request.url,
                    "method": request.method,
                    "headers": dict(request.headers),
                    "post_data": request.post_data,
                    "resource_type": request.resource_type,
                })

            # Continue with normal request
            await route.continue_()

        await page.route(url_pattern, handle_route)

        _interception_handlers[page_id] = {
            "url_pattern": url_pattern,
            "capture_requests": capture_requests,
            "handler": handle_route,
        }

        return ToolResult.ok(
            {
                "enabled": True,
                "page_id": page_id,
                "url_pattern": url_pattern,
                "capture_requests": capture_requests,
            }
        )

    except Exception as e:
        logger.error("Network interception enable failed", page_id=page_id, error=str(e))
        return ToolResult.fail(f"Network interception enable failed: {e}")


@tool(
    name="network_mock_response",
    description="Mock a network response for matching requests.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "url_pattern": {
                "type": "string",
                "description": "URL pattern to mock (regex or glob)",
            },
            "status": {
                "type": "integer",
                "description": "HTTP status code",
                "default": 200,
            },
            "body": {
                "type": "string",
                "description": "Response body (string or JSON string)",
            },
            "content_type": {
                "type": "string",
                "description": "Content-Type header",
                "default": "application/json",
            },
            "headers": {
                "type": "object",
                "description": "Additional response headers",
            },
        },
        "required": ["page_id", "url_pattern", "body"],
    },
    permission_level=2,
    capability_category=CapabilityCategory.WEB,
)
async def network_mock_response(
    page_id: str,
    url_pattern: str,
    body: str,
    status: int = 200,
    content_type: str = "application/json",
    headers: dict | None = None,
) -> ToolResult:
    """Mock a network response."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        response_headers = {"Content-Type": content_type}
        if headers:
            response_headers.update(headers)

        async def mock_handler(route: Route) -> None:
            await route.fulfill(
                status=status,
                body=body,
                headers=response_headers,
            )

        await page.route(url_pattern, mock_handler)

        return ToolResult.ok(
            {
                "mocked": True,
                "page_id": page_id,
                "url_pattern": url_pattern,
                "status": status,
                "content_type": content_type,
            }
        )

    except Exception as e:
        logger.error("Network mock response failed", page_id=page_id, error=str(e))
        return ToolResult.fail(f"Network mock response failed: {e}")


@tool(
    name="network_mock_json",
    description="Mock a JSON API response. Convenience wrapper for network_mock_response.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "url_pattern": {
                "type": "string",
                "description": "URL pattern to mock",
            },
            "data": {
                "type": "object",
                "description": "JSON data to return",
            },
            "status": {
                "type": "integer",
                "default": 200,
            },
        },
        "required": ["page_id", "url_pattern", "data"],
    },
    permission_level=2,
    capability_category=CapabilityCategory.WEB,
)
async def network_mock_json(
    page_id: str,
    url_pattern: str,
    data: dict | list,
    status: int = 200,
) -> ToolResult:
    """Mock a JSON API response."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        body = json.dumps(data)

        async def mock_handler(route: Route) -> None:
            await route.fulfill(
                status=status,
                body=body,
                content_type="application/json",
            )

        await page.route(url_pattern, mock_handler)

        return ToolResult.ok(
            {
                "mocked": True,
                "page_id": page_id,
                "url_pattern": url_pattern,
                "status": status,
                "data_type": type(data).__name__,
            }
        )

    except Exception as e:
        logger.error("Network mock JSON failed", page_id=page_id, error=str(e))
        return ToolResult.fail(f"Network mock JSON failed: {e}")


@tool(
    name="network_block_urls",
    description="Block requests to matching URLs.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "url_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of URL patterns to block",
            },
        },
        "required": ["page_id", "url_patterns"],
    },
    permission_level=2,
    capability_category=CapabilityCategory.WEB,
)
async def network_block_urls(
    page_id: str,
    url_patterns: list[str],
) -> ToolResult:
    """Block requests to matching URLs."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        blocked_count = 0

        for pattern in url_patterns:
            async def block_handler(route: Route) -> None:
                await route.abort("blockedbyclient")

            await page.route(pattern, block_handler)
            blocked_count += 1

        return ToolResult.ok(
            {
                "blocked": True,
                "page_id": page_id,
                "patterns_count": blocked_count,
                "patterns": url_patterns,
            }
        )

    except Exception as e:
        logger.error("Network block URLs failed", page_id=page_id, error=str(e))
        return ToolResult.fail(f"Network block URLs failed: {e}")


# ============================================================================
# Request Capture and Analysis
# ============================================================================


@tool(
    name="network_get_requests",
    description="Get captured network requests.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "url_filter": {
                "type": "string",
                "description": "Filter requests by URL (substring match)",
            },
            "method_filter": {
                "type": "string",
                "description": "Filter by HTTP method",
            },
            "resource_type_filter": {
                "type": "string",
                "description": "Filter by resource type (document, xhr, fetch, etc.)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of requests to return",
                "default": 100,
            },
            "clear": {
                "type": "boolean",
                "description": "Clear captured requests after retrieval",
                "default": False,
            },
        },
        "required": ["page_id"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def network_get_requests(
    page_id: str,
    url_filter: str | None = None,
    method_filter: str | None = None,
    resource_type_filter: str | None = None,
    limit: int = 100,
    clear: bool = False,
) -> ToolResult:
    """Get captured network requests."""
    try:
        if page_id not in _captured_requests:
            return ToolResult.ok(
                {
                    "requests": [],
                    "count": 0,
                    "message": "No requests captured. Enable interception first.",
                }
            )

        requests = _captured_requests[page_id].copy()

        # Apply filters
        if url_filter:
            requests = [r for r in requests if url_filter in r["url"]]

        if method_filter:
            requests = [r for r in requests if r["method"].upper() == method_filter.upper()]

        if resource_type_filter:
            requests = [r for r in requests if r["resource_type"] == resource_type_filter]

        # Apply limit
        total_count = len(requests)
        requests = requests[:limit]

        # Clear if requested
        if clear:
            _captured_requests[page_id] = []

        return ToolResult.ok(
            {
                "requests": requests,
                "count": len(requests),
                "total_count": total_count,
                "cleared": clear,
            }
        )

    except Exception as e:
        logger.error("Network get requests failed", page_id=page_id, error=str(e))
        return ToolResult.fail(f"Network get requests failed: {e}")


@tool(
    name="network_wait_for_response",
    description="Wait for a specific network response.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "url_pattern": {
                "type": "string",
                "description": "URL pattern to wait for (glob or regex)",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in milliseconds",
                "default": 30000,
            },
        },
        "required": ["page_id", "url_pattern"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def network_wait_for_response(
    page_id: str,
    url_pattern: str,
    timeout: int = 30000,
) -> ToolResult:
    """Wait for a network response."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        response = await page.wait_for_response(url_pattern, timeout=timeout)

        # Get response details
        response_data = {
            "url": response.url,
            "status": response.status,
            "status_text": response.status_text,
            "ok": response.ok,
            "headers": dict(response.headers),
        }

        # Try to get body for JSON responses
        try:
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                response_data["body"] = await response.json()
            else:
                # Get first 1000 chars of text for non-JSON
                text = await response.text()
                response_data["body_preview"] = text[:1000] if len(text) > 1000 else text
        except Exception:
            pass

        return ToolResult.ok(response_data)

    except Exception as e:
        logger.error(
            "Network wait for response failed",
            page_id=page_id,
            url_pattern=url_pattern,
            error=str(e),
        )
        return ToolResult.fail(f"Network wait for response failed: {e}")


@tool(
    name="network_wait_for_request",
    description="Wait for a specific network request.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "url_pattern": {
                "type": "string",
                "description": "URL pattern to wait for",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in milliseconds",
                "default": 30000,
            },
        },
        "required": ["page_id", "url_pattern"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def network_wait_for_request(
    page_id: str,
    url_pattern: str,
    timeout: int = 30000,
) -> ToolResult:
    """Wait for a network request."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        request = await page.wait_for_request(url_pattern, timeout=timeout)

        request_data = {
            "url": request.url,
            "method": request.method,
            "headers": dict(request.headers),
            "post_data": request.post_data,
            "resource_type": request.resource_type,
        }

        # Try to parse post data as JSON
        if request.post_data:
            try:
                request_data["post_data_json"] = json.loads(request.post_data)
            except json.JSONDecodeError:
                pass

        return ToolResult.ok(request_data)

    except Exception as e:
        logger.error(
            "Network wait for request failed",
            page_id=page_id,
            url_pattern=url_pattern,
            error=str(e),
        )
        return ToolResult.fail(f"Network wait for request failed: {e}")


@tool(
    name="network_clear_interceptors",
    description="Clear all network interceptors and mocks for a page.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
        },
        "required": ["page_id"],
    },
    permission_level=2,
    capability_category=CapabilityCategory.WEB,
)
async def network_clear_interceptors(page_id: str) -> ToolResult:
    """Clear all network interceptors."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        # Remove all route handlers
        await page.unroute_all()

        # Clear captured requests
        if page_id in _captured_requests:
            del _captured_requests[page_id]

        # Clear handler tracking
        if page_id in _interception_handlers:
            del _interception_handlers[page_id]

        return ToolResult.ok(
            {
                "cleared": True,
                "page_id": page_id,
            }
        )

    except Exception as e:
        logger.error("Network clear interceptors failed", page_id=page_id, error=str(e))
        return ToolResult.fail(f"Network clear interceptors failed: {e}")
