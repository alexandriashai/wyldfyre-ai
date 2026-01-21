"""
Element interaction tools for the QA Agent.

Provides tools for interacting with page elements:
- Click, double-click, hover
- Fill inputs, select options
- Check/uncheck checkboxes
- Keyboard input and key presses
- Drag and drop
- File uploads
- Element queries and information
"""

from typing import Any

from ai_core import CapabilityCategory, get_logger
from base_agent import ToolResult, tool

from ..browser_config import BROWSER_DEFAULTS
from ..browser_manager import get_browser_manager

logger = get_logger(__name__)


# ============================================================================
# Click Actions
# ============================================================================


@tool(
    name="element_click",
    description="Click on an element matching the selector.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "selector": {
                "type": "string",
                "description": "CSS or Playwright selector for the element",
            },
            "button": {
                "type": "string",
                "enum": ["left", "right", "middle"],
                "description": "Mouse button to use",
                "default": "left",
            },
            "click_count": {
                "type": "integer",
                "description": "Number of clicks",
                "default": 1,
            },
            "delay": {
                "type": "integer",
                "description": "Delay between mousedown and mouseup in ms",
                "default": 0,
            },
            "force": {
                "type": "boolean",
                "description": "Force click even if element is not actionable",
                "default": False,
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in milliseconds",
                "default": 30000,
            },
        },
        "required": ["page_id", "selector"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def element_click(
    page_id: str,
    selector: str,
    button: str = "left",
    click_count: int = 1,
    delay: int = 0,
    force: bool = False,
    timeout: int = 30000,
) -> ToolResult:
    """Click an element."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        await page.click(
            selector,
            button=button,
            click_count=click_count,
            delay=delay,
            force=force,
            timeout=timeout,
        )

        return ToolResult.ok(
            {
                "clicked": True,
                "selector": selector,
                "button": button,
            }
        )

    except Exception as e:
        logger.error("Click failed", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Click failed: {e}")


@tool(
    name="element_dblclick",
    description="Double-click on an element.",
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
            "force": {
                "type": "boolean",
                "default": False,
            },
            "timeout": {
                "type": "integer",
                "default": 30000,
            },
        },
        "required": ["page_id", "selector"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def element_dblclick(
    page_id: str,
    selector: str,
    force: bool = False,
    timeout: int = 30000,
) -> ToolResult:
    """Double-click an element."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        await page.dblclick(selector, force=force, timeout=timeout)

        return ToolResult.ok({"double_clicked": True, "selector": selector})

    except Exception as e:
        logger.error("Double-click failed", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Double-click failed: {e}")


@tool(
    name="element_hover",
    description="Hover over an element.",
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
            "force": {
                "type": "boolean",
                "default": False,
            },
            "timeout": {
                "type": "integer",
                "default": 30000,
            },
        },
        "required": ["page_id", "selector"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def element_hover(
    page_id: str,
    selector: str,
    force: bool = False,
    timeout: int = 30000,
) -> ToolResult:
    """Hover over an element."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        await page.hover(selector, force=force, timeout=timeout)

        return ToolResult.ok({"hovered": True, "selector": selector})

    except Exception as e:
        logger.error("Hover failed", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Hover failed: {e}")


# ============================================================================
# Input Actions
# ============================================================================


@tool(
    name="element_fill",
    description="Fill an input element with text. Clears existing value first.",
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
                "description": "Text to fill",
            },
            "force": {
                "type": "boolean",
                "default": False,
            },
            "timeout": {
                "type": "integer",
                "default": 30000,
            },
        },
        "required": ["page_id", "selector", "value"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def element_fill(
    page_id: str,
    selector: str,
    value: str,
    force: bool = False,
    timeout: int = 30000,
) -> ToolResult:
    """Fill an input with text."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        await page.fill(selector, value, force=force, timeout=timeout)

        return ToolResult.ok(
            {
                "filled": True,
                "selector": selector,
                "value_length": len(value),
            }
        )

    except Exception as e:
        logger.error("Fill failed", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Fill failed: {e}")


@tool(
    name="element_type",
    description="Type text into an element with keyboard events. Useful for inputs that need key events.",
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
                "description": "Text to type",
            },
            "delay": {
                "type": "integer",
                "description": "Delay between key presses in ms",
                "default": 0,
            },
            "timeout": {
                "type": "integer",
                "default": 30000,
            },
        },
        "required": ["page_id", "selector", "text"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def element_type(
    page_id: str,
    selector: str,
    text: str,
    delay: int = 0,
    timeout: int = 30000,
) -> ToolResult:
    """Type text into an element."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        await page.type(selector, text, delay=delay, timeout=timeout)

        return ToolResult.ok(
            {
                "typed": True,
                "selector": selector,
                "text_length": len(text),
            }
        )

    except Exception as e:
        logger.error("Type failed", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Type failed: {e}")


@tool(
    name="element_clear",
    description="Clear the value of an input element.",
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
                "default": 30000,
            },
        },
        "required": ["page_id", "selector"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def element_clear(
    page_id: str,
    selector: str,
    timeout: int = 30000,
) -> ToolResult:
    """Clear an input element."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        # Clear by filling with empty string
        await page.fill(selector, "", timeout=timeout)

        return ToolResult.ok({"cleared": True, "selector": selector})

    except Exception as e:
        logger.error("Clear failed", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Clear failed: {e}")


@tool(
    name="element_press",
    description="Press a key or key combination on an element.",
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
            "key": {
                "type": "string",
                "description": "Key to press (e.g., 'Enter', 'Tab', 'Control+a')",
            },
            "delay": {
                "type": "integer",
                "description": "Delay between keydown and keyup in ms",
                "default": 0,
            },
            "timeout": {
                "type": "integer",
                "default": 30000,
            },
        },
        "required": ["page_id", "selector", "key"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def element_press(
    page_id: str,
    selector: str,
    key: str,
    delay: int = 0,
    timeout: int = 30000,
) -> ToolResult:
    """Press a key on an element."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        await page.press(selector, key, delay=delay, timeout=timeout)

        return ToolResult.ok(
            {
                "pressed": True,
                "selector": selector,
                "key": key,
            }
        )

    except Exception as e:
        logger.error("Press failed", page_id=page_id, selector=selector, key=key, error=str(e))
        return ToolResult.fail(f"Press failed: {e}")


@tool(
    name="element_focus",
    description="Focus on an element.",
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
                "default": 30000,
            },
        },
        "required": ["page_id", "selector"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def element_focus(
    page_id: str,
    selector: str,
    timeout: int = 30000,
) -> ToolResult:
    """Focus on an element."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        await page.focus(selector, timeout=timeout)

        return ToolResult.ok({"focused": True, "selector": selector})

    except Exception as e:
        logger.error("Focus failed", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Focus failed: {e}")


# ============================================================================
# Form Controls
# ============================================================================


@tool(
    name="element_select_option",
    description="Select option(s) in a <select> element.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "selector": {
                "type": "string",
                "description": "CSS or Playwright selector for the select element",
            },
            "value": {
                "type": "string",
                "description": "Option value to select",
            },
            "label": {
                "type": "string",
                "description": "Option label (visible text) to select",
            },
            "index": {
                "type": "integer",
                "description": "Option index to select (0-based)",
            },
            "timeout": {
                "type": "integer",
                "default": 30000,
            },
        },
        "required": ["page_id", "selector"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def element_select_option(
    page_id: str,
    selector: str,
    value: str | None = None,
    label: str | None = None,
    index: int | None = None,
    timeout: int = 30000,
) -> ToolResult:
    """Select option(s) in a select element."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        # Build select arguments
        kwargs: dict[str, Any] = {"timeout": timeout}
        selection_info = {}

        if value is not None:
            result = await page.select_option(selector, value=value, **kwargs)
            selection_info["value"] = value
        elif label is not None:
            result = await page.select_option(selector, label=label, **kwargs)
            selection_info["label"] = label
        elif index is not None:
            result = await page.select_option(selector, index=index, **kwargs)
            selection_info["index"] = index
        else:
            return ToolResult.fail("Must specify value, label, or index")

        return ToolResult.ok(
            {
                "selected": True,
                "selector": selector,
                "selected_values": result,
                **selection_info,
            }
        )

    except Exception as e:
        logger.error("Select option failed", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Select option failed: {e}")


@tool(
    name="element_check",
    description="Check a checkbox or radio button.",
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
            "force": {
                "type": "boolean",
                "default": False,
            },
            "timeout": {
                "type": "integer",
                "default": 30000,
            },
        },
        "required": ["page_id", "selector"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def element_check(
    page_id: str,
    selector: str,
    force: bool = False,
    timeout: int = 30000,
) -> ToolResult:
    """Check a checkbox or radio button."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        await page.check(selector, force=force, timeout=timeout)

        return ToolResult.ok({"checked": True, "selector": selector})

    except Exception as e:
        logger.error("Check failed", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Check failed: {e}")


@tool(
    name="element_uncheck",
    description="Uncheck a checkbox.",
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
            "force": {
                "type": "boolean",
                "default": False,
            },
            "timeout": {
                "type": "integer",
                "default": 30000,
            },
        },
        "required": ["page_id", "selector"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def element_uncheck(
    page_id: str,
    selector: str,
    force: bool = False,
    timeout: int = 30000,
) -> ToolResult:
    """Uncheck a checkbox."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        await page.uncheck(selector, force=force, timeout=timeout)

        return ToolResult.ok({"unchecked": True, "selector": selector})

    except Exception as e:
        logger.error("Uncheck failed", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Uncheck failed: {e}")


# ============================================================================
# Advanced Actions
# ============================================================================


@tool(
    name="element_drag_drop",
    description="Drag an element to another element.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "source_selector": {
                "type": "string",
                "description": "Selector for the element to drag",
            },
            "target_selector": {
                "type": "string",
                "description": "Selector for the drop target",
            },
            "force": {
                "type": "boolean",
                "default": False,
            },
            "timeout": {
                "type": "integer",
                "default": 30000,
            },
        },
        "required": ["page_id", "source_selector", "target_selector"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def element_drag_drop(
    page_id: str,
    source_selector: str,
    target_selector: str,
    force: bool = False,
    timeout: int = 30000,
) -> ToolResult:
    """Drag and drop an element."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        await page.drag_and_drop(
            source_selector,
            target_selector,
            force=force,
            timeout=timeout,
        )

        return ToolResult.ok(
            {
                "dragged": True,
                "source": source_selector,
                "target": target_selector,
            }
        )

    except Exception as e:
        logger.error(
            "Drag and drop failed",
            page_id=page_id,
            source=source_selector,
            target=target_selector,
            error=str(e),
        )
        return ToolResult.fail(f"Drag and drop failed: {e}")


@tool(
    name="element_upload_file",
    description="Upload file(s) to a file input element.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "selector": {
                "type": "string",
                "description": "Selector for the file input",
            },
            "file_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of file paths to upload",
            },
            "timeout": {
                "type": "integer",
                "default": 30000,
            },
        },
        "required": ["page_id", "selector", "file_paths"],
    },
    permission_level=2,
    capability_category=CapabilityCategory.WEB,
)
async def element_upload_file(
    page_id: str,
    selector: str,
    file_paths: list[str],
    timeout: int = 30000,
) -> ToolResult:
    """Upload files to a file input."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        await page.set_input_files(selector, file_paths, timeout=timeout)

        return ToolResult.ok(
            {
                "uploaded": True,
                "selector": selector,
                "file_count": len(file_paths),
            }
        )

    except Exception as e:
        logger.error("File upload failed", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"File upload failed: {e}")


# ============================================================================
# Element Query Tools
# ============================================================================


@tool(
    name="element_query",
    description="Query for an element and check if it exists.",
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
        },
        "required": ["page_id", "selector"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def element_query(
    page_id: str,
    selector: str,
) -> ToolResult:
    """Query for an element."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        element = await page.query_selector(selector)

        return ToolResult.ok(
            {
                "found": element is not None,
                "selector": selector,
            }
        )

    except Exception as e:
        logger.error("Element query failed", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Element query failed: {e}")


@tool(
    name="element_query_all",
    description="Query for all elements matching a selector.",
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
        },
        "required": ["page_id", "selector"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def element_query_all(
    page_id: str,
    selector: str,
) -> ToolResult:
    """Query for all matching elements."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        elements = await page.query_selector_all(selector)

        return ToolResult.ok(
            {
                "count": len(elements),
                "selector": selector,
            }
        )

    except Exception as e:
        logger.error("Element query all failed", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Element query all failed: {e}")


@tool(
    name="element_count",
    description="Count elements matching a selector.",
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
        },
        "required": ["page_id", "selector"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def element_count(
    page_id: str,
    selector: str,
) -> ToolResult:
    """Count elements matching selector."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        count = await page.locator(selector).count()

        return ToolResult.ok(
            {
                "count": count,
                "selector": selector,
            }
        )

    except Exception as e:
        logger.error("Element count failed", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Element count failed: {e}")


@tool(
    name="element_get_text",
    description="Get the text content of an element.",
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
                "default": 30000,
            },
        },
        "required": ["page_id", "selector"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def element_get_text(
    page_id: str,
    selector: str,
    timeout: int = 30000,
) -> ToolResult:
    """Get text content of an element."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        text = await page.text_content(selector, timeout=timeout)

        return ToolResult.ok(
            {
                "text": text,
                "selector": selector,
            }
        )

    except Exception as e:
        logger.error("Get text failed", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Get text failed: {e}")


@tool(
    name="element_get_attribute",
    description="Get an attribute value from an element.",
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
                "description": "Attribute name to get",
            },
            "timeout": {
                "type": "integer",
                "default": 30000,
            },
        },
        "required": ["page_id", "selector", "attribute"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def element_get_attribute(
    page_id: str,
    selector: str,
    attribute: str,
    timeout: int = 30000,
) -> ToolResult:
    """Get an attribute from an element."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        value = await page.get_attribute(selector, attribute, timeout=timeout)

        return ToolResult.ok(
            {
                "value": value,
                "selector": selector,
                "attribute": attribute,
            }
        )

    except Exception as e:
        logger.error(
            "Get attribute failed",
            page_id=page_id,
            selector=selector,
            attribute=attribute,
            error=str(e),
        )
        return ToolResult.fail(f"Get attribute failed: {e}")


@tool(
    name="element_is_visible",
    description="Check if an element is visible.",
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
async def element_is_visible(
    page_id: str,
    selector: str,
    timeout: int = 5000,
) -> ToolResult:
    """Check if element is visible."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        visible = await page.is_visible(selector, timeout=timeout)

        return ToolResult.ok(
            {
                "visible": visible,
                "selector": selector,
            }
        )

    except Exception as e:
        logger.error("Is visible check failed", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Is visible check failed: {e}")


@tool(
    name="element_is_enabled",
    description="Check if an element is enabled.",
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
async def element_is_enabled(
    page_id: str,
    selector: str,
    timeout: int = 5000,
) -> ToolResult:
    """Check if element is enabled."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        enabled = await page.is_enabled(selector, timeout=timeout)

        return ToolResult.ok(
            {
                "enabled": enabled,
                "selector": selector,
            }
        )

    except Exception as e:
        logger.error("Is enabled check failed", page_id=page_id, selector=selector, error=str(e))
        return ToolResult.fail(f"Is enabled check failed: {e}")
