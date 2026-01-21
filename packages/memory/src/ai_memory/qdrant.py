"""
Qdrant vector database client for semantic search.
"""

from typing import Any
from uuid import uuid4

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams

from ai_core import (
    QdrantSettings,
    StorageError,
    get_logger,
    get_settings,
    memory_operation_duration_seconds,
    memory_operations_total,
)

from .embeddings import EMBEDDING_DIMENSION, EmbeddingService, get_embedding_service

logger = get_logger(__name__)


class QdrantStore:
    """
    Qdrant vector store for semantic memory.

    Provides:
    - Collection management
    - Vector storage and retrieval
    - Semantic search with filtering
    """

    def __init__(
        self,
        collection_name: str,
        settings: QdrantSettings | None = None,
        embedding_service: EmbeddingService | None = None,
    ):
        self._collection_name = collection_name
        self._settings = settings or get_settings().qdrant
        self._embedding_service = embedding_service or get_embedding_service()
        self._client: AsyncQdrantClient | None = None

    async def connect(self) -> None:
        """Connect to Qdrant."""
        if self._client is not None:
            return

        logger.info(
            "Connecting to Qdrant",
            host=self._settings.host,
            port=self._settings.port,
        )

        self._client = AsyncQdrantClient(
            host=self._settings.host,
            port=self._settings.port,
            grpc_port=self._settings.grpc_port,
            api_key=self._settings.api_key.get_secret_value() or None,
            prefer_grpc=self._settings.prefer_grpc,
            https=self._settings.https,
        )

        # Ensure collection exists
        await self._ensure_collection()
        logger.info("Connected to Qdrant", collection=self._collection_name)

    async def disconnect(self) -> None:
        """Disconnect from Qdrant."""
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> AsyncQdrantClient:
        """Get Qdrant client."""
        if self._client is None:
            raise RuntimeError("Not connected to Qdrant. Call connect() first.")
        return self._client

    async def _ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        collections = await self.client.get_collections()
        exists = any(c.name == self._collection_name for c in collections.collections)

        if not exists:
            await self.client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIMENSION,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Created collection", collection=self._collection_name)

    async def upsert(
        self,
        id: str | None,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Insert or update a document.

        Args:
            id: Document ID (generated if not provided)
            text: Document text
            metadata: Additional metadata

        Returns:
            Document ID
        """
        doc_id = id or str(uuid4())
        metadata = metadata or {}

        try:
            with memory_operation_duration_seconds.labels(
                tier="warm", operation="upsert"
            ).time():
                # Generate embedding
                embedding = await self._embedding_service.generate(text)

                # Store in Qdrant
                await self.client.upsert(
                    collection_name=self._collection_name,
                    points=[
                        models.PointStruct(
                            id=doc_id,
                            vector=embedding,
                            payload={
                                "text": text,
                                **metadata,
                            },
                        )
                    ],
                )

            memory_operations_total.labels(
                tier="warm", operation="upsert", status="success"
            ).inc()
            return doc_id

        except Exception as e:
            memory_operations_total.labels(
                tier="warm", operation="upsert", status="error"
            ).inc()
            logger.error("Failed to upsert document", error=str(e))
            raise StorageError(f"Failed to upsert document: {e}", cause=e)

    async def search(
        self,
        query: str,
        limit: int = 10,
        score_threshold: float = 0.7,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Semantic search for similar documents.

        Args:
            query: Search query
            limit: Maximum results
            score_threshold: Minimum similarity score
            filter: Metadata filter

        Returns:
            List of matching documents with scores
        """
        try:
            with memory_operation_duration_seconds.labels(
                tier="warm", operation="search"
            ).time():
                # Generate query embedding
                query_embedding = await self._embedding_service.generate(query)

                # Build filter
                qdrant_filter = None
                if filter:
                    conditions = []
                    for key, value in filter.items():
                        if isinstance(value, list):
                            conditions.append(
                                models.FieldCondition(
                                    key=key,
                                    match=models.MatchAny(any=value),
                                )
                            )
                        else:
                            conditions.append(
                                models.FieldCondition(
                                    key=key,
                                    match=models.MatchValue(value=value),
                                )
                            )
                    qdrant_filter = models.Filter(must=conditions)

                # Search using query_points (qdrant-client 1.7+)
                response = await self.client.query_points(
                    collection_name=self._collection_name,
                    query=query_embedding,
                    limit=limit,
                    score_threshold=score_threshold,
                    query_filter=qdrant_filter,
                    with_payload=True,
                )

            memory_operations_total.labels(
                tier="warm", operation="search", status="success"
            ).inc()

            return [
                {
                    "id": str(point.id),
                    "score": point.score,
                    "text": point.payload.get("text", "") if point.payload else "",
                    "metadata": {
                        k: v for k, v in (point.payload or {}).items() if k != "text"
                    },
                }
                for point in response.points
            ]

        except Exception as e:
            memory_operations_total.labels(
                tier="warm", operation="search", status="error"
            ).inc()
            logger.error("Search failed", error=str(e))
            raise StorageError(f"Search failed: {e}", cause=e)

    async def delete(self, id: str) -> bool:
        """Delete a document by ID."""
        try:
            await self.client.delete(
                collection_name=self._collection_name,
                points_selector=models.PointIdsList(points=[id]),
            )
            memory_operations_total.labels(
                tier="warm", operation="delete", status="success"
            ).inc()
            return True
        except Exception as e:
            memory_operations_total.labels(
                tier="warm", operation="delete", status="error"
            ).inc()
            logger.error("Delete failed", id=id, error=str(e))
            return False

    async def get(self, id: str) -> dict[str, Any] | None:
        """Get a document by ID."""
        try:
            results = await self.client.retrieve(
                collection_name=self._collection_name,
                ids=[id],
            )
            if results:
                point = results[0]
                return {
                    "id": str(point.id),
                    "text": point.payload.get("text", ""),
                    "metadata": {
                        k: v for k, v in point.payload.items() if k != "text"
                    },
                }
            return None
        except Exception as e:
            logger.error("Get failed", id=id, error=str(e))
            return None

    async def count(self) -> int:
        """Get total document count."""
        info = await self.client.get_collection(self._collection_name)
        return info.points_count

    async def scroll(
        self,
        filter: dict[str, Any] | None = None,
        limit: int = 100,
        offset: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Scroll through all documents in the collection.

        Args:
            filter: Optional metadata filter
            limit: Number of documents per batch
            offset: Pagination offset (point ID to start after)

        Returns:
            Tuple of (documents, next_offset)
        """
        try:
            # Build filter
            qdrant_filter = None
            if filter:
                conditions = []
                for key, value in filter.items():
                    if isinstance(value, list):
                        conditions.append(
                            models.FieldCondition(
                                key=key,
                                match=models.MatchAny(any=value),
                            )
                        )
                    else:
                        conditions.append(
                            models.FieldCondition(
                                key=key,
                                match=models.MatchValue(value=value),
                            )
                        )
                qdrant_filter = models.Filter(must=conditions)

            results, next_offset = await self.client.scroll(
                collection_name=self._collection_name,
                scroll_filter=qdrant_filter,
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            documents = [
                {
                    "id": str(point.id),
                    "text": point.payload.get("text", ""),
                    "metadata": {
                        k: v for k, v in point.payload.items() if k != "text"
                    },
                }
                for point in results
            ]

            return documents, next_offset

        except Exception as e:
            logger.error("Scroll failed", error=str(e))
            raise StorageError(f"Scroll failed: {e}", cause=e)

    async def delete_batch(self, ids: list[str]) -> int:
        """Delete multiple documents by IDs."""
        if not ids:
            return 0

        try:
            await self.client.delete(
                collection_name=self._collection_name,
                points_selector=models.PointIdsList(points=ids),
            )
            memory_operations_total.labels(
                tier="warm", operation="delete_batch", status="success"
            ).inc()
            return len(ids)
        except Exception as e:
            memory_operations_total.labels(
                tier="warm", operation="delete_batch", status="error"
            ).inc()
            logger.error("Batch delete failed", count=len(ids), error=str(e))
            return 0
