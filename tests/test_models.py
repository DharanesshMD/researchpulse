"""Tests for database models."""

from __future__ import annotations

from datetime import datetime, timezone

from researchpulse.storage.db_models import (
    Paper,
    Repository,
    NewsArticle,
    RedditPost,
    SourceType,
)


class TestPaperModel:
    """Test Paper SQLModel."""

    def test_create_paper(self):
        paper = Paper(
            title="Test Paper",
            url="https://arxiv.org/abs/2301.12345",
            source=SourceType.ARXIV,
            content="This is an abstract.",
            arxiv_id="2301.12345",
            authors='["Author One", "Author Two"]',
            categories="cs.AI,cs.LG",
        )
        assert paper.title == "Test Paper"
        assert paper.source == SourceType.ARXIV
        assert paper.arxiv_id == "2301.12345"

    def test_paper_defaults(self):
        paper = Paper(
            title="Minimal Paper",
            url="https://arxiv.org/abs/0000.00000",
            source=SourceType.ARXIV,
            arxiv_id="0000.00000",
        )
        assert paper.content == ""
        assert paper.summary is None
        assert paper.relevance_score is None


class TestRepositoryModel:
    """Test Repository SQLModel."""

    def test_create_repository(self):
        repo = Repository(
            title="owner/repo",
            url="https://github.com/owner/repo",
            source=SourceType.GITHUB,
            full_name="owner/repo",
            stars=1000,
            forks=100,
            language="Python",
        )
        assert repo.stars == 1000
        assert repo.language == "Python"


class TestNewsArticleModel:
    """Test NewsArticle SQLModel."""

    def test_create_news_article(self):
        article = NewsArticle(
            title="Breaking News",
            url="https://example.com/article",
            source=SourceType.NEWS,
            content="Article content here.",
            feed_name="Test Feed",
            feed_url="https://example.com/feed.xml",
        )
        assert article.feed_name == "Test Feed"
        assert article.author is None


class TestRedditPostModel:
    """Test RedditPost SQLModel."""

    def test_create_reddit_post(self):
        post = RedditPost(
            title="Interesting post",
            url="https://reddit.com/r/test/comments/abc123",
            source=SourceType.REDDIT,
            reddit_id="abc123",
            subreddit="MachineLearning",
            score=500,
            num_comments=42,
        )
        assert post.subreddit == "MachineLearning"
        assert post.score == 500
