"""
Browser assertion tools for the QA Agent.

Provides Playwright expect-style assertions for E2E testing:
- Element visibility, enabled state
- Text content, input values
- Attribute values
- Page URL and title
- Element count
"""

import re
from typing import Any

from ai_core import CapabilityCategory, get_logger
from base_agent import ToolResult, tool
from playwright.async_api import expect

from ..browser_manager import get_browser_manager

logger = get_logger(__name__)


# ============================================================================
# Element Visibility Assertions
# ============================================================================


@tool(
    name="expect_element_visible",
    description="Assert that an element is visible on the page.",
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
            "timeout": {
                "type": "integer",
                "description": "Timeout in milliseconds",
                "default": 5000,
            },
        },
        "required": ["page_id", "selector"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def expect_element_visible(
    page_id: str,
    selector: str,
    timeout: int = 5000,
) -> ToolResult:
    """Assert element is visible."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        locator = page.locator(selector)
        await expect(locator).to_be_visible(timeout=timeout)

        return ToolResult.ok(
            {
                "passed": True,
                "assertion": "visible",
                "selector": selector,
            }
        )

    except AssertionError as e:
        return ToolResult.ok(
            {
                "passed": False,
                "assertion": "visible",
                "selector": selector,
                "error": str(e),
            }
        )
    except Exception as e:
        logger.error("Visibility assertion error", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Visibility assertion error: {e}")


@tool(
    name="expect_element_hidden",
    description="Assert that an element is hidden or not present.",
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
            "timeout": {
                "type": "integer",
                "default": 5000,
            },
        },
        "required": ["page_id", "selector"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def expect_element_hidden(
    page_id: str,
    selector: str,
    timeout: int = 5000,
) -> ToolResult:
    """Assert element is hidden."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        locator = page.locator(selector)
        await expect(locator).to_be_hidden(timeout=timeout)

        return ToolResult.ok(
            {
                "passed": True,
                "assertion": "hidden",
                "selector": selector,
            }
        )

    except AssertionError as e:
        return ToolResult.ok(
            {
                "passed": False,
                "assertion": "hidden",
                "selector": selector,
                "error": str(e),
            }
        )
    except Exception as e:
        logger.error("Hidden assertion error", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Hidden assertion error: {e}")


@tool(
    name="expect_element_enabled",
    description="Assert that an element is enabled (not disabled).",
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
            "timeout": {
                "type": "integer",
                "default": 5000,
            },
        },
        "required": ["page_id", "selector"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def expect_element_enabled(
    page_id: str,
    selector: str,
    timeout: int = 5000,
) -> ToolResult:
    """Assert element is enabled."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        locator = page.locator(selector)
        await expect(locator).to_be_enabled(timeout=timeout)

        return ToolResult.ok(
            {
                "passed": True,
                "assertion": "enabled",
                "selector": selector,
            }
        )

    except AssertionError as e:
        return ToolResult.ok(
            {
                "passed": False,
                "assertion": "enabled",
                "selector": selector,
                "error": str(e),
            }
        )
    except Exception as e:
        logger.error("Enabled assertion error", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Enabled assertion error: {e}")


# ============================================================================
# Text Content Assertions
# ============================================================================


@tool(
    name="expect_element_text",
    description="Assert that an element contains or matches specific text.",
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
            "text": {
                "type": "string",
                "description": "Expected text content",
            },
            "exact": {
                "type": "boolean",
                "description": "If true, match exactly. If false, match substring",
                "default": False,
            },
            "ignore_case": {
                "type": "boolean",
                "description": "Ignore case when matching",
                "default": False,
            },
            "use_regex": {
                "type": "boolean",
                "description": "Treat text as a regular expression",
                "default": False,
            },
            "timeout": {
                "type": "integer",
                "default": 5000,
            },
        },
        "required": ["page_id", "selector", "text"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def expect_element_text(
    page_id: str,
    selector: str,
    text: str,
    exact: bool = False,
    ignore_case: bool = False,
    use_regex: bool = False,
    timeout: int = 5000,
) -> ToolResult:
    """Assert element has specific text."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        locator = page.locator(selector)

        if use_regex:
            flags = re.IGNORECASE if ignore_case else 0
            pattern = re.compile(text, flags)
            await expect(locator).to_have_text(pattern, timeout=timeout)
        elif exact:
            await expect(locator).to_have_text(text, ignore_case=ignore_case, timeout=timeout)
        else:
            await expect(locator).to_contain_text(text, ignore_case=ignore_case, timeout=timeout)

        return ToolResult.ok(
            {
                "passed": True,
                "assertion": "text",
                "selector": selector,
                "expected": text,
                "exact": exact,
            }
        )

    except AssertionError as e:
        return ToolResult.ok(
            {
                "passed": False,
                "assertion": "text",
                "selector": selector,
                "expected": text,
                "error": str(e),
            }
        )
    except Exception as e:
        logger.error("Text assertion error", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Text assertion error: {e}")


@tool(
    name="expect_element_value",
    description="Assert that an input element has a specific value.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "selector": {
                "type": "string",
                "description": "CSS or Playwright selector for the input",
            },
            "value": {
                "type": "string",
                "description": "Expected input value",
            },
            "timeout": {
                "type": "integer",
                "default": 5000,
            },
        },
        "required": ["page_id", "selector", "value"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def expect_element_value(
    page_id: str,
    selector: str,
    value: str,
    timeout: int = 5000,
) -> ToolResult:
    """Assert input has specific value."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        locator = page.locator(selector)
        await expect(locator).to_have_value(value, timeout=timeout)

        return ToolResult.ok(
            {
                "passed": True,
                "assertion": "value",
                "selector": selector,
                "expected": value,
            }
        )

    except AssertionError as e:
        return ToolResult.ok(
            {
                "passed": False,
                "assertion": "value",
                "selector": selector,
                "expected": value,
                "error": str(e),
            }
        )
    except Exception as e:
        logger.error("Value assertion error", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Value assertion error: {e}")


# ============================================================================
# Attribute Assertions
# ============================================================================


@tool(
    name="expect_element_attribute",
    description="Assert that an element has a specific attribute value.",
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
            "attribute": {
                "type": "string",
                "description": "Attribute name",
            },
            "value": {
                "type": "string",
                "description": "Expected attribute value",
            },
            "timeout": {
                "type": "integer",
                "default": 5000,
            },
        },
        "required": ["page_id", "selector", "attribute", "value"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def expect_element_attribute(
    page_id: str,
    selector: str,
    attribute: str,
    value: str,
    timeout: int = 5000,
) -> ToolResult:
    """Assert element has specific attribute value."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        locator = page.locator(selector)
        await expect(locator).to_have_attribute(attribute, value, timeout=timeout)

        return ToolResult.ok(
            {
                "passed": True,
                "assertion": "attribute",
                "selector": selector,
                "attribute": attribute,
                "expected": value,
            }
        )

    except AssertionError as e:
        return ToolResult.ok(
            {
                "passed": False,
                "assertion": "attribute",
                "selector": selector,
                "attribute": attribute,
                "expected": value,
                "error": str(e),
            }
        )
    except Exception as e:
        logger.error(
            "Attribute assertion error",
            page_id=page_id,
            selector=selector,
            attribute=attribute,
            error=str(e),
        )
        return ToolResult.fail(f"Attribute assertion error: {e}")


# ============================================================================
# Page Assertions
# ============================================================================


@tool(
    name="expect_page_url",
    description="Assert that the page URL matches or contains a pattern.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "url": {
                "type": "string",
                "description": "Expected URL or pattern (supports * wildcard)",
            },
            "exact": {
                "type": "boolean",
                "description": "If true, match exactly. If false, match pattern",
                "default": False,
            },
            "use_regex": {
                "type": "boolean",
                "description": "Treat url as a regular expression",
                "default": False,
            },
            "timeout": {
                "type": "integer",
                "default": 5000,
            },
        },
        "required": ["page_id", "url"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def expect_page_url(
    page_id: str,
    url: str,
    exact: bool = False,
    use_regex: bool = False,
    timeout: int = 5000,
) -> ToolResult:
    """Assert page URL matches."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        if use_regex:
            pattern = re.compile(url)
            await expect(page).to_have_url(pattern, timeout=timeout)
        elif exact:
            await expect(page).to_have_url(url, timeout=timeout)
        else:
            # Use pattern matching with *
            await expect(page).to_have_url(url, timeout=timeout)

        actual_url = page.url

        return ToolResult.ok(
            {
                "passed": True,
                "assertion": "url",
                "expected": url,
                "actual": actual_url,
            }
        )

    except AssertionError as e:
        return ToolResult.ok(
            {
                "passed": False,
                "assertion": "url",
                "expected": url,
                "actual": page.url if page else None,
                "error": str(e),
            }
        )
    except Exception as e:
        logger.error("URL assertion error", page_id=page_id, error=str(e))
        return ToolResult.fail(f"URL assertion error: {e}")


@tool(
    name="expect_page_title",
    description="Assert that the page title matches.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "title": {
                "type": "string",
                "description": "Expected page title",
            },
            "use_regex": {
                "type": "boolean",
                "description": "Treat title as a regular expression",
                "default": False,
            },
            "timeout": {
                "type": "integer",
                "default": 5000,
            },
        },
        "required": ["page_id", "title"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def expect_page_title(
    page_id: str,
    title: str,
    use_regex: bool = False,
    timeout: int = 5000,
) -> ToolResult:
    """Assert page title matches."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        if use_regex:
            pattern = re.compile(title)
            await expect(page).to_have_title(pattern, timeout=timeout)
        else:
            await expect(page).to_have_title(title, timeout=timeout)

        actual_title = await page.title()

        return ToolResult.ok(
            {
                "passed": True,
                "assertion": "title",
                "expected": title,
                "actual": actual_title,
            }
        )

    except AssertionError as e:
        return ToolResult.ok(
            {
                "passed": False,
                "assertion": "title",
                "expected": title,
                "error": str(e),
            }
        )
    except Exception as e:
        logger.error("Title assertion error", page_id=page_id, error=str(e))
        return ToolResult.fail(f"Title assertion error: {e}")


# ============================================================================
# Count Assertions
# ============================================================================


@tool(
    name="expect_element_count",
    description="Assert that the number of elements matching a selector equals expected count.",
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
            "count": {
                "type": "integer",
                "description": "Expected number of elements",
            },
            "timeout": {
                "type": "integer",
                "default": 5000,
            },
        },
        "required": ["page_id", "selector", "count"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def expect_element_count(
    page_id: str,
    selector: str,
    count: int,
    timeout: int = 5000,
) -> ToolResult:
    """Assert element count matches."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        locator = page.locator(selector)
        await expect(locator).to_have_count(count, timeout=timeout)

        return ToolResult.ok(
            {
                "passed": True,
                "assertion": "count",
                "selector": selector,
                "expected": count,
            }
        )

    except AssertionError as e:
        # Get actual count for error reporting
        try:
            actual_count = await page.locator(selector).count()
        except Exception:
            actual_count = None

        return ToolResult.ok(
            {
                "passed": False,
                "assertion": "count",
                "selector": selector,
                "expected": count,
                "actual": actual_count,
                "error": str(e),
            }
        )
    except Exception as e:
        logger.error("Count assertion error", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Count assertion error: {e}")


# ============================================================================
# State Assertions
# ============================================================================


@tool(
    name="expect_element_checked",
    description="Assert that a checkbox or radio button is checked.",
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
            "timeout": {
                "type": "integer",
                "default": 5000,
            },
        },
        "required": ["page_id", "selector"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def expect_element_checked(
    page_id: str,
    selector: str,
    timeout: int = 5000,
) -> ToolResult:
    """Assert element is checked."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        locator = page.locator(selector)
        await expect(locator).to_be_checked(timeout=timeout)

        return ToolResult.ok(
            {
                "passed": True,
                "assertion": "checked",
                "selector": selector,
            }
        )

    except AssertionError as e:
        return ToolResult.ok(
            {
                "passed": False,
                "assertion": "checked",
                "selector": selector,
                "error": str(e),
            }
        )
    except Exception as e:
        logger.error("Checked assertion error", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Checked assertion error: {e}")


@tool(
    name="expect_element_focused",
    description="Assert that an element has focus.",
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
            "timeout": {
                "type": "integer",
                "default": 5000,
            },
        },
        "required": ["page_id", "selector"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def expect_element_focused(
    page_id: str,
    selector: str,
    timeout: int = 5000,
) -> ToolResult:
    """Assert element is focused."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        locator = page.locator(selector)
        await expect(locator).to_be_focused(timeout=timeout)

        return ToolResult.ok(
            {
                "passed": True,
                "assertion": "focused",
                "selector": selector,
            }
        )

    except AssertionError as e:
        return ToolResult.ok(
            {
                "passed": False,
                "assertion": "focused",
                "selector": selector,
                "error": str(e),
            }
        )
    except Exception as e:
        logger.error("Focused assertion error", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Focused assertion error: {e}")
