"""Tests for the alert engine."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from researchpulse.config import ResearchPulseConfig, AlertsConfig
from researchpulse.outputs.alert_engine import AlertEngine


def _make_items() -> list[dict]:
    return [
        {
            "title": "New Gemma 3 model released",
            "content": "Google released Gemma 3, a new on-device LLM.",
            "source": "news",
            "url": "https://example.com/gemma",
            "relevance_score": 0.9,
        },
        {
            "title": "Python 3.14 features",
            "content": "New features in Python including better typing support.",
            "source": "news",
            "url": "https://example.com/python",
            "relevance_score": 0.3,
        },
        {
            "title": "Snapdragon AI benchmark",
            "content": "Qualcomm Snapdragon achieves new edge inference record.",
            "source": "reddit",
            "url": "https://reddit.com/r/ai/snapdragon",
            "relevance_score": 0.85,
        },
    ]


class TestAlertEngine:
    """Test alert engine keyword and relevance matching."""

    @pytest.fixture
    def engine(self) -> AlertEngine:
        config = ResearchPulseConfig()
        config.alerts = AlertsConfig(
            enabled=True,
            keywords=["Gemma", "Snapdragon", "on-device"],
            notify_via="log",
            min_relevance=0.8,
        )
        return AlertEngine(config=config)

    @pytest.mark.asyncio
    async def test_keyword_matching(self, engine: AlertEngine):
        """Should match items containing keywords."""
        items = _make_items()
        matches = await engine.check(items)

        matched_titles = [m["title"] for m in matches]
        assert "New Gemma 3 model released" in matched_titles
        assert "Snapdragon AI benchmark" in matched_titles

    @pytest.mark.asyncio
    async def test_keyword_case_insensitive(self, engine: AlertEngine):
        """Keyword matching should be case-insensitive."""
        items = [{"title": "GEMMA is great", "content": "", "relevance_score": 0.0}]
        matches = await engine.check(items)
        assert len(matches) == 1

    @pytest.mark.asyncio
    async def test_relevance_threshold(self, engine: AlertEngine):
        """Should match items above relevance threshold."""
        items = _make_items()
        matches = await engine.check(items)

        # Gemma (0.9) and Snapdragon (0.85) exceed 0.8 threshold
        # Python (0.3) does not
        assert not any(m["title"] == "Python 3.14 features" for m in matches)

    @pytest.mark.asyncio
    async def test_alert_reasons(self, engine: AlertEngine):
        """Each match should include alert_reasons."""
        items = _make_items()
        matches = await engine.check(items)

        gemma_match = next(m for m in matches if "Gemma" in m["title"])
        reasons = gemma_match["alert_reasons"]
        assert any("Gemma" in r for r in reasons)
        assert any("on-device" in r for r in reasons)
        assert any("relevance" in r.lower() for r in reasons)

    @pytest.mark.asyncio
    async def test_disabled_engine(self):
        """Disabled engine should return no matches."""
        config = ResearchPulseConfig()
        config.alerts = AlertsConfig(enabled=False, keywords=["Gemma"])
        engine = AlertEngine(config=config)

        matches = await engine.check(_make_items())
        assert matches == []

    @pytest.mark.asyncio
    async def test_no_matches(self, engine: AlertEngine):
        """Items with no keyword/relevance hits should not match."""
        items = [
            {"title": "Cooking recipes", "content": "Best pasta recipes.", "relevance_score": 0.1},
        ]
        matches = await engine.check(items)
        assert matches == []

    @pytest.mark.asyncio
    async def test_notify_log(self, engine: AlertEngine):
        """Log notification should return count of matches."""
        items = _make_items()
        matches = await engine.check(items)
        sent = await engine.notify(matches, channel="log")
        assert sent == len(matches)

    @pytest.mark.asyncio
    async def test_notify_empty(self, engine: AlertEngine):
        """No matches should send zero notifications."""
        sent = await engine.notify([], channel="log")
        assert sent == 0

    @respx.mock
    @pytest.mark.asyncio
    async def test_notify_slack(self, engine: AlertEngine, monkeypatch):
        """Should POST to Slack webhook."""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
        respx.post("https://hooks.slack.com/test").mock(
            return_value=httpx.Response(200)
        )

        matches = [{"title": "Test", "url": "https://x.com", "source": "news", "alert_reasons": ["keyword"]}]
        sent = await engine.notify(matches, channel="slack")
        assert sent == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_notify_ntfy(self, engine: AlertEngine, monkeypatch):
        """Should POST to ntfy.sh."""
        monkeypatch.setenv("NTFY_TOPIC", "test_topic")
        respx.post("https://ntfy.sh/test_topic").mock(
            return_value=httpx.Response(200)
        )

        matches = [{"title": "Test", "url": "https://x.com", "source": "news", "alert_reasons": ["keyword"]}]
        sent = await engine.notify(matches, channel="ntfy")
        assert sent == 1

    @pytest.mark.asyncio
    async def test_check_and_notify(self, engine: AlertEngine):
        """Convenience method should check and notify."""
        items = _make_items()
        sent = await engine.check_and_notify(items)
        assert sent >= 1
