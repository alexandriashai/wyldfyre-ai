"""
WebSocket connection manager.
"""

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

from ai_core import get_logger

logger = get_logger(__name__)


@dataclass
class Connection:
    """Represents a WebSocket connection."""

    websocket: WebSocket
    user_id: str
    username: str
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ConnectionManager:
    """
    Manages WebSocket connections for real-time chat.

    Tracks connections per user and provides broadcast capabilities.
    """

    def __init__(self, max_connections_per_user: int = 5):
        self.max_connections_per_user = max_connections_per_user
        # user_id -> list of Connection
        self._connections: dict[str, list[Connection]] = defaultdict(list)
        # websocket -> Connection for reverse lookup
        self._websocket_to_connection: dict[WebSocket, Connection] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        username: str,
    ) -> Connection:
        """
        Accept and register a new WebSocket connection.

        Args:
            websocket: The WebSocket connection
            user_id: User's ID
            username: User's display name

        Returns:
            Connection object

        Raises:
            ValueError: If user has too many connections
        """
        async with self._lock:
            # Check connection limit
            user_connections = self._connections[user_id]
            if len(user_connections) >= self.max_connections_per_user:
                # Close oldest connection
                oldest = user_connections[0]
                await self._remove_connection(oldest)
                logger.info(
                    "Closed oldest connection for user",
                    user_id=user_id,
                    reason="connection_limit",
                )

            # Accept the connection
            await websocket.accept()

            # Create and store connection
            connection = Connection(
                websocket=websocket,
                user_id=user_id,
                username=username,
            )

            self._connections[user_id].append(connection)
            self._websocket_to_connection[websocket] = connection

            logger.info(
                "WebSocket connected",
                user_id=user_id,
                connections=len(self._connections[user_id]),
            )

            return connection

    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove a WebSocket connection.

        Args:
            websocket: The WebSocket to disconnect
        """
        async with self._lock:
            connection = self._websocket_to_connection.get(websocket)
            if connection:
                await self._remove_connection(connection)

    async def _remove_connection(self, connection: Connection) -> None:
        """Remove a connection from tracking (must hold lock)."""
        user_id = connection.user_id
        websocket = connection.websocket

        # Remove from user's connections
        if user_id in self._connections:
            self._connections[user_id] = [
                c for c in self._connections[user_id] if c.websocket != websocket
            ]
            if not self._connections[user_id]:
                del self._connections[user_id]

        # Remove from reverse lookup
        self._websocket_to_connection.pop(websocket, None)

        logger.info("WebSocket disconnected", user_id=user_id)

        # Try to close the websocket
        try:
            await websocket.close()
        except Exception:
            pass

    async def send_personal(
        self,
        user_id: str,
        message: dict[str, Any],
    ) -> int:
        """
        Send a message to all connections for a specific user.

        Args:
            user_id: Target user ID
            message: Message to send

        Returns:
            Number of connections message was sent to
        """
        connections = self._connections.get(user_id, [])
        sent_count = 0

        for connection in connections[:]:  # Copy list to avoid modification during iteration
            try:
                await connection.websocket.send_json(message)
                connection.last_activity = datetime.now(timezone.utc)
                sent_count += 1
            except Exception as e:
                logger.warning(
                    "Failed to send to user",
                    user_id=user_id,
                    error=str(e),
                )
                # Remove dead connection
                async with self._lock:
                    await self._remove_connection(connection)

        return sent_count

    async def broadcast(
        self,
        message: dict[str, Any],
        exclude_user: str | None = None,
    ) -> int:
        """
        Broadcast a message to all connected users.

        Args:
            message: Message to broadcast
            exclude_user: Optional user ID to exclude

        Returns:
            Number of connections message was sent to
        """
        sent_count = 0

        for user_id, connections in list(self._connections.items()):
            if user_id == exclude_user:
                continue

            for connection in connections[:]:
                try:
                    await connection.websocket.send_json(message)
                    connection.last_activity = datetime.now(timezone.utc)
                    sent_count += 1
                except Exception as e:
                    logger.warning(
                        "Broadcast failed for connection",
                        user_id=user_id,
                        error=str(e),
                    )
                    async with self._lock:
                        await self._remove_connection(connection)

        return sent_count

    async def send_typing_indicator(
        self,
        user_id: str,
        conversation_id: str,
        agent: str | None = None,
    ) -> None:
        """
        Send typing indicator to a user.

        Args:
            user_id: Target user ID
            conversation_id: Conversation context
            agent: Agent that is typing (if applicable)
        """
        await self.send_personal(
            user_id,
            {
                "type": "typing",
                "conversation_id": conversation_id,
                "agent": agent,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    def get_connection_count(self, user_id: str | None = None) -> int:
        """
        Get number of active connections.

        Args:
            user_id: Optional user ID to filter by

        Returns:
            Connection count
        """
        if user_id:
            return len(self._connections.get(user_id, []))
        return sum(len(conns) for conns in self._connections.values())

    def get_connected_users(self) -> list[str]:
        """Get list of connected user IDs."""
        return list(self._connections.keys())

    def is_user_connected(self, user_id: str) -> bool:
        """Check if a user has any active connections."""
        return user_id in self._connections and len(self._connections[user_id]) > 0


# Global connection manager instance
_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager."""
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
