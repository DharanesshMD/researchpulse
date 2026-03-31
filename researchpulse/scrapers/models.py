"""
Scraped item dataclass — the universal interchange format between scrapers and storage.

All scrapers produce ScrapedItem instances. The storage layer converts these
to the appropriate SQLModel table type (Paper, Repository, NewsArticle, RedditPost).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ScrapedItem:
    """
    Source-agnostic representation of a scraped research item.

    Every scraper outputs a list of ScrapedItem instances.
    Extra source-specific fields go in the `extra` dict.
    """

    title: str
    url: str
    source: str  # "arxiv", "github", "news", "reddit"
    content: str = ""
    published_at: datetime | None = None
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.source}] {self.title} ({self.url})"

    def __repr__(self) -> str:
        return f"ScrapedItem(source={self.source!r}, title={self.title!r})"
