"""
Browser helper utilities and Page Object Model base classes.

Provides:
- Page Object Model base class
- Common wyld-core page objects
- Retry and wait helpers
- Utility functions for browser automation
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from ai_core import get_logger
from playwright.async_api import Page, Locator, expect

from .browser_config import BROWSER_DEFAULTS, WYLD_SELECTORS
from .browser_manager import get_browser_manager

logger = get_logger(__name__)

T = TypeVar("T")


# ============================================================================
# Retry Helper
# ============================================================================


class RetryHelper:
    """Helper for retrying operations with exponential backoff."""

    @staticmethod
    async def with_retry(
        operation: Callable[[], Any],
        max_attempts: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        exceptions: tuple = (Exception,),
    ) -> Any:
        """
        Retry an async operation with exponential backoff.

        Args:
            operation: Async callable to execute
            max_attempts: Maximum retry attempts
            delay: Initial delay between retries
            backoff: Multiplier for delay after each retry
            exceptions: Exception types to catch and retry

        Returns:
            Result of successful operation

        Raises:
            Last exception if all retries fail
        """
        last_exception = None
        current_delay = delay

        for attempt in range(1, max_attempts + 1):
            try:
                return await operation()
            except exceptions as e:
                last_exception = e
                if attempt < max_attempts:
                    logger.warning(
                        "Operation failed, retrying",
                        attempt=attempt,
                        max_attempts=max_attempts,
                        delay=current_delay,
                        error=str(e),
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff

        raise last_exception


# ============================================================================
# Wait Strategies
# ============================================================================


class WaitStrategies:
    """Common wait strategies for browser automation."""

    @staticmethod
    async def wait_for_api_response(
        page: Page,
        url_pattern: str,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        Wait for an API response and return its data.

        Args:
            page: Playwright Page
            url_pattern: URL pattern to wait for
            timeout: Timeout in milliseconds

        Returns:
            Response data dict
        """
        response = await page.wait_for_response(url_pattern, timeout=timeout)
        return {
            "url": response.url,
            "status": response.status,
            "ok": response.ok,
            "body": await response.json() if response.ok else None,
        }

    @staticmethod
    async def wait_for_toast(
        page: Page,
        message: str | None = None,
        timeout: int = 5000,
        selector: str = WYLD_SELECTORS.TOAST_MESSAGE,
    ) -> bool:
        """
        Wait for a toast notification to appear.

        Args:
            page: Playwright Page
            message: Expected message text (optional)
            timeout: Timeout in milliseconds
            selector: Toast element selector

        Returns:
            True if toast appeared with expected message
        """
        try:
            locator = page.locator(selector)
            await expect(locator).to_be_visible(timeout=timeout)

            if message:
                await expect(locator).to_contain_text(message, timeout=timeout)

            return True
        except Exception:
            return False

    @staticmethod
    async def wait_for_loading_complete(
        page: Page,
        timeout: int = 30000,
        spinner_selector: str = WYLD_SELECTORS.LOADING_SPINNER,
    ) -> bool:
        """
        Wait for loading spinner to disappear.

        Args:
            page: Playwright Page
            timeout: Timeout in milliseconds
            spinner_selector: Loading spinner selector

        Returns:
            True if loading completed
        """
        try:
            locator = page.locator(spinner_selector)
            await expect(locator).to_be_hidden(timeout=timeout)
            return True
        except Exception:
            return False

    @staticmethod
    async def wait_for_network_idle(
        page: Page,
        timeout: int = 30000,
    ) -> None:
        """Wait for network to be idle."""
        await page.wait_for_load_state("networkidle", timeout=timeout)

    @staticmethod
    async def wait_for_modal(
        page: Page,
        timeout: int = 5000,
        selector: str = WYLD_SELECTORS.MODAL_OVERLAY,
    ) -> bool:
        """
        Wait for a modal dialog to appear.

        Args:
            page: Playwright Page
            timeout: Timeout in milliseconds
            selector: Modal selector

        Returns:
            True if modal appeared
        """
        try:
            await page.wait_for_selector(selector, state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    @staticmethod
    async def wait_for_modal_close(
        page: Page,
        timeout: int = 5000,
        selector: str = WYLD_SELECTORS.MODAL_OVERLAY,
    ) -> bool:
        """
        Wait for a modal dialog to close.

        Args:
            page: Playwright Page
            timeout: Timeout in milliseconds
            selector: Modal selector

        Returns:
            True if modal closed
        """
        try:
            await page.wait_for_selector(selector, state="hidden", timeout=timeout)
            return True
        except Exception:
            return False


# ============================================================================
# Page Object Model Base
# ============================================================================


class PageObjectBase(ABC):
    """
    Base class for Page Object Model pattern.

    Provides a structured way to interact with web pages,
    encapsulating selectors and common operations.
    """

    # Override in subclass
    URL: str = ""
    SELECTORS: dict[str, str] = {}

    def __init__(self, page: Page) -> None:
        """
        Initialize page object.

        Args:
            page: Playwright Page instance
        """
        self._page = page

    @property
    def page(self) -> Page:
        """Get the underlying Playwright page."""
        return self._page

    def locator(self, selector_name: str) -> Locator:
        """
        Get a locator by selector name.

        Args:
            selector_name: Key in SELECTORS dict

        Returns:
            Playwright Locator

        Raises:
            KeyError: If selector not found
        """
        if selector_name not in self.SELECTORS:
            raise KeyError(f"Selector '{selector_name}' not found in {self.__class__.__name__}")
        return self._page.locator(self.SELECTORS[selector_name])

    async def navigate(self, wait_until: str = "load") -> None:
        """Navigate to the page URL."""
        if not self.URL:
            raise ValueError(f"URL not defined for {self.__class__.__name__}")
        await self._page.goto(self.URL, wait_until=wait_until)

    async def fill(self, selector_name: str, value: str) -> None:
        """Fill a form field by selector name."""
        await self.locator(selector_name).fill(value)

    async def click(self, selector_name: str) -> None:
        """Click an element by selector name."""
        await self.locator(selector_name).click()

    async def get_text(self, selector_name: str) -> str:
        """Get text content by selector name."""
        return await self.locator(selector_name).text_content() or ""

    async def is_visible(self, selector_name: str) -> bool:
        """Check if element is visible."""
        return await self.locator(selector_name).is_visible()

    async def wait_for_navigation(self, timeout: int = 30000) -> bool:
        """Wait for navigation to complete."""
        try:
            await self._page.wait_for_load_state("load", timeout=timeout)
            return True
        except Exception:
            return False

    @abstractmethod
    async def is_loaded(self) -> bool:
        """Check if the page is properly loaded."""
        pass


# ============================================================================
# Wyld-Core Page Objects
# ============================================================================


class LoginPage(PageObjectBase):
    """Page object for wyld-core login page."""

    URL = "/login"
    SELECTORS = {
        "email": WYLD_SELECTORS.LOGIN_EMAIL,
        "password": WYLD_SELECTORS.LOGIN_PASSWORD,
        "submit": WYLD_SELECTORS.LOGIN_SUBMIT,
        "error": WYLD_SELECTORS.FORM_ERROR,
    }

    async def is_loaded(self) -> bool:
        """Check if login page is loaded."""
        return await self.is_visible("email") and await self.is_visible("submit")

    async def login(
        self,
        email: str,
        password: str,
        wait_for_redirect: bool = True,
    ) -> bool:
        """
        Perform login.

        Args:
            email: User email
            password: User password
            wait_for_redirect: Wait for successful redirect

        Returns:
            True if login succeeded
        """
        await self.fill("email", email)
        await self.fill("password", password)

        if wait_for_redirect:
            async with self._page.expect_navigation():
                await self.click("submit")
        else:
            await self.click("submit")

        # Check for error
        try:
            error_visible = await self._page.locator(self.SELECTORS["error"]).is_visible(
                timeout=2000
            )
            return not error_visible
        except Exception:
            return True

    async def get_error_message(self) -> str | None:
        """Get login error message if visible."""
        try:
            if await self.is_visible("error"):
                return await self.get_text("error")
        except Exception:
            pass
        return None


class RegistrationPage(PageObjectBase):
    """Page object for wyld-core registration page."""

    URL = "/register"
    SELECTORS = {
        "name": WYLD_SELECTORS.REGISTER_NAME,
        "email": WYLD_SELECTORS.REGISTER_EMAIL,
        "password": WYLD_SELECTORS.REGISTER_PASSWORD,
        "confirm_password": WYLD_SELECTORS.REGISTER_CONFIRM,
        "submit": WYLD_SELECTORS.REGISTER_SUBMIT,
        "error": WYLD_SELECTORS.FORM_ERROR,
    }

    async def is_loaded(self) -> bool:
        """Check if registration page is loaded."""
        return await self.is_visible("email") and await self.is_visible("submit")

    async def register(
        self,
        name: str,
        email: str,
        password: str,
        confirm_password: str | None = None,
    ) -> bool:
        """
        Perform registration.

        Args:
            name: User name
            email: User email
            password: User password
            confirm_password: Password confirmation (uses password if not provided)

        Returns:
            True if registration succeeded
        """
        await self.fill("name", name)
        await self.fill("email", email)
        await self.fill("password", password)
        await self.fill("confirm_password", confirm_password or password)

        async with self._page.expect_navigation():
            await self.click("submit")

        # Check for error
        try:
            error_visible = await self._page.locator(self.SELECTORS["error"]).is_visible(
                timeout=2000
            )
            return not error_visible
        except Exception:
            return True


class ChatPage(PageObjectBase):
    """Page object for wyld-core chat interface."""

    URL = "/chat"
    SELECTORS = {
        "input": WYLD_SELECTORS.CHAT_INPUT,
        "send": WYLD_SELECTORS.SEND_BUTTON,
        "messages": WYLD_SELECTORS.MESSAGE_LIST,
        "message_item": WYLD_SELECTORS.MESSAGE_ITEM,
        "loading": WYLD_SELECTORS.LOADING_SPINNER,
    }

    async def is_loaded(self) -> bool:
        """Check if chat page is loaded."""
        return await self.is_visible("input") and await self.is_visible("send")

    async def send_message(
        self,
        message: str,
        wait_for_response: bool = True,
        timeout: int = 60000,
    ) -> bool:
        """
        Send a chat message.

        Args:
            message: Message to send
            wait_for_response: Wait for AI response
            timeout: Response timeout

        Returns:
            True if message sent (and response received if waiting)
        """
        # Get current message count
        initial_count = await self.get_message_count()

        # Type and send
        await self.fill("input", message)
        await self.click("send")

        if wait_for_response:
            # Wait for at least 2 new messages (user + AI)
            try:
                await self._page.wait_for_function(
                    f"document.querySelectorAll('{self.SELECTORS['message_item']}').length >= {initial_count + 2}",
                    timeout=timeout,
                )
                return True
            except Exception:
                return False

        return True

    async def get_message_count(self) -> int:
        """Get number of messages in chat."""
        return await self.locator("message_item").count()

    async def get_last_message(self) -> str:
        """Get the last message text."""
        messages = self.locator("message_item")
        count = await messages.count()
        if count > 0:
            return await messages.nth(count - 1).text_content() or ""
        return ""

    async def wait_for_loading(self, timeout: int = 60000) -> bool:
        """Wait for loading indicator to disappear."""
        return await WaitStrategies.wait_for_loading_complete(
            self._page,
            timeout=timeout,
            spinner_selector=self.SELECTORS["loading"],
        )


class NavigationHelper:
    """Helper for navigating the wyld-core application."""

    def __init__(self, page: Page) -> None:
        self._page = page

    async def goto_home(self) -> None:
        """Navigate to home page."""
        await self._page.click(WYLD_SELECTORS.NAV_HOME)
        await self._page.wait_for_load_state("load")

    async def goto_projects(self) -> None:
        """Navigate to projects page."""
        await self._page.click(WYLD_SELECTORS.NAV_PROJECTS)
        await self._page.wait_for_load_state("load")

    async def goto_settings(self) -> None:
        """Navigate to settings page."""
        await self._page.click(WYLD_SELECTORS.NAV_SETTINGS)
        await self._page.wait_for_load_state("load")

    async def goto_profile(self) -> None:
        """Navigate to profile page."""
        await self._page.click(WYLD_SELECTORS.NAV_PROFILE)
        await self._page.wait_for_load_state("load")


# ============================================================================
# Utility Functions
# ============================================================================


async def get_page_object(page_id: str, page_class: type[PageObjectBase]) -> PageObjectBase | None:
    """
    Get a page object instance for a managed page.

    Args:
        page_id: Page ID from browser manager
        page_class: Page object class to instantiate

    Returns:
        Page object instance or None if page not found
    """
    manager = get_browser_manager()
    page = manager.get_page(page_id)

    if not page:
        return None

    return page_class(page)


async def take_screenshot_on_failure(
    page: Page,
    test_name: str,
    output_dir: str = "/tmp/qa_screenshots",
) -> str | None:
    """
    Take a screenshot for debugging failures.

    Args:
        page: Playwright Page
        test_name: Test name for filename
        output_dir: Screenshot output directory

    Returns:
        Screenshot path or None if failed
    """
    from pathlib import Path
    from datetime import datetime

    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"failure_{test_name}_{timestamp}.png"
        path = str(output_path / filename)

        await page.screenshot(path=path, full_page=True)
        return path
    except Exception as e:
        logger.warning("Failed to take failure screenshot", error=str(e))
        return None


def create_page_objects_for_page(page: Page) -> dict[str, PageObjectBase]:
    """
    Create all available page objects for a page.

    Args:
        page: Playwright Page

    Returns:
        Dict mapping page names to page objects
    """
    return {
        "login": LoginPage(page),
        "register": RegistrationPage(page),
        "chat": ChatPage(page),
    }
