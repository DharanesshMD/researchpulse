"""Tests for the semantic deduplicator."""

from __future__ import annotations

import pytest

from researchpulse.pipeline.deduplicator import (
    SemanticDeduplicator,
    _cosine_similarity,
    DuplicateGroup,
)


class TestCosineSimilarity:
    """Test the cosine similarity utility."""

    def test_identical_vectors(self):
        assert _cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert _cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        assert _cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)

    def test_similar_vectors(self):
        sim = _cosine_similarity([1, 1, 0], [1, 1, 0.1])
        assert sim > 0.99

    def test_empty_vectors(self):
        assert _cosine_similarity([], []) == 0.0

    def test_zero_vector(self):
        assert _cosine_similarity([0, 0, 0], [1, 2, 3]) == 0.0

    def test_different_lengths(self):
        assert _cosine_similarity([1, 2], [1, 2, 3]) == 0.0


class TestSemanticDeduplicator:
    """Test the semantic deduplicator."""

    @pytest.fixture
    def dedup(self) -> SemanticDeduplicator:
        return SemanticDeduplicator(similarity_threshold=0.95)

    @pytest.mark.asyncio
    async def test_no_duplicates(self, dedup: SemanticDeduplicator):
        """Distinct embeddings should not be grouped."""
        items = [
            {"title": "A", "content": "About AI", "source": "arxiv"},
            {"title": "B", "content": "About cooking", "source": "news"},
        ]
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ]
        groups = await dedup.find_duplicates(items, embeddings)
        assert len(groups) == 0

    @pytest.mark.asyncio
    async def test_finds_duplicates(self, dedup: SemanticDeduplicator):
        """Nearly identical embeddings should be grouped."""
        items = [
            {"title": "A", "content": "AI paper from arxiv", "source": "arxiv"},
            {"title": "B", "content": "Same AI paper on HN", "source": "news"},
            {"title": "C", "content": "Unrelated", "source": "reddit"},
        ]
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.999, 0.001, 0.0],  # Very similar to first
            [0.0, 1.0, 0.0],      # Different
        ]
        groups = await dedup.find_duplicates(items, embeddings)
        assert len(groups) == 1
        assert set(groups[0].indices) == {0, 1}

    @pytest.mark.asyncio
    async def test_deduplicate_removes_lower_quality(self, dedup: SemanticDeduplicator):
        """Dedup should keep the higher-quality version."""
        items = [
            {"title": "A", "content": "X" * 500, "source": "arxiv"},     # Higher quality (longer, arxiv)
            {"title": "B", "content": "X" * 50, "source": "reddit"},      # Lower quality
            {"title": "C", "content": "Different", "source": "github"},
        ]
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.999, 0.001, 0.0],
            [0.0, 1.0, 0.0],
        ]
        result = await dedup.deduplicate(items, embeddings)
        assert len(result) == 2
        # Should keep the arxiv one and the unique github one
        sources = [r["source"] for r in result]
        assert "arxiv" in sources
        assert "github" in sources
        assert "reddit" not in sources

    @pytest.mark.asyncio
    async def test_deduplicate_no_items(self, dedup: SemanticDeduplicator):
        result = await dedup.deduplicate([], [])
        assert result == []

    @pytest.mark.asyncio
    async def test_deduplicate_single_item(self, dedup: SemanticDeduplicator):
        items = [{"title": "A", "content": "text", "source": "arxiv"}]
        embeddings = [[1.0, 0.0, 0.0]]
        result = await dedup.deduplicate(items, embeddings)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_mismatched_lengths_raises(self, dedup: SemanticDeduplicator):
        with pytest.raises(ValueError, match="same length"):
            await dedup.find_duplicates(
                [{"title": "A"}],
                [[1.0], [2.0]],
            )

    def test_pick_primary_prefers_longer_content(self, dedup: SemanticDeduplicator):
        items = [
            {"content": "short", "source": "news"},
            {"content": "x" * 1000, "source": "news"},
        ]
        assert dedup._pick_primary(items, [0, 1]) == 1

    def test_pick_primary_prefers_arxiv(self, dedup: SemanticDeduplicator):
        items = [
            {"content": "text", "source": "reddit"},
            {"content": "text", "source": "arxiv"},
        ]
        assert dedup._pick_primary(items, [0, 1]) == 1
