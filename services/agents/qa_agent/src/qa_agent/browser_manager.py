"""
Browser pool manager for Playwright browser automation.

Provides a singleton manager for efficient browser resource management,
including browser pools, context isolation, and automatic cleanup.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from ai_core import get_logger
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from .browser_config import (
    BROWSER_DEFAULTS,
    RESOURCE_LIMITS,
    BrowserType,
    get_browser_launch_args,
    get_context_options,
)

logger = get_logger(__name__)


@dataclass
class BrowserResource:
    """Tracked browser instance."""

    id: str
    browser: Browser
    browser_type: BrowserType
    created_at: float
    last_used: float
    task_id: str | None = None


@dataclass
class ContextResource:
    """Tracked browser context."""

    id: str
    context: BrowserContext
    browser_id: str
    created_at: float
    last_used: float
    storage_state_path: str | None = None
    task_id: str | None = None


@dataclass
class PageResource:
    """Tracked page instance."""

    id: str
    page: Page
    context_id: str
    created_at: float
    last_used: float
    url: str = ""
    task_id: str | None = None


@dataclass
class BrowserManagerStats:
    """Statistics for browser manager."""

    browsers_active: int = 0
    contexts_active: int = 0
    pages_active: int = 0
    browsers_created_total: int = 0
    contexts_created_total: int = 0
    pages_created_total: int = 0
    cleanups_performed: int = 0
    errors_encountered: int = 0


class BrowserManager:
    """
    Singleton manager for Playwright browser resources.

    Handles browser pool management, context isolation,
    and automatic cleanup of stale resources.
    """

    _instance: "BrowserManager | None" = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls) -> "BrowserManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._playwright: Playwright | None = None
        self._browsers: dict[str, BrowserResource] = {}
        self._contexts: dict[str, ContextResource] = {}
        self._pages: dict[str, PageResource] = {}
        self._stats = BrowserManagerStats()
        self._cleanup_task: asyncio.Task | None = None
        self._shutdown = False
        self._initialized = True

    async def initialize(self) -> None:
        """Initialize Playwright and start cleanup task."""
        async with self._lock:
            if self._playwright is not None:
                return

            logger.info("Initializing BrowserManager")
            self._playwright = await async_playwright().start()
            self._shutdown = False

            # Start background cleanup task
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("BrowserManager initialized")

    async def _cleanup_loop(self) -> None:
        """Background task to cleanup stale resources."""
        while not self._shutdown:
            try:
                await asyncio.sleep(RESOURCE_LIMITS.cleanup_interval)
                if not self._shutdown:
                    await self.cleanup_stale_resources()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Cleanup loop error", error=str(e))
                self._stats.errors_encountered += 1

    async def shutdown(self) -> None:
        """Shutdown manager and cleanup all resources."""
        logger.info("Shutting down BrowserManager")
        self._shutdown = True

        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Close all resources
        await self.close_all()

        # Stop Playwright
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

        logger.info("BrowserManager shutdown complete")

    async def launch_browser(
        self,
        browser_type: str = "chromium",
        task_id: str | None = None,
        **options: Any,
    ) -> str:
        """
        Launch a new browser instance.

        Args:
            browser_type: Type of browser (chromium, firefox, webkit)
            task_id: Optional task ID for resource tracking
            **options: Additional browser launch options

        Returns:
            Browser ID string

        Raises:
            RuntimeError: If manager not initialized or resource limits exceeded
        """
        await self.initialize()

        if len(self._browsers) >= RESOURCE_LIMITS.max_browsers:
            # Try to cleanup before failing
            await self.cleanup_stale_resources()
            if len(self._browsers) >= RESOURCE_LIMITS.max_browsers:
                raise RuntimeError(
                    f"Maximum browsers ({RESOURCE_LIMITS.max_browsers}) reached"
                )

        browser_type_enum = BrowserType(browser_type.lower())
        launch_args = get_browser_launch_args(browser_type_enum)
        launch_args.update(options)

        browser_launcher = getattr(self._playwright, browser_type_enum.value)
        browser = await browser_launcher.launch(**launch_args)

        browser_id = str(uuid4())
        now = time.time()

        self._browsers[browser_id] = BrowserResource(
            id=browser_id,
            browser=browser,
            browser_type=browser_type_enum,
            created_at=now,
            last_used=now,
            task_id=task_id,
        )

        self._stats.browsers_created_total += 1
        self._stats.browsers_active = len(self._browsers)

        logger.info(
            "Browser launched",
            browser_id=browser_id,
            browser_type=browser_type,
            task_id=task_id,
        )

        return browser_id

    async def close_browser(self, browser_id: str) -> bool:
        """
        Close a browser and all its contexts/pages.

        Args:
            browser_id: Browser ID to close

        Returns:
            True if browser was closed, False if not found
        """
        resource = self._browsers.get(browser_id)
        if not resource:
            return False

        # Close all contexts belonging to this browser
        context_ids = [
            ctx_id
            for ctx_id, ctx in self._contexts.items()
            if ctx.browser_id == browser_id
        ]
        for ctx_id in context_ids:
            await self.close_context(ctx_id)

        try:
            await resource.browser.close()
        except Exception as e:
            logger.warning("Error closing browser", browser_id=browser_id, error=str(e))

        del self._browsers[browser_id]
        self._stats.browsers_active = len(self._browsers)

        logger.info("Browser closed", browser_id=browser_id)
        return True

    async def create_context(
        self,
        browser_id: str,
        storage_state: str | dict | None = None,
        task_id: str | None = None,
        **options: Any,
    ) -> str:
        """
        Create a new browser context.

        Args:
            browser_id: Browser ID to create context in
            storage_state: Optional storage state path or dict
            task_id: Optional task ID for resource tracking
            **options: Additional context options

        Returns:
            Context ID string

        Raises:
            ValueError: If browser not found
            RuntimeError: If context limits exceeded
        """
        resource = self._browsers.get(browser_id)
        if not resource:
            raise ValueError(f"Browser not found: {browser_id}")

        # Count contexts for this browser
        browser_contexts = sum(
            1 for ctx in self._contexts.values() if ctx.browser_id == browser_id
        )
        if browser_contexts >= RESOURCE_LIMITS.max_contexts_per_browser:
            raise RuntimeError(
                f"Maximum contexts per browser ({RESOURCE_LIMITS.max_contexts_per_browser}) reached"
            )

        context_options = get_context_options(storage_state=storage_state, **options)
        context = await resource.browser.new_context(**context_options)

        context_id = str(uuid4())
        now = time.time()

        storage_path = storage_state if isinstance(storage_state, str) else None

        self._contexts[context_id] = ContextResource(
            id=context_id,
            context=context,
            browser_id=browser_id,
            created_at=now,
            last_used=now,
            storage_state_path=storage_path,
            task_id=task_id or resource.task_id,
        )

        # Update browser last used
        resource.last_used = now

        self._stats.contexts_created_total += 1
        self._stats.contexts_active = len(self._contexts)

        logger.info(
            "Context created",
            context_id=context_id,
            browser_id=browser_id,
            task_id=task_id,
        )

        return context_id

    async def close_context(self, context_id: str) -> bool:
        """
        Close a context and all its pages.

        Args:
            context_id: Context ID to close

        Returns:
            True if context was closed, False if not found
        """
        resource = self._contexts.get(context_id)
        if not resource:
            return False

        # Close all pages belonging to this context
        page_ids = [
            page_id
            for page_id, page in self._pages.items()
            if page.context_id == context_id
        ]
        for page_id in page_ids:
            await self.close_page(page_id)

        try:
            await resource.context.close()
        except Exception as e:
            logger.warning("Error closing context", context_id=context_id, error=str(e))

        del self._contexts[context_id]
        self._stats.contexts_active = len(self._contexts)

        logger.info("Context closed", context_id=context_id)
        return True

    async def new_page(
        self,
        context_id: str,
        task_id: str | None = None,
    ) -> str:
        """
        Create a new page in a context.

        Args:
            context_id: Context ID to create page in
            task_id: Optional task ID for resource tracking

        Returns:
            Page ID string

        Raises:
            ValueError: If context not found
            RuntimeError: If page limits exceeded
        """
        resource = self._contexts.get(context_id)
        if not resource:
            raise ValueError(f"Context not found: {context_id}")

        # Count pages for this context
        context_pages = sum(
            1 for page in self._pages.values() if page.context_id == context_id
        )
        if context_pages >= RESOURCE_LIMITS.max_pages_per_context:
            raise RuntimeError(
                f"Maximum pages per context ({RESOURCE_LIMITS.max_pages_per_context}) reached"
            )

        page = await resource.context.new_page()

        # Set default timeouts
        page.set_default_timeout(BROWSER_DEFAULTS.default_timeout)
        page.set_default_navigation_timeout(BROWSER_DEFAULTS.navigation_timeout)

        page_id = str(uuid4())
        now = time.time()

        self._pages[page_id] = PageResource(
            id=page_id,
            page=page,
            context_id=context_id,
            created_at=now,
            last_used=now,
            task_id=task_id or resource.task_id,
        )

        # Update context last used
        resource.last_used = now

        self._stats.pages_created_total += 1
        self._stats.pages_active = len(self._pages)

        logger.info(
            "Page created",
            page_id=page_id,
            context_id=context_id,
            task_id=task_id,
        )

        return page_id

    async def close_page(self, page_id: str) -> bool:
        """
        Close a page.

        Args:
            page_id: Page ID to close

        Returns:
            True if page was closed, False if not found
        """
        resource = self._pages.get(page_id)
        if not resource:
            return False

        try:
            await resource.page.close()
        except Exception as e:
            logger.warning("Error closing page", page_id=page_id, error=str(e))

        del self._pages[page_id]
        self._stats.pages_active = len(self._pages)

        logger.info("Page closed", page_id=page_id)
        return True

    def get_page(self, page_id: str) -> Page | None:
        """
        Get a page by ID.

        Args:
            page_id: Page ID to retrieve

        Returns:
            Page instance or None if not found
        """
        resource = self._pages.get(page_id)
        if resource:
            resource.last_used = time.time()
            # Also update context and browser
            if resource.context_id in self._contexts:
                ctx = self._contexts[resource.context_id]
                ctx.last_used = time.time()
                if ctx.browser_id in self._browsers:
                    self._browsers[ctx.browser_id].last_used = time.time()
            return resource.page
        return None

    def get_context(self, context_id: str) -> BrowserContext | None:
        """
        Get a context by ID.

        Args:
            context_id: Context ID to retrieve

        Returns:
            BrowserContext instance or None if not found
        """
        resource = self._contexts.get(context_id)
        if resource:
            resource.last_used = time.time()
            if resource.browser_id in self._browsers:
                self._browsers[resource.browser_id].last_used = time.time()
            return resource.context
        return None

    def get_browser(self, browser_id: str) -> Browser | None:
        """
        Get a browser by ID.

        Args:
            browser_id: Browser ID to retrieve

        Returns:
            Browser instance or None if not found
        """
        resource = self._browsers.get(browser_id)
        if resource:
            resource.last_used = time.time()
            return resource.browser
        return None

    async def cleanup_stale_resources(self) -> int:
        """
        Cleanup resources that have exceeded their idle timeout.

        Returns:
            Number of resources cleaned up
        """
        now = time.time()
        cleaned = 0

        # Cleanup stale pages first
        stale_pages = [
            page_id
            for page_id, page in self._pages.items()
            if (now - page.last_used) > RESOURCE_LIMITS.page_timeout
        ]
        for page_id in stale_pages:
            await self.close_page(page_id)
            cleaned += 1

        # Cleanup stale contexts
        stale_contexts = [
            ctx_id
            for ctx_id, ctx in self._contexts.items()
            if (now - ctx.last_used) > RESOURCE_LIMITS.context_timeout
        ]
        for ctx_id in stale_contexts:
            await self.close_context(ctx_id)
            cleaned += 1

        # Cleanup stale browsers
        stale_browsers = [
            browser_id
            for browser_id, browser in self._browsers.items()
            if (now - browser.last_used) > RESOURCE_LIMITS.browser_timeout
        ]
        for browser_id in stale_browsers:
            await self.close_browser(browser_id)
            cleaned += 1

        if cleaned > 0:
            self._stats.cleanups_performed += 1
            logger.info("Cleaned up stale resources", count=cleaned)

        return cleaned

    async def cleanup_task_resources(self, task_id: str) -> int:
        """
        Cleanup all resources associated with a specific task.

        Args:
            task_id: Task ID to cleanup resources for

        Returns:
            Number of resources cleaned up
        """
        cleaned = 0

        # Close pages for this task
        page_ids = [
            page_id
            for page_id, page in self._pages.items()
            if page.task_id == task_id
        ]
        for page_id in page_ids:
            await self.close_page(page_id)
            cleaned += 1

        # Close contexts for this task
        context_ids = [
            ctx_id
            for ctx_id, ctx in self._contexts.items()
            if ctx.task_id == task_id
        ]
        for ctx_id in context_ids:
            await self.close_context(ctx_id)
            cleaned += 1

        # Close browsers for this task
        browser_ids = [
            browser_id
            for browser_id, browser in self._browsers.items()
            if browser.task_id == task_id
        ]
        for browser_id in browser_ids:
            await self.close_browser(browser_id)
            cleaned += 1

        if cleaned > 0:
            logger.info(
                "Cleaned up task resources",
                task_id=task_id,
                count=cleaned,
            )

        return cleaned

    async def close_all(self) -> int:
        """
        Close all browsers and their resources.

        Returns:
            Number of browsers closed
        """
        browser_ids = list(self._browsers.keys())
        for browser_id in browser_ids:
            await self.close_browser(browser_id)

        return len(browser_ids)

    def list_browsers(self) -> list[dict[str, Any]]:
        """List all active browsers with metadata."""
        now = time.time()
        return [
            {
                "id": resource.id,
                "browser_type": resource.browser_type.value,
                "created_at": resource.created_at,
                "idle_seconds": int(now - resource.last_used),
                "task_id": resource.task_id,
                "context_count": sum(
                    1 for ctx in self._contexts.values() if ctx.browser_id == resource.id
                ),
            }
            for resource in self._browsers.values()
        ]

    def list_contexts(self, browser_id: str | None = None) -> list[dict[str, Any]]:
        """List active contexts, optionally filtered by browser."""
        now = time.time()
        contexts = self._contexts.values()
        if browser_id:
            contexts = [ctx for ctx in contexts if ctx.browser_id == browser_id]

        return [
            {
                "id": resource.id,
                "browser_id": resource.browser_id,
                "created_at": resource.created_at,
                "idle_seconds": int(now - resource.last_used),
                "task_id": resource.task_id,
                "has_storage_state": resource.storage_state_path is not None,
                "page_count": sum(
                    1 for page in self._pages.values() if page.context_id == resource.id
                ),
            }
            for resource in contexts
        ]

    def list_pages(self, context_id: str | None = None) -> list[dict[str, Any]]:
        """List active pages, optionally filtered by context."""
        now = time.time()
        pages = self._pages.values()
        if context_id:
            pages = [page for page in pages if page.context_id == context_id]

        return [
            {
                "id": resource.id,
                "context_id": resource.context_id,
                "url": resource.url,
                "created_at": resource.created_at,
                "idle_seconds": int(now - resource.last_used),
                "task_id": resource.task_id,
            }
            for resource in pages
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get manager statistics."""
        return {
            "browsers_active": self._stats.browsers_active,
            "contexts_active": self._stats.contexts_active,
            "pages_active": self._stats.pages_active,
            "browsers_created_total": self._stats.browsers_created_total,
            "contexts_created_total": self._stats.contexts_created_total,
            "pages_created_total": self._stats.pages_created_total,
            "cleanups_performed": self._stats.cleanups_performed,
            "errors_encountered": self._stats.errors_encountered,
            "limits": {
                "max_browsers": RESOURCE_LIMITS.max_browsers,
                "max_contexts_per_browser": RESOURCE_LIMITS.max_contexts_per_browser,
                "max_pages_per_context": RESOURCE_LIMITS.max_pages_per_context,
            },
        }

    def update_page_url(self, page_id: str, url: str) -> None:
        """Update the tracked URL for a page."""
        if page_id in self._pages:
            self._pages[page_id].url = url


# Global singleton instance
_browser_manager: BrowserManager | None = None


def get_browser_manager() -> BrowserManager:
    """Get the singleton BrowserManager instance."""
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserManager()
    return _browser_manager


async def initialize_browser_manager() -> BrowserManager:
    """Initialize and return the BrowserManager."""
    manager = get_browser_manager()
    await manager.initialize()
    return manager


async def shutdown_browser_manager() -> None:
    """Shutdown the BrowserManager."""
    global _browser_manager
    if _browser_manager:
        await _browser_manager.shutdown()
        _browser_manager = None
