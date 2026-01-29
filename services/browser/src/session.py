"""
Browser session wrapper.

Manages a single browser session for a project, including page interactions,
event capturing, and screenshot streaming.
"""

import asyncio
import base64
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from uuid import uuid4

from PIL import Image
from playwright.async_api import (
    Browser,
    BrowserContext,
    ConsoleMessage,
    Page,
    Playwright,
    Request,
    Response,
    async_playwright,
)

from .config import config


@dataclass
class ConsoleEntry:
    """Captured console message."""

    level: str  # log, warn, error, info, debug
    message: str
    timestamp: str
    source: str = ""
    line: int = 0


@dataclass
class NetworkEntry:
    """Captured network request."""

    url: str
    method: str
    status: int | None = None
    status_text: str = ""
    response_time: float | None = None
    error: str | None = None
    resource_type: str = ""
    timestamp: str = ""


@dataclass
class BrowserSession:
    """
    Browser session for a project.

    Manages a single Playwright browser instance with context and page,
    capturing events and providing screenshot streaming.
    """

    id: str
    project_id: str
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)

    _playwright: Playwright | None = field(default=None, repr=False)
    _browser: Browser | None = field(default=None, repr=False)
    _context: BrowserContext | None = field(default=None, repr=False)
    _page: Page | None = field(default=None, repr=False)

    # Event capture
    _console_messages: list[ConsoleEntry] = field(default_factory=list, repr=False)
    _network_requests: dict[str, NetworkEntry] = field(default_factory=dict, repr=False)
    _failed_requests: list[NetworkEntry] = field(default_factory=list, repr=False)

    # State
    _is_streaming: bool = field(default=False, repr=False)
    _stream_task: asyncio.Task | None = field(default=None, repr=False)
    _current_url: str = field(default="", repr=False)
    _page_title: str = field(default="", repr=False)

    # Event callback for real-time publishing
    _event_callback: Any = field(default=None, repr=False)

    @classmethod
    async def create(cls, project_id: str) -> "BrowserSession":
        """Create and initialize a new browser session."""
        session = cls(
            id=str(uuid4()),
            project_id=project_id,
        )
        await session._initialize()
        return session

    async def _initialize(self) -> None:
        """Initialize Playwright browser and context."""
        self._playwright = await async_playwright().start()

        # Launch browser
        self._browser = await self._playwright.chromium.launch(
            headless=config.headless,
            args=[
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )

        # Create context with viewport
        self._context = await self._browser.new_context(
            viewport={
                "width": config.viewport_width,
                "height": config.viewport_height,
            },
            ignore_https_errors=True,
            locale="en-US",
        )

        # Create initial page
        self._page = await self._context.new_page()

        # Set timeouts
        self._page.set_default_timeout(config.default_timeout)
        self._page.set_default_navigation_timeout(config.navigation_timeout)

        # Attach event listeners
        self._page.on("console", self._on_console)
        self._page.on("request", self._on_request)
        self._page.on("response", self._on_response)
        self._page.on("requestfailed", self._on_request_failed)
        self._page.on("load", self._on_load)

    async def close(self) -> None:
        """Close the browser session."""
        await self.stop_streaming()

        if self._page:
            await self._page.close()
            self._page = None

        if self._context:
            await self._context.close()
            self._context = None

        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    @property
    def page(self) -> Page | None:
        """Get the current page."""
        return self._page

    @property
    def current_url(self) -> str:
        """Get current page URL."""
        return self._current_url or (self._page.url if self._page else "")

    @property
    def page_title(self) -> str:
        """Get current page title."""
        return self._page_title

    def touch(self) -> None:
        """Update last used timestamp."""
        self.last_used = time.time()

    # Navigation
    async def navigate(self, url: str, wait_until: str = "load") -> dict[str, Any]:
        """Navigate to URL."""
        if not self._page:
            return {"error": "Page not initialized"}

        self.touch()

        try:
            response = await self._page.goto(url, wait_until=wait_until)
            self._current_url = self._page.url
            self._page_title = await self._page.title()

            return {
                "success": True,
                "url": self._current_url,
                "title": self._page_title,
                "status": response.status if response else None,
            }
        except Exception as e:
            return {"error": str(e), "url": url}

    async def go_back(self) -> dict[str, Any]:
        """Navigate back in history."""
        if not self._page:
            return {"error": "Page not initialized"}

        self.touch()

        try:
            await self._page.go_back()
            self._current_url = self._page.url
            self._page_title = await self._page.title()
            return {"success": True, "url": self._current_url}
        except Exception as e:
            return {"error": str(e)}

    async def go_forward(self) -> dict[str, Any]:
        """Navigate forward in history."""
        if not self._page:
            return {"error": "Page not initialized"}

        self.touch()

        try:
            await self._page.go_forward()
            self._current_url = self._page.url
            self._page_title = await self._page.title()
            return {"success": True, "url": self._current_url}
        except Exception as e:
            return {"error": str(e)}

    async def reload(self) -> dict[str, Any]:
        """Reload current page."""
        if not self._page:
            return {"error": "Page not initialized"}

        self.touch()

        try:
            await self._page.reload()
            self._current_url = self._page.url
            self._page_title = await self._page.title()
            return {"success": True, "url": self._current_url}
        except Exception as e:
            return {"error": str(e)}

    # Interactions
    async def click(
        self,
        selector: str | None = None,
        x: int | None = None,
        y: int | None = None,
        button: str = "left",
        click_count: int = 1,
    ) -> dict[str, Any]:
        """Click on element or coordinates."""
        if not self._page:
            return {"error": "Page not initialized"}

        self.touch()

        try:
            if selector:
                await self._page.click(
                    selector,
                    button=button,
                    click_count=click_count,
                )
                return {"success": True, "selector": selector}
            elif x is not None and y is not None:
                await self._page.mouse.click(x, y, button=button, click_count=click_count)
                return {"success": True, "coordinates": {"x": x, "y": y}}
            else:
                return {"error": "Must provide selector or coordinates"}
        except Exception as e:
            return {"error": str(e)}

    async def type_text(
        self,
        text: str,
        selector: str | None = None,
        delay: int = 50,
        clear_first: bool = False,
    ) -> dict[str, Any]:
        """Type text into element or current focus."""
        if not self._page:
            return {"error": "Page not initialized"}

        self.touch()

        try:
            if selector:
                if clear_first:
                    await self._page.fill(selector, "")
                await self._page.type(selector, text, delay=delay)
                return {"success": True, "selector": selector, "length": len(text)}
            else:
                await self._page.keyboard.type(text, delay=delay)
                return {"success": True, "length": len(text)}
        except Exception as e:
            return {"error": str(e)}

    async def fill(self, selector: str, value: str) -> dict[str, Any]:
        """Fill input with value (clears first)."""
        if not self._page:
            return {"error": "Page not initialized"}

        self.touch()

        try:
            await self._page.fill(selector, value)
            return {"success": True, "selector": selector}
        except Exception as e:
            return {"error": str(e)}

    async def press(self, key: str) -> dict[str, Any]:
        """Press keyboard key."""
        if not self._page:
            return {"error": "Page not initialized"}

        self.touch()

        try:
            await self._page.keyboard.press(key)
            return {"success": True, "key": key}
        except Exception as e:
            return {"error": str(e)}

    async def scroll(
        self,
        delta_x: int = 0,
        delta_y: int = 0,
        x: int | None = None,
        y: int | None = None,
    ) -> dict[str, Any]:
        """Scroll page."""
        if not self._page:
            return {"error": "Page not initialized"}

        self.touch()

        try:
            # Move to position if specified
            if x is not None and y is not None:
                await self._page.mouse.move(x, y)

            await self._page.mouse.wheel(delta_x, delta_y)
            return {"success": True, "deltaX": delta_x, "deltaY": delta_y}
        except Exception as e:
            return {"error": str(e)}

    async def hover(self, selector: str) -> dict[str, Any]:
        """Hover over element."""
        if not self._page:
            return {"error": "Page not initialized"}

        self.touch()

        try:
            await self._page.hover(selector)
            return {"success": True, "selector": selector}
        except Exception as e:
            return {"error": str(e)}

    async def select_option(self, selector: str, value: str | list[str]) -> dict[str, Any]:
        """Select option in dropdown."""
        if not self._page:
            return {"error": "Page not initialized"}

        self.touch()

        try:
            values = [value] if isinstance(value, str) else value
            await self._page.select_option(selector, values)
            return {"success": True, "selector": selector, "values": values}
        except Exception as e:
            return {"error": str(e)}

    async def wait_for_selector(
        self,
        selector: str,
        state: str = "visible",
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Wait for element."""
        if not self._page:
            return {"error": "Page not initialized"}

        self.touch()

        try:
            await self._page.wait_for_selector(
                selector,
                state=state,
                timeout=timeout or config.default_timeout,
            )
            return {"success": True, "selector": selector, "state": state}
        except Exception as e:
            return {"error": str(e), "selector": selector}

    async def wait_for_navigation(self, wait_until: str = "load") -> dict[str, Any]:
        """Wait for navigation to complete."""
        if not self._page:
            return {"error": "Page not initialized"}

        self.touch()

        try:
            await self._page.wait_for_load_state(wait_until)
            self._current_url = self._page.url
            self._page_title = await self._page.title()
            return {"success": True, "url": self._current_url}
        except Exception as e:
            return {"error": str(e)}

    # Content inspection
    async def get_content(
        self,
        selector: str | None = None,
        format: str = "text",
    ) -> dict[str, Any]:
        """Get page or element content."""
        if not self._page:
            return {"error": "Page not initialized"}

        self.touch()

        try:
            if selector:
                element = await self._page.query_selector(selector)
                if not element:
                    return {"error": f"Element not found: {selector}"}

                if format == "html":
                    content = await element.inner_html()
                else:
                    content = await element.inner_text()
            else:
                if format == "html":
                    content = await self._page.content()
                else:
                    content = await self._page.inner_text("body")

            return {"success": True, "content": content, "format": format}
        except Exception as e:
            return {"error": str(e)}

    async def find_elements(self, selector: str) -> dict[str, Any]:
        """Find elements matching selector."""
        if not self._page:
            return {"error": "Page not initialized"}

        self.touch()

        try:
            elements = await self._page.query_selector_all(selector)
            results = []

            for i, el in enumerate(elements[:20]):  # Limit to 20 results
                text = await el.inner_text()
                tag = await el.evaluate("e => e.tagName.toLowerCase()")
                bbox = await el.bounding_box()

                results.append({
                    "index": i,
                    "tag": tag,
                    "text": text[:200] if text else "",
                    "visible": bbox is not None,
                    "box": bbox,
                })

            return {"success": True, "count": len(elements), "elements": results}
        except Exception as e:
            return {"error": str(e)}

    async def evaluate(self, expression: str) -> dict[str, Any]:
        """Execute JavaScript."""
        if not self._page:
            return {"error": "Page not initialized"}

        self.touch()

        try:
            result = await self._page.evaluate(expression)
            return {"success": True, "result": result}
        except Exception as e:
            return {"error": str(e)}

    # Screenshots
    async def screenshot(
        self,
        full_page: bool = False,
        quality: int | None = None,
        format: str = "jpeg",
    ) -> dict[str, Any]:
        """Take screenshot."""
        if not self._page:
            return {"error": "Page not initialized"}

        self.touch()

        try:
            screenshot_bytes = await self._page.screenshot(
                full_page=full_page,
                type=format,
                quality=quality or config.jpeg_quality if format == "jpeg" else None,
            )

            encoded = base64.b64encode(screenshot_bytes).decode("utf-8")
            return {
                "success": True,
                "data": encoded,
                "format": format,
                "full_page": full_page,
            }
        except Exception as e:
            return {"error": str(e)}

    async def capture_frame(self) -> bytes | None:
        """Capture a single frame for streaming (fast, JPEG)."""
        if not self._page:
            return None

        try:
            return await self._page.screenshot(
                type="jpeg",
                quality=config.jpeg_quality,
            )
        except Exception:
            return None

    def set_event_callback(self, callback: Any) -> None:
        """Set callback for real-time event publishing."""
        self._event_callback = callback

    async def _publish_event(self, event_type: str, data: dict) -> None:
        """Publish event through callback if set."""
        if self._event_callback:
            try:
                await self._event_callback(event_type, data)
            except Exception:
                pass  # Don't let callback errors affect session

    # Console and network capture
    def _on_console(self, message: ConsoleMessage) -> None:
        """Handle console message."""
        entry = ConsoleEntry(
            level=message.type,
            message=message.text,
            timestamp=datetime.now(timezone.utc).isoformat(),
            source=message.location.get("url", "") if message.location else "",
            line=message.location.get("lineNumber", 0) if message.location else 0,
        )
        self._console_messages.append(entry)

        # Keep only last 100 messages
        if len(self._console_messages) > 100:
            self._console_messages = self._console_messages[-100:]

        # Publish event in real-time (fire and forget)
        if self._event_callback:
            asyncio.create_task(self._publish_event("console", {
                "level": entry.level,
                "message": entry.message,
                "timestamp": entry.timestamp,
                "source": entry.source,
                "line": entry.line,
            }))

    def _on_request(self, request: Request) -> None:
        """Handle network request start."""
        self._network_requests[request.url] = NetworkEntry(
            url=request.url,
            method=request.method,
            resource_type=request.resource_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _on_response(self, response: Response) -> None:
        """Handle network response."""
        if response.url in self._network_requests:
            entry = self._network_requests[response.url]
            entry.status = response.status
            entry.status_text = response.status_text

            # Publish network event
            if self._event_callback:
                asyncio.create_task(self._publish_event("network", {
                    "url": entry.url,
                    "method": entry.method,
                    "status": entry.status,
                    "status_text": entry.status_text,
                    "resource_type": entry.resource_type,
                    "timestamp": entry.timestamp,
                }))

    def _on_request_failed(self, request: Request) -> None:
        """Handle failed network request."""
        entry = NetworkEntry(
            url=request.url,
            method=request.method,
            resource_type=request.resource_type,
            error=request.failure or "Request failed",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._failed_requests.append(entry)

        # Keep only last 50 failed requests
        if len(self._failed_requests) > 50:
            self._failed_requests = self._failed_requests[-50:]

        # Publish failed request event
        if self._event_callback:
            asyncio.create_task(self._publish_event("network_error", {
                "url": entry.url,
                "method": entry.method,
                "error": entry.error,
                "timestamp": entry.timestamp,
            }))

    def _on_load(self, page: Page) -> None:
        """Handle page load."""
        self._current_url = page.url

    def get_console_errors(self) -> list[dict[str, Any]]:
        """Get console errors and warnings."""
        return [
            {
                "level": e.level,
                "message": e.message,
                "timestamp": e.timestamp,
                "source": e.source,
                "line": e.line,
            }
            for e in self._console_messages
            if e.level in ("error", "warning")
        ]

    def get_network_errors(self) -> list[dict[str, Any]]:
        """Get failed network requests."""
        failed = [
            {
                "url": e.url,
                "method": e.method,
                "error": e.error,
                "timestamp": e.timestamp,
            }
            for e in self._failed_requests
        ]

        # Also include 4xx/5xx responses
        for entry in self._network_requests.values():
            if entry.status and entry.status >= 400:
                failed.append({
                    "url": entry.url,
                    "method": entry.method,
                    "status": entry.status,
                    "status_text": entry.status_text,
                    "timestamp": entry.timestamp,
                })

        return failed

    def get_network_requests(
        self,
        url_filter: str | None = None,
        status_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get network requests with optional filtering."""
        requests = []

        for entry in self._network_requests.values():
            if url_filter and url_filter not in entry.url:
                continue

            if status_filter == "error" and (not entry.status or entry.status < 400):
                continue

            if status_filter == "success" and (not entry.status or entry.status >= 400):
                continue

            requests.append({
                "url": entry.url,
                "method": entry.method,
                "status": entry.status,
                "status_text": entry.status_text,
                "resource_type": entry.resource_type,
                "timestamp": entry.timestamp,
            })

        return requests

    def clear_console(self) -> None:
        """Clear captured console messages."""
        self._console_messages = []

    def clear_network(self) -> None:
        """Clear captured network data."""
        self._network_requests = {}
        self._failed_requests = []

    # Streaming control
    async def start_streaming(self, callback: Any) -> None:
        """Start screenshot streaming."""
        if self._is_streaming:
            return

        self._is_streaming = True
        self._stream_task = asyncio.create_task(self._stream_loop(callback))

    async def stop_streaming(self) -> None:
        """Stop screenshot streaming."""
        self._is_streaming = False
        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
            self._stream_task = None

    async def _stream_loop(self, callback: Any) -> None:
        """Streaming loop that captures and publishes frames."""
        interval = 1.0 / config.stream_fps

        while self._is_streaming:
            try:
                frame = await self.capture_frame()
                if frame:
                    await callback(frame)
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception:
                # Continue streaming even on errors
                await asyncio.sleep(interval)

    # Viewport management
    async def set_viewport(
        self,
        width: int,
        height: int,
        device_scale_factor: float = 1,
        is_mobile: bool = False,
        has_touch: bool = False,
    ) -> dict[str, Any]:
        """Set browser viewport size with optional mobile emulation.

        Args:
            width: Viewport width in pixels
            height: Viewport height in pixels
            device_scale_factor: Device pixel ratio (default 1)
            is_mobile: Whether to emulate mobile device
            has_touch: Whether to emulate touch events

        Note: For full mobile emulation (user agent, touch, etc.),
        this recreates the browser context.
        """
        if not self._browser:
            return {"error": "Browser not initialized"}

        try:
            current_url = self._page.url if self._page else None

            # Close existing context and page
            if self._page:
                await self._page.close()
                self._page = None
            if self._context:
                await self._context.close()
                self._context = None

            # Create new context with full viewport/mobile settings
            context_options = {
                "viewport": {"width": width, "height": height},
                "device_scale_factor": device_scale_factor,
                "is_mobile": is_mobile,
                "has_touch": has_touch,
                "ignore_https_errors": True,
                "locale": "en-US",
            }

            # Add mobile user agent if mobile emulation
            if is_mobile:
                context_options["user_agent"] = (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
                )

            self._context = await self._browser.new_context(**context_options)

            # Create new page
            self._page = await self._context.new_page()

            # Set timeouts
            self._page.set_default_timeout(config.default_timeout)
            self._page.set_default_navigation_timeout(config.navigation_timeout)

            # Reattach event listeners
            self._page.on("console", self._on_console)
            self._page.on("request", self._on_request)
            self._page.on("response", self._on_response)
            self._page.on("requestfailed", self._on_request_failed)
            self._page.on("load", self._on_load)

            # Navigate back to previous URL if there was one
            if current_url and current_url != "about:blank":
                await self._page.goto(current_url, wait_until="load")
                self._current_url = self._page.url
                self._page_title = await self._page.title()

            return {
                "success": True,
                "viewport": {
                    "width": width,
                    "height": height,
                    "device_scale_factor": device_scale_factor,
                    "is_mobile": is_mobile,
                    "has_touch": has_touch,
                },
                "url": self._current_url,
            }
        except Exception as e:
            return {"error": str(e)}

    # Permission management
    async def set_permissions(self, permissions: list[str], origin: str | None = None) -> dict[str, Any]:
        """Grant browser permissions.

        Args:
            permissions: List of permission names (e.g., "geolocation", "camera", "microphone")
            origin: Origin to grant permissions for (default: all origins)

        Available permissions:
            - geolocation
            - midi
            - notifications
            - camera
            - microphone
            - clipboard-read
            - clipboard-write
            - payment-handler
        """
        if not self._context:
            return {"error": "Context not initialized"}

        try:
            # Grant permissions - if origin is provided and valid, use it; otherwise grant for all origins
            if origin and origin != "*":
                await self._context.grant_permissions(permissions, origin=origin)
            else:
                await self._context.grant_permissions(permissions)
            return {
                "success": True,
                "permissions": permissions,
                "origin": origin or "all",
            }
        except Exception as e:
            return {"error": str(e), "permissions": permissions}

    # Auth detection
    async def detect_login_page(self) -> dict[str, Any]:
        """Detect if current page is a login page."""
        if not self._page:
            return {"is_login_page": False, "error": "Page not initialized"}

        self.touch()

        try:
            # Check for common login indicators
            indicators = await self._page.evaluate("""
                () => {
                    const hasPasswordField = !!document.querySelector('input[type="password"]');
                    const hasLoginButton = !!document.querySelector(
                        'button[type="submit"], input[type="submit"], [data-testid*="login"], .login-btn, #login-button'
                    );
                    const hasLoginForm = !!document.querySelector(
                        'form[action*="login"], form[action*="signin"], form[action*="auth"]'
                    );
                    const hasOAuthButtons = !!document.querySelector(
                        '[class*="oauth"], [class*="social-login"], [href*="oauth"], [href*="auth"]'
                    );
                    const pageText = document.body?.innerText?.toLowerCase() || "";
                    const hasLoginText = pageText.includes("sign in") ||
                                        pageText.includes("log in") ||
                                        pageText.includes("login");

                    return {
                        hasPasswordField,
                        hasLoginButton,
                        hasLoginForm,
                        hasOAuthButtons,
                        hasLoginText,
                    };
                }
            """)

            is_login = (
                indicators.get("hasPasswordField", False)
                or (indicators.get("hasLoginButton", False) and indicators.get("hasLoginText", False))
                or indicators.get("hasLoginForm", False)
            )

            return {
                "is_login_page": is_login,
                "indicators": indicators,
                "url": self._page.url,
            }
        except Exception as e:
            return {"is_login_page": False, "error": str(e)}

    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "current_url": self.current_url,
            "page_title": self.page_title,
            "is_streaming": self._is_streaming,
        }
