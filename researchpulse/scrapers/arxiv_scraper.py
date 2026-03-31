"""
ArXiv scraper — fetches papers by category and keyword from the ArXiv API.

Uses the `arxiv` Python package for structured API access.
Outputs ScrapedItem instances with ArXiv-specific metadata in `extra`.
"""

from __future__ import annotations

import asyncio
import json
from datetime import timezone
from typing import Any

import arxiv

from researchpulse.config import ResearchPulseConfig
from researchpulse.scrapers.base import BaseScraper
from researchpulse.scrapers.models import ScrapedItem


class ArxivScraper(BaseScraper):
    """Scrape papers from ArXiv by category and keyword."""

    source_name = "arxiv"

    def __init__(self, config: ResearchPulseConfig, **kwargs: Any) -> None:
        # ArXiv API asks for max 1 request per 3 seconds
        super().__init__(config, rate_limit=0.33, **kwargs)
        self.arxiv_config = config.scraping.sources.arxiv

    def _build_query(self) -> str:
        """Build an ArXiv API query string from config."""
        parts: list[str] = []

        # Category filters
        if self.arxiv_config.categories:
            cat_parts = [f"cat:{cat}" for cat in self.arxiv_config.categories]
            parts.append(f"({' OR '.join(cat_parts)})")

        # Keyword filters
        if self.arxiv_config.keywords:
            kw_parts = [
                f'(ti:"{kw}" OR abs:"{kw}")'
                for kw in self.arxiv_config.keywords
            ]
            parts.append(f"({' OR '.join(kw_parts)})")

        if not parts:
            return "cat:cs.AI"

        return " AND ".join(parts)

    def _get_sort_criterion(self) -> arxiv.SortCriterion:
        """Map config sort_by to arxiv.SortCriterion."""
        mapping = {
            "submitted": arxiv.SortCriterion.SubmittedDate,
            "relevance": arxiv.SortCriterion.Relevance,
            "lastUpdatedDate": arxiv.SortCriterion.LastUpdatedDate,
        }
        return mapping.get(self.arxiv_config.sort_by, arxiv.SortCriterion.SubmittedDate)

    async def scrape(self) -> list[ScrapedItem]:
        """Fetch papers from ArXiv API."""
        if not self.arxiv_config.enabled:
            self.logger.info("ArXiv scraper is disabled")
            return []

        query = self._build_query()
        self.logger.info("Querying ArXiv", query=query, max_results=self.arxiv_config.max_results)

        # arxiv library is synchronous — run in executor
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            self._fetch_results,
            query,
        )

        items: list[ScrapedItem] = []
        for result in results:
            try:
                item = self._result_to_item(result)
                items.append(item)
            except Exception as e:
                self.logger.warning(
                    "Failed to parse ArXiv result",
                    error=str(e),
                    title=getattr(result, "title", "unknown"),
                )

        return items

    def _fetch_results(self, query: str) -> list[arxiv.Result]:
        """Synchronous ArXiv API call (runs in thread pool)."""
        client = arxiv.Client(
            page_size=min(50, self.arxiv_config.max_results),
            delay_seconds=3.0,
            num_retries=3,
        )
        search = arxiv.Search(
            query=query,
            max_results=self.arxiv_config.max_results,
            sort_by=self._get_sort_criterion(),
            sort_order=arxiv.SortOrder.Descending,
        )
        return list(client.results(search))

    def _result_to_item(self, result: arxiv.Result) -> ScrapedItem:
        """Convert an arxiv.Result to a ScrapedItem."""
        # Extract arxiv ID from entry_id (e.g., "http://arxiv.org/abs/2301.12345v1")
        arxiv_id = result.entry_id.split("/abs/")[-1] if result.entry_id else ""

        # Build author list
        authors = [str(a) for a in result.authors]

        # Categories
        categories = result.categories if result.categories else []

        # Ensure published_at is timezone-aware
        published_at = result.published
        if published_at and published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)

        return ScrapedItem(
            title=result.title.strip(),
            url=result.entry_id,
            source="arxiv",
            content=result.summary.strip() if result.summary else "",
            published_at=published_at,
            tags=categories,
            extra={
                "arxiv_id": arxiv_id,
                "authors": json.dumps(authors),
                "categories": ",".join(categories),
                "pdf_url": result.pdf_url,
                "doi": result.doi,
                "journal_ref": result.journal_ref,
                "comment": result.comment,
            },
        )
