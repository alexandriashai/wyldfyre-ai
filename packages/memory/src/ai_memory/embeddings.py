"""
Embedding generation using OpenAI API with optional Redis caching.
"""

from typing import Any, Sequence

import numpy as np
from openai import AsyncOpenAI

from ai_core import (
    EmbeddingError,
    circuit_breaker,
    embedding_generation_duration_seconds,
    get_cost_tracker,
    get_logger,
    get_settings,
)

from .embedding_cache import EmbeddingCache

logger = get_logger(__name__)

# Default embedding model
DEFAULT_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536


class EmbeddingService:
    """
    Service for generating text embeddings using OpenAI.

    Features:
    - Batch embedding generation
    - Automatic retries with circuit breaker
    - Redis caching for reduced API calls and latency
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        dimension: int = EMBEDDING_DIMENSION,
        redis_client: Any = None,
        cache_ttl: int = 86400 * 7,  # 7 days default
    ):
        self._model = model
        self._dimension = dimension
        settings = get_settings()
        self._client = AsyncOpenAI(
            api_key=settings.api.openai_api_key.get_secret_value()
        )

        # Initialize cache if Redis client provided
        self._cache = EmbeddingCache(redis_client, ttl_seconds=cache_ttl) if redis_client else None

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        return self._dimension

    @property
    def cache_stats(self) -> dict | None:
        """Get cache statistics if caching is enabled."""
        return self._cache.stats if self._cache else None

    @circuit_breaker("openai-embeddings")
    async def generate(self, text: str) -> list[float]:
        """
        Generate embedding for a single text with caching.

        Args:
            text: Text to embed

        Returns:
            Embedding vector

        Raises:
            EmbeddingError: If embedding generation fails
        """
        if not text.strip():
            return [0.0] * self._dimension

        # Check cache first
        if self._cache:
            cached = await self._cache.get(text, self._model)
            if cached is not None:
                return cached

        try:
            with embedding_generation_duration_seconds.labels(
                model=self._model
            ).time():
                response = await self._client.embeddings.create(
                    model=self._model,
                    input=text,
                    dimensions=self._dimension,
                )

            embedding = response.data[0].embedding

            # Track embedding cost
            if response.usage:
                await get_cost_tracker().record_embedding_usage(
                    model=self._model,
                    input_tokens=response.usage.total_tokens,
                )

            # Cache the result
            if self._cache:
                await self._cache.set(text, self._model, embedding)

            return embedding

        except Exception as e:
            logger.error("Failed to generate embedding", error=str(e))
            raise EmbeddingError(
                f"Failed to generate embedding: {e}",
                context={"model": self._model},
                cause=e,
            )

    @circuit_breaker("openai-embeddings")
    async def generate_batch(
        self,
        texts: Sequence[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts with caching.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Filter empty texts and track indices
        valid_texts = []
        valid_indices = []
        for i, text in enumerate(texts):
            if text.strip():
                valid_texts.append(text)
                valid_indices.append(i)

        if not valid_texts:
            return [[0.0] * self._dimension for _ in texts]

        # Check cache for all valid texts first
        cached_results: dict[int, list[float]] = {}
        uncached_texts: list[str] = []
        uncached_indices: list[int] = []

        if self._cache:
            for i, text in enumerate(valid_texts):
                cached = await self._cache.get(text, self._model)
                if cached is not None:
                    cached_results[valid_indices[i]] = cached
                else:
                    uncached_texts.append(text)
                    uncached_indices.append(valid_indices[i])
        else:
            uncached_texts = valid_texts
            uncached_indices = valid_indices

        # Process uncached texts in batches
        all_embeddings: list[list[float]] = []

        for i in range(0, len(uncached_texts), batch_size):
            batch = uncached_texts[i:i + batch_size]
            batch_indices = uncached_indices[i:i + batch_size]

            try:
                with embedding_generation_duration_seconds.labels(
                    model=self._model
                ).time():
                    response = await self._client.embeddings.create(
                        model=self._model,
                        input=batch,
                        dimensions=self._dimension,
                    )

                batch_embeddings = [item.embedding for item in response.data]

                # Track embedding cost for the batch
                if response.usage:
                    await get_cost_tracker().record_embedding_usage(
                        model=self._model,
                        input_tokens=response.usage.total_tokens,
                    )

                # Cache the new embeddings
                if self._cache:
                    for text, embedding in zip(batch, batch_embeddings):
                        await self._cache.set(text, self._model, embedding)

                all_embeddings.extend(batch_embeddings)

            except Exception as e:
                logger.error(
                    "Failed to generate batch embeddings",
                    batch_start=i,
                    batch_size=len(batch),
                    error=str(e),
                )
                raise EmbeddingError(
                    f"Failed to generate batch embeddings: {e}",
                    context={"batch_start": i, "batch_size": len(batch)},
                    cause=e,
                )

        # Reconstruct full list with zeros for empty texts
        result = [[0.0] * self._dimension for _ in texts]

        # Add cached results
        for idx, embedding in cached_results.items():
            result[idx] = embedding

        # Add newly generated results
        for idx, embedding in zip(uncached_indices, all_embeddings):
            result[idx] = embedding

        return result

    def cosine_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
    ) -> float:
        """Calculate cosine similarity between two embeddings."""
        a = np.array(embedding1)
        b = np.array(embedding2)

        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))


# Global instance
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Get global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
