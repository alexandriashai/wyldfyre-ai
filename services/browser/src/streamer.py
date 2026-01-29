"""
Screenshot streaming via Redis pub/sub.

Captures browser screenshots at configurable FPS and publishes
to Redis for real-time frontend viewing.
"""

import asyncio
import base64
import json
from datetime import datetime, timezone
from typing import Any

import structlog
import redis.asyncio as redis

from .config import Channels, config
from .session import BrowserSession

logger = structlog.get_logger(__name__)


class ScreenshotStreamer:
    """
    Streams browser screenshots to Redis.

    Captures frames at configurable FPS and publishes to Redis pub/sub
    for real-time viewing by the frontend.
    """

    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client
        self._active_streams: dict[str, asyncio.Task] = {}
        self._shutdown = False

    async def start_stream(self, session: BrowserSession) -> None:
        """
        Start streaming screenshots for a session.

        Args:
            session: Browser session to stream
        """
        project_id = session.project_id

        if project_id in self._active_streams:
            logger.warning("Stream already active", project_id=project_id)
            return

        logger.info(
            "Starting screenshot stream",
            project_id=project_id,
            fps=config.stream_fps,
        )

        # Create streaming task
        task = asyncio.create_task(self._stream_loop(session))
        self._active_streams[project_id] = task

        # Notify session ready
        await self._publish_event(project_id, {
            "type": "session_ready",
            "session_id": session.id,
            "url": session.current_url,
        })

    async def stop_stream(self, project_id: str) -> None:
        """
        Stop streaming for a project.

        Args:
            project_id: Project identifier
        """
        task = self._active_streams.pop(project_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped screenshot stream", project_id=project_id)

    async def stop_all(self) -> None:
        """Stop all active streams."""
        self._shutdown = True
        for project_id in list(self._active_streams.keys()):
            await self.stop_stream(project_id)

    def is_streaming(self, project_id: str) -> bool:
        """Check if streaming is active for a project."""
        return project_id in self._active_streams

    async def _stream_loop(self, session: BrowserSession) -> None:
        """
        Main streaming loop.

        Captures screenshots at configured FPS and publishes to Redis.
        """
        project_id = session.project_id
        interval = 1.0 / config.stream_fps
        last_url = ""
        frame_count = 0

        try:
            while not self._shutdown:
                try:
                    # Capture frame
                    frame = await session.capture_frame()
                    if frame:
                        # Publish frame
                        await self._publish_frame(project_id, frame, frame_count)
                        frame_count += 1

                    # Check for URL change
                    current_url = session.current_url
                    if current_url != last_url:
                        await self._publish_event(project_id, {
                            "type": "url_change",
                            "url": current_url,
                            "title": session.page_title,
                        })
                        last_url = current_url

                    await asyncio.sleep(interval)

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(
                        "Stream loop error",
                        project_id=project_id,
                        error=str(e),
                    )
                    await asyncio.sleep(interval)

        except asyncio.CancelledError:
            pass
        finally:
            # Cleanup
            self._active_streams.pop(project_id, None)
            logger.info(
                "Stream loop ended",
                project_id=project_id,
                frames_sent=frame_count,
            )

    async def _publish_frame(
        self,
        project_id: str,
        frame: bytes,
        frame_number: int,
    ) -> None:
        """Publish a screenshot frame to Redis."""
        try:
            channel = Channels.session_frame(project_id)
            encoded = base64.b64encode(frame).decode("utf-8")

            message = {
                "type": "frame",
                "data": encoded,
                "frame": frame_number,
                "timestamp": datetime.now(timezone.utc).timestamp(),
            }

            await self._redis.publish(channel, json.dumps(message))

        except Exception as e:
            logger.error(
                "Failed to publish frame",
                project_id=project_id,
                error=str(e),
            )

    async def _publish_event(self, project_id: str, event: dict[str, Any]) -> None:
        """Publish an event to Redis."""
        try:
            channel = Channels.session_event(project_id)
            event["timestamp"] = datetime.now(timezone.utc).isoformat()
            await self._redis.publish(channel, json.dumps(event))
        except Exception as e:
            logger.error(
                "Failed to publish event",
                project_id=project_id,
                error=str(e),
            )

    async def publish_console(
        self,
        project_id: str,
        level: str,
        message: str,
    ) -> None:
        """Publish console message to Redis."""
        await self._publish_event(project_id, {
            "type": "console",
            "level": level,
            "message": message,
        })

    async def publish_error(
        self,
        project_id: str,
        error: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Publish error to Redis."""
        await self._publish_event(project_id, {
            "type": "error",
            "error": error,
            "details": details or {},
        })
