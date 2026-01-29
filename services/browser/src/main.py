"""
Browser Debug Service entry point.

Provides browser automation for agents with real-time streaming
and interactive control.
"""

import asyncio
import json
import os
import signal
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as redis
import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .auth_handler import AuthenticationHandler
from .browser_pool import (
    BrowserPool,
    get_browser_pool,
    initialize_browser_pool,
    shutdown_browser_pool,
)
from .config import Channels, config
from .narrator import BrowserNarrator
from .session import BrowserSession
from .streamer import ScreenshotStreamer

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger(__name__)


class BrowserService:
    """
    Main browser service controller.

    Manages browser pool, streaming, and command processing.
    """

    def __init__(self) -> None:
        self._redis: redis.Redis | None = None
        self._pool: BrowserPool | None = None
        self._streamer: ScreenshotStreamer | None = None
        self._auth_handler: AuthenticationHandler | None = None
        self._subscriber_task: asyncio.Task | None = None
        self._shutdown = False

    async def start(self) -> None:
        """Start the browser service."""
        logger.info(
            "Starting Browser Debug Service",
            redis_host=config.redis_host,
        )

        # Connect to Redis
        self._redis = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            password=config.redis_password or None,
            db=config.redis_db,
            decode_responses=False,
        )

        # Verify Redis connection
        await self._redis.ping()
        logger.info("Connected to Redis")

        # Initialize components
        self._pool = await initialize_browser_pool()
        self._streamer = ScreenshotStreamer(self._redis)
        self._auth_handler = AuthenticationHandler(self._redis)

        # Start task subscriber
        self._subscriber_task = asyncio.create_task(self._subscribe_to_tasks())

        logger.info("Browser Debug Service started")

    async def stop(self) -> None:
        """Stop the browser service."""
        logger.info("Stopping Browser Debug Service")
        self._shutdown = True

        # Stop subscriber
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass

        # Stop streamer
        if self._streamer:
            await self._streamer.stop_all()

        # Stop browser pool
        await shutdown_browser_pool()

        # Close Redis
        if self._redis:
            await self._redis.close()

        logger.info("Browser Debug Service stopped")

    async def _subscribe_to_tasks(self) -> None:
        """Subscribe to browser task channel."""
        logger.info("Subscribing to browser tasks")

        try:
            pubsub = self._redis.pubsub()
            await pubsub.subscribe(Channels.AGENT_BROWSER_TASKS)

            async for message in pubsub.listen():
                if self._shutdown:
                    break

                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await self._handle_task(data)
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON in task message")
                    except Exception as e:
                        logger.error("Task handling error", error=str(e))

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Subscriber error", error=str(e))

    async def _handle_task(self, task: dict[str, Any]) -> None:
        """
        Handle incoming browser task.

        Args:
            task: Task data from pub/sub
        """
        task_type = task.get("type")
        project_id = task.get("project_id")
        correlation_id = task.get("correlation_id")

        if not project_id:
            logger.warning("Task missing project_id", task=task)
            return

        logger.debug(
            "Handling browser task",
            type=task_type,
            project_id=project_id,
        )

        try:
            # Get or create session
            session = await self._pool.get_session(project_id)

            # Set event callback for real-time console/network publishing
            async def event_callback(event_type: str, data: dict) -> None:
                await self._publish_session_event(project_id, event_type, data)
            session.set_event_callback(event_callback)

            # Route to handler
            handlers = {
                "navigate": self._handle_navigate,
                "click": self._handle_click,
                "type": self._handle_type,
                "screenshot": self._handle_screenshot,
                "get_content": self._handle_get_content,
                "wait": self._handle_wait,
                "evaluate": self._handle_evaluate,
                "check_auth": self._handle_check_auth,
                "start_stream": self._handle_start_stream,
                "stop_stream": self._handle_stop_stream,
                "close": self._handle_close,
                "scroll": self._handle_scroll,
                "find_elements": self._handle_find_elements,
                "get_console": self._handle_get_console,
                "get_network": self._handle_get_network,
                "set_permissions": self._handle_set_permissions,
                "set_viewport": self._handle_set_viewport,
            }

            handler = handlers.get(task_type)
            if handler:
                result = await handler(session, task)
            else:
                result = {"error": f"Unknown task type: {task_type}"}

            # Publish result
            await self._publish_result(
                project_id,
                correlation_id,
                result,
            )

        except Exception as e:
            logger.error(
                "Task handling failed",
                type=task_type,
                project_id=project_id,
                error=str(e),
            )
            await self._publish_result(
                project_id,
                correlation_id,
                {"error": str(e)},
            )

    async def _publish_result(
        self,
        project_id: str,
        correlation_id: str | None,
        result: dict[str, Any],
    ) -> None:
        """Publish task result to Redis."""
        message = {
            "type": "task_result",
            "project_id": project_id,
            "correlation_id": correlation_id,
            "result": result,
        }

        await self._redis.publish(
            Channels.session_event(project_id),
            json.dumps(message),
        )

    async def _publish_session_event(
        self,
        project_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Publish session event (console, network) to Redis."""
        message = {
            "type": event_type,
            "project_id": project_id,
            **data,
        }

        await self._redis.publish(
            Channels.session_event(project_id),
            json.dumps(message),
        )

    # Task handlers

    async def _handle_navigate(
        self,
        session: BrowserSession,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle navigate task."""
        url = task.get("url")
        wait_until = task.get("wait_until", "load")

        if not url:
            return {"error": "URL required"}

        return await session.navigate(url, wait_until)

    async def _handle_click(
        self,
        session: BrowserSession,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle click task."""
        selector = task.get("selector")
        x = task.get("x")
        y = task.get("y")
        button = task.get("button", "left")

        return await session.click(selector, x, y, button)

    async def _handle_type(
        self,
        session: BrowserSession,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle type task."""
        text = task.get("text", "")
        selector = task.get("selector")
        delay = task.get("delay", 50)
        clear = task.get("clear", False)

        return await session.type_text(text, selector, delay, clear)

    async def _handle_screenshot(
        self,
        session: BrowserSession,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle screenshot task."""
        full_page = task.get("full_page", False)
        quality = task.get("quality")
        format = task.get("format", "jpeg")

        return await session.screenshot(full_page, quality, format)

    async def _handle_get_content(
        self,
        session: BrowserSession,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle get_content task."""
        selector = task.get("selector")
        format = task.get("format", "text")

        return await session.get_content(selector, format)

    async def _handle_wait(
        self,
        session: BrowserSession,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle wait task."""
        selector = task.get("selector")
        state = task.get("state", "visible")
        timeout = task.get("timeout")

        if selector:
            return await session.wait_for_selector(selector, state, timeout)
        else:
            return await session.wait_for_navigation()

    async def _handle_evaluate(
        self,
        session: BrowserSession,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle evaluate task."""
        expression = task.get("expression", "")
        return await session.evaluate(expression)

    async def _handle_check_auth(
        self,
        session: BrowserSession,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle check_auth task."""
        return await self._auth_handler.detect_login_page(session)

    async def _handle_start_stream(
        self,
        session: BrowserSession,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle start_stream task."""
        await self._streamer.start_stream(session)

        # Navigate to initial URL only if page is blank (no existing content)
        # This prevents interrupting AI agent work when user opens debug panel
        initial_url = task.get("initial_url")
        current_url = session.page.url if session.page else None
        is_blank_page = not current_url or current_url in ("about:blank", "chrome://newtab/")

        if initial_url and is_blank_page:
            logger.info(
                "Navigating to initial URL (blank page)",
                project_id=session.project_id,
                url=initial_url,
            )
            nav_result = await session.navigate(initial_url, wait_until="load")
            return {
                "success": True,
                "streaming": True,
                "initial_url": initial_url,
                "navigation": nav_result,
            }
        elif initial_url and not is_blank_page:
            logger.info(
                "Skipping initial URL navigation (page already has content)",
                project_id=session.project_id,
                current_url=current_url,
            )

        return {"success": True, "streaming": True, "current_url": current_url}

    async def _handle_stop_stream(
        self,
        session: BrowserSession,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle stop_stream task."""
        await self._streamer.stop_stream(session.project_id)
        return {"success": True, "streaming": False}

    async def _handle_close(
        self,
        session: BrowserSession,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle close task."""
        project_id = session.project_id
        await self._streamer.stop_stream(project_id)
        await self._pool.close_session(project_id)
        return {"success": True, "closed": True}

    async def _handle_scroll(
        self,
        session: BrowserSession,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle scroll task."""
        delta_x = task.get("delta_x", 0)
        delta_y = task.get("delta_y", 0)
        x = task.get("x")
        y = task.get("y")

        return await session.scroll(delta_x, delta_y, x, y)

    async def _handle_find_elements(
        self,
        session: BrowserSession,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle find_elements task."""
        selector = task.get("selector", "")
        return await session.find_elements(selector)

    async def _handle_get_console(
        self,
        session: BrowserSession,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle get_console task."""
        errors_only = task.get("errors_only", False)
        clear = task.get("clear", False)

        if errors_only:
            messages = session.get_console_errors()
        else:
            messages = [
                {
                    "level": e.level,
                    "message": e.message,
                    "timestamp": e.timestamp,
                }
                for e in session._console_messages
            ]

        if clear:
            session.clear_console()

        return {"success": True, "messages": messages}

    async def _handle_get_network(
        self,
        session: BrowserSession,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle get_network task."""
        errors_only = task.get("errors_only", False)
        url_filter = task.get("url_filter")
        clear = task.get("clear", False)

        if errors_only:
            requests = session.get_network_errors()
        else:
            status_filter = "error" if errors_only else None
            requests = session.get_network_requests(url_filter, status_filter)

        if clear:
            session.clear_network()

        return {"success": True, "requests": requests}

    async def _handle_set_permissions(
        self,
        session: BrowserSession,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle set_permissions task."""
        permissions = task.get("permissions", [])
        origin = task.get("origin", "*")

        if not permissions:
            return {"success": True, "message": "No permissions to set"}

        logger.info(
            "Setting browser permissions",
            project_id=session.project_id,
            permissions=permissions,
        )

        return await session.set_permissions(permissions, origin)

    async def _handle_set_viewport(
        self,
        session: BrowserSession,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle set_viewport task."""
        width = task.get("width", 1280)
        height = task.get("height", 720)
        device_scale_factor = task.get("device_scale_factor", 1)
        is_mobile = task.get("is_mobile", False)
        has_touch = task.get("has_touch", False)

        logger.info(
            "Setting browser viewport",
            project_id=session.project_id,
            width=width,
            height=height,
        )

        return await session.set_viewport(width, height, device_scale_factor, is_mobile, has_touch)

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        stats = {
            "status": "running" if not self._shutdown else "stopping",
        }

        if self._pool:
            stats["pool"] = self._pool.get_stats()

        return stats


# Global service instance
_service: BrowserService | None = None


def get_service() -> BrowserService:
    """Get the browser service instance."""
    global _service
    if _service is None:
        _service = BrowserService()
    return _service


# FastAPI app for health checks
@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler."""
    service = get_service()
    await service.start()
    yield
    await service.stop()


app = FastAPI(
    title="Browser Debug Service",
    description="Browser automation for AI agents",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return JSONResponse({"status": "healthy"})


@app.get("/stats")
async def stats():
    """Get service statistics."""
    service = get_service()
    return JSONResponse(service.get_stats())


async def main() -> None:
    """Main entry point."""
    # Setup signal handlers
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Received shutdown signal")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    # Start FastAPI server
    config_uvicorn = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=config.health_port,
        log_level="info",
    )
    server = uvicorn.Server(config_uvicorn)

    # Run server
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
