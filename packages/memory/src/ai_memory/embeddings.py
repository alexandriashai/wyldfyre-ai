"""
Embedding generation using OpenAI API.
"""

import asyncio
from typing import Sequence

import numpy as np
from openai import AsyncOpenAI

from ai_core import (
    EmbeddingError,
    circuit_breaker,
    embedding_generation_duration_seconds,
    get_logger,
    get_settings,
)

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
    - Caching (optional)
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        dimension: int = EMBEDDING_DIMENSION,
    ):
        self._model = model
        self._dimension = dimension
        settings = get_settings()
        self._client = AsyncOpenAI(
            api_key=settings.api.openai_api_key.get_secret_value()
        )

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        return self._dimension

    @circuit_breaker("openai-embeddings")
    async def generate(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector

        Raises:
            EmbeddingError: If embedding generation fails
        """
        if not text.strip():
            return [0.0] * self._dimension

        try:
            with embedding_generation_duration_seconds.labels(
                model=self._model
            ).time():
                response = await self._client.embeddings.create(
                    model=self._model,
                    input=text,
                    dimensions=self._dimension,
                )

            return response.data[0].embedding

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
        Generate embeddings for multiple texts.

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

        # Process in batches
        all_embeddings: list[list[float]] = []

        for i in range(0, len(valid_texts), batch_size):
            batch = valid_texts[i:i + batch_size]

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
        for idx, embedding in zip(valid_indices, all_embeddings):
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
