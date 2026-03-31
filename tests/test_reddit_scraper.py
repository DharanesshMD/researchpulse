"""Tests for the Reddit scraper."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from researchpulse.config import ResearchPulseConfig
from researchpulse.scrapers.reddit_scraper import RedditScraper


def _make_mock_post(
    post_id: str = "abc123",
    title: str = "Test Post",
    score: int = 100,
    num_comments: int = 42,
    selftext: str = "This is the post body.",
    subreddit: str = "MachineLearning",
    is_self: bool = True,
    created_utc: float = 1705305600.0,  # 2024-01-15 12:00:00 UTC
    author: str = "test_user",
    permalink: str = "/r/MachineLearning/comments/abc123/test_post/",
    flair: str | None = "Discussion",
) -> MagicMock:
    """Create a mock Reddit submission."""
    post = MagicMock()
    post.id = post_id
    post.title = title
    post.score = score
    post.num_comments = num_comments
    post.selftext = selftext
    post.is_self = is_self
    post.is_video = False
    post.post_hint = None
    post.created_utc = created_utc
    post.author = MagicMock(__str__=lambda self: author)
    post.permalink = permalink
    post.link_flair_text = flair
    return post


class TestRedditScraper:
    """Test Reddit scraper functionality."""

    @pytest.fixture
    def scraper(self, sample_config: ResearchPulseConfig) -> RedditScraper:
        return RedditScraper(sample_config)

    def test_post_to_item_conversion(self, scraper: RedditScraper):
        """Should correctly convert a Reddit post to ScrapedItem."""
        post = _make_mock_post(
            title="[D] New RLHF paper results",
            score=250,
            num_comments=80,
        )

        item = scraper._post_to_item(post, "MachineLearning")

        assert item.title == "[D] New RLHF paper results"
        assert item.source == "reddit"
        assert item.extra["score"] == 250
        assert item.extra["num_comments"] == 80
        assert item.extra["subreddit"] == "MachineLearning"
        assert "Discussion" in item.tags

    def test_post_type_detection(self, scraper: RedditScraper):
        """Should detect different post types."""
        # Self post
        self_post = _make_mock_post(is_self=True)
        item = scraper._post_to_item(self_post, "test")
        assert item.extra["post_type"] == "self"

        # Link post
        link_post = _make_mock_post(is_self=False)
        item = scraper._post_to_item(link_post, "test")
        assert item.extra["post_type"] == "link"

    @pytest.mark.asyncio
    async def test_scrape_disabled(self, sample_config: ResearchPulseConfig):
        """Disabled scraper should return empty list."""
        sample_config.scraping.sources.reddit.enabled = False
        scraper = RedditScraper(sample_config)
        items = await scraper.scrape()
        assert items == []

    @pytest.mark.asyncio
    async def test_scrape_missing_credentials(self, scraper: RedditScraper, monkeypatch):
        """Should handle missing Reddit credentials gracefully."""
        monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
        monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)

        items = await scraper.scrape()
        assert items == []

    @pytest.mark.asyncio
    async def test_scrape_with_mock_reddit(self, scraper: RedditScraper, monkeypatch):
        """Should scrape posts from mocked Reddit API."""
        monkeypatch.setenv("REDDIT_CLIENT_ID", "test_id")
        monkeypatch.setenv("REDDIT_CLIENT_SECRET", "test_secret")

        mock_posts = [
            _make_mock_post(post_id="1", title="High Score Post", score=200),
            _make_mock_post(post_id="2", title="Low Score Post", score=5),
            _make_mock_post(post_id="3", title="Medium Score Post", score=100),
        ]

        # Create mock subreddit
        mock_subreddit = AsyncMock()

        async def mock_hot(limit=None):
            for post in mock_posts:
                yield post

        mock_subreddit.hot = mock_hot

        # Create mock reddit client
        mock_reddit = AsyncMock()
        mock_reddit.subreddit = AsyncMock(return_value=mock_subreddit)
        mock_reddit.close = AsyncMock()

        with patch.object(scraper, "_create_reddit_client", return_value=mock_reddit):
            items = await scraper.scrape()

        # Should filter out low score post (min_score=50 from default config)
        assert all(item.extra["score"] >= scraper.reddit_config.min_score for item in items)
        assert any(item.title == "High Score Post" for item in items)
