"""
Embedding generator for research content (Phase 2).

Will generate vector embeddings using configurable models
(OpenAI ada, Anthropic, or local models).
"""

from __future__ import annotations


class EmbeddingGenerator:
    """Generate embeddings for text chunks."""

    def __init__(self, model: str = "text-embedding-3-small") -> None:
        self.model = model

    async def embed(self, text: str) -> list[float]:
        """Generate an embedding for a single text."""
        raise NotImplementedError("Embedding generation is implemented in Phase 2")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        raise NotImplementedError("Embedding generation is implemented in Phase 2")
