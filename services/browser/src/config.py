"""
Browser service configuration.
"""

import os
from dataclasses import dataclass


@dataclass
class BrowserConfig:
    """Browser service configuration."""

    # Redis
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_password: str = os.getenv("REDIS_PASSWORD", "")
    redis_db: int = int(os.getenv("REDIS_DB", "0"))

    # Browser settings
    headless: bool = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
    viewport_width: int = int(os.getenv("BROWSER_VIEWPORT_WIDTH", "1280"))
    viewport_height: int = int(os.getenv("BROWSER_VIEWPORT_HEIGHT", "720"))
    default_timeout: int = int(os.getenv("BROWSER_DEFAULT_TIMEOUT", "30000"))
    navigation_timeout: int = int(os.getenv("BROWSER_NAV_TIMEOUT", "30000"))

    # Streaming settings
    stream_fps: int = int(os.getenv("BROWSER_STREAM_FPS", "10"))
    jpeg_quality: int = int(os.getenv("BROWSER_JPEG_QUALITY", "80"))

    # Resource limits
    max_sessions_per_project: int = int(os.getenv("BROWSER_MAX_SESSIONS", "3"))
    session_timeout: int = int(os.getenv("BROWSER_SESSION_TIMEOUT", "300"))  # 5 min
    page_timeout: int = int(os.getenv("BROWSER_PAGE_TIMEOUT", "60"))  # 1 min

    # Health check port
    health_port: int = int(os.getenv("BROWSER_HEALTH_PORT", "8002"))

    # Screenshot storage
    screenshot_dir: str = os.getenv("BROWSER_SCREENSHOT_DIR", "/tmp/browser_screenshots")
    session_dir: str = os.getenv("BROWSER_SESSION_DIR", "/tmp/browser_sessions")


# Global config instance
config = BrowserConfig()


# Redis channel names
class Channels:
    """Redis pub/sub channel names."""

    @staticmethod
    def session_control(project_id: str) -> str:
        """Control commands for a browser session."""
        return f"browser:{project_id}:control"

    @staticmethod
    def session_frame(project_id: str) -> str:
        """Screenshot frames from a browser session."""
        return f"browser:{project_id}:frame"

    @staticmethod
    def session_event(project_id: str) -> str:
        """Events from a browser session (url change, console, errors)."""
        return f"browser:{project_id}:event"

    @staticmethod
    def narration(project_id: str) -> str:
        """Agent narration messages."""
        return f"browser:{project_id}:narration"

    AGENT_BROWSER_TASKS = "browser:tasks"
    AGENT_RESPONSES = "agent:responses"
