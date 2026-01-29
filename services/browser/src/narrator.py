"""
Browser action narrator.

Publishes agent narration messages to chat, allowing users
to follow along with browser automation actions.
"""

import base64
import json
from datetime import datetime, timezone
from typing import Any

import structlog
import redis.asyncio as redis

from .config import Channels
from .session import BrowserSession

logger = structlog.get_logger(__name__)


class BrowserNarrator:
    """
    Narrates browser actions to chat.

    Publishes narration messages that appear in the chat interface,
    allowing users to follow along with what the agent is doing.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        project_id: str,
        user_id: str | None = None,
        conversation_id: str | None = None,
    ) -> None:
        self._redis = redis_client
        self._project_id = project_id
        self._user_id = user_id
        self._conversation_id = conversation_id

    async def narrate(
        self,
        action: str,
        detail: str | None = None,
        session: BrowserSession | None = None,
        include_thumbnail: bool = True,
    ) -> None:
        """
        Publish narration of an action.

        Args:
            action: Action type (e.g., "Navigating", "Clicking", "Typing")
            detail: Additional detail about the action
            session: Browser session for thumbnail capture
            include_thumbnail: Whether to include a screenshot thumbnail
        """
        thumbnail = None

        if include_thumbnail and session:
            try:
                # Capture small thumbnail
                frame = await session.capture_frame()
                if frame:
                    thumbnail = base64.b64encode(frame).decode("utf-8")
            except Exception:
                pass

        message = {
            "type": "browser_narration",
            "action": action,
            "detail": detail,
            "thumbnail": thumbnail,
            "url": session.current_url if session else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project_id": self._project_id,
            "user_id": self._user_id,
            "conversation_id": self._conversation_id,
        }

        await self._publish(message)

        logger.debug(
            "Narration published",
            action=action,
            detail=detail,
        )

    async def narrate_navigation(
        self,
        url: str,
        session: BrowserSession | None = None,
    ) -> None:
        """Narrate navigation action."""
        await self.narrate(
            "Navigating",
            f"Going to {url}",
            session,
        )

    async def narrate_click(
        self,
        target: str,
        session: BrowserSession | None = None,
    ) -> None:
        """Narrate click action."""
        await self.narrate(
            "Clicking",
            f"Clicking {target}",
            session,
        )

    async def narrate_type(
        self,
        target: str,
        masked: bool = False,
        session: BrowserSession | None = None,
    ) -> None:
        """Narrate typing action."""
        if masked:
            await self.narrate(
                "Typing",
                f"Entering text into {target} (masked)",
                session,
            )
        else:
            await self.narrate(
                "Typing",
                f"Typing into {target}",
                session,
            )

    async def narrate_wait(
        self,
        reason: str,
        session: BrowserSession | None = None,
    ) -> None:
        """Narrate waiting action."""
        await self.narrate(
            "Waiting",
            reason,
            session,
            include_thumbnail=False,
        )

    async def narrate_found(
        self,
        item: str,
        session: BrowserSession | None = None,
    ) -> None:
        """Narrate discovery."""
        await self.narrate(
            "Found",
            item,
            session,
        )

    async def narrate_auth_needed(
        self,
        session: BrowserSession | None = None,
    ) -> None:
        """Narrate authentication need."""
        await self.narrate(
            "Authentication Required",
            "Login page detected - need credentials to continue",
            session,
        )

    async def narrate_result(
        self,
        success: bool,
        message: str,
        session: BrowserSession | None = None,
    ) -> None:
        """Narrate action result."""
        action = "Success" if success else "Failed"
        await self.narrate(
            action,
            message,
            session,
        )

    async def prompt_user(
        self,
        prompt_type: str,
        message: str,
        options: list[str] | None = None,
        session: BrowserSession | None = None,
    ) -> None:
        """
        Send a prompt to the user.

        Args:
            prompt_type: Type of prompt (auth, input, confirm, choice)
            message: Prompt message
            options: List of options for choice prompts
            session: Browser session for context
        """
        thumbnail = None
        if session:
            try:
                frame = await session.capture_frame()
                if frame:
                    thumbnail = base64.b64encode(frame).decode("utf-8")
            except Exception:
                pass

        prompt = {
            "type": "browser_prompt",
            "prompt_type": prompt_type,
            "message": message,
            "options": options,
            "thumbnail": thumbnail,
            "url": session.current_url if session else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project_id": self._project_id,
            "user_id": self._user_id,
            "conversation_id": self._conversation_id,
        }

        await self._publish(prompt)

        logger.info(
            "User prompt sent",
            prompt_type=prompt_type,
            message=message,
        )

    async def publish_screenshot(
        self,
        session: BrowserSession,
        message: str | None = None,
    ) -> None:
        """
        Publish a full screenshot to chat.

        Args:
            session: Browser session
            message: Optional message to accompany screenshot
        """
        result = await session.screenshot(full_page=False)

        if result.get("success"):
            await self._publish({
                "type": "browser_screenshot",
                "data": result["data"],
                "message": message,
                "url": session.current_url,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "project_id": self._project_id,
                "user_id": self._user_id,
                "conversation_id": self._conversation_id,
            })

    async def _publish(self, message: dict[str, Any]) -> None:
        """Publish message to Redis."""
        try:
            # Publish to both narration channel and agent responses
            await self._redis.publish(
                Channels.narration(self._project_id),
                json.dumps(message),
            )

            # Also publish to agent responses for chat integration
            await self._redis.publish(
                Channels.AGENT_RESPONSES,
                json.dumps(message),
            )

        except Exception as e:
            logger.error(
                "Failed to publish narration",
                error=str(e),
            )
