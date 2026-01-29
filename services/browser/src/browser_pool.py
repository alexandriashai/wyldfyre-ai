"""
Browser pool manager.

Manages browser sessions per project with automatic cleanup.
"""

import asyncio
import time
from typing import Any

import structlog

from .config import config
from .session import BrowserSession

logger = structlog.get_logger(__name__)


class BrowserPool:
    """
    Pool of browser sessions, one per project.

    Manages session lifecycle, cleanup, and provides session access.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, BrowserSession] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None
        self._shutdown = False

    async def start(self) -> None:
        """Start the browser pool with cleanup task."""
        logger.info("Starting browser pool")
        self._shutdown = False
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Stop the browser pool and cleanup all sessions."""
        logger.info("Stopping browser pool")
        self._shutdown = True

        # Stop cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        # Close all sessions
        await self.close_all()
        logger.info("Browser pool stopped")

    async def _cleanup_loop(self) -> None:
        """Background task to cleanup stale sessions."""
        while not self._shutdown:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                if not self._shutdown:
                    await self._cleanup_stale_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Cleanup loop error", error=str(e))

    async def _cleanup_stale_sessions(self) -> int:
        """Remove sessions that have been idle too long."""
        now = time.time()
        to_remove = []

        async with self._lock:
            for project_id, session in self._sessions.items():
                idle_time = now - session.last_used
                if idle_time > config.session_timeout:
                    to_remove.append(project_id)

        count = 0
        for project_id in to_remove:
            await self.close_session(project_id)
            count += 1
            logger.info(
                "Cleaned up stale session",
                project_id=project_id,
            )

        return count

    async def get_session(self, project_id: str) -> BrowserSession:
        """
        Get or create a browser session for a project.

        Args:
            project_id: Project identifier

        Returns:
            BrowserSession instance
        """
        async with self._lock:
            if project_id in self._sessions:
                session = self._sessions[project_id]
                session.touch()
                return session

            # Check session limit
            if len(self._sessions) >= config.max_sessions_per_project * 3:
                # Try to cleanup first
                await self._cleanup_stale_sessions()

                if len(self._sessions) >= config.max_sessions_per_project * 3:
                    raise RuntimeError("Maximum browser sessions reached")

            # Create new session
            logger.info("Creating new browser session", project_id=project_id)
            session = await BrowserSession.create(project_id)
            self._sessions[project_id] = session

            logger.info(
                "Browser session created",
                project_id=project_id,
                session_id=session.id,
            )
            return session

    async def close_session(self, project_id: str) -> bool:
        """
        Close a browser session.

        Args:
            project_id: Project identifier

        Returns:
            True if session was closed, False if not found
        """
        async with self._lock:
            session = self._sessions.pop(project_id, None)

        if session:
            await session.close()
            logger.info(
                "Browser session closed",
                project_id=project_id,
                session_id=session.id,
            )
            return True

        return False

    async def close_all(self) -> int:
        """
        Close all browser sessions.

        Returns:
            Number of sessions closed
        """
        async with self._lock:
            sessions = list(self._sessions.items())
            self._sessions.clear()

        count = 0
        for project_id, session in sessions:
            try:
                await session.close()
                count += 1
                logger.info("Closed session", project_id=project_id)
            except Exception as e:
                logger.error(
                    "Error closing session",
                    project_id=project_id,
                    error=str(e),
                )

        return count

    def has_session(self, project_id: str) -> bool:
        """Check if a session exists for project."""
        return project_id in self._sessions

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all active sessions."""
        return [session.to_dict() for session in self._sessions.values()]

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics."""
        now = time.time()
        sessions = list(self._sessions.values())

        return {
            "active_sessions": len(sessions),
            "max_sessions": config.max_sessions_per_project * 3,
            "session_timeout": config.session_timeout,
            "sessions": [
                {
                    "project_id": s.project_id,
                    "session_id": s.id,
                    "idle_seconds": int(now - s.last_used),
                    "current_url": s.current_url,
                    "is_streaming": s._is_streaming,
                }
                for s in sessions
            ],
        }


# Global pool instance
_browser_pool: BrowserPool | None = None


def get_browser_pool() -> BrowserPool:
    """Get the global browser pool instance."""
    global _browser_pool
    if _browser_pool is None:
        _browser_pool = BrowserPool()
    return _browser_pool


async def initialize_browser_pool() -> BrowserPool:
    """Initialize and start the browser pool."""
    pool = get_browser_pool()
    await pool.start()
    return pool


async def shutdown_browser_pool() -> None:
    """Shutdown the browser pool."""
    global _browser_pool
    if _browser_pool:
        await _browser_pool.stop()
        _browser_pool = None
