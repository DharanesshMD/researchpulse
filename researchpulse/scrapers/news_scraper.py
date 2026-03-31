"""
News / RSS feed scraper — parses RSS feeds and optionally extracts full article text.

Uses `feedparser` for RSS parsing and optionally `crawl4ai` for full-text extraction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser

from researchpulse.config import ResearchPulseConfig
from researchpulse.scrapers.base import BaseScraper
from researchpulse.scrapers.models import ScrapedItem


class NewsScraper(BaseScraper):
    """Scrape news articles from RSS feeds."""

    source_name = "news"

    def __init__(self, config: ResearchPulseConfig, **kwargs: Any) -> None:
        super().__init__(config, rate_limit=2.0, **kwargs)
        self.news_config = config.scraping.sources.news

    async def scrape(self) -> list[ScrapedItem]:
        """Fetch and parse all configured RSS feeds."""
        if not self.news_config.enabled:
            self.logger.info("News scraper is disabled")
            return []

        items: list[ScrapedItem] = []

        for feed_entry in self.news_config.feeds:
            try:
                feed_items = await self._parse_feed(
                    feed_url=feed_entry.url,
                    feed_name=feed_entry.name or feed_entry.url,
                )
                items.extend(feed_items)
            except Exception as e:
                self.logger.warning(
                    "Failed to parse feed",
                    feed_url=feed_entry.url,
                    feed_name=feed_entry.name,
                    error=str(e),
                )

        return items

    async def _parse_feed(self, feed_url: str, feed_name: str) -> list[ScrapedItem]:
        """Parse a single RSS feed and return ScrapedItem instances."""
        self.logger.info("Fetching feed", feed_url=feed_url, feed_name=feed_name)

        # Fetch the raw RSS XML
        response = await self._get(feed_url)
        raw_xml = response.text

        # Parse with feedparser
        feed = feedparser.parse(raw_xml)

        if feed.bozo and not feed.entries:
            self.logger.warning("Feed parse error", feed_url=feed_url, error=str(feed.bozo_exception))
            return []

        items: list[ScrapedItem] = []
        max_results = self.news_config.max_results_per_feed

        for entry in feed.entries[:max_results]:
            try:
                item = self._entry_to_item(entry, feed_name, feed_url)
                items.append(item)
            except Exception as e:
                self.logger.warning(
                    "Failed to parse feed entry",
                    title=getattr(entry, "title", "unknown"),
                    error=str(e),
                )

        self.logger.info(
            "Feed parsed",
            feed_name=feed_name,
            items_count=len(items),
        )

        return items

    def _entry_to_item(
        self,
        entry: Any,
        feed_name: str,
        feed_url: str,
    ) -> ScrapedItem:
        """Convert a feedparser entry to a ScrapedItem."""
        title = getattr(entry, "title", "Untitled")
        link = getattr(entry, "link", "")

        # Extract content — prefer summary, fall back to content
        content = ""
        if hasattr(entry, "summary"):
            content = entry.summary
        elif hasattr(entry, "content") and entry.content:
            content = entry.content[0].get("value", "")

        # Strip HTML tags (basic)
        content = self._strip_html(content)

        # Parse published date
        published_at = self._parse_date(entry)

        # Tags from categories
        tags: list[str] = []
        if hasattr(entry, "tags"):
            tags = [tag.get("term", "") for tag in entry.tags if tag.get("term")]

        # Author
        author = getattr(entry, "author", None)

        return ScrapedItem(
            title=title,
            url=link,
            source="news",
            content=content,
            published_at=published_at,
            tags=tags,
            extra={
                "feed_name": feed_name,
                "feed_url": feed_url,
                "author": author,
                "full_text": None,  # Populated by crawl4ai in Phase 2
            },
        )

    def _parse_date(self, entry: Any) -> datetime | None:
        """Try to parse a published date from a feed entry."""
        for attr in ("published", "updated", "created"):
            date_str = getattr(entry, attr, None)
            if date_str:
                try:
                    dt = parsedate_to_datetime(date_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except (ValueError, TypeError):
                    pass

        # Try feedparser's parsed time tuples
        for attr in ("published_parsed", "updated_parsed"):
            time_struct = getattr(entry, attr, None)
            if time_struct:
                try:
                    from calendar import timegm

                    timestamp = timegm(time_struct)
                    return datetime.fromtimestamp(timestamp, tz=timezone.utc)
                except (ValueError, TypeError, OverflowError):
                    pass

        return None

    @staticmethod
    def _strip_html(text: str) -> str:
        """Basic HTML tag stripping."""
        import re

        clean = re.sub(r"<[^>]+>", "", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean
