"""
Browser authentication tools for the QA Agent.

Provides tools for:
- Credential management (store, retrieve, rotate)
- Login automation using stored credentials
- Session state management
- OAuth flows
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ai_core import CapabilityCategory, get_logger
from base_agent import ToolResult, tool

from ..browser_config import SESSION_STORAGE_DIR, WYLD_SELECTORS
from ..browser_manager import get_browser_manager
from ..credential_store import (
    CredentialStore,
    SessionManager,
    get_credential_store,
    get_session_manager,
)

logger = get_logger(__name__)


# ============================================================================
# Credential Management Tools
# ============================================================================


@tool(
    name="credential_store",
    description="Store encrypted credentials for a web application.",
    parameters={
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Application name (e.g., 'wyld-web', 'admin-portal')",
            },
            "credential_type": {
                "type": "string",
                "enum": ["basic", "oauth", "api_key", "session"],
                "description": "Type of credential",
                "default": "basic",
            },
            "username": {
                "type": "string",
                "description": "Username or email",
            },
            "password": {
                "type": "string",
                "description": "Password or secret",
            },
            "role": {
                "type": "string",
                "description": "User role (admin, user, guest)",
                "default": "user",
            },
            "metadata": {
                "type": "object",
                "description": "Additional metadata (client_id, tokens, etc.)",
            },
            "rotation_days": {
                "type": "integer",
                "description": "Days before rotation is recommended",
                "default": 30,
            },
        },
        "required": ["app_name", "username", "password"],
    },
    permission_level=2,
    capability_category=CapabilityCategory.WEB,
)
async def credential_store_tool(
    app_name: str,
    username: str,
    password: str,
    credential_type: str = "basic",
    role: str = "user",
    metadata: dict | None = None,
    rotation_days: int = 30,
    context: dict | None = None,
) -> ToolResult:
    """Store encrypted credentials."""
    try:
        # Get user_id from context
        user_id = context.get("user_id") if context else None
        if not user_id:
            return ToolResult.fail("User ID required for credential storage")

        store = get_credential_store()
        credential_id = await store.store_credential(
            app_name=app_name,
            credential_type=credential_type,
            username=username,
            password=password,
            user_id=user_id,
            role=role,
            metadata=metadata,
            rotation_days=rotation_days,
        )

        return ToolResult.ok(
            {
                "credential_id": credential_id,
                "app_name": app_name,
                "role": role,
                "expires_in_days": rotation_days,
            }
        )

    except Exception as e:
        logger.error("Credential store failed", app_name=app_name, error=str(e))
        return ToolResult.fail(f"Credential store failed: {e}")


@tool(
    name="credential_get",
    description="Retrieve a credential for an application (returns masked info, not password).",
    parameters={
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Application name",
            },
            "credential_type": {
                "type": "string",
                "description": "Filter by credential type",
            },
            "role": {
                "type": "string",
                "description": "Filter by role",
            },
        },
        "required": ["app_name"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def credential_get(
    app_name: str,
    credential_type: str | None = None,
    role: str | None = None,
    context: dict | None = None,
) -> ToolResult:
    """Get credential info (not password)."""
    try:
        user_id = context.get("user_id") if context else None
        if not user_id:
            return ToolResult.fail("User ID required")

        store = get_credential_store()
        credential = await store.get_credential(
            app_name=app_name,
            user_id=user_id,
            credential_type=credential_type,
            role=role,
        )

        if not credential:
            return ToolResult.ok(
                {
                    "found": False,
                    "app_name": app_name,
                }
            )

        return ToolResult.ok(
            {
                "found": True,
                "credential_id": credential.id,
                "app_name": credential.app_name,
                "credential_type": credential.credential_type,
                "role": credential.role,
                "username": credential.username,
                "expires_at": credential.expires_at.isoformat() if credential.expires_at else None,
            }
        )

    except Exception as e:
        logger.error("Credential get failed", app_name=app_name, error=str(e))
        return ToolResult.fail(f"Credential get failed: {e}")


@tool(
    name="credential_rotate",
    description="Rotate a credential's password.",
    parameters={
        "type": "object",
        "properties": {
            "credential_id": {
                "type": "string",
                "description": "Credential ID to rotate",
            },
            "new_password": {
                "type": "string",
                "description": "New password",
            },
        },
        "required": ["credential_id", "new_password"],
    },
    permission_level=2,
    capability_category=CapabilityCategory.WEB,
)
async def credential_rotate(
    credential_id: str,
    new_password: str,
    context: dict | None = None,
) -> ToolResult:
    """Rotate credential password."""
    try:
        user_id = context.get("user_id") if context else None
        if not user_id:
            return ToolResult.fail("User ID required")

        store = get_credential_store()
        success = await store.rotate_credential(
            credential_id=credential_id,
            new_password=new_password,
            user_id=user_id,
        )

        if success:
            return ToolResult.ok(
                {
                    "rotated": True,
                    "credential_id": credential_id,
                }
            )
        else:
            return ToolResult.fail("Credential not found or unauthorized")

    except Exception as e:
        logger.error("Credential rotate failed", credential_id=credential_id, error=str(e))
        return ToolResult.fail(f"Credential rotate failed: {e}")


@tool(
    name="credential_list",
    description="List stored credentials (without passwords).",
    parameters={
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Filter by application name",
            },
            "include_expired": {
                "type": "boolean",
                "description": "Include expired credentials",
                "default": False,
            },
        },
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def credential_list(
    app_name: str | None = None,
    include_expired: bool = False,
    context: dict | None = None,
) -> ToolResult:
    """List credentials."""
    try:
        user_id = context.get("user_id") if context else None
        if not user_id:
            return ToolResult.fail("User ID required")

        store = get_credential_store()
        credentials = await store.list_credentials(
            user_id=user_id,
            app_name=app_name,
            include_expired=include_expired,
        )

        return ToolResult.ok(
            {
                "credentials": [
                    {
                        "id": c.id,
                        "app_name": c.app_name,
                        "credential_type": c.credential_type,
                        "role": c.role,
                        "username": c.username,
                        "is_expired": c.is_expired,
                        "days_until_expiry": c.days_until_expiry,
                    }
                    for c in credentials
                ],
                "count": len(credentials),
            }
        )

    except Exception as e:
        logger.error("Credential list failed", error=str(e))
        return ToolResult.fail(f"Credential list failed: {e}")


@tool(
    name="credential_delete",
    description="Delete a stored credential.",
    parameters={
        "type": "object",
        "properties": {
            "credential_id": {
                "type": "string",
                "description": "Credential ID to delete",
            },
        },
        "required": ["credential_id"],
    },
    permission_level=2,
    capability_category=CapabilityCategory.WEB,
)
async def credential_delete(
    credential_id: str,
    context: dict | None = None,
) -> ToolResult:
    """Delete a credential."""
    try:
        user_id = context.get("user_id") if context else None
        if not user_id:
            return ToolResult.fail("User ID required")

        store = get_credential_store()
        success = await store.delete_credential(
            credential_id=credential_id,
            user_id=user_id,
        )

        if success:
            return ToolResult.ok({"deleted": True, "credential_id": credential_id})
        else:
            return ToolResult.fail("Credential not found or unauthorized")

    except Exception as e:
        logger.error("Credential delete failed", credential_id=credential_id, error=str(e))
        return ToolResult.fail(f"Credential delete failed: {e}")


# ============================================================================
# Authentication Flow Tools
# ============================================================================


@tool(
    name="auth_login",
    description="Login to a web app using stored credentials. Fills login form and submits.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "app_name": {
                "type": "string",
                "description": "App name for credential lookup",
            },
            "role": {
                "type": "string",
                "description": "User role to login as",
                "default": "user",
            },
            "login_url": {
                "type": "string",
                "description": "Login page URL (optional, navigates if provided)",
            },
            "selectors": {
                "type": "object",
                "description": "Custom selectors for login form",
                "properties": {
                    "username": {"type": "string"},
                    "password": {"type": "string"},
                    "submit": {"type": "string"},
                },
            },
            "save_session": {
                "type": "boolean",
                "description": "Save session state after login",
                "default": True,
            },
            "wait_for_navigation": {
                "type": "boolean",
                "description": "Wait for navigation after submit",
                "default": True,
            },
        },
        "required": ["page_id", "app_name"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def auth_login(
    page_id: str,
    app_name: str,
    role: str = "user",
    login_url: str | None = None,
    selectors: dict | None = None,
    save_session: bool = True,
    wait_for_navigation: bool = True,
    context: dict | None = None,
) -> ToolResult:
    """Login using stored credentials."""
    try:
        user_id = context.get("user_id") if context else None
        if not user_id:
            return ToolResult.fail("User ID required")

        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        # Get credential
        store = get_credential_store()
        credential = await store.get_credential(
            app_name=app_name,
            user_id=user_id,
            role=role,
        )

        if not credential:
            return ToolResult.fail(f"No credential found for app '{app_name}' role '{role}'")

        # Navigate to login URL if provided
        if login_url:
            await page.goto(login_url, wait_until="load")

        # Use custom selectors or defaults
        sel = selectors or {}
        username_sel = sel.get("username", WYLD_SELECTORS.LOGIN_EMAIL)
        password_sel = sel.get("password", WYLD_SELECTORS.LOGIN_PASSWORD)
        submit_sel = sel.get("submit", WYLD_SELECTORS.LOGIN_SUBMIT)

        # Fill login form
        await page.fill(username_sel, credential.username)
        await page.fill(password_sel, credential.password)

        # Submit
        if wait_for_navigation:
            async with page.expect_navigation():
                await page.click(submit_sel)
        else:
            await page.click(submit_sel)

        # Save session if requested
        session_id = None
        if save_session:
            # Get context for the page
            context_obj = page.context
            session_manager = get_session_manager()
            session_id = await session_manager.save_session(
                context_obj,
                session_name=f"{app_name}_{role}",
                app_name=app_name,
            )

        return ToolResult.ok(
            {
                "logged_in": True,
                "app_name": app_name,
                "role": role,
                "username": credential.username,
                "session_saved": session_id is not None,
                "session_id": session_id,
                "current_url": page.url,
            }
        )

    except Exception as e:
        logger.error("Auth login failed", app_name=app_name, role=role, error=str(e))
        return ToolResult.fail(f"Auth login failed: {e}")


@tool(
    name="auth_logout",
    description="Logout from a web app and clear session.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "logout_url": {
                "type": "string",
                "description": "Logout URL (optional)",
            },
            "logout_selector": {
                "type": "string",
                "description": "Logout button selector (optional)",
            },
            "clear_session": {
                "type": "boolean",
                "description": "Clear saved session state",
                "default": True,
            },
        },
        "required": ["page_id"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def auth_logout(
    page_id: str,
    logout_url: str | None = None,
    logout_selector: str | None = None,
    clear_session: bool = True,
) -> ToolResult:
    """Logout and clear session."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        # Logout via URL or button
        if logout_url:
            await page.goto(logout_url, wait_until="load")
        elif logout_selector:
            await page.click(logout_selector)
        else:
            # Try default logout selector
            try:
                await page.click(WYLD_SELECTORS.LOGOUT_BUTTON, timeout=5000)
            except Exception:
                pass

        # Clear cookies and storage if requested
        if clear_session:
            context = page.context
            await context.clear_cookies()

        return ToolResult.ok(
            {
                "logged_out": True,
                "session_cleared": clear_session,
                "current_url": page.url,
            }
        )

    except Exception as e:
        logger.error("Auth logout failed", error=str(e))
        return ToolResult.fail(f"Auth logout failed: {e}")


# ============================================================================
# Session Management Tools
# ============================================================================


@tool(
    name="auth_save_session",
    description="Save the current browser context state (cookies, localStorage) for later reuse.",
    parameters={
        "type": "object",
        "properties": {
            "context_id": {
                "type": "string",
                "description": "Browser context ID",
            },
            "session_name": {
                "type": "string",
                "description": "Name for this session",
            },
            "app_name": {
                "type": "string",
                "description": "Application this session is for",
            },
        },
        "required": ["context_id", "session_name", "app_name"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def auth_save_session(
    context_id: str,
    session_name: str,
    app_name: str,
) -> ToolResult:
    """Save browser session state."""
    try:
        manager = get_browser_manager()
        context = manager.get_context(context_id)

        if not context:
            return ToolResult.fail(f"Context not found: {context_id}")

        session_manager = get_session_manager()
        session_id = await session_manager.save_session(
            context=context,
            session_name=session_name,
            app_name=app_name,
        )

        return ToolResult.ok(
            {
                "session_id": session_id,
                "session_name": session_name,
                "app_name": app_name,
            }
        )

    except Exception as e:
        logger.error("Save session failed", context_id=context_id, error=str(e))
        return ToolResult.fail(f"Save session failed: {e}")


@tool(
    name="auth_load_session",
    description="Create a new browser context with a saved session state.",
    parameters={
        "type": "object",
        "properties": {
            "browser_id": {
                "type": "string",
                "description": "Browser ID to create context in",
            },
            "session_id": {
                "type": "string",
                "description": "Session ID to load",
            },
        },
        "required": ["browser_id", "session_id"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def auth_load_session(
    browser_id: str,
    session_id: str,
    _task_id: str | None = None,
) -> ToolResult:
    """Load a saved session into a new context."""
    try:
        # Load session state
        session_manager = get_session_manager()
        storage_state = await session_manager.load_session(session_id)

        if not storage_state:
            return ToolResult.fail(f"Session not found or expired: {session_id}")

        # Create context with session state
        manager = get_browser_manager()
        context_id = await manager.create_context(
            browser_id=browser_id,
            storage_state=storage_state,
            task_id=_task_id,
        )

        return ToolResult.ok(
            {
                "context_id": context_id,
                "session_id": session_id,
                "session_loaded": True,
            }
        )

    except Exception as e:
        logger.error("Load session failed", session_id=session_id, error=str(e))
        return ToolResult.fail(f"Load session failed: {e}")


@tool(
    name="auth_list_sessions",
    description="List saved browser sessions.",
    parameters={
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Filter by application name",
            },
        },
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def auth_list_sessions(
    app_name: str | None = None,
) -> ToolResult:
    """List saved sessions."""
    try:
        session_manager = get_session_manager()
        sessions = await session_manager.list_sessions(app_name=app_name)

        return ToolResult.ok(
            {
                "sessions": [
                    {
                        "id": s.id,
                        "session_name": s.session_name,
                        "app_name": s.app_name,
                        "created_at": s.created_at.isoformat(),
                        "expires_at": s.expires_at.isoformat(),
                        "is_valid": s.is_valid,
                    }
                    for s in sessions
                ],
                "count": len(sessions),
            }
        )

    except Exception as e:
        logger.error("List sessions failed", error=str(e))
        return ToolResult.fail(f"List sessions failed: {e}")


@tool(
    name="auth_delete_session",
    description="Delete a saved browser session.",
    parameters={
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Session ID to delete",
            },
        },
        "required": ["session_id"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def auth_delete_session(session_id: str) -> ToolResult:
    """Delete a saved session."""
    try:
        session_manager = get_session_manager()
        deleted = await session_manager.delete_session(session_id)

        if deleted:
            return ToolResult.ok({"deleted": True, "session_id": session_id})
        else:
            return ToolResult.fail(f"Session not found: {session_id}")

    except Exception as e:
        logger.error("Delete session failed", session_id=session_id, error=str(e))
        return ToolResult.fail(f"Delete session failed: {e}")
