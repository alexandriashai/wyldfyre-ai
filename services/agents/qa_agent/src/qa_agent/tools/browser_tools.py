"""
Browser lifecycle and navigation tools for the QA Agent.

Provides tools for:
- Browser instance management (launch, close)
- Context creation and management
- Page lifecycle (create, close)
- Navigation (goto, back, forward, reload)
- Wait operations (selector, load state, URL)
- Page information (URL, title, content)
- JavaScript execution
"""

from typing import Any

from ai_core import CapabilityCategory, get_logger
from base_agent import ToolResult, tool

from ..browser_config import BROWSER_DEFAULTS, BrowserType, WaitState
from ..browser_manager import get_browser_manager

logger = get_logger(__name__)


# ============================================================================
# Browser Lifecycle Tools
# ============================================================================


@tool(
    name="browser_launch",
    description="Launch a new browser instance. Returns a browser_id for subsequent operations.",
    parameters={
        "type": "object",
        "properties": {
            "browser_type": {
                "type": "string",
                "enum": ["chromium", "firefox", "webkit"],
                "description": "Type of browser to launch",
                "default": "chromium",
            },
            "headless": {
                "type": "boolean",
                "description": "Run browser in headless mode",
                "default": True,
            },
        },
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def browser_launch(
    browser_type: str = "chromium",
    headless: bool = True,
    _task_id: str | None = None,
) -> ToolResult:
    """Launch a new browser instance."""
    try:
        manager = get_browser_manager()
        browser_id = await manager.launch_browser(
            browser_type=browser_type,
            headless=headless,
            task_id=_task_id,
        )

        return ToolResult.ok(
            {"browser_id": browser_id},
            browser_type=browser_type,
            headless=headless,
        )

    except Exception as e:
        logger.error("Failed to launch browser", error=str(e))
        return ToolResult.fail(f"Failed to launch browser: {e}")


@tool(
    name="browser_close",
    description="Close a browser instance and all its contexts/pages.",
    parameters={
        "type": "object",
        "properties": {
            "browser_id": {
                "type": "string",
                "description": "Browser ID to close",
            },
        },
        "required": ["browser_id"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def browser_close(browser_id: str) -> ToolResult:
    """Close a browser instance."""
    try:
        manager = get_browser_manager()
        closed = await manager.close_browser(browser_id)

        if closed:
            return ToolResult.ok({"closed": True, "browser_id": browser_id})
        else:
            return ToolResult.fail(f"Browser not found: {browser_id}")

    except Exception as e:
        logger.error("Failed to close browser", browser_id=browser_id, error=str(e))
        return ToolResult.fail(f"Failed to close browser: {e}")


@tool(
    name="browser_close_all",
    description="Close all browser instances. Use for cleanup.",
    parameters={"type": "object", "properties": {}},
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def browser_close_all() -> ToolResult:
    """Close all browser instances."""
    try:
        manager = get_browser_manager()
        count = await manager.close_all()

        return ToolResult.ok(
            {"closed_count": count},
            message=f"Closed {count} browser(s)",
        )

    except Exception as e:
        logger.error("Failed to close all browsers", error=str(e))
        return ToolResult.fail(f"Failed to close all browsers: {e}")


@tool(
    name="browser_list",
    description="List all active browsers with their metadata.",
    parameters={"type": "object", "properties": {}},
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def browser_list() -> ToolResult:
    """List all active browsers."""
    try:
        manager = get_browser_manager()
        browsers = manager.list_browsers()
        stats = manager.get_stats()

        return ToolResult.ok(
            {
                "browsers": browsers,
                "count": len(browsers),
                "stats": stats,
            }
        )

    except Exception as e:
        logger.error("Failed to list browsers", error=str(e))
        return ToolResult.fail(f"Failed to list browsers: {e}")


# ============================================================================
# Context Tools
# ============================================================================


@tool(
    name="browser_context_create",
    description="Create a new browser context for test isolation. Each context has separate cookies and localStorage.",
    parameters={
        "type": "object",
        "properties": {
            "browser_id": {
                "type": "string",
                "description": "Browser ID to create context in",
            },
            "viewport_width": {
                "type": "integer",
                "description": "Viewport width in pixels",
                "default": 1280,
            },
            "viewport_height": {
                "type": "integer",
                "description": "Viewport height in pixels",
                "default": 720,
            },
            "storage_state": {
                "type": "string",
                "description": "Path to storage state file for session restoration",
            },
        },
        "required": ["browser_id"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def browser_context_create(
    browser_id: str,
    viewport_width: int = 1280,
    viewport_height: int = 720,
    storage_state: str | None = None,
    _task_id: str | None = None,
) -> ToolResult:
    """Create a new browser context."""
    try:
        manager = get_browser_manager()
        context_id = await manager.create_context(
            browser_id=browser_id,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            storage_state=storage_state,
            task_id=_task_id,
        )

        return ToolResult.ok(
            {"context_id": context_id, "browser_id": browser_id},
            viewport=f"{viewport_width}x{viewport_height}",
        )

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Failed to create context", browser_id=browser_id, error=str(e))
        return ToolResult.fail(f"Failed to create context: {e}")


@tool(
    name="browser_context_close",
    description="Close a browser context and all its pages.",
    parameters={
        "type": "object",
        "properties": {
            "context_id": {
                "type": "string",
                "description": "Context ID to close",
            },
        },
        "required": ["context_id"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def browser_context_close(context_id: str) -> ToolResult:
    """Close a browser context."""
    try:
        manager = get_browser_manager()
        closed = await manager.close_context(context_id)

        if closed:
            return ToolResult.ok({"closed": True, "context_id": context_id})
        else:
            return ToolResult.fail(f"Context not found: {context_id}")

    except Exception as e:
        logger.error("Failed to close context", context_id=context_id, error=str(e))
        return ToolResult.fail(f"Failed to close context: {e}")


# ============================================================================
# Page Lifecycle Tools
# ============================================================================


@tool(
    name="page_new",
    description="Create a new page (tab) in a browser context.",
    parameters={
        "type": "object",
        "properties": {
            "context_id": {
                "type": "string",
                "description": "Context ID to create page in",
            },
        },
        "required": ["context_id"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def page_new(
    context_id: str,
    _task_id: str | None = None,
) -> ToolResult:
    """Create a new page."""
    try:
        manager = get_browser_manager()
        page_id = await manager.new_page(context_id, task_id=_task_id)

        return ToolResult.ok(
            {"page_id": page_id, "context_id": context_id}
        )

    except ValueError as e:
        return ToolResult.fail(str(e))
    except Exception as e:
        logger.error("Failed to create page", context_id=context_id, error=str(e))
        return ToolResult.fail(f"Failed to create page: {e}")


@tool(
    name="page_close",
    description="Close a page.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID to close",
            },
        },
        "required": ["page_id"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def page_close(page_id: str) -> ToolResult:
    """Close a page."""
    try:
        manager = get_browser_manager()
        closed = await manager.close_page(page_id)

        if closed:
            return ToolResult.ok({"closed": True, "page_id": page_id})
        else:
            return ToolResult.fail(f"Page not found: {page_id}")

    except Exception as e:
        logger.error("Failed to close page", page_id=page_id, error=str(e))
        return ToolResult.fail(f"Failed to close page: {e}")


# ============================================================================
# Navigation Tools
# ============================================================================


@tool(
    name="page_goto",
    description="Navigate a page to a URL.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID to navigate",
            },
            "url": {
                "type": "string",
                "description": "URL to navigate to",
            },
            "wait_until": {
                "type": "string",
                "enum": ["load", "domcontentloaded", "networkidle", "commit"],
                "description": "Wait until this event before returning",
                "default": "load",
            },
            "timeout": {
                "type": "integer",
                "description": "Navigation timeout in milliseconds",
                "default": 30000,
            },
        },
        "required": ["page_id", "url"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def page_goto(
    page_id: str,
    url: str,
    wait_until: str = "load",
    timeout: int = 30000,
) -> ToolResult:
    """Navigate to a URL."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        response = await page.goto(url, wait_until=wait_until, timeout=timeout)

        # Update tracked URL
        manager.update_page_url(page_id, page.url)

        return ToolResult.ok(
            {
                "url": page.url,
                "status": response.status if response else None,
                "ok": response.ok if response else None,
            }
        )

    except Exception as e:
        logger.error("Failed to navigate", page_id=page_id, url=url, error=str(e))
        return ToolResult.fail(f"Failed to navigate: {e}")


@tool(
    name="page_reload",
    description="Reload the current page.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID to reload",
            },
            "wait_until": {
                "type": "string",
                "enum": ["load", "domcontentloaded", "networkidle", "commit"],
                "description": "Wait until this event before returning",
                "default": "load",
            },
            "timeout": {
                "type": "integer",
                "description": "Reload timeout in milliseconds",
                "default": 30000,
            },
        },
        "required": ["page_id"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def page_reload(
    page_id: str,
    wait_until: str = "load",
    timeout: int = 30000,
) -> ToolResult:
    """Reload the page."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        response = await page.reload(wait_until=wait_until, timeout=timeout)

        return ToolResult.ok(
            {
                "url": page.url,
                "status": response.status if response else None,
            }
        )

    except Exception as e:
        logger.error("Failed to reload page", page_id=page_id, error=str(e))
        return ToolResult.fail(f"Failed to reload page: {e}")


@tool(
    name="page_go_back",
    description="Navigate back in history.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "wait_until": {
                "type": "string",
                "enum": ["load", "domcontentloaded", "networkidle", "commit"],
                "default": "load",
            },
            "timeout": {
                "type": "integer",
                "default": 30000,
            },
        },
        "required": ["page_id"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def page_go_back(
    page_id: str,
    wait_until: str = "load",
    timeout: int = 30000,
) -> ToolResult:
    """Navigate back in history."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        response = await page.go_back(wait_until=wait_until, timeout=timeout)
        manager.update_page_url(page_id, page.url)

        return ToolResult.ok(
            {
                "url": page.url,
                "navigated": response is not None,
            }
        )

    except Exception as e:
        logger.error("Failed to go back", page_id=page_id, error=str(e))
        return ToolResult.fail(f"Failed to go back: {e}")


@tool(
    name="page_go_forward",
    description="Navigate forward in history.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "wait_until": {
                "type": "string",
                "enum": ["load", "domcontentloaded", "networkidle", "commit"],
                "default": "load",
            },
            "timeout": {
                "type": "integer",
                "default": 30000,
            },
        },
        "required": ["page_id"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def page_go_forward(
    page_id: str,
    wait_until: str = "load",
    timeout: int = 30000,
) -> ToolResult:
    """Navigate forward in history."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        response = await page.go_forward(wait_until=wait_until, timeout=timeout)
        manager.update_page_url(page_id, page.url)

        return ToolResult.ok(
            {
                "url": page.url,
                "navigated": response is not None,
            }
        )

    except Exception as e:
        logger.error("Failed to go forward", page_id=page_id, error=str(e))
        return ToolResult.fail(f"Failed to go forward: {e}")


# ============================================================================
# Page Information Tools
# ============================================================================


@tool(
    name="page_get_url",
    description="Get the current URL of a page.",
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
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def page_get_url(page_id: str) -> ToolResult:
    """Get the current URL."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        return ToolResult.ok({"url": page.url})

    except Exception as e:
        logger.error("Failed to get URL", page_id=page_id, error=str(e))
        return ToolResult.fail(f"Failed to get URL: {e}")


@tool(
    name="page_get_title",
    description="Get the title of a page.",
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
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def page_get_title(page_id: str) -> ToolResult:
    """Get the page title."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        title = await page.title()
        return ToolResult.ok({"title": title})

    except Exception as e:
        logger.error("Failed to get title", page_id=page_id, error=str(e))
        return ToolResult.fail(f"Failed to get title: {e}")


@tool(
    name="page_get_content",
    description="Get the HTML content of a page.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum content length to return",
                "default": 50000,
            },
        },
        "required": ["page_id"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def page_get_content(
    page_id: str,
    max_length: int = 50000,
) -> ToolResult:
    """Get the page HTML content."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        content = await page.content()
        truncated = len(content) > max_length

        return ToolResult.ok(
            {
                "content": content[:max_length],
                "truncated": truncated,
                "original_length": len(content),
            }
        )

    except Exception as e:
        logger.error("Failed to get content", page_id=page_id, error=str(e))
        return ToolResult.fail(f"Failed to get content: {e}")


# ============================================================================
# Wait Tools
# ============================================================================


@tool(
    name="page_wait_for_selector",
    description="Wait for an element matching the selector to appear.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "selector": {
                "type": "string",
                "description": "CSS or Playwright selector",
            },
            "state": {
                "type": "string",
                "enum": ["attached", "detached", "visible", "hidden"],
                "description": "State to wait for",
                "default": "visible",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in milliseconds",
                "default": 30000,
            },
        },
        "required": ["page_id", "selector"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def page_wait_for_selector(
    page_id: str,
    selector: str,
    state: str = "visible",
    timeout: int = 30000,
) -> ToolResult:
    """Wait for an element to reach the specified state."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        element = await page.wait_for_selector(
            selector,
            state=state,
            timeout=timeout,
        )

        return ToolResult.ok(
            {
                "found": element is not None,
                "selector": selector,
                "state": state,
            }
        )

    except Exception as e:
        logger.error(
            "Wait for selector failed",
            page_id=page_id,
            selector=selector,
            error=str(e),
        )
        return ToolResult.fail(f"Wait for selector failed: {e}")


@tool(
    name="page_wait_for_load_state",
    description="Wait for a specific load state.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "state": {
                "type": "string",
                "enum": ["load", "domcontentloaded", "networkidle"],
                "description": "Load state to wait for",
                "default": "load",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in milliseconds",
                "default": 30000,
            },
        },
        "required": ["page_id"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def page_wait_for_load_state(
    page_id: str,
    state: str = "load",
    timeout: int = 30000,
) -> ToolResult:
    """Wait for a load state."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        await page.wait_for_load_state(state, timeout=timeout)

        return ToolResult.ok(
            {
                "state": state,
                "url": page.url,
            }
        )

    except Exception as e:
        logger.error(
            "Wait for load state failed",
            page_id=page_id,
            state=state,
            error=str(e),
        )
        return ToolResult.fail(f"Wait for load state failed: {e}")


@tool(
    name="page_wait_for_url",
    description="Wait for the page URL to match a pattern.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "url_pattern": {
                "type": "string",
                "description": "URL string or pattern to match (supports * wildcard)",
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
async def page_wait_for_url(
    page_id: str,
    url_pattern: str,
    timeout: int = 30000,
) -> ToolResult:
    """Wait for URL to match a pattern."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        await page.wait_for_url(url_pattern, timeout=timeout)
        manager.update_page_url(page_id, page.url)

        return ToolResult.ok(
            {
                "url": page.url,
                "pattern": url_pattern,
            }
        )

    except Exception as e:
        logger.error(
            "Wait for URL failed",
            page_id=page_id,
            url_pattern=url_pattern,
            error=str(e),
        )
        return ToolResult.fail(f"Wait for URL failed: {e}")


# ============================================================================
# JavaScript Execution
# ============================================================================


@tool(
    name="page_evaluate",
    description="Execute JavaScript in the page context. Use with caution.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "expression": {
                "type": "string",
                "description": "JavaScript expression to evaluate",
            },
        },
        "required": ["page_id", "expression"],
    },
    permission_level=2,
    capability_category=CapabilityCategory.WEB,
)
async def page_evaluate(
    page_id: str,
    expression: str,
) -> ToolResult:
    """Execute JavaScript in the page."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        result = await page.evaluate(expression)

        return ToolResult.ok(
            {
                "result": result,
                "expression": expression[:100],  # Truncate for logging
            }
        )

    except Exception as e:
        logger.error(
            "JavaScript evaluation failed",
            page_id=page_id,
            error=str(e),
        )
        return ToolResult.fail(f"JavaScript evaluation failed: {e}")
