"""
File watcher service using watchdog for detecting filesystem changes.

Emits WebSocket events when files are modified by agents or external processes.
"""

import asyncio
import os
import time
from pathlib import Path
from typing import Callable

from ai_core import get_logger

logger = get_logger(__name__)

# Directories to ignore
IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".next", ".venv", "venv", ".cache"}
DEBOUNCE_MS = 100


class FileChangeEvent:
    """Represents a file change event."""

    def __init__(self, event_type: str, path: str, is_directory: bool = False):
        self.event_type = event_type  # created, modified, deleted, moved
        self.path = path
        self.is_directory = is_directory
        self.timestamp = time.time()


class ProjectFileWatcher:
    """Watches a project directory for file changes and emits events."""

    def __init__(
        self,
        project_id: str,
        root_path: str,
        on_change: Callable[[str, list[FileChangeEvent]], None],
    ):
        self.project_id = project_id
        self.root_path = os.path.realpath(root_path)
        self.on_change = on_change
        self._observer = None
        self._pending_events: list[FileChangeEvent] = []
        self._debounce_task: asyncio.Task | None = None
        self._running = False

    def _should_ignore(self, path: str) -> bool:
        """Check if the path should be ignored."""
        rel_path = os.path.relpath(path, self.root_path)
        parts = rel_path.split(os.sep)
        return any(part in IGNORE_DIRS for part in parts)

    async def start(self) -> None:
        """Start watching the directory."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class Handler(FileSystemEventHandler):
                def __init__(self, watcher: "ProjectFileWatcher"):
                    self.watcher = watcher

                def on_any_event(self, event):
                    if self.watcher._should_ignore(event.src_path):
                        return

                    rel_path = os.path.relpath(event.src_path, self.watcher.root_path)

                    event_type_map = {
                        "created": "created",
                        "modified": "modified",
                        "deleted": "deleted",
                        "moved": "moved",
                    }

                    evt_type = event_type_map.get(event.event_type)
                    if evt_type:
                        change = FileChangeEvent(
                            event_type=evt_type,
                            path=rel_path,
                            is_directory=event.is_directory,
                        )
                        self.watcher._queue_event(change)

            self._observer = Observer()
            handler = Handler(self)
            self._observer.schedule(handler, self.root_path, recursive=True)
            self._observer.start()
            self._running = True

            logger.info(
                "File watcher started",
                project_id=self.project_id,
                root_path=self.root_path,
            )

        except ImportError:
            logger.warning("watchdog not installed, file watching disabled")
        except Exception as e:
            logger.error("Failed to start file watcher", error=str(e))

    async def stop(self) -> None:
        """Stop watching."""
        self._running = False
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

        if self._debounce_task:
            self._debounce_task.cancel()

        logger.info("File watcher stopped", project_id=self.project_id)

    def _queue_event(self, event: FileChangeEvent) -> None:
        """Queue an event with debouncing."""
        self._pending_events.append(event)

        # Reset debounce timer
        if self._debounce_task:
            self._debounce_task.cancel()

        loop = asyncio.get_event_loop()
        self._debounce_task = loop.call_later(
            DEBOUNCE_MS / 1000.0,
            lambda: asyncio.ensure_future(self._flush_events()),
        )

    async def _flush_events(self) -> None:
        """Flush pending events to the callback."""
        if not self._pending_events:
            return

        events = self._pending_events.copy()
        self._pending_events.clear()

        # Deduplicate events for the same path
        seen = {}
        for event in events:
            seen[event.path] = event

        unique_events = list(seen.values())

        try:
            self.on_change(self.project_id, unique_events)
        except Exception as e:
            logger.error("Error in file change callback", error=str(e))


class FileWatcherManager:
    """Manages file watchers for multiple projects."""

    def __init__(self):
        self._watchers: dict[str, ProjectFileWatcher] = {}

    async def start_watching(
        self,
        project_id: str,
        root_path: str,
        on_change: Callable[[str, list[FileChangeEvent]], None],
    ) -> None:
        """Start watching a project directory."""
        if project_id in self._watchers:
            return  # Already watching

        watcher = ProjectFileWatcher(project_id, root_path, on_change)
        await watcher.start()
        self._watchers[project_id] = watcher

    async def stop_watching(self, project_id: str) -> None:
        """Stop watching a project directory."""
        watcher = self._watchers.pop(project_id, None)
        if watcher:
            await watcher.stop()

    async def stop_all(self) -> None:
        """Stop all watchers."""
        for watcher in self._watchers.values():
            await watcher.stop()
        self._watchers.clear()

    def is_watching(self, project_id: str) -> bool:
        """Check if a project is being watched."""
        return project_id in self._watchers


# Global instance
_watcher_manager: FileWatcherManager | None = None


def get_file_watcher_manager() -> FileWatcherManager:
    """Get or create the global file watcher manager."""
    global _watcher_manager
    if _watcher_manager is None:
        _watcher_manager = FileWatcherManager()
    return _watcher_manager
