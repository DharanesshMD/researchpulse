"""Tests for the pipeline orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from researchpulse.config import ResearchPulseConfig
from researchpulse.pipeline.orchestrator import Pipeline, ProcessedItem, PipelineResult
from researchpulse.scrapers.models import ScrapedItem


def _make_scraped_items(count: int = 3) -> list[ScrapedItem]:
    """Create test ScrapedItem instances."""
    return [
        ScrapedItem(
            title=f"Test Item {i}",
            url=f"https://example.com/item-{i}",
            source="arxiv",
            content=f"This is the content of test item {i}. " * 20,
            published_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
            tags=["test", "ai"],
        )
        for i in range(count)
    ]


class TestProcessedItem:
    """Test ProcessedItem data class."""

    def test_to_dict(self):
        item = ProcessedItem(
            title="Test",
            url="https://example.com",
            source="arxiv",
            summary="A summary",
            topic="AI agents",
            relevance_score=0.9,
        )
        d = item.to_dict()
        assert d["title"] == "Test"
        assert d["topic"] == "AI agents"
        assert d["relevance_score"] == 0.9


class TestPipelineResult:
    """Test PipelineResult data class."""

    def test_success_with_stored(self):
        r = PipelineResult(total_stored=5)
        assert r.success is True

    def test_success_with_no_input(self):
        r = PipelineResult(total_input=0)
        assert r.success is True

    def test_failure_with_errors(self):
        r = PipelineResult(total_stored=0, errors=["something failed"])
        assert r.success is False


class TestPipeline:
    """Test the pipeline orchestrator with mocked components."""

    @pytest.fixture
    def pipeline(self) -> Pipeline:
        """Create a pipeline with all components mocked."""
        config = ResearchPulseConfig()
        p = Pipeline(config)

        # Mock the embedder
        p.embedder = AsyncMock()
        p.embedder.embed_batch = AsyncMock(return_value=[
            [1.0, 0.0, 0.0] + [0.0] * 1533,
            [0.0, 1.0, 0.0] + [0.0] * 1533,
            [0.0, 0.0, 1.0] + [0.0] * 1533,
        ])
        p.embedder.dimensions = 1536

        # Mock the summarizer
        p.summarizer = AsyncMock()
        p.summarizer.summarize_batch = AsyncMock(return_value=[
            {"summary": "• Point 1\n• Point 2\n• Point 3", "entities": ["AI"], "key_findings": ["Finding"]},
            {"summary": "• A\n• B\n• C", "entities": ["ML"], "key_findings": ["Result"]},
            {"summary": "• X\n• Y\n• Z", "entities": ["NLP"], "key_findings": ["Insight"]},
        ])

        # Mock the classifier
        p.classifier = AsyncMock()
        p.classifier.classify_batch = AsyncMock(return_value=[
            {"topic": "AI agents", "confidence": 0.9, "relevance_score": 0.85, "reasoning": "test"},
            {"topic": "Large language models", "confidence": 0.8, "relevance_score": 0.7, "reasoning": "test"},
            {"topic": "NLP", "confidence": 0.7, "relevance_score": 0.6, "reasoning": "test"},
        ])

        return p

    @pytest.mark.asyncio
    async def test_full_pipeline(self, pipeline: Pipeline):
        """Should run all pipeline steps and return results."""
        items = _make_scraped_items(3)
        processed, result = await pipeline.process(items)

        assert result.total_input == 3
        assert result.total_chunks > 0
        assert result.total_embedded == 3
        assert result.total_after_dedup == 3
        assert result.total_summarized == 3
        assert result.total_classified == 3
        assert len(result.errors) == 0

        assert len(processed) == 3
        assert processed[0].summary != ""
        assert processed[0].topic == "AI agents"
        assert processed[0].relevance_score == 0.85

    @pytest.mark.asyncio
    async def test_pipeline_skip_all(self, pipeline: Pipeline):
        """Should handle skipping all optional steps."""
        items = _make_scraped_items(2)
        processed, result = await pipeline.process(
            items,
            skip_summary=True,
            skip_classify=True,
            skip_dedup=True,
            skip_embed=True,
        )

        assert result.total_input == 2
        assert result.total_embedded == 0
        assert result.total_summarized == 0
        assert result.total_classified == 0
        assert len(processed) == 2

    @pytest.mark.asyncio
    async def test_pipeline_empty_input(self, pipeline: Pipeline):
        """Empty input should return empty results."""
        processed, result = await pipeline.process([])
        assert result.total_input == 0
        assert result.success is True
        assert processed == []

    @pytest.mark.asyncio
    async def test_pipeline_embedding_failure(self, pipeline: Pipeline):
        """Should handle embedding failures gracefully."""
        pipeline.embedder.embed_batch = AsyncMock(side_effect=Exception("API down"))

        # Adjust summarizer and classifier mocks for 2 items
        pipeline.summarizer.summarize_batch = AsyncMock(return_value=[
            {"summary": "• A\n• B\n• C", "entities": ["X"], "key_findings": ["Y"]},
            {"summary": "• D\n• E\n• F", "entities": ["Z"], "key_findings": ["W"]},
        ])
        pipeline.classifier.classify_batch = AsyncMock(return_value=[
            {"topic": "AI agents", "confidence": 0.9, "relevance_score": 0.8, "reasoning": "t"},
            {"topic": "NLP", "confidence": 0.7, "relevance_score": 0.6, "reasoning": "t"},
        ])

        items = _make_scraped_items(2)
        processed, result = await pipeline.process(items)

        assert result.total_embedded == 0
        assert len(result.errors) == 1
        assert "Embedding failed" in result.errors[0]
        # Pipeline should still continue with summarization and classification
        assert result.total_summarized == 2
        assert result.total_classified == 2

    @pytest.mark.asyncio
    async def test_pipeline_converts_scraped_items(self, pipeline: Pipeline):
        """ScrapedItems should be properly converted to ProcessedItems."""
        items = [
            ScrapedItem(
                title="My Paper",
                url="https://arxiv.org/abs/123",
                source="arxiv",
                content="Abstract text here.",
                tags=["cs.AI", "cs.LG"],
                published_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
            )
        ]

        # Adjust mocks for single item
        pipeline.embedder.embed_batch = AsyncMock(return_value=[[0.1] * 1536])
        pipeline.summarizer.summarize_batch = AsyncMock(return_value=[
            {"summary": "test", "entities": ["E"], "key_findings": ["F"]},
        ])
        pipeline.classifier.classify_batch = AsyncMock(return_value=[
            {"topic": "AI agents", "confidence": 0.9, "relevance_score": 0.8, "reasoning": "r"},
        ])

        processed, result = await pipeline.process(items)

        assert len(processed) == 1
        p = processed[0]
        assert p.title == "My Paper"
        assert p.url == "https://arxiv.org/abs/123"
        assert p.source == "arxiv"
        assert p.tags == "cs.AI,cs.LG"
        assert p.published_at == "2024-06-01T00:00:00+00:00"
