"""
Distributed locking for AI Infrastructure.

Provides Redis-based distributed locks for critical operations
to prevent race conditions across multiple processes/containers.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

from .client import RedisClient


class LockError(Exception):
    """Raised when a lock cannot be acquired."""
    pass


class LockTimeoutError(LockError):
    """Raised when waiting for a lock times out."""
    pass


class DistributedLock:
    """
    Redis-based distributed lock with automatic expiration.

    Uses SET NX EX pattern for atomic lock acquisition.
    Includes owner tracking to prevent accidental release by non-owners.

    Example:
        async with DistributedLock(redis, "agent:status:update").acquire():
            # Critical section - only one process can execute this at a time
            await update_agent_status()
    """

    def __init__(
        self,
        redis: RedisClient,
        key: str,
        ttl: int = 30,
        retry_interval: float = 0.1,
        max_retries: int = 50,
    ):
        """
        Initialize a distributed lock.

        Args:
            redis: Redis client instance
            key: Lock key name (will be prefixed with 'lock:')
            ttl: Lock time-to-live in seconds (auto-expires)
            retry_interval: Seconds between acquisition retries
            max_retries: Maximum number of retry attempts
        """
        self.redis = redis
        self.key = f"lock:{key}"
        self.ttl = ttl
        self.retry_interval = retry_interval
        self.max_retries = max_retries
        self._token: str | None = None

    async def _try_acquire(self) -> bool:
        """
        Attempt to acquire the lock once.

        Returns:
            True if lock was acquired, False otherwise
        """
        self._token = str(uuid.uuid4())
        # SET key value NX EX ttl - only sets if key doesn't exist
        result = await self.redis.set(
            self.key,
            self._token,
            nx=True,
            ex=self.ttl,
        )
        return result is True

    async def _release(self) -> bool:
        """
        Release the lock if we own it.

        Uses Lua script for atomic check-and-delete to prevent
        releasing a lock owned by another process.

        Returns:
            True if lock was released, False if we didn't own it
        """
        if not self._token:
            return False

        # Lua script: only delete if the value matches our token
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = await self.redis.eval(script, 1, self.key, self._token)
        self._token = None
        return bool(result == 1)

    @asynccontextmanager
    async def acquire(
        self,
        timeout: float | None = None,
        blocking: bool = True,
    ) -> AsyncGenerator[None, None]:
        """
        Acquire the lock as a context manager.

        Args:
            timeout: Maximum seconds to wait for lock (None = use max_retries)
            blocking: If False, fail immediately if lock not available

        Raises:
            LockError: If lock cannot be acquired (non-blocking)
            LockTimeoutError: If timeout expires while waiting

        Example:
            async with lock.acquire(timeout=5.0):
                # Do critical work
                pass
        """
        acquired = False
        retries = 0
        start_time = asyncio.get_event_loop().time()

        try:
            while not acquired:
                acquired = await self._try_acquire()

                if acquired:
                    break

                if not blocking:
                    raise LockError(f"Could not acquire lock: {self.key}")

                retries += 1
                if retries >= self.max_retries:
                    raise LockTimeoutError(
                        f"Timeout acquiring lock: {self.key} after {retries} retries"
                    )

                if timeout is not None:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed >= timeout:
                        raise LockTimeoutError(
                            f"Timeout acquiring lock: {self.key} after {elapsed:.2f}s"
                        )

                await asyncio.sleep(self.retry_interval)

            yield

        finally:
            if acquired:
                await self._release()

    async def extend(self, additional_ttl: int | None = None) -> bool:
        """
        Extend the lock's TTL if we own it.

        Useful for long-running operations that need more time.

        Args:
            additional_ttl: New TTL in seconds (defaults to original ttl)

        Returns:
            True if extended, False if we don't own the lock
        """
        if not self._token:
            return False

        new_ttl = additional_ttl or self.ttl

        # Lua script: only extend if we own the lock
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        result = await self.redis.eval(script, 1, self.key, self._token, new_ttl)
        return bool(result == 1)

    async def is_locked(self) -> bool:
        """Check if the lock is currently held by anyone."""
        return await self.redis.exists(self.key) > 0

    async def owned(self) -> bool:
        """Check if we currently own the lock."""
        if not self._token:
            return False
        current = await self.redis.get(self.key)
        return current == self._token


class AgentStatusLock:
    """
    Convenience wrapper for agent status update locking.

    Ensures only one process updates a specific agent's status at a time.

    Example:
        async with AgentStatusLock(redis, "supervisor").acquire():
            await update_status()
    """

    def __init__(self, redis: RedisClient, agent_name: str):
        self._lock = DistributedLock(
            redis,
            f"agent:status:{agent_name}",
            ttl=10,  # Short TTL for status updates
            retry_interval=0.05,
            max_retries=20,
        )

    def acquire(self, **kwargs: Any) -> AbstractAsyncContextManager[None]:
        """Acquire the status lock."""
        return self._lock.acquire(**kwargs)


class TaskLock:
    """
    Convenience wrapper for task processing locking.

    Ensures only one agent processes a specific task at a time.

    Example:
        async with TaskLock(redis, task_id).acquire():
            await process_task()
    """

    def __init__(self, redis: RedisClient, task_id: str):
        self._lock = DistributedLock(
            redis,
            f"task:{task_id}",
            ttl=300,  # 5 minutes for task processing
            retry_interval=0.5,
            max_retries=10,  # Don't wait too long for tasks
        )

    def acquire(self, **kwargs: Any) -> AbstractAsyncContextManager[None]:
        """Acquire the task lock."""
        return self._lock.acquire(**kwargs)
