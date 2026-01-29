"""
Browser Helper Tools - Tools for managing and applying browser helpers.

These tools allow agents to:
- List available helpers for sites
- Apply helpers when navigating
- Create new helpers from actions
- Learn from successful popup dismissals
"""

import json
from typing import Any

from ai_core import CapabilityCategory, get_logger

from .browser_helpers import (
    BrowserHelpersStore,
    CookieConfig,
    DismissAction,
    SiteHelper,
    create_click_dismiss_helper,
    create_cookie_consent_helper,
    create_gdpr_helper,
    get_helpers_store,
    initialize_common_helpers,
)
from .tools import ToolResult, tool

logger = get_logger(__name__)


@tool(
    name="browser_helper_list",
    description="""List available browser helpers for handling cookies and popups.

Use this to see what automation helpers are available before navigating to a site.
Helpers can automatically dismiss cookie banners, consent popups, and more.""",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Filter to specific domain (optional)",
            },
        },
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def browser_helper_list(domain: str | None = None) -> ToolResult:
    """List available browser helpers."""
    try:
        store = get_helpers_store()
        helpers = store.list_helpers()

        if domain:
            helper = store.get_helper(domain)
            if helper:
                return ToolResult.ok({
                    "domain": domain,
                    "helper": {
                        "name": helper.name,
                        "description": helper.description,
                        "cookies": len(helper.cookies),
                        "actions": len(helper.dismiss_actions),
                        "timing": helper.apply_timing,
                        "use_count": helper.use_count,
                    }
                })
            else:
                return ToolResult.ok({
                    "domain": domain,
                    "helper": None,
                    "message": f"No helper found for {domain}",
                })

        return ToolResult.ok({
            "helpers": [
                {
                    "domain": h.domain,
                    "name": h.name,
                    "description": h.description,
                    "cookies": len(h.cookies),
                    "actions": len(h.dismiss_actions),
                    "use_count": h.use_count,
                }
                for h in helpers
            ],
            "count": len(helpers),
        })

    except Exception as e:
        logger.error("browser_helper_list failed", error=str(e))
        return ToolResult.fail(f"Failed to list helpers: {e}")


@tool(
    name="browser_helper_create",
    description="""Create a new browser helper for a site.

Use this to save automation for sites you visit frequently.
You can create helpers that:
- Set cookies (to bypass consent banners)
- Click elements (to dismiss popups)
- Run JavaScript (for complex dismissals)

Templates available:
- "cookie_consent" - Set a consent cookie
- "click_dismiss" - Click a button to dismiss
- "gdpr" - Handle common GDPR banners""",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Domain this helper applies to (e.g., 'example.com')",
            },
            "template": {
                "type": "string",
                "enum": ["cookie_consent", "click_dismiss", "gdpr", "custom"],
                "description": "Template to use",
                "default": "custom",
            },
            "name": {
                "type": "string",
                "description": "Name for this helper",
            },
            "description": {
                "type": "string",
                "description": "Description of what this helper does",
            },
            # For cookie_consent template
            "cookie_name": {
                "type": "string",
                "description": "Cookie name (for cookie_consent template)",
            },
            "cookie_value": {
                "type": "string",
                "description": "Cookie value (for cookie_consent template)",
            },
            # For click_dismiss template
            "selector": {
                "type": "string",
                "description": "CSS selector to click (for click_dismiss template)",
            },
            # For custom helpers
            "cookies": {
                "type": "array",
                "description": "Array of cookies to set [{name, value, domain?, path?}]",
                "items": {"type": "object"},
            },
            "actions": {
                "type": "array",
                "description": "Array of actions [{type, selector?, js_code?}]",
                "items": {"type": "object"},
            },
            "apply_timing": {
                "type": "string",
                "enum": ["before_load", "after_load", "on_popup"],
                "description": "When to apply the helper",
                "default": "after_load",
            },
        },
        "required": ["domain"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def browser_helper_create(
    domain: str,
    template: str = "custom",
    name: str | None = None,
    description: str | None = None,
    cookie_name: str | None = None,
    cookie_value: str | None = None,
    selector: str | None = None,
    cookies: list[dict] | None = None,
    actions: list[dict] | None = None,
    apply_timing: str = "after_load",
) -> ToolResult:
    """Create a new browser helper."""
    try:
        store = get_helpers_store()

        # Check if helper already exists
        existing = store.get_helper(domain)
        if existing:
            return ToolResult.fail(
                f"Helper already exists for {domain}. Use browser_helper_delete first to replace it."
            )

        # Create from template
        if template == "cookie_consent":
            if not cookie_name:
                cookie_name = "cookieConsent"
            if not cookie_value:
                cookie_value = "accepted"
            helper = create_cookie_consent_helper(
                domain=domain,
                cookie_name=cookie_name,
                cookie_value=cookie_value,
                name=name,
            )

        elif template == "click_dismiss":
            if not selector:
                return ToolResult.fail("selector is required for click_dismiss template")
            helper = create_click_dismiss_helper(
                domain=domain,
                selector=selector,
                name=name,
                description=description,
            )

        elif template == "gdpr":
            helper = create_gdpr_helper(domain)
            if name:
                helper.name = name
            if description:
                helper.description = description

        else:  # custom
            cookie_configs = []
            if cookies:
                for c in cookies:
                    cookie_configs.append(CookieConfig(
                        name=c["name"],
                        value=c["value"],
                        domain=c.get("domain"),
                        path=c.get("path", "/"),
                        secure=c.get("secure", False),
                        http_only=c.get("http_only", False),
                        same_site=c.get("same_site", "Lax"),
                    ))

            dismiss_actions = []
            if actions:
                for a in actions:
                    action = DismissAction(
                        type=a.get("type", "click"),
                        selector=a.get("selector"),
                        js_code=a.get("js_code"),
                        wait_after=a.get("wait_after", 500),
                        description=a.get("description", ""),
                    )
                    dismiss_actions.append(action)

            helper = SiteHelper(
                domain=domain,
                name=name or f"{domain} Helper",
                description=description or "Custom browser helper",
                cookies=cookie_configs,
                dismiss_actions=dismiss_actions,
                apply_timing=apply_timing,
            )

        store.add_helper(helper)

        return ToolResult.ok({
            "created": True,
            "domain": domain,
            "name": helper.name,
            "cookies": len(helper.cookies),
            "actions": len(helper.dismiss_actions),
            "timing": helper.apply_timing,
        })

    except Exception as e:
        logger.error("browser_helper_create failed", error=str(e))
        return ToolResult.fail(f"Failed to create helper: {e}")


@tool(
    name="browser_helper_delete",
    description="Delete a browser helper for a domain.",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Domain to delete helper for",
            },
        },
        "required": ["domain"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def browser_helper_delete(domain: str) -> ToolResult:
    """Delete a browser helper."""
    try:
        store = get_helpers_store()
        if store.remove_helper(domain):
            return ToolResult.ok({
                "deleted": True,
                "domain": domain,
            })
        else:
            return ToolResult.fail(f"No helper found for {domain}")

    except Exception as e:
        logger.error("browser_helper_delete failed", error=str(e))
        return ToolResult.fail(f"Failed to delete helper: {e}")


@tool(
    name="browser_helper_apply",
    description="""Apply a browser helper's cookies to the current page context.

Use this BEFORE navigating to a site to set cookies that bypass consent banners.
This sets cookies in the browser context so they're sent with the navigation request.

Example workflow:
1. browser_helper_apply(domain="example.com") - Set cookies
2. browser_open(url="https://example.com") - Navigate (cookies already set)""",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Domain to apply helper for",
            },
        },
        "required": ["domain"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def browser_helper_apply(domain: str) -> ToolResult:
    """Apply a helper's cookies to the browser context."""
    try:
        from . import browser_debug_tools as bdt

        store = get_helpers_store()
        helper = store.get_helper(domain)

        if not helper:
            return ToolResult.ok({
                "applied": False,
                "domain": domain,
                "message": "No helper found for this domain",
            })

        if not helper.cookies:
            return ToolResult.ok({
                "applied": False,
                "domain": domain,
                "message": "Helper has no cookies to apply",
            })

        # Build JavaScript to set cookies
        cookie_scripts = []
        for cookie in helper.cookies:
            cookie_domain = cookie.domain or domain
            parts = [
                f"{cookie.name}={cookie.value}",
                f"path={cookie.path}",
            ]
            if cookie.secure:
                parts.append("secure")
            if cookie.same_site:
                parts.append(f"samesite={cookie.same_site}")
            if cookie.expires:
                parts.append(f"expires={cookie.expires}")

            cookie_str = "; ".join(parts)
            cookie_scripts.append(f'document.cookie = "{cookie_str}";')

        js_code = "\n".join(cookie_scripts)

        # Execute via browser_evaluate
        result = await bdt._send_command(
            "evaluate",
            narrate=False,
            expression=js_code,
            wait_for_result=True,
            timeout=10.0,
        )

        if result.get("error"):
            return ToolResult.fail(f"Failed to set cookies: {result['error']}")

        # Record usage
        store.record_use(domain)

        return ToolResult.ok({
            "applied": True,
            "domain": domain,
            "helper": helper.name,
            "cookies_set": len(helper.cookies),
            "cookie_names": [c.name for c in helper.cookies],
        })

    except Exception as e:
        logger.error("browser_helper_apply failed", error=str(e))
        return ToolResult.fail(f"Failed to apply helper: {e}")


@tool(
    name="browser_helper_run_actions",
    description="""Run a helper's dismiss actions on the current page.

Use this AFTER the page loads to click dismiss buttons or run scripts
that close popups. The helper's actions are executed in order.

Example workflow:
1. browser_open(url="https://example.com") - Navigate to site
2. browser_helper_run_actions(domain="example.com") - Dismiss popups""",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Domain to run helper actions for",
            },
        },
        "required": ["domain"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def browser_helper_run_actions(domain: str) -> ToolResult:
    """Run a helper's dismiss actions."""
    try:
        import asyncio
        from . import browser_debug_tools as bdt

        logger.info("browser_helper_run_actions called", domain=domain)

        store = get_helpers_store()
        helper = store.get_helper(domain)

        logger.info("Helper lookup result", domain=domain, found=helper is not None,
                   helper_name=helper.name if helper else None,
                   actions_count=len(helper.dismiss_actions) if helper else 0)

        if not helper:
            return ToolResult.ok({
                "executed": False,
                "domain": domain,
                "message": "No helper found for this domain",
            })

        if not helper.dismiss_actions:
            return ToolResult.ok({
                "executed": False,
                "domain": domain,
                "message": "Helper has no dismiss actions",
            })

        results = []
        for action in helper.dismiss_actions:
            try:
                if action.type == "click" and action.selector:
                    logger.info("Executing click action", selector=action.selector, has_js_code=bool(action.js_code))

                    # If action has custom js_code, try that FIRST (most reliable)
                    if action.js_code:
                        logger.info("Using custom JS code from helper")
                        result = await bdt._send_command(
                            "evaluate",
                            narrate=False,
                            expression=action.js_code,
                            wait_for_result=True,
                            timeout=5.0,
                        )
                        if not result.get("error"):
                            results.append({
                                "type": "click",
                                "selector": action.selector,
                                "method": "js_code",
                                "success": True,
                            })
                            continue

                    # Try normal click
                    result = await bdt._send_command(
                        "click",
                        narrate=False,
                        selector=action.selector,
                        wait_for_result=True,
                        timeout=5.0,
                    )
                    logger.info("Click result", selector=action.selector, result=result)

                    # If failed due to visibility, try force click
                    if result.get("error") and ("not visible" in str(result.get("error", "")).lower()
                                                or "timeout" in str(result.get("error", "")).lower()):
                        logger.info("Normal click failed, trying force click", selector=action.selector)
                        result = await bdt._send_command(
                            "click",
                            narrate=False,
                            selector=action.selector,
                            force=True,
                            wait_for_result=True,
                            timeout=5.0,
                        )

                        # If force also failed, try JS click
                        if result.get("error"):
                            logger.info("Force click failed, trying JS click", selector=action.selector)
                            js_code = f"""
                                (() => {{
                                    const el = document.querySelector('{action.selector}');
                                    if (el) {{ el.click(); return {{ success: true }}; }}
                                    return {{ success: false, error: 'Element not found' }};
                                }})()
                            """
                            result = await bdt._send_command(
                                "evaluate",
                                narrate=False,
                                expression=js_code,
                                wait_for_result=True,
                                timeout=5.0,
                            )

                    results.append({
                        "type": "click",
                        "selector": action.selector,
                        "success": not result.get("error"),
                        "error": result.get("error"),
                    })

                elif action.type == "set_cookie" and action.cookie:
                    cookie = action.cookie
                    parts = [f"{cookie.name}={cookie.value}", f"path={cookie.path}"]
                    if cookie.secure:
                        parts.append("secure")
                    cookie_str = "; ".join(parts)
                    js = f'document.cookie = "{cookie_str}";'
                    result = await bdt._send_command(
                        "evaluate",
                        narrate=False,
                        expression=js,
                        wait_for_result=True,
                        timeout=5.0,
                    )
                    results.append({
                        "type": "set_cookie",
                        "cookie": cookie.name,
                        "success": not result.get("error"),
                    })

                elif action.type == "execute_js" and action.js_code:
                    result = await bdt._send_command(
                        "evaluate",
                        narrate=False,
                        expression=action.js_code,
                        wait_for_result=True,
                        timeout=5.0,
                    )
                    results.append({
                        "type": "execute_js",
                        "success": not result.get("error"),
                        "error": result.get("error"),
                    })

                # Wait after action
                if action.wait_after > 0:
                    await asyncio.sleep(action.wait_after / 1000)

            except Exception as e:
                results.append({
                    "type": action.type,
                    "success": False,
                    "error": str(e),
                })

        # Record usage
        store.record_use(domain)

        successful = sum(1 for r in results if r.get("success"))
        return ToolResult.ok({
            "executed": True,
            "domain": domain,
            "helper": helper.name,
            "total_actions": len(results),
            "successful": successful,
            "results": results,
        })

    except Exception as e:
        logger.error("browser_helper_run_actions failed", error=str(e))
        return ToolResult.fail(f"Failed to run actions: {e}")


@tool(
    name="browser_helper_learn",
    description="""Learn a new helper from an action you just performed.

After you successfully dismiss a popup by clicking a button,
use this to save that action as a reusable helper.

Example:
1. browser_click(selector="#accept-cookies") - Dismiss banner
2. browser_helper_learn(domain="example.com", action_type="click", selector="#accept-cookies")
   - Save it for next time""",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Domain this helper applies to",
            },
            "action_type": {
                "type": "string",
                "enum": ["click", "set_cookie"],
                "description": "Type of action that worked",
            },
            "selector": {
                "type": "string",
                "description": "CSS selector that was clicked (for click actions)",
            },
            "cookie_name": {
                "type": "string",
                "description": "Cookie name (for set_cookie actions)",
            },
            "cookie_value": {
                "type": "string",
                "description": "Cookie value (for set_cookie actions)",
            },
            "name": {
                "type": "string",
                "description": "Name for this helper",
            },
            "description": {
                "type": "string",
                "description": "What this helper does",
            },
        },
        "required": ["domain", "action_type"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def browser_helper_learn(
    domain: str,
    action_type: str,
    selector: str | None = None,
    cookie_name: str | None = None,
    cookie_value: str | None = None,
    name: str | None = None,
    description: str | None = None,
) -> ToolResult:
    """Learn a new helper from a successful action."""
    try:
        store = get_helpers_store()

        # Check if we're updating an existing helper
        existing = store.get_helper(domain)
        if existing:
            # Add the new action to existing helper
            if action_type == "click" and selector:
                new_action = DismissAction(
                    type="click",
                    selector=selector,
                    description=description or f"Click {selector}",
                )
                existing.dismiss_actions.append(new_action)
                if selector not in existing.popup_selectors:
                    existing.popup_selectors.append(selector)

            elif action_type == "set_cookie" and cookie_name:
                new_cookie = CookieConfig(
                    name=cookie_name,
                    value=cookie_value or "accepted",
                )
                existing.cookies.append(new_cookie)

            store.add_helper(existing)  # This saves

            return ToolResult.ok({
                "learned": True,
                "updated_existing": True,
                "domain": domain,
                "helper": existing.name,
                "total_actions": len(existing.dismiss_actions),
                "total_cookies": len(existing.cookies),
            })

        # Create new helper
        if action_type == "click":
            if not selector:
                return ToolResult.fail("selector is required for click action")
            helper = create_click_dismiss_helper(
                domain=domain,
                selector=selector,
                name=name,
                description=description,
            )

        elif action_type == "set_cookie":
            if not cookie_name:
                return ToolResult.fail("cookie_name is required for set_cookie action")
            helper = create_cookie_consent_helper(
                domain=domain,
                cookie_name=cookie_name,
                cookie_value=cookie_value or "accepted",
                name=name,
            )

        else:
            return ToolResult.fail(f"Unknown action type: {action_type}")

        store.add_helper(helper)

        return ToolResult.ok({
            "learned": True,
            "updated_existing": False,
            "domain": domain,
            "helper": helper.name,
            "action_type": action_type,
        })

    except Exception as e:
        logger.error("browser_helper_learn failed", error=str(e))
        return ToolResult.fail(f"Failed to learn helper: {e}")


@tool(
    name="browser_helper_init_common",
    description="""Initialize common browser helpers for popular sites.

This adds pre-configured helpers for sites like Google, YouTube, and
common consent management platforms (CookieBot, etc.).""",
    parameters={"type": "object", "properties": {}},
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def browser_helper_init_common() -> ToolResult:
    """Initialize common browser helpers."""
    try:
        initialize_common_helpers()
        store = get_helpers_store()
        helpers = store.list_helpers()

        return ToolResult.ok({
            "initialized": True,
            "helpers": [
                {"domain": h.domain, "name": h.name}
                for h in helpers
            ],
            "count": len(helpers),
        })

    except Exception as e:
        logger.error("browser_helper_init_common failed", error=str(e))
        return ToolResult.fail(f"Failed to initialize helpers: {e}")


# Export all tools
BROWSER_HELPER_TOOLS = [
    browser_helper_list,
    browser_helper_create,
    browser_helper_delete,
    browser_helper_apply,
    browser_helper_run_actions,
    browser_helper_learn,
    browser_helper_init_common,
]
