"""Tests for the storage layer — database and repositories."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from researchpulse.storage.database import Database
from researchpulse.storage.db_models import (
    Paper,
    Repository,
    NewsArticle,
    RedditPost,
    SourceType,
)
from researchpulse.storage.repository import (
    PaperRepository,
    RepositoryRepo,
    NewsArticleRepository,
    RedditPostRepository,
    scraped_item_to_model,
)
from researchpulse.scrapers.models import ScrapedItem


class TestDatabase:
    """Test database connection and table creation."""

    @pytest.mark.asyncio
    async def test_create_tables(self, sqlite_db_url: str):
        """Should create all tables without error."""
        db = Database(sqlite_db_url)
        await db.create_tables()
        await db.close()

    @pytest.mark.asyncio
    async def test_session_context_manager(self, sqlite_db_url: str):
        """Should provide working async sessions."""
        db = Database(sqlite_db_url)
        await db.create_tables()

        async with db.session() as session:
            paper = Paper(
                title="Test",
                url="https://arxiv.org/abs/test",
                source=SourceType.ARXIV,
                arxiv_id="test",
            )
            session.add(paper)

        # Verify it was committed
        async with db.session() as session:
            repo = PaperRepository(session)
            count = await repo.count()
            assert count == 1

        await db.close()


class TestPaperRepository:
    """Test Paper CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_and_get(self, sqlite_db_url: str):
        db = Database(sqlite_db_url)
        await db.create_tables()

        async with db.session() as session:
            repo = PaperRepository(session)
            paper = Paper(
                title="Test Paper",
                url="https://arxiv.org/abs/2301.12345",
                source=SourceType.ARXIV,
                arxiv_id="2301.12345",
                content="Abstract text",
                categories="cs.AI,cs.LG",
            )
            created = await repo.create(paper)
            assert created.id is not None

            fetched = await repo.get_by_id(created.id)
            assert fetched is not None
            assert fetched.title == "Test Paper"

        await db.close()

    @pytest.mark.asyncio
    async def test_get_by_url(self, sqlite_db_url: str):
        db = Database(sqlite_db_url)
        await db.create_tables()

        async with db.session() as session:
            repo = PaperRepository(session)
            paper = Paper(
                title="URL Test",
                url="https://arxiv.org/abs/unique123",
                source=SourceType.ARXIV,
                arxiv_id="unique123",
            )
            await repo.create(paper)

            found = await repo.get_by_url("https://arxiv.org/abs/unique123")
            assert found is not None
            assert found.arxiv_id == "unique123"

            not_found = await repo.get_by_url("https://arxiv.org/abs/nonexistent")
            assert not_found is None

        await db.close()

    @pytest.mark.asyncio
    async def test_list_all_with_pagination(self, sqlite_db_url: str):
        db = Database(sqlite_db_url)
        await db.create_tables()

        async with db.session() as session:
            repo = PaperRepository(session)
            for i in range(5):
                paper = Paper(
                    title=f"Paper {i}",
                    url=f"https://arxiv.org/abs/{i}",
                    source=SourceType.ARXIV,
                    arxiv_id=str(i),
                )
                await repo.create(paper)

            all_papers = await repo.list_all(limit=100)
            assert len(all_papers) == 5

            page = await repo.list_all(offset=2, limit=2)
            assert len(page) == 2

        await db.close()

    @pytest.mark.asyncio
    async def test_count(self, sqlite_db_url: str):
        db = Database(sqlite_db_url)
        await db.create_tables()

        async with db.session() as session:
            repo = PaperRepository(session)
            assert await repo.count() == 0

            paper = Paper(
                title="Count Test",
                url="https://arxiv.org/abs/count",
                source=SourceType.ARXIV,
                arxiv_id="count",
            )
            await repo.create(paper)
            assert await repo.count() == 1

        await db.close()


class TestScrapedItemConversion:
    """Test converting ScrapedItem to SQLModel instances."""

    def test_arxiv_conversion(self):
        item = ScrapedItem(
            title="Test Paper",
            url="https://arxiv.org/abs/2301.12345",
            source="arxiv",
            content="Abstract",
            tags=["cs.AI", "cs.LG"],
            extra={
                "arxiv_id": "2301.12345",
                "authors": '["Author A"]',
                "categories": "cs.AI,cs.LG",
                "pdf_url": "https://arxiv.org/pdf/2301.12345",
            },
        )
        model = scraped_item_to_model(item)
        assert isinstance(model, Paper)
        assert model.arxiv_id == "2301.12345"
        assert model.tags == "cs.AI,cs.LG"

    def test_github_conversion(self):
        item = ScrapedItem(
            title="owner/repo",
            url="https://github.com/owner/repo",
            source="github",
            content="A great project",
            tags=["llm", "ai"],
            extra={
                "full_name": "owner/repo",
                "stars": 500,
                "forks": 50,
                "language": "Python",
            },
        )
        model = scraped_item_to_model(item)
        assert isinstance(model, Repository)
        assert model.stars == 500

    def test_news_conversion(self):
        item = ScrapedItem(
            title="News Article",
            url="https://example.com/article",
            source="news",
            content="Article text",
            extra={"feed_name": "Test Feed", "feed_url": "https://example.com/feed"},
        )
        model = scraped_item_to_model(item)
        assert isinstance(model, NewsArticle)
        assert model.feed_name == "Test Feed"

    def test_reddit_conversion(self):
        item = ScrapedItem(
            title="Reddit Post",
            url="https://reddit.com/r/test/123",
            source="reddit",
            content="Post body",
            extra={
                "reddit_id": "123",
                "subreddit": "test",
                "score": 200,
                "num_comments": 50,
            },
        )
        model = scraped_item_to_model(item)
        assert isinstance(model, RedditPost)
        assert model.score == 200

    def test_unknown_source_raises(self):
        item = ScrapedItem(
            title="Unknown",
            url="https://example.com",
            source="unknown_source",
        )
        with pytest.raises(ValueError, match="Unknown source"):
            scraped_item_to_model(item)
