"""
Tmux session manager for AI Infrastructure agents.

Provides process orchestration for running multiple agents
in isolated tmux windows with monitoring and control.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import libtmux
import yaml

from ai_core import AgentError, get_logger

logger = get_logger(__name__)


class AgentState(str, Enum):
    """Agent process state."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    RESTARTING = "restarting"


@dataclass
class AgentConfig:
    """Configuration for an agent process."""
    name: str
    command: str
    working_dir: str = "."
    environment: dict[str, str] = field(default_factory=dict)
    auto_restart: bool = True
    restart_delay: int = 5
    max_restarts: int = 3


@dataclass
class AgentProcess:
    """Represents a running agent process."""
    config: AgentConfig
    window: libtmux.Window | None = None
    state: AgentState = AgentState.STOPPED
    restart_count: int = 0
    last_error: str | None = None


class TmuxManager:
    """
    Manages tmux sessions for AI Infrastructure agents.

    Features:
    - Create and manage agent sessions
    - Monitor agent processes
    - Auto-restart on failure
    - Log capture
    """

    def __init__(
        self,
        session_name: str = "ai-infrastructure",
        config_path: Path | None = None,
    ):
        self._session_name = session_name
        self._config_path = config_path
        self._server: libtmux.Server | None = None
        self._session: libtmux.Session | None = None
        self._agents: dict[str, AgentProcess] = {}

    def connect(self) -> None:
        """Connect to tmux server."""
        self._server = libtmux.Server()
        logger.info("Connected to tmux server")

    def disconnect(self) -> None:
        """Disconnect from tmux server."""
        self._server = None
        self._session = None

    @property
    def server(self) -> libtmux.Server:
        """Get tmux server."""
        if self._server is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._server

    def create_session(self) -> libtmux.Session:
        """Create or attach to the agent session."""
        # Check if session exists
        existing = self.server.sessions.filter(session_name=self._session_name)
        if existing:
            self._session = existing[0]
            logger.info("Attached to existing session", session=self._session_name)
        else:
            self._session = self.server.new_session(
                session_name=self._session_name,
                attach=False,
            )
            logger.info("Created new session", session=self._session_name)

        return self._session

    @property
    def session(self) -> libtmux.Session:
        """Get current session."""
        if self._session is None:
            raise RuntimeError("No session. Call create_session() first.")
        return self._session

    def load_config(self, config_path: Path | None = None) -> list[AgentConfig]:
        """Load agent configurations from YAML file."""
        path = config_path or self._config_path
        if not path or not path.exists():
            logger.warning("No config file found", path=str(path))
            return []

        with open(path) as f:
            data = yaml.safe_load(f)

        agents = []
        for agent_data in data.get("agents", []):
            config = AgentConfig(
                name=agent_data["name"],
                command=agent_data["command"],
                working_dir=agent_data.get("working_dir", "."),
                environment=agent_data.get("environment", {}),
                auto_restart=agent_data.get("auto_restart", True),
                restart_delay=agent_data.get("restart_delay", 5),
                max_restarts=agent_data.get("max_restarts", 3),
            )
            agents.append(config)

        logger.info("Loaded agent configs", count=len(agents))
        return agents

    def start_agent(self, config: AgentConfig) -> AgentProcess:
        """Start an agent in a new tmux window."""
        if config.name in self._agents:
            existing = self._agents[config.name]
            if existing.state == AgentState.RUNNING:
                logger.warning("Agent already running", agent=config.name)
                return existing

        # Create window for agent
        window = self.session.new_window(
            window_name=config.name,
            attach=False,
        )

        # Set environment variables
        pane = window.active_pane
        for key, value in config.environment.items():
            pane.send_keys(f"export {key}={value}")

        # Change to working directory
        if config.working_dir != ".":
            pane.send_keys(f"cd {config.working_dir}")

        # Run command
        pane.send_keys(config.command)

        process = AgentProcess(
            config=config,
            window=window,
            state=AgentState.RUNNING,
        )
        self._agents[config.name] = process

        logger.info("Started agent", agent=config.name, command=config.command)
        return process

    def stop_agent(self, name: str, force: bool = False) -> bool:
        """Stop an agent."""
        if name not in self._agents:
            logger.warning("Agent not found", agent=name)
            return False

        process = self._agents[name]
        if process.window:
            pane = process.window.active_pane

            if force:
                # Send SIGKILL
                pane.send_keys("C-c", suppress_history=False)
                pane.send_keys("C-c", suppress_history=False)
            else:
                # Graceful shutdown
                pane.send_keys("C-c", suppress_history=False)

            # Kill the window
            process.window.kill()

        process.state = AgentState.STOPPED
        process.window = None

        logger.info("Stopped agent", agent=name)
        return True

    def restart_agent(self, name: str) -> AgentProcess | None:
        """Restart an agent."""
        if name not in self._agents:
            logger.warning("Agent not found", agent=name)
            return None

        process = self._agents[name]
        process.state = AgentState.RESTARTING
        process.restart_count += 1

        # Stop if running
        if process.window:
            self.stop_agent(name)

        # Wait before restart
        import time
        time.sleep(process.config.restart_delay)

        # Start again
        return self.start_agent(process.config)

    def get_agent_status(self, name: str) -> dict[str, Any]:
        """Get agent status."""
        if name not in self._agents:
            return {"name": name, "state": "not_found"}

        process = self._agents[name]
        return {
            "name": name,
            "state": process.state.value,
            "restart_count": process.restart_count,
            "last_error": process.last_error,
            "window_id": process.window.id if process.window else None,
        }

    def get_all_status(self) -> list[dict[str, Any]]:
        """Get status of all agents."""
        return [self.get_agent_status(name) for name in self._agents]

    def capture_output(self, name: str, lines: int = 100) -> list[str]:
        """Capture recent output from agent."""
        if name not in self._agents:
            return []

        process = self._agents[name]
        if not process.window:
            return []

        pane = process.window.active_pane
        output = pane.capture_pane(start=-lines)
        return output

    def start_all(self, configs: list[AgentConfig] | None = None) -> None:
        """Start all agents from config."""
        if configs is None:
            configs = self.load_config()

        for config in configs:
            try:
                self.start_agent(config)
            except Exception as e:
                logger.error("Failed to start agent", agent=config.name, error=str(e))

    def stop_all(self, force: bool = False) -> None:
        """Stop all agents."""
        for name in list(self._agents.keys()):
            self.stop_agent(name, force=force)

    def kill_session(self) -> None:
        """Kill the entire tmux session."""
        if self._session:
            self._session.kill()
            self._session = None
            self._agents.clear()
            logger.info("Killed session", session=self._session_name)


# Default agent configurations
DEFAULT_AGENTS = [
    AgentConfig(
        name="supervisor",
        command="python -m services.supervisor",
        working_dir="/app",
    ),
    AgentConfig(
        name="code-agent",
        command="python -m services.agents.code_agent",
        working_dir="/app",
    ),
    AgentConfig(
        name="data-agent",
        command="python -m services.agents.data_agent",
        working_dir="/app",
    ),
    AgentConfig(
        name="infra-agent",
        command="python -m services.agents.infra_agent",
        working_dir="/app",
    ),
    AgentConfig(
        name="research-agent",
        command="python -m services.agents.research_agent",
        working_dir="/app",
    ),
    AgentConfig(
        name="qa-agent",
        command="python -m services.agents.qa_agent",
        working_dir="/app",
    ),
]
