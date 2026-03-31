"""
Database models for ResearchPulse.

Uses SQLModel for both Pydantic validation and SQLAlchemy ORM.
All research content is stored in typed tables with a shared base structure.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class SourceType(str, Enum):
    """Enumeration of supported content sources."""
    ARXIV = "arxiv"
    GITHUB = "github"
    NEWS = "news"
    REDDIT = "reddit"


# ---------------------------------------------------------------------------
# Base model with shared fields
# ---------------------------------------------------------------------------

class ResearchItemBase(SQLModel):
    """Shared fields across all research item types."""

    title: str = Field(index=True)
    url: str = Field(unique=True, index=True)
    source: SourceType = Field(index=True)
    content: str = Field(default="")
    summary: Optional[str] = Field(default=None)
    tags: Optional[str] = Field(default=None, description="Comma-separated tags")
    relevance_score: Optional[float] = Field(default=None)
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    published_at: Optional[datetime] = Field(default=None)


# ---------------------------------------------------------------------------
# ArXiv Papers
# ---------------------------------------------------------------------------

class Paper(ResearchItemBase, table=True):
    """ArXiv paper metadata and abstract."""

    __tablename__ = "papers"

    id: Optional[int] = Field(default=None, primary_key=True)
    arxiv_id: str = Field(unique=True, index=True)
    authors: str = Field(default="")  # JSON-serialized list
    categories: str = Field(default="")  # Comma-separated
    pdf_url: Optional[str] = Field(default=None)
    doi: Optional[str] = Field(default=None)
    journal_ref: Optional[str] = Field(default=None)
    comment: Optional[str] = Field(default=None)


# ---------------------------------------------------------------------------
# GitHub Repositories
# ---------------------------------------------------------------------------

class Repository(ResearchItemBase, table=True):
    """GitHub repository metadata."""

    __tablename__ = "repositories"

    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str = Field(unique=True, index=True)  # owner/repo
    description: Optional[str] = Field(default=None)
    language: Optional[str] = Field(default=None)
    stars: int = Field(default=0)
    forks: int = Field(default=0)
    open_issues: int = Field(default=0)
    topics: Optional[str] = Field(default=None)  # Comma-separated
    readme_content: Optional[str] = Field(default=None)
    last_pushed_at: Optional[datetime] = Field(default=None)


# ---------------------------------------------------------------------------
# News Articles
# ---------------------------------------------------------------------------

class NewsArticle(ResearchItemBase, table=True):
    """News article or blog post from RSS feeds."""

    __tablename__ = "news_articles"

    id: Optional[int] = Field(default=None, primary_key=True)
    feed_name: str = Field(default="")
    feed_url: str = Field(default="")
    author: Optional[str] = Field(default=None)
    full_text: Optional[str] = Field(default=None)


# ---------------------------------------------------------------------------
# Reddit Posts
# ---------------------------------------------------------------------------

class RedditPost(ResearchItemBase, table=True):
    """Reddit post from monitored subreddits."""

    __tablename__ = "reddit_posts"

    id: Optional[int] = Field(default=None, primary_key=True)
    reddit_id: str = Field(unique=True, index=True)
    subreddit: str = Field(index=True)
    author: Optional[str] = Field(default=None)
    score: int = Field(default=0)
    num_comments: int = Field(default=0)
    selftext: Optional[str] = Field(default=None)
    post_type: Optional[str] = Field(default=None)  # link, self, image, video
