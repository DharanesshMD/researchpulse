"""Tests for scraper resilience, proxy rotation, and backoff retries."""

from __future__ import annotations

import httpx
import pytest
import respx
from unittest.mock import patch

from researchpulse.config import ResearchPulseConfig
from researchpulse.scrapers.base import BaseScraper, DEFAULT_USER_AGENTS
from researchpulse.scrapers.models import ScrapedItem


# Dummy concrete scraper for testing BaseScraper logic
class DummyScraper(BaseScraper):
    source_name = "dummy"

    async def scrape(self) -> list[ScrapedItem]:
        await self._get("https://api.example.com/data")
        return []


class TestScraperResilience:
    """Test scraper resilience, proxy rotation, and retry mechanics."""

    @pytest.fixture
    def config(self) -> ResearchPulseConfig:
        config = ResearchPulseConfig()
        config.scraping.max_retries = 2
        config.scraping.user_agent_rotation = True
        config.scraping.proxies.enabled = True
        config.scraping.proxies.ips = [
            "http://proxy-1.com:8080",
            "http://proxy-2.com:8080",
            "http://proxy-3.com:8080",
        ]
        config.scraping.proxies.rotation_strategy = "round_robin"
        return config

    @pytest.mark.asyncio
    async def test_proxy_rotation_round_robin(self, config: ResearchPulseConfig):
        """Test round-robin proxy rotation across multiple client creations."""
        scraper = DummyScraper(config)

        # First client creation
        client1 = scraper.client
        assert scraper._current_proxy == "http://proxy-1.com:8080"
        assert scraper._current_user_agent in DEFAULT_USER_AGENTS

        # Rotate session
        await scraper._rotate_session()
        client2 = scraper.client
        assert scraper._current_proxy == "http://proxy-2.com:8080"

        # Rotate session again
        await scraper._rotate_session()
        client3 = scraper.client
        assert scraper._current_proxy == "http://proxy-3.com:8080"

        # Wrap around
        await scraper._rotate_session()
        client4 = scraper.client
        assert scraper._current_proxy == "http://proxy-1.com:8080"

        await scraper.close()

    @pytest.mark.asyncio
    async def test_proxy_rotation_random(self, config: ResearchPulseConfig):
        """Test random proxy selection strategy."""
        config.scraping.proxies.rotation_strategy = "random"
        scraper = DummyScraper(config)

        with patch("random.choice", return_value="http://proxy-3.com:8080") as mock_choice:
            client = scraper.client
            assert scraper._current_proxy == "http://proxy-3.com:8080"
            mock_choice.assert_any_call(config.scraping.proxies.ips)

        await scraper.close()

    @pytest.mark.asyncio
    async def test_user_agent_rotation_disabled(self, config: ResearchPulseConfig):
        """When User-Agent rotation is disabled, use default scraper UA."""
        config.scraping.user_agent_rotation = False
        scraper = DummyScraper(config)

        client = scraper.client
        assert scraper._current_user_agent == "ResearchPulse/0.1 (research-scraper)"
        await scraper.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_retry_on_429_success(self, config: ResearchPulseConfig):
        """A 429 error should trigger session/proxy rotation and retry, succeeding on the next attempt."""
        scraper = DummyScraper(config)
        
        # Configure tenacity with zero wait for instant test execution
        with patch("tenacity.wait_random_exponential.__call__", return_value=0.0):
            # Route: first request returns 429, second request returns 200
            route = respx.get("https://api.example.com/data")
            route.mock(side_effect=[
                httpx.Response(429),
                httpx.Response(200, json={"status": "ok"})
            ])

            # Ensure we start on proxy 1
            client1 = scraper.client
            assert scraper._current_proxy == "http://proxy-1.com:8080"

            # Execute run/scrape which calls GET
            await scraper.run()

            # Should have rotated to proxy 2 after the 429
            assert scraper._current_proxy == "http://proxy-2.com:8080"
            assert route.call_count == 2

        await scraper.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_retry_exhaustion_raises(self, config: ResearchPulseConfig):
        """If errors persist past max_retries, it should eventually fail."""
        scraper = DummyScraper(config)

        with patch("tenacity.wait_random_exponential.__call__", return_value=0.0):
            # Mock all requests to return 429
            route = respx.get("https://api.example.com/data").mock(
                return_value=httpx.Response(429)
            )

            # run() catches errors and returns empty list
            items = await scraper.run()
            assert items == []
            
            # 1 initial attempt + 2 retries = 3 calls total
            assert route.call_count == 3
            # Rotated past proxy 1 and 2, ends on proxy 3
            assert scraper._current_proxy == "http://proxy-3.com:8080"

        await scraper.close()
