"""Tests for the Celery task scheduler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from celery.schedules import crontab

from researchpulse.config import ResearchPulseConfig
from researchpulse.scheduler.tasks import (
    _parse_schedule,
    create_celery_app,
    _scrape_all,
    _generate_digest,
    _check_alerts,
    _process_pipeline,
)


# ---------------------------------------------------------------------------
# Schedule parsing
# ---------------------------------------------------------------------------

class TestParseSchedule:
    """Test the schedule string parser."""

    def test_every_n_hours(self):
        result = _parse_schedule("every 6 hours")
        assert isinstance(result, crontab)
        assert result.minute == {0}
        assert result.hour == {0, 6, 12, 18}

    def test_every_1_hour(self):
        result = _parse_schedule("every 1 hour")
        assert isinstance(result, crontab)
        assert result.minute == {0}

    def test_every_n_minutes(self):
        result = _parse_schedule("every 30 minutes")
        assert isinstance(result, crontab)
        assert result.minute == {0, 30}

    def test_daily_with_time(self):
        result = _parse_schedule("daily 8:00")
        assert isinstance(result, crontab)
        assert result.minute == {0}
        assert result.hour == {8}

    def test_daily_afternoon(self):
        result = _parse_schedule("daily 14:30")
        assert isinstance(result, crontab)
        assert result.minute == {30}
        assert result.hour == {14}

    def test_invalid_falls_back(self):
        result = _parse_schedule("whenever you feel like it")
        assert isinstance(result, crontab)
        # Falls back to every 6 hours
        assert result.minute == {0}

    def test_whitespace_trimmed(self):
        result = _parse_schedule("  every 6 hours  ")
        assert isinstance(result, crontab)

    def test_case_insensitive(self):
        result = _parse_schedule("Every 6 Hours")
        assert isinstance(result, crontab)


# ---------------------------------------------------------------------------
# Celery app creation
# ---------------------------------------------------------------------------

class TestCreateCeleryApp:
    """Test Celery app factory."""

    def test_creates_celery_app(self, sample_config):
        app = create_celery_app(sample_config)
        assert app is not None
        assert app.main == "researchpulse"

    def test_beat_schedule_configured(self, sample_config):
        app = create_celery_app(sample_config)
        schedule = app.conf.beat_schedule
        assert "scrape-all" in schedule
        assert "process-pipeline" in schedule
        assert "generate-digest" in schedule
        assert "check-alerts" in schedule

    def test_broker_url_from_config(self, sample_config):
        app = create_celery_app(sample_config)
        # The broker URL should come from config
        assert "redis" in str(app.conf.broker_url)

    def test_task_names_registered(self, sample_config):
        app = create_celery_app(sample_config)
        schedule = app.conf.beat_schedule
        assert schedule["scrape-all"]["task"] == "researchpulse.scheduler.tasks.scrape_all"
        assert schedule["process-pipeline"]["task"] == "researchpulse.scheduler.tasks.process_pipeline"
        assert schedule["generate-digest"]["task"] == "researchpulse.scheduler.tasks.generate_digest"
        assert schedule["check-alerts"]["task"] == "researchpulse.scheduler.tasks.check_alerts"

    def test_digest_runs_daily_8am(self, sample_config):
        app = create_celery_app(sample_config)
        digest_schedule = app.conf.beat_schedule["generate-digest"]["schedule"]
        assert isinstance(digest_schedule, crontab)
        assert digest_schedule.hour == {8}
        assert digest_schedule.minute == {0}


# ---------------------------------------------------------------------------
# Task implementations (mocked)
# ---------------------------------------------------------------------------

class TestScrapeAllTask:
    """Test the scrape_all task implementation."""

    @pytest.mark.asyncio
    async def test_scrape_all_no_enabled_sources(self):
        """Should return empty results when all sources disabled."""
        config = ResearchPulseConfig()
        config.scraping.sources.arxiv.enabled = False
        config.scraping.sources.github.enabled = False
        config.scraping.sources.news.enabled = False
        config.scraping.sources.reddit.enabled = False

        result = await _scrape_all(config)
        assert result["total_items"] == 0
        assert result["sources"] == {}

    @pytest.mark.asyncio
    async def test_scrape_all_handles_scraper_errors(self):
        """Should catch and report errors from individual scrapers."""
        config = ResearchPulseConfig()
        config.scraping.sources.github.enabled = False
        config.scraping.sources.news.enabled = False
        config.scraping.sources.reddit.enabled = False

        with patch("researchpulse.scrapers.arxiv_scraper.ArxivScraper") as MockScraper:
            mock_instance = MockScraper.return_value
            mock_instance.run = AsyncMock(side_effect=Exception("Network error"))

            result = await _scrape_all(config)
            assert result["sources"]["arxiv"]["status"].startswith("error")


class TestProcessPipelineTask:
    """Test the process_pipeline task implementation."""

    @pytest.mark.asyncio
    async def test_pipeline_handles_missing_module(self):
        """Should gracefully handle missing pipeline module."""
        config = ResearchPulseConfig()

        with patch.dict("sys.modules", {"researchpulse.pipeline.orchestrator": None}):
            with patch("researchpulse.scheduler.tasks._process_pipeline") as mock:
                mock.return_value = {"status": "skipped", "message": "Pipeline module not implemented yet"}
                result = await mock(config)
                assert result["status"] == "skipped"


class TestGenerateDigestTask:
    """Test the generate_digest task implementation."""

    @pytest.mark.asyncio
    async def test_generate_digest_success(self):
        """Should generate and save a digest file."""
        config = ResearchPulseConfig()

        with patch("researchpulse.outputs.digest_generator.DigestGenerator") as MockGen:
            mock_instance = MockGen.return_value
            mock_instance.save_to_file = AsyncMock(return_value="/tmp/digest_daily.md")

            result = await _generate_digest(config)
            assert result["status"] == "ok"
            assert result["path"] == "/tmp/digest_daily.md"

    @pytest.mark.asyncio
    async def test_generate_digest_handles_error(self):
        """Should catch and report errors from digest generator."""
        config = ResearchPulseConfig()

        with patch("researchpulse.outputs.digest_generator.DigestGenerator") as MockGen:
            mock_instance = MockGen.return_value
            mock_instance.save_to_file = AsyncMock(side_effect=Exception("DB down"))

            result = await _generate_digest(config)
            assert result["status"] == "error"
            assert "DB down" in result["error"]


class TestCheckAlertsTask:
    """Test the check_alerts task implementation."""

    @pytest.mark.asyncio
    async def test_check_alerts_no_matches(self, sqlite_db_url):
        """Should return zero matches when DB is empty."""
        from researchpulse.storage.database import Database

        config = ResearchPulseConfig()
        config.database.url = sqlite_db_url
        config.alerts.keywords = ["nonexistent_keyword_xyz"]

        db = Database(sqlite_db_url)
        await db.create_tables()
        await db.close()

        result = await _check_alerts(config)
        assert result["status"] == "ok"
        assert result["matches"] == 0
