"""
Qdrant vector store client wrapper.

Provides embedding storage and similarity search for RAG
using Qdrant as the vector database backend.
"""

from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from researchpulse.config import VectorStoreConfig
from researchpulse.utils.logging import get_logger

logger = get_logger("storage.vector_store")

DEFAULT_EMBEDDING_DIM = 1536  # text-embedding-3-small


class VectorStore:
    """
    Qdrant vector store wrapper.

    Stores embeddings with metadata for each research item,
    supports filtered similarity search for RAG retrieval.
    """

    def __init__(
        self,
        url: str = "http://localhost:6333",
        collection_name: str = "research_items",
        embedding_dim: int = DEFAULT_EMBEDDING_DIM,
    ) -> None:
        self.url = url
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self._client: AsyncQdrantClient | None = None

    @classmethod
    def from_config(cls, config: VectorStoreConfig, embedding_dim: int = DEFAULT_EMBEDDING_DIM) -> VectorStore:
        """Create a VectorStore from app config."""
        return cls(
            url=config.url,
            collection_name=config.collection_name,
            embedding_dim=embedding_dim,
        )

    @property
    def client(self) -> AsyncQdrantClient:
        """Lazy-initialized async Qdrant client."""
        if self._client is None:
            self._client = AsyncQdrantClient(url=self.url)
        return self._client

    async def ensure_collection(self) -> None:
        """Create the collection if it doesn't exist."""
        collections = await self.client.get_collections()
        existing = [c.name for c in collections.collections]

        if self.collection_name not in existing:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Collection created", collection=self.collection_name)
        else:
            logger.debug("Collection already exists", collection=self.collection_name)

    async def store_embeddings(
        self,
        items: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> int:
        """
        Store item embeddings in Qdrant.

        Args:
            items: List of item dicts with at least "url", "title", "source", "content" keys.
            embeddings: Corresponding embedding vectors.

        Returns:
            Number of points stored.
        """
        if len(items) != len(embeddings):
            raise ValueError(f"Items ({len(items)}) and embeddings ({len(embeddings)}) must match")

        if not items:
            return 0

        await self.ensure_collection()

        points = []
        for item, embedding in zip(items, embeddings):
            # Use a deterministic ID based on URL for idempotent upserts
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, item.get("url", str(uuid.uuid4()))))

            payload = {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "content_preview": (item.get("content", "") or "")[:500],
                "summary": item.get("summary", ""),
                "topic": item.get("topic", ""),
                "relevance_score": item.get("relevance_score", 0.0),
                "tags": item.get("tags", ""),
                "published_at": item.get("published_at", ""),
                "chunk_index": item.get("chunk_index", 0),
                "source_id": item.get("source_id", ""),
            }

            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload,
            ))

        # Upsert in batches of 100
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            await self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )

        logger.info("Embeddings stored", count=len(points), collection=self.collection_name)
        return len(points)

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        source_filter: str | None = None,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for similar items by embedding vector.

        Args:
            query_embedding: The query vector.
            top_k: Maximum results to return.
            source_filter: Optional filter by source type (arxiv, github, etc.).
            score_threshold: Optional minimum similarity score.

        Returns:
            List of dicts with "id", "score", and all payload fields.
        """
        query_filter = None
        if source_filter:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="source",
                        match=MatchValue(value=source_filter),
                    )
                ]
            )

        results = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            query_filter=query_filter,
            limit=top_k,
            score_threshold=score_threshold,
        )

        items = []
        for point in results.points:
            item = {
                "id": str(point.id),
                "score": point.score,
                **(point.payload or {}),
            }
            items.append(item)

        logger.debug("Vector search completed", results=len(items), top_k=top_k)
        return items

    async def delete(self, urls: list[str]) -> None:
        """
        Delete items from the vector store by URL.

        Args:
            urls: List of item URLs to delete.
        """
        if not urls:
            return

        point_ids = [
            str(uuid.uuid5(uuid.NAMESPACE_URL, url))
            for url in urls
        ]

        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=point_ids,
        )
        logger.info("Points deleted", count=len(point_ids))

    async def count(self) -> int:
        """Get the number of points in the collection."""
        info = await self.client.get_collection(self.collection_name)
        return info.points_count or 0

    async def close(self) -> None:
        """Close the Qdrant client connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None
