"""
Browser Debug Tools for AI Agents.

Tools for interactive browser debugging that work with the Browser Debug Service.
These tools enable agents to:
- Navigate and interact with web pages
- Capture screenshots and content
- Detect authentication pages
- Get console and network errors
- Create bug/improvement tasks from findings
- Narrate actions to users in real-time

Commands are sent to the Browser Service via Redis pub/sub.
"""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ai_core import CapabilityCategory, get_logger
from ai_messaging import PubSubManager, RedisClient

from .tools import ToolResult, tool

logger = get_logger(__name__)

# Redis channels
BROWSER_TASKS_CHANNEL = "browser:tasks"


def _event_channel(project_id: str) -> str:
    return f"browser:{project_id}:event"


def _narration_channel(project_id: str) -> str:
    return f"browser:{project_id}:narration"


# Global Redis client reference (set by agent)
_redis_client: RedisClient | None = None
_current_project_id: str | None = None
_current_user_id: str | None = None
_current_conversation_id: str | None = None


def configure_browser_tools(
    redis: RedisClient,
    project_id: str,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> None:
    """
    Configure browser tools with Redis client and context.

    Call this before using browser tools to set up the connection
    and project context.
    """
    global _redis_client, _current_project_id, _current_user_id, _current_conversation_id
    _redis_client = redis
    _current_project_id = project_id
    _current_user_id = user_id
    _current_conversation_id = conversation_id


async def _send_command(
    command_type: str,
    narrate: bool = True,
    narration_action: str | None = None,
    narration_detail: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Send command to browser service via Redis."""
    if not _redis_client or not _current_project_id:
        return {"error": "Browser tools not configured. Call configure_browser_tools first."}

    correlation_id = str(uuid4())

    message = {
        "type": command_type,
        "project_id": _current_project_id,
        "user_id": _current_user_id,
        "correlation_id": correlation_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }

    # Send narration if enabled
    if narrate and narration_action:
        await _send_narration(narration_action, narration_detail)

    # Send command
    await _redis_client.publish(BROWSER_TASKS_CHANNEL, json.dumps(message))

    return {"sent": True, "correlation_id": correlation_id}


async def _send_narration(action: str, detail: str | None = None) -> None:
    """Send narration message to chat."""
    if not _redis_client or not _current_project_id:
        return

    message = {
        "type": "browser_narration",
        "action": action,
        "detail": detail,
        "project_id": _current_project_id,
        "user_id": _current_user_id,
        "conversation_id": _current_conversation_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    await _redis_client.publish(_narration_channel(_current_project_id), json.dumps(message))
    await _redis_client.publish("agent:responses", json.dumps(message))


# ============================================================================
# Navigation Tools
# ============================================================================


@tool(
    name="browser_open",
    description="Open browser and navigate to a URL. Narrates the action to the user.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to navigate to",
            },
            "wait_until": {
                "type": "string",
                "enum": ["load", "domcontentloaded", "networkidle"],
                "description": "Wait until this event before returning",
                "default": "load",
            },
            "narrate": {
                "type": "boolean",
                "description": "Whether to narrate the action to the user",
                "default": True,
            },
        },
        "required": ["url"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def browser_open(
    url: str,
    wait_until: str = "load",
    narrate: bool = True,
) -> ToolResult:
    """Open browser and navigate to URL."""
    try:
        result = await _send_command(
            "navigate",
            narrate=narrate,
            narration_action="Navigating",
            narration_detail=f"Going to {url}",
            url=url,
            wait_until=wait_until,
        )

        if result.get("error"):
            return ToolResult.fail(result["error"])

        return ToolResult.ok(
            {"url": url, "correlation_id": result.get("correlation_id")},
            message=f"Navigating to {url}",
        )

    except Exception as e:
        logger.error("browser_open failed", url=url, error=str(e))
        return ToolResult.fail(f"Failed to open URL: {e}")


@tool(
    name="browser_click",
    description="Click an element or coordinates on the page. Narrates the action.",
    parameters={
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": "CSS selector or element description to click",
            },
            "x": {
                "type": "integer",
                "description": "X coordinate to click (alternative to selector)",
            },
            "y": {
                "type": "integer",
                "description": "Y coordinate to click (alternative to selector)",
            },
            "narrate": {
                "type": "boolean",
                "description": "Whether to narrate the action",
                "default": True,
            },
        },
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def browser_click(
    selector: str | None = None,
    x: int | None = None,
    y: int | None = None,
    narrate: bool = True,
) -> ToolResult:
    """Click element or coordinates."""
    try:
        target = selector if selector else f"coordinates ({x}, {y})"

        result = await _send_command(
            "click",
            narrate=narrate,
            narration_action="Clicking",
            narration_detail=f"Clicking {target}",
            selector=selector,
            x=x,
            y=y,
        )

        if result.get("error"):
            return ToolResult.fail(result["error"])

        return ToolResult.ok(
            {"target": target, "correlation_id": result.get("correlation_id")},
            message=f"Clicked {target}",
        )

    except Exception as e:
        logger.error("browser_click failed", error=str(e))
        return ToolResult.fail(f"Failed to click: {e}")


@tool(
    name="browser_type",
    description="Type text into an element. Masks sensitive input in narration.",
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to type",
            },
            "selector": {
                "type": "string",
                "description": "CSS selector of element to type into",
            },
            "mask": {
                "type": "boolean",
                "description": "Hide text in narration (for passwords)",
                "default": False,
            },
            "clear": {
                "type": "boolean",
                "description": "Clear the field before typing",
                "default": False,
            },
            "narrate": {
                "type": "boolean",
                "description": "Whether to narrate the action",
                "default": True,
            },
        },
        "required": ["text"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def browser_type(
    text: str,
    selector: str | None = None,
    mask: bool = False,
    clear: bool = False,
    narrate: bool = True,
) -> ToolResult:
    """Type text into element."""
    try:
        display_text = "••••••••" if mask else f"'{text[:20]}...'" if len(text) > 20 else f"'{text}'"
        target = selector if selector else "focused element"

        result = await _send_command(
            "type",
            narrate=narrate,
            narration_action="Typing",
            narration_detail=f"Entering {display_text} into {target}",
            text=text,
            selector=selector,
            clear=clear,
        )

        if result.get("error"):
            return ToolResult.fail(result["error"])

        return ToolResult.ok(
            {"typed": True, "length": len(text), "masked": mask},
            message=f"Typed into {target}",
        )

    except Exception as e:
        logger.error("browser_type failed", error=str(e))
        return ToolResult.fail(f"Failed to type: {e}")


# ============================================================================
# Content Inspection Tools
# ============================================================================


@tool(
    name="browser_screenshot",
    description="Take a screenshot of the current page.",
    parameters={
        "type": "object",
        "properties": {
            "full_page": {
                "type": "boolean",
                "description": "Capture full scrollable page",
                "default": False,
            },
        },
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def browser_screenshot(
    full_page: bool = False,
) -> ToolResult:
    """Take screenshot and return base64 data."""
    try:
        result = await _send_command(
            "screenshot",
            narrate=False,
            full_page=full_page,
        )

        if result.get("error"):
            return ToolResult.fail(result["error"])

        return ToolResult.ok(
            {"requested": True, "full_page": full_page},
            message="Screenshot requested",
        )

    except Exception as e:
        logger.error("browser_screenshot failed", error=str(e))
        return ToolResult.fail(f"Failed to take screenshot: {e}")


@tool(
    name="browser_get_content",
    description="Get page content (text or HTML).",
    parameters={
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": "CSS selector for specific element (optional)",
            },
            "format": {
                "type": "string",
                "enum": ["text", "html"],
                "description": "Content format to return",
                "default": "text",
            },
        },
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def browser_get_content(
    selector: str | None = None,
    format: str = "text",
) -> ToolResult:
    """Get page or element content."""
    try:
        result = await _send_command(
            "get_content",
            narrate=False,
            selector=selector,
            format=format,
        )

        if result.get("error"):
            return ToolResult.fail(result["error"])

        return ToolResult.ok(
            {"requested": True, "selector": selector, "format": format},
        )

    except Exception as e:
        logger.error("browser_get_content failed", error=str(e))
        return ToolResult.fail(f"Failed to get content: {e}")


@tool(
    name="browser_find_elements",
    description="Find elements matching a selector or description.",
    parameters={
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": "CSS selector or natural language description",
            },
        },
        "required": ["selector"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def browser_find_elements(
    selector: str,
) -> ToolResult:
    """Find elements matching selector."""
    try:
        result = await _send_command(
            "find_elements",
            narrate=False,
            selector=selector,
        )

        if result.get("error"):
            return ToolResult.fail(result["error"])

        return ToolResult.ok(
            {"requested": True, "selector": selector},
        )

    except Exception as e:
        logger.error("browser_find_elements failed", error=str(e))
        return ToolResult.fail(f"Failed to find elements: {e}")


# ============================================================================
# Wait and State Tools
# ============================================================================


@tool(
    name="browser_wait",
    description="Wait for an element or condition.",
    parameters={
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": "CSS selector to wait for",
            },
            "state": {
                "type": "string",
                "enum": ["visible", "hidden", "attached", "detached"],
                "description": "State to wait for",
                "default": "visible",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in milliseconds",
                "default": 30000,
            },
        },
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def browser_wait(
    selector: str | None = None,
    state: str = "visible",
    timeout: int = 30000,
) -> ToolResult:
    """Wait for element or condition."""
    try:
        await _send_narration("Waiting", f"Waiting for {selector or 'page'} to be {state}")

        result = await _send_command(
            "wait",
            narrate=False,
            selector=selector,
            state=state,
            timeout=timeout,
        )

        if result.get("error"):
            return ToolResult.fail(result["error"])

        return ToolResult.ok(
            {"requested": True, "selector": selector, "state": state},
        )

    except Exception as e:
        logger.error("browser_wait failed", error=str(e))
        return ToolResult.fail(f"Failed to wait: {e}")


@tool(
    name="browser_check_auth",
    description="Check if the current page is a login/authentication page.",
    parameters={"type": "object", "properties": {}},
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def browser_check_auth() -> ToolResult:
    """Check if page requires authentication."""
    try:
        result = await _send_command(
            "check_auth",
            narrate=False,
        )

        if result.get("error"):
            return ToolResult.fail(result["error"])

        return ToolResult.ok(
            {"requested": True},
            message="Checking for login page",
        )

    except Exception as e:
        logger.error("browser_check_auth failed", error=str(e))
        return ToolResult.fail(f"Failed to check auth: {e}")


# ============================================================================
# Interactive Prompt Tools
# ============================================================================


@tool(
    name="browser_prompt_user",
    description="Ask the user a question and wait for their response.",
    parameters={
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Question to ask the user",
            },
            "prompt_type": {
                "type": "string",
                "enum": ["confirm", "input", "choice"],
                "description": "Type of prompt",
                "default": "confirm",
            },
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Options for choice prompts",
            },
        },
        "required": ["message"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def browser_prompt_user(
    message: str,
    prompt_type: str = "confirm",
    options: list[str] | None = None,
) -> ToolResult:
    """Ask user a question."""
    try:
        if not _redis_client or not _current_project_id:
            return ToolResult.fail("Browser tools not configured")

        prompt_message = {
            "type": "browser_prompt",
            "prompt_type": prompt_type,
            "message": message,
            "options": options,
            "project_id": _current_project_id,
            "user_id": _current_user_id,
            "conversation_id": _current_conversation_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        await _redis_client.publish("agent:responses", json.dumps(prompt_message))
        await _redis_client.publish(_narration_channel(_current_project_id), json.dumps(prompt_message))

        return ToolResult.ok(
            {"prompted": True, "message": message},
            message="User prompt sent",
        )

    except Exception as e:
        logger.error("browser_prompt_user failed", error=str(e))
        return ToolResult.fail(f"Failed to prompt user: {e}")


@tool(
    name="browser_request_credentials",
    description="Request authentication credentials from the user.",
    parameters={
        "type": "object",
        "properties": {
            "site": {
                "type": "string",
                "description": "Site name or URL needing credentials",
            },
            "use_test_if_available": {
                "type": "boolean",
                "description": "Use test credentials if configured",
                "default": True,
            },
        },
        "required": ["site"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def browser_request_credentials(
    site: str,
    use_test_if_available: bool = True,
) -> ToolResult:
    """Request credentials from user."""
    try:
        await _send_narration(
            "Authentication Required",
            f"Login needed for {site}",
        )

        # Prompt user for auth decision
        options = []
        if use_test_if_available:
            options.append("Use test credentials")
        options.extend(["Enter credentials manually", "Skip this step"])

        return await browser_prompt_user(
            f"I need to log in to {site}. How should I proceed?",
            prompt_type="choice",
            options=options,
        )

    except Exception as e:
        logger.error("browser_request_credentials failed", error=str(e))
        return ToolResult.fail(f"Failed to request credentials: {e}")


# ============================================================================
# Error Debugging Tools
# ============================================================================


@tool(
    name="browser_get_console_errors",
    description="Get JavaScript console errors and warnings from the page.",
    parameters={
        "type": "object",
        "properties": {
            "clear": {
                "type": "boolean",
                "description": "Clear errors after retrieving",
                "default": False,
            },
        },
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def browser_get_console_errors(
    clear: bool = False,
) -> ToolResult:
    """Get console errors."""
    try:
        result = await _send_command(
            "get_console",
            narrate=False,
            errors_only=True,
            clear=clear,
        )

        if result.get("error"):
            return ToolResult.fail(result["error"])

        return ToolResult.ok(
            {"requested": True, "clear": clear},
        )

    except Exception as e:
        logger.error("browser_get_console_errors failed", error=str(e))
        return ToolResult.fail(f"Failed to get console errors: {e}")


@tool(
    name="browser_get_network_errors",
    description="Get failed network requests (4xx, 5xx, timeouts).",
    parameters={
        "type": "object",
        "properties": {
            "url_filter": {
                "type": "string",
                "description": "Filter by URL pattern (optional)",
            },
            "clear": {
                "type": "boolean",
                "description": "Clear errors after retrieving",
                "default": False,
            },
        },
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def browser_get_network_errors(
    url_filter: str | None = None,
    clear: bool = False,
) -> ToolResult:
    """Get network errors."""
    try:
        result = await _send_command(
            "get_network",
            narrate=False,
            errors_only=True,
            url_filter=url_filter,
            clear=clear,
        )

        if result.get("error"):
            return ToolResult.fail(result["error"])

        return ToolResult.ok(
            {"requested": True, "url_filter": url_filter},
        )

    except Exception as e:
        logger.error("browser_get_network_errors failed", error=str(e))
        return ToolResult.fail(f"Failed to get network errors: {e}")


@tool(
    name="browser_get_network_requests",
    description="Get all network requests, optionally filtered.",
    parameters={
        "type": "object",
        "properties": {
            "url_filter": {
                "type": "string",
                "description": "Filter by URL pattern",
            },
            "status_filter": {
                "type": "string",
                "enum": ["error", "success", "all"],
                "description": "Filter by response status",
                "default": "all",
            },
        },
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def browser_get_network_requests(
    url_filter: str | None = None,
    status_filter: str = "all",
) -> ToolResult:
    """Get network requests."""
    try:
        result = await _send_command(
            "get_network",
            narrate=False,
            errors_only=status_filter == "error",
            url_filter=url_filter,
        )

        if result.get("error"):
            return ToolResult.fail(result["error"])

        return ToolResult.ok(
            {"requested": True, "url_filter": url_filter, "status_filter": status_filter},
        )

    except Exception as e:
        logger.error("browser_get_network_requests failed", error=str(e))
        return ToolResult.fail(f"Failed to get network requests: {e}")


@tool(
    name="browser_evaluate",
    description="Execute JavaScript in the page context.",
    parameters={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "JavaScript expression to evaluate",
            },
        },
        "required": ["expression"],
    },
    permission_level=2,
    capability_category=CapabilityCategory.WEB,
)
async def browser_evaluate(
    expression: str,
) -> ToolResult:
    """Execute JavaScript."""
    try:
        result = await _send_command(
            "evaluate",
            narrate=False,
            expression=expression,
        )

        if result.get("error"):
            return ToolResult.fail(result["error"])

        return ToolResult.ok(
            {"requested": True, "expression": expression[:100]},
        )

    except Exception as e:
        logger.error("browser_evaluate failed", error=str(e))
        return ToolResult.fail(f"Failed to evaluate: {e}")


# ============================================================================
# Task Creation Tools
# ============================================================================


@tool(
    name="browser_create_bug_task",
    description="Create a bug task from browser findings with screenshot and error logs.",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Bug title",
            },
            "description": {
                "type": "string",
                "description": "Bug description",
            },
            "severity": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "Bug severity",
                "default": "medium",
            },
            "steps_to_reproduce": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Steps to reproduce the bug",
            },
            "include_screenshot": {
                "type": "boolean",
                "description": "Attach current screenshot",
                "default": True,
            },
            "include_console_errors": {
                "type": "boolean",
                "description": "Attach console errors",
                "default": True,
            },
            "include_network_errors": {
                "type": "boolean",
                "description": "Attach network errors",
                "default": True,
            },
        },
        "required": ["title", "description"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def browser_create_bug_task(
    title: str,
    description: str,
    severity: str = "medium",
    steps_to_reproduce: list[str] | None = None,
    include_screenshot: bool = True,
    include_console_errors: bool = True,
    include_network_errors: bool = True,
) -> ToolResult:
    """Create a bug task from browser findings."""
    try:
        if not _redis_client or not _current_project_id:
            return ToolResult.fail("Browser tools not configured")

        # Create task via API (this would typically go through a task service)
        task_data = {
            "type": "bug_task",
            "title": title,
            "description": description,
            "severity": severity,
            "steps_to_reproduce": steps_to_reproduce or [],
            "include_screenshot": include_screenshot,
            "include_console_errors": include_console_errors,
            "include_network_errors": include_network_errors,
            "project_id": _current_project_id,
            "user_id": _current_user_id,
            "source": "browser_debug",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Publish task creation request
        await _redis_client.publish("tasks:create", json.dumps(task_data))

        await _send_narration(
            "Task Created",
            f"Created bug task: {title}",
        )

        return ToolResult.ok(
            {
                "title": title,
                "severity": severity,
                "created": True,
            },
            message=f"Created bug task: {title}",
        )

    except Exception as e:
        logger.error("browser_create_bug_task failed", error=str(e))
        return ToolResult.fail(f"Failed to create bug task: {e}")


@tool(
    name="browser_create_improvement_task",
    description="Create an improvement task based on browser observations.",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Improvement title",
            },
            "description": {
                "type": "string",
                "description": "Improvement description",
            },
            "category": {
                "type": "string",
                "enum": ["ux", "performance", "accessibility", "security"],
                "description": "Improvement category",
                "default": "ux",
            },
            "current_state": {
                "type": "string",
                "description": "Description of current state",
            },
            "desired_state": {
                "type": "string",
                "description": "Description of desired state",
            },
        },
        "required": ["title", "description"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def browser_create_improvement_task(
    title: str,
    description: str,
    category: str = "ux",
    current_state: str | None = None,
    desired_state: str | None = None,
) -> ToolResult:
    """Create an improvement task."""
    try:
        if not _redis_client or not _current_project_id:
            return ToolResult.fail("Browser tools not configured")

        task_data = {
            "type": "improvement_task",
            "title": title,
            "description": description,
            "category": category,
            "current_state": current_state,
            "desired_state": desired_state,
            "project_id": _current_project_id,
            "user_id": _current_user_id,
            "source": "browser_debug",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        await _redis_client.publish("tasks:create", json.dumps(task_data))

        await _send_narration(
            "Task Created",
            f"Created improvement task: {title}",
        )

        return ToolResult.ok(
            {
                "title": title,
                "category": category,
                "created": True,
            },
            message=f"Created improvement task: {title}",
        )

    except Exception as e:
        logger.error("browser_create_improvement_task failed", error=str(e))
        return ToolResult.fail(f"Failed to create improvement task: {e}")


# Collect all tools for registration
BROWSER_DEBUG_TOOLS = [
    browser_open,
    browser_click,
    browser_type,
    browser_screenshot,
    browser_get_content,
    browser_find_elements,
    browser_wait,
    browser_check_auth,
    browser_prompt_user,
    browser_request_credentials,
    browser_get_console_errors,
    browser_get_network_errors,
    browser_get_network_requests,
    browser_evaluate,
    browser_create_bug_task,
    browser_create_improvement_task,
]
