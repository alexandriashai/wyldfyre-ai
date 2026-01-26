"""
Statusline Service - Dynamic terminal status display for PAI agents.

Provides real-time feedback on:
- Learning signals (↑ success, ↓ failure, → neutral)
- Context usage and token counts
- Agent status and current task
- Trend indicators

Display Modes:
- minimal: Just status icons
- standard: Status + brief metrics
- verbose: Full metrics display
- debug: All available data

Integration:
- Can update tmux status line
- Can output to dedicated status file
- Provides API for UI consumption
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .logging import get_logger

logger = get_logger(__name__)


class StatuslineMode(str, Enum):
    """Display modes for the status line."""
    MINIMAL = "minimal"
    STANDARD = "standard"
    VERBOSE = "verbose"
    DEBUG = "debug"


class AgentStatusIcon(str, Enum):
    """Status icons for agents."""
    IDLE = "💤"
    BUSY = "⚡"
    THINKING = "🤔"
    EXECUTING = "🔧"
    LEARNING = "📚"
    ERROR = "❌"
    SUCCESS = "✅"
    WARNING = "⚠️"


class LearningSignal(str, Enum):
    """Learning signal indicators."""
    BOOST = "↑"      # Success - learning boosted
    DECAY = "↓"      # Failure - learning decayed
    NEUTRAL = "→"    # Neutral - no change
    NEW = "+"        # New learning created
    EXTRACT = "◆"    # Learning extracted from task


@dataclass
class StatusMetrics:
    """Metrics tracked for status display."""
    # Task metrics
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_in_progress: int = 0
    current_task: str | None = None

    # Learning metrics
    learnings_boosted: int = 0
    learnings_decayed: int = 0
    learnings_created: int = 0
    last_learning_signal: LearningSignal | None = None

    # Token metrics
    tokens_used: int = 0
    tokens_limit: int = 0
    context_percentage: float = 0.0

    # Performance metrics
    avg_task_duration_ms: float = 0.0
    memory_operations: int = 0

    # Session metrics
    session_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)


@dataclass
class StatuslineConfig:
    """Configuration for status line display."""
    mode: StatuslineMode = StatuslineMode.STANDARD
    update_interval_ms: int = 500
    tmux_enabled: bool = True
    file_output_path: str | None = None
    show_trends: bool = True
    trend_window_seconds: int = 60


class StatuslineService:
    """
    Service for managing and displaying agent status.

    Tracks metrics, formats output, and optionally updates
    tmux status line or writes to file.
    """

    def __init__(
        self,
        config: StatuslineConfig | None = None,
        agent_name: str = "pai",
    ):
        self.config = config or StatuslineConfig()
        self.agent_name = agent_name
        self.metrics = StatusMetrics()
        self._learning_history: list[tuple[datetime, LearningSignal]] = []
        self._status_icon = AgentStatusIcon.IDLE
        self._running = False
        self._update_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the status line update loop."""
        if self._running:
            return

        self._running = True
        self.metrics.session_start = datetime.now(timezone.utc)

        if self.config.tmux_enabled or self.config.file_output_path:
            self._update_task = asyncio.create_task(self._update_loop())

        logger.info(
            "Statusline service started",
            mode=self.config.mode.value,
            agent=self.agent_name,
        )

    async def stop(self) -> None:
        """Stop the status line update loop."""
        self._running = False
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

        logger.info("Statusline service stopped")

    async def _update_loop(self) -> None:
        """Background loop for updating status display."""
        while self._running:
            try:
                status_line = self.format_status()

                if self.config.tmux_enabled:
                    await self._update_tmux(status_line)

                if self.config.file_output_path:
                    await self._write_file(status_line)

                await asyncio.sleep(self.config.update_interval_ms / 1000)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Statusline update error", error=str(e))
                await asyncio.sleep(1)

    def format_status(self) -> str:
        """
        Format the current status based on display mode.

        Returns:
            Formatted status string
        """
        if self.config.mode == StatuslineMode.MINIMAL:
            return self._format_minimal()
        elif self.config.mode == StatuslineMode.STANDARD:
            return self._format_standard()
        elif self.config.mode == StatuslineMode.VERBOSE:
            return self._format_verbose()
        else:  # DEBUG
            return self._format_debug()

    def _format_minimal(self) -> str:
        """Minimal format - just icons."""
        parts = [self._status_icon.value]

        # Learning signal
        if self.metrics.last_learning_signal:
            parts.append(self.metrics.last_learning_signal.value)

        # Trend indicator
        if self.config.show_trends:
            trend = self._calculate_trend()
            parts.append(trend)

        return " ".join(parts)

    def _format_standard(self) -> str:
        """Standard format - icons + brief metrics."""
        parts = []

        # Agent status
        parts.append(f"{self._status_icon.value} {self.agent_name}")

        # Task info
        if self.metrics.current_task:
            parts.append(f"[{self.metrics.current_task[:20]}]")

        # Learning signals
        learning_str = self._format_learning_summary()
        if learning_str:
            parts.append(learning_str)

        # Context usage
        if self.metrics.context_percentage > 0:
            parts.append(f"ctx:{self.metrics.context_percentage:.0f}%")

        # Tasks
        parts.append(f"✓{self.metrics.tasks_completed}")
        if self.metrics.tasks_failed > 0:
            parts.append(f"✗{self.metrics.tasks_failed}")

        return " | ".join(parts)

    def _format_verbose(self) -> str:
        """Verbose format - full metrics."""
        lines = []

        # Header
        lines.append(f"═══ {self.agent_name} Status ═══")

        # Status
        lines.append(f"Status: {self._status_icon.value} {self._status_icon.name}")
        if self.metrics.current_task:
            lines.append(f"Task: {self.metrics.current_task}")

        # Tasks
        lines.append(f"Tasks: ✓{self.metrics.tasks_completed} ✗{self.metrics.tasks_failed} ⏳{self.metrics.tasks_in_progress}")

        # Learning
        lines.append(f"Learning: ↑{self.metrics.learnings_boosted} ↓{self.metrics.learnings_decayed} +{self.metrics.learnings_created}")

        # Tokens
        if self.metrics.tokens_limit > 0:
            lines.append(f"Tokens: {self.metrics.tokens_used:,}/{self.metrics.tokens_limit:,} ({self.metrics.context_percentage:.1f}%)")

        # Performance
        if self.metrics.avg_task_duration_ms > 0:
            lines.append(f"Avg Duration: {self.metrics.avg_task_duration_ms:.0f}ms")

        # Memory
        lines.append(f"Memory Ops: {self.metrics.memory_operations}")

        # Session
        uptime = datetime.now(timezone.utc) - self.metrics.session_start
        lines.append(f"Uptime: {uptime.seconds // 60}m {uptime.seconds % 60}s")

        return "\n".join(lines)

    def _format_debug(self) -> str:
        """Debug format - all available data."""
        import json
        data = {
            "agent": self.agent_name,
            "status": self._status_icon.name,
            "mode": self.config.mode.value,
            "metrics": {
                "tasks_completed": self.metrics.tasks_completed,
                "tasks_failed": self.metrics.tasks_failed,
                "tasks_in_progress": self.metrics.tasks_in_progress,
                "current_task": self.metrics.current_task,
                "learnings_boosted": self.metrics.learnings_boosted,
                "learnings_decayed": self.metrics.learnings_decayed,
                "learnings_created": self.metrics.learnings_created,
                "tokens_used": self.metrics.tokens_used,
                "tokens_limit": self.metrics.tokens_limit,
                "context_percentage": self.metrics.context_percentage,
                "avg_task_duration_ms": self.metrics.avg_task_duration_ms,
                "memory_operations": self.metrics.memory_operations,
                "session_start": self.metrics.session_start.isoformat(),
                "last_activity": self.metrics.last_activity.isoformat(),
            },
            "learning_history": [
                {"time": t.isoformat(), "signal": s.value}
                for t, s in self._learning_history[-10:]
            ],
            "trend": self._calculate_trend(),
        }
        return json.dumps(data, indent=2)

    def _format_learning_summary(self) -> str:
        """Format learning signals summary."""
        parts = []

        if self.metrics.learnings_boosted > 0:
            parts.append(f"↑{self.metrics.learnings_boosted}")
        if self.metrics.learnings_decayed > 0:
            parts.append(f"↓{self.metrics.learnings_decayed}")
        if self.metrics.learnings_created > 0:
            parts.append(f"+{self.metrics.learnings_created}")

        return "".join(parts)

    def _calculate_trend(self) -> str:
        """Calculate recent trend from learning history."""
        now = datetime.now(timezone.utc)
        window_start = now.timestamp() - self.config.trend_window_seconds

        recent = [s for t, s in self._learning_history if t.timestamp() > window_start]

        if not recent:
            return "—"

        boosts = sum(1 for s in recent if s == LearningSignal.BOOST)
        decays = sum(1 for s in recent if s == LearningSignal.DECAY)

        if boosts > decays * 2:
            return "📈"  # Strong uptrend
        elif boosts > decays:
            return "↗"   # Uptrend
        elif decays > boosts * 2:
            return "📉"  # Strong downtrend
        elif decays > boosts:
            return "↘"   # Downtrend
        else:
            return "→"   # Neutral

    async def _update_tmux(self, status_line: str) -> None:
        """Update tmux status line."""
        try:
            import subprocess
            # Update tmux window name or status
            subprocess.run(
                ["tmux", "rename-window", status_line[:40]],
                capture_output=True,
                timeout=1,
            )
        except Exception:
            pass  # Silently ignore tmux errors

    async def _write_file(self, status_line: str) -> None:
        """Write status to file."""
        if not self.config.file_output_path:
            return

        try:
            import aiofiles
            async with aiofiles.open(self.config.file_output_path, "w") as f:
                await f.write(status_line)
        except Exception as e:
            logger.debug("Failed to write status file", error=str(e))

    # =========================================================================
    # Status Update Methods
    # =========================================================================

    def set_status(self, status: AgentStatusIcon) -> None:
        """Set the agent status icon."""
        self._status_icon = status
        self.metrics.update_activity()

    def set_current_task(self, task: str | None) -> None:
        """Set the current task description."""
        self.metrics.current_task = task
        if task:
            self.metrics.tasks_in_progress = 1
            self.set_status(AgentStatusIcon.BUSY)
        else:
            self.metrics.tasks_in_progress = 0
            self.set_status(AgentStatusIcon.IDLE)
        self.metrics.update_activity()

    def record_task_complete(self, success: bool, duration_ms: float = 0) -> None:
        """Record task completion."""
        if success:
            self.metrics.tasks_completed += 1
            self.set_status(AgentStatusIcon.SUCCESS)
        else:
            self.metrics.tasks_failed += 1
            self.set_status(AgentStatusIcon.ERROR)

        # Update average duration
        total_tasks = self.metrics.tasks_completed + self.metrics.tasks_failed
        if total_tasks > 0 and duration_ms > 0:
            # Exponential moving average
            alpha = 0.2
            self.metrics.avg_task_duration_ms = (
                alpha * duration_ms +
                (1 - alpha) * self.metrics.avg_task_duration_ms
            )

        self.metrics.current_task = None
        self.metrics.tasks_in_progress = 0
        self.metrics.update_activity()

    def record_learning_signal(self, signal: LearningSignal) -> None:
        """Record a learning signal."""
        now = datetime.now(timezone.utc)
        self._learning_history.append((now, signal))
        self.metrics.last_learning_signal = signal

        # Trim old history
        cutoff = now.timestamp() - 300  # Keep 5 minutes
        self._learning_history = [
            (t, s) for t, s in self._learning_history
            if t.timestamp() > cutoff
        ]

        # Update metrics
        if signal == LearningSignal.BOOST:
            self.metrics.learnings_boosted += 1
        elif signal == LearningSignal.DECAY:
            self.metrics.learnings_decayed += 1
        elif signal in (LearningSignal.NEW, LearningSignal.EXTRACT):
            self.metrics.learnings_created += 1

        self.metrics.update_activity()

    def update_token_usage(self, tokens_used: int, tokens_limit: int) -> None:
        """Update token usage metrics."""
        self.metrics.tokens_used = tokens_used
        self.metrics.tokens_limit = tokens_limit
        if tokens_limit > 0:
            self.metrics.context_percentage = (tokens_used / tokens_limit) * 100
        self.metrics.update_activity()

    def increment_memory_ops(self, count: int = 1) -> None:
        """Increment memory operations counter."""
        self.metrics.memory_operations += count
        self.metrics.update_activity()

    def set_mode(self, mode: StatuslineMode | str) -> None:
        """Change the display mode."""
        if isinstance(mode, str):
            mode = StatuslineMode(mode)
        self.config.mode = mode
        logger.info("Statusline mode changed", mode=mode.value)

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics as dictionary."""
        return {
            "agent": self.agent_name,
            "status": self._status_icon.name,
            "tasks_completed": self.metrics.tasks_completed,
            "tasks_failed": self.metrics.tasks_failed,
            "tasks_in_progress": self.metrics.tasks_in_progress,
            "current_task": self.metrics.current_task,
            "learnings_boosted": self.metrics.learnings_boosted,
            "learnings_decayed": self.metrics.learnings_decayed,
            "learnings_created": self.metrics.learnings_created,
            "tokens_used": self.metrics.tokens_used,
            "context_percentage": self.metrics.context_percentage,
            "memory_operations": self.metrics.memory_operations,
            "trend": self._calculate_trend(),
            "uptime_seconds": (datetime.now(timezone.utc) - self.metrics.session_start).seconds,
        }


# Global statusline instances per agent
_statuslines: dict[str, StatuslineService] = {}


def get_statusline(
    agent_name: str = "pai",
    config: StatuslineConfig | None = None,
) -> StatuslineService:
    """Get or create a statusline service for an agent."""
    if agent_name not in _statuslines:
        _statuslines[agent_name] = StatuslineService(config, agent_name)
    return _statuslines[agent_name]


async def init_statusline(
    agent_name: str = "pai",
    config: StatuslineConfig | None = None,
) -> StatuslineService:
    """Initialize and start a statusline service."""
    statusline = get_statusline(agent_name, config)
    await statusline.start()
    return statusline
