"""
Generic CRUD repository with upsert support.

Provides BaseRepository[T] that all model-specific repositories inherit from.
URL-based deduplication via upsert.
"""

from __future__ import annotations

import json
from typing import Generic, TypeVar, Type, Sequence

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from researchpulse.scrapers.models import ScrapedItem
from researchpulse.storage.db_models import (
    NewsArticle,
    Paper,
    RedditPost,
    Repository,
    SourceType,
)
from researchpulse.utils.logging import get_logger

T = TypeVar("T", bound=SQLModel)
logger = get_logger("storage.repository")


class BaseRepository(Generic[T]):
    """
    Generic async CRUD repository for SQLModel tables.

    Provides create, get, list, count, and upsert operations.
    URL-based deduplication: upsert skips items with duplicate URLs.
    """

    def __init__(self, model: Type[T], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def create(self, item: T) -> T:
        """Insert a new item into the database."""
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def get_by_id(self, item_id: int) -> T | None:
        """Fetch an item by its primary key."""
        return await self.session.get(self.model, item_id)

    async def get_by_url(self, url: str) -> T | None:
        """Fetch an item by its URL (unique constraint)."""
        stmt = select(self.model).where(self.model.url == url)  # type: ignore[attr-defined]
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[T]:
        """List items with pagination."""
        stmt = (
            select(self.model)
            .offset(offset)
            .limit(limit)
            .order_by(self.model.id.desc())  # type: ignore[attr-defined]
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count(self) -> int:
        """Count total items in the table."""
        stmt = select(func.count()).select_from(self.model)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def upsert(self, item: T) -> T:
        """
        Insert or skip on URL conflict (idempotent).

        For PostgreSQL: uses ON CONFLICT DO NOTHING.
        For SQLite: catches IntegrityError.
        """
        try:
            self.session.add(item)
            await self.session.flush()
            await self.session.refresh(item)
            return item
        except Exception:
            await self.session.rollback()
            # Item already exists — fetch and return existing
            existing = await self.get_by_url(item.url)  # type: ignore[attr-defined]
            if existing:
                return existing
            raise

    async def bulk_upsert(self, items: list[T]) -> int:
        """
        Bulk insert items, skipping duplicates. Returns count of new items.
        """
        new_count = 0
        for item in items:
            existing = await self.get_by_url(item.url)  # type: ignore[attr-defined]
            if existing is None:
                self.session.add(item)
                new_count += 1

        if new_count > 0:
            await self.session.flush()

        return new_count


# ---------------------------------------------------------------------------
# Model-specific repositories
# ---------------------------------------------------------------------------


class PaperRepository(BaseRepository[Paper]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Paper, session)

    async def list_by_category(
        self, category: str, limit: int = 50
    ) -> Sequence[Paper]:
        """List papers filtered by category."""
        stmt = (
            select(Paper)
            .where(Paper.categories.contains(category))
            .limit(limit)
            .order_by(Paper.scraped_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class RepositoryRepo(BaseRepository[Repository]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Repository, session)

    async def list_by_min_stars(
        self, min_stars: int = 100, limit: int = 50
    ) -> Sequence[Repository]:
        """List repos with at least min_stars."""
        stmt = (
            select(Repository)
            .where(Repository.stars >= min_stars)
            .limit(limit)
            .order_by(Repository.stars.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class NewsArticleRepository(BaseRepository[NewsArticle]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(NewsArticle, session)

    async def list_by_feed(
        self, feed_name: str, limit: int = 50
    ) -> Sequence[NewsArticle]:
        """List articles from a specific feed."""
        stmt = (
            select(NewsArticle)
            .where(NewsArticle.feed_name == feed_name)
            .limit(limit)
            .order_by(NewsArticle.scraped_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class RedditPostRepository(BaseRepository[RedditPost]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RedditPost, session)

    async def list_by_subreddit(
        self, subreddit: str, limit: int = 50
    ) -> Sequence[RedditPost]:
        """List posts from a specific subreddit."""
        stmt = (
            select(RedditPost)
            .where(RedditPost.subreddit == subreddit)
            .limit(limit)
            .order_by(RedditPost.score.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


# ---------------------------------------------------------------------------
# ScrapedItem → SQLModel conversion
# ---------------------------------------------------------------------------


def scraped_item_to_model(item: ScrapedItem) -> Paper | Repository | NewsArticle | RedditPost:
    """
    Convert a ScrapedItem to the appropriate SQLModel instance.

    Uses the item's `source` field to determine the target model.
    Extra source-specific fields are pulled from `item.extra`.
    """
    tags_str = ",".join(item.tags) if item.tags else None

    if item.source == "arxiv":
        return Paper(
            title=item.title,
            url=item.url,
            source=SourceType.ARXIV,
            content=item.content,
            tags=tags_str,
            scraped_at=item.scraped_at,
            published_at=item.published_at,
            arxiv_id=item.extra.get("arxiv_id", ""),
            authors=item.extra.get("authors", "[]"),
            categories=item.extra.get("categories", ""),
            pdf_url=item.extra.get("pdf_url"),
            doi=item.extra.get("doi"),
            journal_ref=item.extra.get("journal_ref"),
            comment=item.extra.get("comment"),
        )

    elif item.source == "github":
        return Repository(
            title=item.title,
            url=item.url,
            source=SourceType.GITHUB,
            content=item.content,
            tags=tags_str,
            scraped_at=item.scraped_at,
            published_at=item.published_at,
            full_name=item.extra.get("full_name", item.title),
            description=item.extra.get("description"),
            language=item.extra.get("language"),
            stars=item.extra.get("stars", 0),
            forks=item.extra.get("forks", 0),
            open_issues=item.extra.get("open_issues", 0),
            topics=item.extra.get("topics"),
            readme_content=item.extra.get("readme_content"),
            last_pushed_at=item.extra.get("last_pushed_at"),
        )

    elif item.source == "news":
        return NewsArticle(
            title=item.title,
            url=item.url,
            source=SourceType.NEWS,
            content=item.content,
            tags=tags_str,
            scraped_at=item.scraped_at,
            published_at=item.published_at,
            feed_name=item.extra.get("feed_name", ""),
            feed_url=item.extra.get("feed_url", ""),
            author=item.extra.get("author"),
            full_text=item.extra.get("full_text"),
        )

    elif item.source == "reddit":
        return RedditPost(
            title=item.title,
            url=item.url,
            source=SourceType.REDDIT,
            content=item.content,
            tags=tags_str,
            scraped_at=item.scraped_at,
            published_at=item.published_at,
            reddit_id=item.extra.get("reddit_id", ""),
            subreddit=item.extra.get("subreddit", ""),
            author=item.extra.get("author"),
            score=item.extra.get("score", 0),
            num_comments=item.extra.get("num_comments", 0),
            selftext=item.extra.get("selftext"),
            post_type=item.extra.get("post_type"),
        )

    else:
        raise ValueError(f"Unknown source: {item.source}")
