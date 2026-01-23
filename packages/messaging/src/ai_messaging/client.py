"""
Redis client wrapper with connection pooling and health checks.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, cast

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from redis.asyncio.client import Pipeline

from ai_core import RedisSettings, get_logger, get_settings

logger = get_logger(__name__)


class RedisClient:
    """
    Async Redis client with connection pooling.

    Provides a wrapper around redis-py with:
    - Connection pooling
    - Health checks
    - Graceful shutdown
    """

    def __init__(self, settings: RedisSettings | None = None):
        self._settings = settings or get_settings().redis
        self._pool: ConnectionPool | None = None
        self._client: "redis.Redis[str] | None" = None

    async def connect(self) -> None:
        """Initialize connection pool and connect to Redis."""
        if self._pool is not None:
            return

        logger.info(
            "Connecting to Redis",
            host=self._settings.host,
            port=self._settings.port,
        )

        self._pool = ConnectionPool.from_url(
            self._settings.url,
            max_connections=self._settings.max_connections,
            decode_responses=True,
        )
        self._client = redis.Redis(connection_pool=self._pool)

        # Test connection
        await self._client.ping()  # type: ignore[misc]
        logger.info("Connected to Redis")

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._pool:
            await self._pool.disconnect()
            self._pool = None
        logger.info("Disconnected from Redis")

    async def close(self) -> None:
        """Alias for disconnect() for compatibility."""
        await self.disconnect()

    @property
    def client(self) -> "redis.Redis[str]":
        """Get Redis client instance."""
        if self._client is None:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        return self._client

    async def health_check(self) -> bool:
        """Check if Redis connection is healthy."""
        try:
            await self.client.ping()  # type: ignore[misc]
            return True
        except Exception as e:
            logger.error("Redis health check failed", error=str(e))
            return False

    async def ping(self) -> bool:
        """Ping Redis server."""
        result = await self.client.ping()  # type: ignore[misc]
        return bool(result)

    def pubsub(self) -> "redis.client.PubSub":
        """Get a PubSub instance for subscribing to channels."""
        return self.client.pubsub()

    # Key-Value Operations
    async def get(self, key: str) -> str | None:
        """Get value by key."""
        result = await self.client.get(key)
        return cast(str | None, result)

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        px: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool | None:
        """Set key-value with optional expiration and conditions."""
        result = await self.client.set(key, value, ex=ex, px=px, nx=nx, xx=xx)
        return cast(bool | None, result)

    async def delete(self, *keys: str) -> int:
        """Delete keys."""
        result = await self.client.delete(*keys)
        return cast(int, result)

    async def exists(self, *keys: str) -> int:
        """Check if keys exist."""
        result = await self.client.exists(*keys)
        return cast(int, result)

    async def expire(self, key: str, seconds: int) -> bool:
        """Set key expiration."""
        result = await self.client.expire(key, seconds)
        return cast(bool, result)

    # Hash Operations
    async def hget(self, name: str, key: str) -> str | None:
        """Get hash field value."""
        result = await self.client.hget(name, key)  # type: ignore[misc]
        return cast(str | None, result)

    async def hset(
        self,
        name: str,
        key: str | None = None,
        value: str | None = None,
        mapping: dict[str, str] | None = None,
    ) -> int:
        """
        Set hash field(s).

        Can be called with either:
        - key and value for a single field
        - mapping for multiple fields
        """
        result = await self.client.hset(name, key=key, value=value, mapping=mapping)  # type: ignore[misc]
        return cast(int, result)

    async def hgetall(self, name: str) -> dict[str, str]:
        """Get all hash fields."""
        result = await self.client.hgetall(name)  # type: ignore[misc]
        return cast(dict[str, str], result)

    async def hdel(self, name: str, *keys: str) -> int:
        """Delete hash fields."""
        result = await self.client.hdel(name, *keys)  # type: ignore[misc]
        return cast(int, result)

    async def hincrby(self, name: str, key: str, amount: int = 1) -> int:
        """Increment hash field by amount."""
        result = await self.client.hincrby(name, key, amount)  # type: ignore[misc]
        return cast(int, result)

    # List Operations
    async def lpush(self, name: str, *values: str) -> int:
        """Push values to left of list."""
        result = await self.client.lpush(name, *values)  # type: ignore[misc]
        return cast(int, result)

    async def rpush(self, name: str, *values: str) -> int:
        """Push values to right of list."""
        result = await self.client.rpush(name, *values)  # type: ignore[misc]
        return cast(int, result)

    async def lpop(self, name: str) -> str | None:
        """Pop value from left of list."""
        result = await self.client.lpop(name)  # type: ignore[misc]
        return cast(str | None, result)

    async def rpop(self, name: str) -> str | None:
        """Pop value from right of list."""
        result = await self.client.rpop(name)  # type: ignore[misc]
        return cast(str | None, result)

    async def lrange(self, name: str, start: int, end: int) -> list[str]:
        """Get range of list values."""
        result = await self.client.lrange(name, start, end)  # type: ignore[misc]
        return cast(list[str], result)

    async def llen(self, name: str) -> int:
        """Get list length."""
        result = await self.client.llen(name)  # type: ignore[misc]
        return cast(int, result)

    async def ltrim(self, name: str, start: int, end: int) -> bool:
        """Trim list to specified range."""
        result = await self.client.ltrim(name, start, end)  # type: ignore[misc]
        return cast(bool, result)

    # Stream Operations
    async def xadd(
        self,
        name: str,
        fields: dict[str, str],
        id: str = "*",
        maxlen: int | None = None,
    ) -> str:
        """Add entry to stream."""
        result = await self.client.xadd(name, fields, id=id, maxlen=maxlen)  # type: ignore[arg-type]
        return cast(str, result)

    async def xread(
        self,
        streams: dict[str, str],
        count: int | None = None,
        block: int | None = None,
    ) -> list[Any]:
        """Read from streams."""
        result = await self.client.xread(streams, count=count, block=block)  # type: ignore[arg-type]
        return cast(list[Any], result)

    async def xrange(
        self,
        name: str,
        min: str = "-",
        max: str = "+",
        count: int | None = None,
    ) -> list[Any]:
        """Read range from stream."""
        result = await self.client.xrange(name, min=min, max=max, count=count)
        return cast(list[Any], result)

    def pipeline(self, transaction: bool = True) -> Pipeline:
        """Get a pipeline instance for batched operations."""
        return self.client.pipeline(transaction=transaction)

    # Sorted Set Operations (for rate limiting)
    async def zadd(self, name: str, mapping: dict[str, float]) -> int:
        """Add members to sorted set."""
        result = await self.client.zadd(name, mapping)
        return cast(int, result)

    async def zcard(self, name: str) -> int:
        """Get cardinality of sorted set."""
        result = await self.client.zcard(name)
        return cast(int, result)

    async def zremrangebyscore(self, name: str, min: float, max: float) -> int:
        """Remove members by score range."""
        result = await self.client.zremrangebyscore(name, min, max)
        return cast(int, result)

    async def lrem(self, name: str, count: int, value: str) -> int:
        """Remove elements from list."""
        result = await self.client.lrem(name, count, value)  # type: ignore[misc]
        return cast(int, result)

    async def sadd(self, name: str, *values: str) -> int:
        """Add members to set."""
        result = await self.client.sadd(name, *values)  # type: ignore[misc]
        return cast(int, result)

    async def srem(self, name: str, *values: str) -> int:
        """Remove members from set."""
        result = await self.client.srem(name, *values)  # type: ignore[misc]
        return cast(int, result)

    async def smembers(self, name: str) -> "set[str]":
        """Get all members of set."""
        result = await self.client.smembers(name)  # type: ignore[misc]
        return cast("set[str]", result)

    async def sismember(self, name: str, value: str) -> bool:
        """Check if value is member of set."""
        result = await self.client.sismember(name, value)  # type: ignore[misc]
        return cast(bool, result)

    # Lua Script Operations
    async def eval(
        self,
        script: str,
        numkeys: int,
        *keys_and_args: str | int,
    ) -> Any:
        """Execute a Lua script."""
        return await self.client.eval(script, numkeys, *keys_and_args)  # type: ignore[misc]


# Global client instance
_redis_client: RedisClient | None = None


async def get_redis_client() -> RedisClient:
    """Get global Redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
        await _redis_client.connect()
    return _redis_client


@asynccontextmanager
async def redis_client_context() -> AsyncIterator[RedisClient]:
    """Context manager for Redis client."""
    client = RedisClient()
    await client.connect()
    try:
        yield client
    finally:
        await client.disconnect()
