"""
Abstract base scraper that all source scrapers inherit from.

Provides:
- Async HTTP client (httpx)
- Built-in rate limiting
- Structured logging
- Common interface: scrape() → list[ScrapedItem]
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx

from researchpulse.config import ResearchPulseConfig
from researchpulse.scrapers.models import ScrapedItem
from researchpulse.utils.logging import get_logger
from researchpulse.utils.rate_limiter import AsyncRateLimiter


class BaseScraper(ABC):
    """
    Abstract base class for all research scrapers.

    Subclasses must implement:
    - source_name: class attribute identifying the source
    - scrape(): async method returning a list of ScrapedItem
    """

    source_name: str = "base"

    def __init__(
        self,
        config: ResearchPulseConfig,
        rate_limit: float = 1.0,
        **kwargs: Any,
    ) -> None:
        self.config = config
        self.logger = get_logger(f"scraper.{self.source_name}")
        self.rate_limiter = AsyncRateLimiter(rate=rate_limit)
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy-initialized async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.scraping.request_timeout),
                follow_redirects=True,
                headers={"User-Agent": "ResearchPulse/0.1 (research-scraper)"},
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> BaseScraper:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Rate-limited GET request."""
        async with self.rate_limiter:
            self.logger.debug("GET request", url=url)
            response = await self.client.get(url, **kwargs)
            response.raise_for_status()
            return response

    async def _post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Rate-limited POST request."""
        async with self.rate_limiter:
            self.logger.debug("POST request", url=url)
            response = await self.client.post(url, **kwargs)
            response.raise_for_status()
            return response

    @abstractmethod
    async def scrape(self) -> list[ScrapedItem]:
        """
        Execute the scraping logic and return a list of ScrapedItem.

        Each subclass implements this with source-specific logic.
        Must be resilient — log errors and continue processing.
        """
        ...

    async def run(self) -> list[ScrapedItem]:
        """
        Public entry point: run the scraper with logging and error handling.

        Returns scraped items. Logs errors but doesn't raise.
        """
        self.logger.info("Starting scrape", source=self.source_name)
        try:
            items = await self.scrape()
            self.logger.info(
                "Scrape completed",
                source=self.source_name,
                items_count=len(items),
            )
            return items
        except Exception as e:
            self.logger.error(
                "Scrape failed",
                source=self.source_name,
                error=str(e),
                exc_info=True,
            )
            return []
        finally:
            await self.close()
