"""
Redis-backed embedding cache to reduce API calls and latency.
"""
import hashlib
import json
from typing import Any, Optional

from ai_core import get_logger

logger = get_logger(__name__)


class EmbeddingCache:
    """
    Cache embeddings in Redis to avoid redundant API calls.

    Features:
    - Content-based hashing for cache keys
    - Configurable TTL
    - Batch operation support
    - Cache statistics tracking
    """

    def __init__(
        self,
        redis_client: Any,  # RedisClient from ai_messaging
        prefix: str = "emb_cache:",
        ttl_seconds: int = 86400 * 7,  # 7 days default
    ):
        """
        Initialize embedding cache.

        Args:
            redis_client: Redis client instance
            prefix: Key prefix for cache entries
            ttl_seconds: Time-to-live for cached embeddings (default 7 days)
        """
        self._redis = redis_client
        self._prefix = prefix
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0

    def _cache_key(self, text: str, model: str) -> str:
        """
        Generate cache key from text content hash.

        Uses SHA256 hash of model + text to create unique key.
        """
        content = f"{model}:{text}"
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"{self._prefix}{content_hash}"

    async def get(self, text: str, model: str) -> Optional[list[float]]:
        """
        Get cached embedding if exists.

        Args:
            text: Original text that was embedded
            model: Embedding model name

        Returns:
            Cached embedding vector or None if not found
        """
        key = self._cache_key(text, model)
        try:
            cached = await self._redis.get(key)
            if cached:
                self._hits += 1
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")

        self._misses += 1
        return None

    async def set(self, text: str, model: str, embedding: list[float]) -> bool:
        """
        Cache an embedding.

        Args:
            text: Original text
            model: Embedding model name
            embedding: Embedding vector to cache

        Returns:
            True if cached successfully
        """
        key = self._cache_key(text, model)
        try:
            await self._redis.set(key, json.dumps(embedding), ex=self._ttl)
            return True
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")
            return False

    async def get_batch(
        self,
        texts: list[str],
        model: str,
    ) -> tuple[dict[int, list[float]], list[int]]:
        """
        Get cached embeddings for batch.

        Args:
            texts: List of texts to look up
            model: Embedding model name

        Returns:
            Tuple of (cached_results dict, missing_indices list)
            - cached_results: Dict mapping original index to embedding
            - missing_indices: List of indices that need to be generated
        """
        cached: dict[int, list[float]] = {}
        missing: list[int] = []

        for i, text in enumerate(texts):
            result = await self.get(text, model)
            if result is not None:
                cached[i] = result
            else:
                missing.append(i)

        return cached, missing

    async def set_batch(
        self,
        texts: list[str],
        model: str,
        embeddings: list[list[float]],
        indices: list[int] | None = None,
    ) -> int:
        """
        Cache multiple embeddings.

        Args:
            texts: Original texts
            model: Embedding model name
            embeddings: Embedding vectors
            indices: Optional indices mapping embeddings to texts

        Returns:
            Number of successfully cached embeddings
        """
        success_count = 0

        if indices:
            # Map embeddings to specific text indices
            for idx, embedding in zip(indices, embeddings):
                if idx < len(texts):
                    if await self.set(texts[idx], model, embedding):
                        success_count += 1
        else:
            # Direct 1:1 mapping
            for text, embedding in zip(texts, embeddings):
                if await self.set(text, model, embedding):
                    success_count += 1

        return success_count

    async def invalidate(self, text: str, model: str) -> bool:
        """
        Remove a specific embedding from cache.

        Args:
            text: Original text
            model: Embedding model name

        Returns:
            True if deleted successfully
        """
        key = self._cache_key(text, model)
        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache invalidate failed: {e}")
            return False

    async def clear_all(self) -> int:
        """
        Clear all cached embeddings.

        Returns:
            Number of keys deleted
        """
        try:
            # Find all cache keys
            keys = await self._redis.keys(f"{self._prefix}*")
            if keys:
                deleted = await self._redis.delete(*keys)
                logger.info(f"Cleared {deleted} cached embeddings")
                return deleted
        except Exception as e:
            logger.warning(f"Cache clear failed: {e}")
        return 0

    @property
    def stats(self) -> dict[str, Any]:
        """
        Return cache statistics.

        Returns:
            Dict with hits, misses, and hit rate
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total": total,
            "hit_rate": f"{hit_rate:.1f}%",
            "hit_rate_decimal": hit_rate / 100,
        }

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._hits = 0
        self._misses = 0
