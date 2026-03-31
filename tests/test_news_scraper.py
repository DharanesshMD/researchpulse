"""Tests for the News/RSS scraper."""

from __future__ import annotations

import httpx
import pytest
import respx

from researchpulse.config import ResearchPulseConfig
from researchpulse.scrapers.news_scraper import NewsScraper


MOCK_RSS_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <description>A test RSS feed</description>
    <item>
      <title>Breaking: New AI Model Released</title>
      <link>https://example.com/article1</link>
      <description>A new AI model has been released that outperforms GPT-4.</description>
      <pubDate>Mon, 15 Jan 2024 12:00:00 GMT</pubDate>
      <category>AI</category>
      <category>LLM</category>
    </item>
    <item>
      <title>Guide to RAG Systems</title>
      <link>https://example.com/article2</link>
      <description>&lt;p&gt;Learn how to build &lt;b&gt;RAG&lt;/b&gt; systems.&lt;/p&gt;</description>
      <pubDate>Tue, 16 Jan 2024 09:00:00 GMT</pubDate>
      <author>John Doe</author>
    </item>
    <item>
      <title>Untitled Article</title>
      <link>https://example.com/article3</link>
    </item>
  </channel>
</rss>
"""


class TestNewsScraper:
    """Test News/RSS scraper functionality."""

    @pytest.fixture
    def scraper(self, sample_config: ResearchPulseConfig) -> NewsScraper:
        # Ensure the config has a test feed
        from researchpulse.config import NewsFeedEntry
        sample_config.scraping.sources.news.feeds = [
            NewsFeedEntry(url="https://example.com/feed.xml", name="Test Feed")
        ]
        return NewsScraper(sample_config)

    @respx.mock
    @pytest.mark.asyncio
    async def test_scrape_rss_feed(self, scraper: NewsScraper):
        """Should parse RSS feed and return ScrapedItem instances."""
        # Mock the feed URL from config
        respx.get(url__regex=r".*").mock(
            return_value=httpx.Response(200, text=MOCK_RSS_FEED)
        )

        items = await scraper.scrape()

        assert len(items) == 3
        assert items[0].title == "Breaking: New AI Model Released"
        assert items[0].source == "news"
        assert items[0].url == "https://example.com/article1"
        assert "AI" in items[0].tags

    @respx.mock
    @pytest.mark.asyncio
    async def test_html_stripping(self, scraper: NewsScraper):
        """Should strip HTML tags from content."""
        respx.get(url__regex=r".*").mock(
            return_value=httpx.Response(200, text=MOCK_RSS_FEED)
        )

        items = await scraper.scrape()

        # Second article has HTML in description
        rag_article = items[1]
        assert "<p>" not in rag_article.content
        assert "<b>" not in rag_article.content
        assert "RAG" in rag_article.content

    @respx.mock
    @pytest.mark.asyncio
    async def test_date_parsing(self, scraper: NewsScraper):
        """Should parse published dates correctly."""
        respx.get(url__regex=r".*").mock(
            return_value=httpx.Response(200, text=MOCK_RSS_FEED)
        )

        items = await scraper.scrape()

        assert items[0].published_at is not None
        assert items[0].published_at.year == 2024
        assert items[0].published_at.month == 1
        assert items[0].published_at.day == 15

    @respx.mock
    @pytest.mark.asyncio
    async def test_feed_fetch_failure(self, scraper: NewsScraper):
        """Should handle feed fetch failures gracefully."""
        respx.get(url__regex=r".*").mock(
            return_value=httpx.Response(500)
        )

        items = await scraper.scrape()
        assert items == []

    @pytest.mark.asyncio
    async def test_scrape_disabled(self, sample_config: ResearchPulseConfig):
        """Disabled scraper should return empty list."""
        sample_config.scraping.sources.news.enabled = False
        scraper = NewsScraper(sample_config)
        items = await scraper.scrape()
        assert items == []

    def test_strip_html_static(self):
        """Test HTML stripping utility."""
        assert NewsScraper._strip_html("<p>Hello <b>world</b></p>") == "Hello world"
        assert NewsScraper._strip_html("No tags here") == "No tags here"
        assert NewsScraper._strip_html("  Multiple   spaces  ") == "Multiple spaces"
