"""Tests for the GitHub scraper."""

from __future__ import annotations

import base64
import json

import httpx
import pytest
import respx

from researchpulse.config import ResearchPulseConfig
from researchpulse.scrapers.github_scraper import GitHubScraper


MOCK_SEARCH_RESPONSE = {
    "total_count": 2,
    "items": [
        {
            "full_name": "owner/repo-1",
            "html_url": "https://github.com/owner/repo-1",
            "description": "A great LLM tool",
            "language": "Python",
            "stargazers_count": 500,
            "forks_count": 50,
            "open_issues_count": 10,
            "topics": ["llm", "ai"],
            "created_at": "2023-06-01T00:00:00Z",
            "pushed_at": "2024-01-15T00:00:00Z",
        },
        {
            "full_name": "owner/repo-2",
            "html_url": "https://github.com/owner/repo-2",
            "description": "Another ML project",
            "language": "Rust",
            "stargazers_count": 200,
            "forks_count": 20,
            "open_issues_count": 5,
            "topics": ["machine-learning"],
            "created_at": "2023-08-01T00:00:00Z",
            "pushed_at": "2024-01-10T00:00:00Z",
        },
    ],
}

MOCK_README_RESPONSE = {
    "content": base64.b64encode(b"# Repo 1\n\nThis is a great project.").decode(),
    "encoding": "base64",
}


class TestGitHubScraper:
    """Test GitHub scraper functionality."""

    @pytest.fixture
    def scraper(self, sample_config: ResearchPulseConfig) -> GitHubScraper:
        return GitHubScraper(sample_config)

    def test_build_queries_default(self, scraper: GitHubScraper):
        """Default config (no topics) should build a fallback query."""
        queries = scraper._build_queries()
        assert len(queries) > 0
        # Default has no topics/keywords → fallback query with stars filter
        assert any("stars:>=" in q for q in queries)

    def test_build_queries_with_topics(self, sample_config: ResearchPulseConfig):
        """Config with topics should produce topic-based queries."""
        sample_config.scraping.sources.github.topics = ["llm", "rag"]
        scraper = GitHubScraper(sample_config)
        queries = scraper._build_queries()
        assert any("topic:" in q for q in queries)

    @respx.mock
    @pytest.mark.asyncio
    async def test_scrape_returns_items(self, scraper: GitHubScraper):
        """Scraping should return ScrapedItem instances."""
        # Mock search API
        respx.get("https://api.github.com/search/repositories").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH_RESPONSE)
        )
        # Mock README API
        respx.get(url__regex=r".*/readme$").mock(
            return_value=httpx.Response(200, json=MOCK_README_RESPONSE)
        )

        items = await scraper.scrape()

        assert len(items) >= 1
        assert items[0].source == "github"
        assert items[0].extra["stars"] == 500

    @respx.mock
    @pytest.mark.asyncio
    async def test_scrape_deduplicates(self, scraper: GitHubScraper):
        """Same repo appearing in multiple queries should not be duplicated."""
        # Two queries returning the same repo
        respx.get("https://api.github.com/search/repositories").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH_RESPONSE)
        )
        respx.get(url__regex=r".*/readme$").mock(
            return_value=httpx.Response(200, json=MOCK_README_RESPONSE)
        )

        items = await scraper.scrape()
        urls = [item.url for item in items]
        # No duplicate URLs
        assert len(urls) == len(set(urls))

    @pytest.mark.asyncio
    async def test_scrape_disabled(self, sample_config: ResearchPulseConfig):
        """Disabled scraper should return empty list."""
        sample_config.scraping.sources.github.enabled = False
        scraper = GitHubScraper(sample_config)
        items = await scraper.scrape()
        assert items == []

    @respx.mock
    @pytest.mark.asyncio
    async def test_readme_fetch_failure(self, scraper: GitHubScraper):
        """Should handle README fetch failures gracefully."""
        respx.get("https://api.github.com/search/repositories").mock(
            return_value=httpx.Response(200, json=MOCK_SEARCH_RESPONSE)
        )
        # README returns 404
        respx.get(url__regex=r".*/readme$").mock(
            return_value=httpx.Response(404)
        )

        items = await scraper.scrape()
        # Should still return items even without README
        assert len(items) >= 1
