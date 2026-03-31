"""Tests for the embedding generator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from researchpulse.pipeline.embedder import EmbeddingGenerator


def _mock_embedding_response(embeddings: list[list[float]]):
    """Create a mock OpenAI embedding response."""
    response = MagicMock()
    response.data = [
        MagicMock(embedding=emb, index=i)
        for i, emb in enumerate(embeddings)
    ]
    return response


class TestEmbeddingGenerator:
    """Test embedding generation with mocked OpenAI API."""

    @pytest.fixture
    def generator(self) -> EmbeddingGenerator:
        gen = EmbeddingGenerator(model="text-embedding-3-small", api_key="test-key")
        return gen

    @pytest.mark.asyncio
    async def test_embed_single(self, generator: EmbeddingGenerator):
        """Should return an embedding vector for a single text."""
        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(
            return_value=_mock_embedding_response([[0.1, 0.2, 0.3]])
        )
        generator._client = mock_client

        result = await generator.embed("test text")
        assert result == [0.1, 0.2, 0.3]
        mock_client.embeddings.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_empty_text(self, generator: EmbeddingGenerator):
        """Empty text should return zero vector."""
        result = await generator.embed("")
        assert len(result) == generator.dimensions
        assert all(v == 0.0 for v in result)

    @pytest.mark.asyncio
    async def test_embed_batch(self, generator: EmbeddingGenerator):
        """Should return embeddings for a batch of texts."""
        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(
            return_value=_mock_embedding_response([
                [0.1, 0.2, 0.3],
                [0.4, 0.5, 0.6],
            ])
        )
        generator._client = mock_client

        results = await generator.embed_batch(["text one", "text two"])
        assert len(results) == 2
        assert results[0] == [0.1, 0.2, 0.3]
        assert results[1] == [0.4, 0.5, 0.6]

    @pytest.mark.asyncio
    async def test_embed_batch_with_empties(self, generator: EmbeddingGenerator):
        """Empty texts in batch should get zero vectors."""
        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(
            return_value=_mock_embedding_response([[0.1, 0.2, 0.3]])
        )
        generator._client = mock_client

        results = await generator.embed_batch(["real text", "", "  "])
        assert len(results) == 3
        assert results[0] == [0.1, 0.2, 0.3]
        assert all(v == 0.0 for v in results[1])  # Empty
        assert all(v == 0.0 for v in results[2])  # Whitespace-only

    @pytest.mark.asyncio
    async def test_embed_batch_empty_list(self, generator: EmbeddingGenerator):
        """Empty list should return empty list."""
        results = await generator.embed_batch([])
        assert results == []

    def test_dimensions(self):
        gen_small = EmbeddingGenerator(model="text-embedding-3-small")
        assert gen_small.dimensions == 1536

        gen_large = EmbeddingGenerator(model="text-embedding-3-large")
        assert gen_large.dimensions == 3072
