"""
Reddit scraper — monitors subreddits for high-quality posts.

Uses `asyncpraw` (async fork of PRAW) for Reddit API access.
Filters by minimum score and configurable sort order.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from researchpulse.config import ResearchPulseConfig
from researchpulse.scrapers.base import BaseScraper
from researchpulse.scrapers.models import ScrapedItem


class RedditScraper(BaseScraper):
    """Scrape posts from monitored subreddits via asyncpraw."""

    source_name = "reddit"

    def __init__(self, config: ResearchPulseConfig, **kwargs: Any) -> None:
        # Reddit API rate limit: 60 requests/min
        super().__init__(config, rate_limit=1.0, **kwargs)
        self.reddit_config = config.scraping.sources.reddit

    def _create_reddit_client(self) -> Any:
        """Create an asyncpraw Reddit client."""
        import asyncpraw

        client_id = os.environ.get("REDDIT_CLIENT_ID", "")
        client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
        user_agent = os.environ.get("REDDIT_USER_AGENT", "ResearchPulse/0.1")

        if not client_id or not client_secret:
            raise ValueError(
                "Reddit credentials not found. Set REDDIT_CLIENT_ID and "
                "REDDIT_CLIENT_SECRET environment variables."
            )

        return asyncpraw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )

    async def scrape(self) -> list[ScrapedItem]:
        """Fetch posts from all configured subreddits."""
        if not self.reddit_config.enabled:
            self.logger.info("Reddit scraper is disabled")
            return []

        try:
            reddit = self._create_reddit_client()
        except ValueError as e:
            self.logger.error("Reddit client initialization failed", error=str(e))
            return []

        items: list[ScrapedItem] = []

        try:
            for subreddit_name in self.reddit_config.subreddits:
                try:
                    sub_items = await self._scrape_subreddit(reddit, subreddit_name)
                    items.extend(sub_items)
                except Exception as e:
                    self.logger.warning(
                        "Failed to scrape subreddit",
                        subreddit=subreddit_name,
                        error=str(e),
                    )
        finally:
            await reddit.close()

        return items

    async def _scrape_subreddit(
        self,
        reddit: Any,
        subreddit_name: str,
    ) -> list[ScrapedItem]:
        """Scrape posts from a single subreddit."""
        self.logger.info(
            "Scraping subreddit",
            subreddit=subreddit_name,
            sort_by=self.reddit_config.sort_by,
        )

        subreddit = await reddit.subreddit(subreddit_name)
        items: list[ScrapedItem] = []

        # Get the appropriate listing method
        listing = self._get_listing(subreddit)

        async for post in listing:
            # Filter by minimum score
            if post.score < self.reddit_config.min_score:
                continue

            try:
                item = self._post_to_item(post, subreddit_name)
                items.append(item)
            except Exception as e:
                self.logger.warning(
                    "Failed to parse Reddit post",
                    post_id=getattr(post, "id", "unknown"),
                    error=str(e),
                )

            if len(items) >= self.reddit_config.max_results:
                break

        self.logger.info(
            "Subreddit scraped",
            subreddit=subreddit_name,
            items_count=len(items),
        )

        return items

    def _get_listing(self, subreddit: Any) -> Any:
        """Get the appropriate listing generator based on config sort_by."""
        limit = self.reddit_config.max_results * 2  # Fetch extra to account for score filtering

        if self.reddit_config.sort_by == "hot":
            return subreddit.hot(limit=limit)
        elif self.reddit_config.sort_by == "new":
            return subreddit.new(limit=limit)
        elif self.reddit_config.sort_by == "top":
            return subreddit.top(
                time_filter=self.reddit_config.time_filter,
                limit=limit,
            )
        elif self.reddit_config.sort_by == "rising":
            return subreddit.rising(limit=limit)
        else:
            return subreddit.hot(limit=limit)

    def _post_to_item(self, post: Any, subreddit_name: str) -> ScrapedItem:
        """Convert a Reddit submission to a ScrapedItem."""
        # Determine post type
        if post.is_self:
            post_type = "self"
        elif hasattr(post, "is_video") and post.is_video:
            post_type = "video"
        elif hasattr(post, "post_hint") and post.post_hint == "image":
            post_type = "image"
        else:
            post_type = "link"

        # Build content from title + selftext
        content = post.selftext if post.selftext else ""

        # Parse creation time
        published_at = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)

        # Extract flair as tags
        tags: list[str] = []
        if hasattr(post, "link_flair_text") and post.link_flair_text:
            tags.append(post.link_flair_text)

        return ScrapedItem(
            title=post.title,
            url=f"https://reddit.com{post.permalink}",
            source="reddit",
            content=content,
            published_at=published_at,
            tags=tags,
            extra={
                "reddit_id": post.id,
                "subreddit": subreddit_name,
                "author": str(post.author) if post.author else "[deleted]",
                "score": post.score,
                "num_comments": post.num_comments,
                "selftext": post.selftext,
                "post_type": post_type,
            },
        )
