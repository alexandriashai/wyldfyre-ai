"""
Authentication detection and handling.

Detects login pages and handles credential prompts for browser sessions.
"""

import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any

import structlog
import redis.asyncio as redis

from .config import config
from .session import BrowserSession

logger = structlog.get_logger(__name__)


class AuthDecision(str, Enum):
    """User decision for authentication."""

    USE_TEST_CREDS = "test_creds"
    MANUAL_LOGIN = "manual"
    SKIP = "skip"


@dataclass
class TestCredentials:
    """Test credentials for a site."""

    username: str
    password: str
    extra: dict[str, str] | None = None


class AuthenticationHandler:
    """
    Handles authentication detection and credential management.

    Detects login pages, prompts for auth decisions, and manages
    test credentials for automated testing.
    """

    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client
        self._test_credentials: dict[str, TestCredentials] = {}
        self._pending_auth: dict[str, str] = {}  # project_id -> correlation_id

    async def load_test_credentials(self, project_id: str) -> None:
        """
        Load test credentials for a project from Redis or config.

        Args:
            project_id: Project identifier
        """
        try:
            # Try to load from Redis
            key = f"project:{project_id}:test_credentials"
            data = await self._redis.get(key)

            if data:
                creds_data = json.loads(data)
                for site, cred in creds_data.items():
                    self._test_credentials[f"{project_id}:{site}"] = TestCredentials(
                        username=cred.get("username", ""),
                        password=cred.get("password", ""),
                        extra=cred.get("extra"),
                    )
                logger.info(
                    "Loaded test credentials",
                    project_id=project_id,
                    sites=list(creds_data.keys()),
                )
        except Exception as e:
            logger.warning(
                "Failed to load test credentials",
                project_id=project_id,
                error=str(e),
            )

    async def detect_login_page(self, session: BrowserSession) -> dict[str, Any]:
        """
        Detect if the current page is a login page.

        Args:
            session: Browser session to check

        Returns:
            Detection result with indicators
        """
        return await session.detect_login_page()

    async def detect_2fa_page(self, session: BrowserSession) -> dict[str, Any]:
        """
        Detect if the current page is a 2FA/MFA page.

        Args:
            session: Browser session to check

        Returns:
            Detection result
        """
        if not session.page:
            return {"is_2fa_page": False, "error": "Page not initialized"}

        try:
            indicators = await session.page.evaluate("""
                () => {
                    const pageText = document.body?.innerText?.toLowerCase() || "";
                    const has2faText = pageText.includes("two-factor") ||
                                      pageText.includes("2fa") ||
                                      pageText.includes("verification code") ||
                                      pageText.includes("authenticator") ||
                                      pageText.includes("security code");

                    const hasCodeInput = !!document.querySelector(
                        'input[name*="code"], input[name*="otp"], input[name*="2fa"], ' +
                        'input[autocomplete="one-time-code"], input[inputmode="numeric"]'
                    );

                    return {
                        has2faText,
                        hasCodeInput,
                    };
                }
            """)

            is_2fa = indicators.get("has2faText", False) and indicators.get("hasCodeInput", False)

            return {
                "is_2fa_page": is_2fa,
                "indicators": indicators,
                "url": session.page.url,
            }
        except Exception as e:
            return {"is_2fa_page": False, "error": str(e)}

    def has_test_credentials(self, project_id: str, site: str | None = None) -> bool:
        """
        Check if test credentials exist.

        Args:
            project_id: Project identifier
            site: Optional site identifier

        Returns:
            True if credentials exist
        """
        if site:
            return f"{project_id}:{site}" in self._test_credentials

        # Check for any credentials for this project
        return any(
            key.startswith(f"{project_id}:")
            for key in self._test_credentials
        )

    def get_test_credentials(
        self,
        project_id: str,
        site: str | None = None,
    ) -> TestCredentials | None:
        """
        Get test credentials.

        Args:
            project_id: Project identifier
            site: Optional site identifier

        Returns:
            TestCredentials if found, None otherwise
        """
        if site:
            return self._test_credentials.get(f"{project_id}:{site}")

        # Return first credentials for this project
        for key, creds in self._test_credentials.items():
            if key.startswith(f"{project_id}:"):
                return creds

        return None

    async def fill_login_form(
        self,
        session: BrowserSession,
        credentials: TestCredentials,
    ) -> dict[str, Any]:
        """
        Fill a login form with credentials.

        Args:
            session: Browser session
            credentials: Credentials to use

        Returns:
            Result of form filling
        """
        if not session.page:
            return {"error": "Page not initialized"}

        try:
            # Find and fill username field
            username_selectors = [
                'input[type="email"]',
                'input[type="text"][name*="user"]',
                'input[type="text"][name*="email"]',
                'input[type="text"][id*="user"]',
                'input[type="text"][id*="email"]',
                'input[autocomplete="username"]',
                'input[autocomplete="email"]',
            ]

            for selector in username_selectors:
                element = await session.page.query_selector(selector)
                if element and await element.is_visible():
                    await element.fill(credentials.username)
                    break

            # Find and fill password field
            password_element = await session.page.query_selector('input[type="password"]')
            if password_element and await password_element.is_visible():
                await password_element.fill(credentials.password)

            return {"success": True, "message": "Credentials filled"}

        except Exception as e:
            return {"error": str(e)}

    async def submit_login_form(self, session: BrowserSession) -> dict[str, Any]:
        """
        Submit the login form.

        Args:
            session: Browser session

        Returns:
            Result of submission
        """
        if not session.page:
            return {"error": "Page not initialized"}

        try:
            # Try to find and click submit button
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Sign in")',
                'button:has-text("Log in")',
                'button:has-text("Login")',
                '[data-testid="login-button"]',
                '.login-button',
                '#login-button',
            ]

            for selector in submit_selectors:
                try:
                    element = await session.page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.click()
                        # Wait for navigation
                        await session.page.wait_for_load_state("load", timeout=10000)
                        return {
                            "success": True,
                            "url": session.page.url,
                        }
                except Exception:
                    continue

            # Try pressing Enter as fallback
            await session.page.keyboard.press("Enter")
            await session.page.wait_for_load_state("load", timeout=10000)

            return {
                "success": True,
                "url": session.page.url,
                "method": "enter_key",
            }

        except Exception as e:
            return {"error": str(e)}

    async def request_auth_decision(
        self,
        project_id: str,
        correlation_id: str,
        site: str | None = None,
    ) -> None:
        """
        Request auth decision from user via Redis pub/sub.

        Args:
            project_id: Project identifier
            correlation_id: Correlation ID for response tracking
            site: Optional site identifier
        """
        self._pending_auth[project_id] = correlation_id

        has_test = self.has_test_credentials(project_id, site)

        message = {
            "type": "auth_request",
            "project_id": project_id,
            "correlation_id": correlation_id,
            "site": site,
            "has_test_credentials": has_test,
        }

        await self._redis.publish(
            f"browser:{project_id}:event",
            json.dumps(message),
        )

    async def wait_for_auth_decision(
        self,
        project_id: str,
        timeout: int = 120,
    ) -> AuthDecision | None:
        """
        Wait for auth decision from user.

        Args:
            project_id: Project identifier
            timeout: Timeout in seconds

        Returns:
            AuthDecision or None if timeout
        """
        # This would be handled via the WebSocket connection
        # The user's response comes through the control channel
        # For now, return None (implementation depends on message routing)
        return None

    def clear_pending_auth(self, project_id: str) -> None:
        """Clear pending auth request for project."""
        self._pending_auth.pop(project_id, None)
