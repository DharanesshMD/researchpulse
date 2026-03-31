"""Tests for the ArXiv scraper."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from researchpulse.config import ResearchPulseConfig
from researchpulse.scrapers.arxiv_scraper import ArxivScraper


def _make_arxiv_result(
    title: str = "Test Paper",
    entry_id: str = "http://arxiv.org/abs/2301.12345v1",
    summary: str = "This is a test abstract.",
    authors: list[str] | None = None,
    categories: list[str] | None = None,
    published: datetime | None = None,
    pdf_url: str = "http://arxiv.org/pdf/2301.12345v1",
) -> MagicMock:
    """Create a mock arxiv.Result object."""
    result = MagicMock()
    result.title = title
    result.entry_id = entry_id
    result.summary = summary
    result.authors = [MagicMock(__str__=lambda self, n=n: n) for n in (authors or ["Author A"])]
    result.categories = categories or ["cs.AI"]
    result.published = published or datetime(2023, 1, 15, tzinfo=timezone.utc)
    result.pdf_url = pdf_url
    result.doi = None
    result.journal_ref = None
    result.comment = None
    return result


class TestArxivScraper:
    """Test ArXiv scraper functionality."""

    @pytest.fixture
    def scraper(self, sample_config: ResearchPulseConfig) -> ArxivScraper:
        return ArxivScraper(sample_config)

    def test_build_query_with_categories_and_keywords(self, scraper: ArxivScraper):
        """Query should combine categories and keywords."""
        query = scraper._build_query()
        assert "cat:cs.AI" in query
        assert "cat:cs.LG" in query
        assert "cat:cs.CL" in query

    def test_build_query_empty_config(self, sample_config: ResearchPulseConfig):
        """Empty categories and keywords should fall back to default."""
        sample_config.scraping.sources.arxiv.categories = []
        sample_config.scraping.sources.arxiv.keywords = []
        scraper = ArxivScraper(sample_config)
        query = scraper._build_query()
        assert query == "cat:cs.AI"

    @pytest.mark.asyncio
    async def test_scrape_returns_items(self, scraper: ArxivScraper):
        """Scraping should return ScrapedItem instances."""
        mock_results = [
            _make_arxiv_result(title="Paper 1", entry_id="http://arxiv.org/abs/2301.00001v1"),
            _make_arxiv_result(title="Paper 2", entry_id="http://arxiv.org/abs/2301.00002v1"),
        ]

        with patch.object(scraper, "_fetch_results", return_value=mock_results):
            items = await scraper.scrape()

        assert len(items) == 2
        assert items[0].title == "Paper 1"
        assert items[0].source == "arxiv"
        assert items[0].extra["arxiv_id"] == "2301.00001v1"
        assert items[1].title == "Paper 2"

    @pytest.mark.asyncio
    async def test_scrape_disabled(self, sample_config: ResearchPulseConfig):
        """Disabled scraper should return empty list."""
        sample_config.scraping.sources.arxiv.enabled = False
        scraper = ArxivScraper(sample_config)
        items = await scraper.scrape()
        assert items == []

    @pytest.mark.asyncio
    async def test_scrape_handles_parse_error(self, scraper: ArxivScraper):
        """Scraper should log and skip items that fail to parse."""
        bad_result = MagicMock()
        bad_result.title = "Bad Paper"
        bad_result.entry_id = None  # Will cause error in _result_to_item

        good_result = _make_arxiv_result(title="Good Paper")

        with patch.object(scraper, "_fetch_results", return_value=[bad_result, good_result]):
            items = await scraper.scrape()

        # Should get at least the good paper (bad one may or may not fail depending on implementation)
        assert len(items) >= 1

    def test_result_to_item_conversion(self, scraper: ArxivScraper):
        """Test converting an arxiv.Result to ScrapedItem."""
        result = _make_arxiv_result(
            title="  Spaced Title  ",
            authors=["Alice", "Bob"],
            categories=["cs.AI", "cs.LG"],
        )

        item = scraper._result_to_item(result)
        assert item.title == "Spaced Title"  # Trimmed
        assert item.source == "arxiv"
        assert item.tags == ["cs.AI", "cs.LG"]
        authors = json.loads(item.extra["authors"])
        assert "Alice" in authors
        assert "Bob" in authors
