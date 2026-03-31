"""
Qdrant vector store client wrapper (Phase 2 stub).

Will provide embedding storage and similarity search for RAG.
"""

from __future__ import annotations


class VectorStore:
    """Qdrant vector store wrapper — implemented in Phase 2."""

    def __init__(self, url: str = "http://localhost:6333", collection_name: str = "research_items"):
        self.url = url
        self.collection_name = collection_name

    async def store_embeddings(self, items: list, embeddings: list) -> None:
        """Store item embeddings in Qdrant."""
        raise NotImplementedError("Vector store is implemented in Phase 2")

    async def search(self, query_embedding: list[float], top_k: int = 10) -> list:
        """Search for similar items by embedding."""
        raise NotImplementedError("Vector store is implemented in Phase 2")

    async def delete(self, ids: list[str]) -> None:
        """Delete items from the vector store."""
        raise NotImplementedError("Vector store is implemented in Phase 2")
