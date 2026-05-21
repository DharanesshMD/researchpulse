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
import random
from typing import Any

import httpx
from tenacity import AsyncRetrying, stop_after_attempt, wait_random_exponential, retry_if_exception

from researchpulse.config import ResearchPulseConfig
from researchpulse.scrapers.models import ScrapedItem
from researchpulse.utils.logging import get_logger
from researchpulse.utils.rate_limiter import AsyncRateLimiter


DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
]


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
        self._proxy_index = 0
        self._current_user_agent: str | None = None
        self._current_proxy: str | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy-initialized async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = self._create_client()
        return self._client

    def _create_client(self) -> httpx.AsyncClient:
        """Create a new httpx.AsyncClient with selected proxy and User-Agent."""
        # 1. Proxy Selection
        proxies_config = self.config.scraping.proxies
        if proxies_config.enabled and proxies_config.ips:
            if self._current_proxy is None:
                if proxies_config.rotation_strategy == "random":
                    self._current_proxy = random.choice(proxies_config.ips)
                else:  # round_robin
                    self._current_proxy = proxies_config.ips[
                        self._proxy_index % len(proxies_config.ips)
                    ]
                self.logger.debug("Selected proxy for session", proxy=self._current_proxy)
        else:
            self._current_proxy = None

        # 2. User-Agent Selection
        if self.config.scraping.user_agent_rotation:
            if self._current_user_agent is None:
                ua_list = (
                    self.config.scraping.custom_user_agents
                    if self.config.scraping.custom_user_agents
                    else DEFAULT_USER_AGENTS
                )
                self._current_user_agent = random.choice(ua_list)
        else:
            self._current_user_agent = "ResearchPulse/0.1 (research-scraper)"

        headers = {"User-Agent": self._current_user_agent}
        
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.scraping.request_timeout),
            follow_redirects=True,
            headers=headers,
            proxy=self._current_proxy,
        )

        # Hook for subclasses (like GitHub) to customize the client after creation
        self._on_client_created(client)
        return client

    def _on_client_created(self, client: httpx.AsyncClient) -> None:
        """Hook called when a new client session is created. Override in subclasses."""
        pass

    async def _rotate_session(self, clear_cookies: bool = True) -> None:
        """Rotate to the next proxy/UA and re-create client on the next request."""
        self.logger.info("Rotating session/proxy", old_proxy=self._current_proxy)
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None
        self._current_proxy = None
        self._current_user_agent = None
        self._proxy_index += 1

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> BaseScraper:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    def _should_retry(self, exception: Exception) -> bool:
        """Determine if we should retry the request based on exception."""
        if isinstance(exception, httpx.RequestError):
            return True
        if isinstance(exception, httpx.HTTPStatusError):
            status = exception.response.status_code
            if status in (403, 429, 500, 502, 503, 504):
                return True
        return False

    async def _before_retry_sleep(self, retry_state: Any) -> None:
        """Callback executed before tenacity sleeps for retry."""
        exc = retry_state.outcome.exception()
        self.logger.warning(
            "Request failed, scheduling retry",
            attempt=retry_state.attempt_number,
            error=str(exc),
        )

        # Rotate session if we hit rate limits (429), access blocks (403), or network issues
        is_block_or_network = False
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (403, 429):
            is_block_or_network = True
        elif isinstance(exc, httpx.RequestError):
            is_block_or_network = True

        if is_block_or_network and self.config.scraping.proxies.enabled:
            await self._rotate_session(clear_cookies=True)

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Execute request with rate-limiting, retries, and proxy rotation."""
        max_attempts = max(1, self.config.scraping.max_retries + 1)

        async with self.rate_limiter:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_random_exponential(multiplier=1, max=10),
                retry=retry_if_exception(self._should_retry),
                before_sleep=self._before_retry_sleep,
                reraise=True,
            ):
                with attempt:
                    client = self.client
                    self.logger.debug(
                        f"Executing request ({method})",
                        url=url,
                        proxy=self._current_proxy,
                        user_agent=self._current_user_agent,
                    )
                    response = await client.request(method, url, **kwargs)
                    response.raise_for_status()
                    return response

    async def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Rate-limited GET request with retries and session rotation."""
        return await self._request("GET", url, **kwargs)

    async def _post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Rate-limited POST request with retries and session rotation."""
        return await self._request("POST", url, **kwargs)

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
