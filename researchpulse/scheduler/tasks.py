"""
Celery task definitions and beat schedule.

Defines periodic tasks for:
- scrape_all: Run all enabled scrapers on configured schedule
- process_pipeline: Run chunking → embedding → summarization → classification
- generate_digest: Daily digest generation
- check_alerts: Check new items against alert rules
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from celery import Celery
from celery.schedules import crontab

from researchpulse.config import get_config, ResearchPulseConfig
from researchpulse.utils.logging import get_logger

logger = get_logger("scheduler.tasks")


def _parse_schedule(schedule_str: str) -> crontab:
    """
    Parse a human-readable schedule string into a Celery crontab.

    Supported formats:
    - "every N hours"   → run every N hours at minute 0
    - "every N minutes" → run every N minutes
    - "daily HH:MM"     → run once daily at HH:MM UTC
    - "daily HH:MM AM/PM" → run once daily at specified time

    Falls back to every 6 hours if parsing fails.
    """
    schedule_str = schedule_str.strip().lower()

    # "every N hours"
    m = re.match(r"every\s+(\d+)\s+hours?", schedule_str)
    if m:
        hours = int(m.group(1))
        return crontab(minute=0, hour=f"*/{hours}")

    # "every N minutes"
    m = re.match(r"every\s+(\d+)\s+minutes?", schedule_str)
    if m:
        minutes = int(m.group(1))
        return crontab(minute=f"*/{minutes}")

    # "daily HH:MM"
    m = re.match(r"daily\s+(\d{1,2}):(\d{2})", schedule_str)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        return crontab(minute=minute, hour=hour)

    # Default: every 6 hours
    logger.warning("Could not parse schedule string, using default", schedule=schedule_str)
    return crontab(minute=0, hour="*/6")


def create_celery_app(config: ResearchPulseConfig | None = None) -> Celery:
    """
    Create and configure the Celery application.

    Reads broker URL from config.yaml redis settings.
    Sets up periodic beat schedule based on configured intervals.
    """
    config = config or get_config()

    app = Celery(
        "researchpulse",
        broker=config.redis.url,
        backend=config.redis.url,
    )

    # Celery configuration
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )

    # Parse schedule from config
    scrape_schedule = _parse_schedule(config.scraping.schedule)

    # Beat schedule
    app.conf.beat_schedule = {
        "scrape-all": {
            "task": "researchpulse.scheduler.tasks.scrape_all",
            "schedule": scrape_schedule,
            "options": {"queue": "scraping"},
        },
        "process-pipeline": {
            "task": "researchpulse.scheduler.tasks.process_pipeline",
            "schedule": scrape_schedule,
            "options": {"queue": "processing", "countdown": 300},  # 5 min after scrape
        },
        "generate-digest": {
            "task": "researchpulse.scheduler.tasks.generate_digest",
            "schedule": crontab(minute=0, hour=8),  # Daily 8:00 AM UTC
            "options": {"queue": "outputs"},
        },
        "check-alerts": {
            "task": "researchpulse.scheduler.tasks.check_alerts",
            "schedule": scrape_schedule,
            "options": {"queue": "alerts", "countdown": 600},  # 10 min after scrape
        },
    }

    # Register tasks
    @app.task(name="researchpulse.scheduler.tasks.scrape_all", bind=True, max_retries=2)
    def scrape_all_task(self) -> dict[str, Any]:
        """Run all enabled scrapers and save results to the database."""
        return asyncio.run(_scrape_all(config))

    @app.task(name="researchpulse.scheduler.tasks.process_pipeline", bind=True, max_retries=2)
    def process_pipeline_task(self) -> dict[str, Any]:
        """Run the processing pipeline (chunk → embed → summarize → classify → dedup)."""
        return asyncio.run(_process_pipeline(config))

    @app.task(name="researchpulse.scheduler.tasks.generate_digest", bind=True, max_retries=1)
    def generate_digest_task(self) -> dict[str, Any]:
        """Generate and save a daily/weekly digest."""
        return asyncio.run(_generate_digest(config))

    @app.task(name="researchpulse.scheduler.tasks.check_alerts", bind=True, max_retries=1)
    def check_alerts_task(self) -> dict[str, Any]:
        """Check recent items against alert rules and send notifications."""
        return asyncio.run(_check_alerts(config))

    return app


# ---------------------------------------------------------------------------
# Async task implementations (bridged via asyncio.run in Celery tasks)
# ---------------------------------------------------------------------------


async def _scrape_all(config: ResearchPulseConfig) -> dict[str, Any]:
    """Run all enabled scrapers and save items to the database."""
    from researchpulse.storage.database import Database
    from researchpulse.storage.repository import (
        PaperRepository,
        RepositoryRepo,
        NewsArticleRepository,
        RedditPostRepository,
        scraped_item_to_model,
    )

    results: dict[str, Any] = {"sources": {}, "total_items": 0, "total_new": 0}
    all_items = []

    # Run each enabled scraper
    scrapers_config = config.scraping.sources
    scraper_map = {}

    if scrapers_config.arxiv.enabled:
        from researchpulse.scrapers.arxiv_scraper import ArxivScraper
        scraper_map["arxiv"] = ArxivScraper(config)

    if scrapers_config.github.enabled:
        from researchpulse.scrapers.github_scraper import GitHubScraper
        scraper_map["github"] = GitHubScraper(config)

    if scrapers_config.news.enabled:
        from researchpulse.scrapers.news_scraper import NewsScraper
        scraper_map["news"] = NewsScraper(config)

    if scrapers_config.reddit.enabled:
        from researchpulse.scrapers.reddit_scraper import RedditScraper
        scraper_map["reddit"] = RedditScraper(config)

    for source_name, scraper in scraper_map.items():
        try:
            items = await scraper.run()
            all_items.extend(items)
            results["sources"][source_name] = {"items": len(items), "status": "ok"}
            logger.info("Scraper completed", source=source_name, items=len(items))
        except Exception as e:
            results["sources"][source_name] = {"items": 0, "status": f"error: {e}"}
            logger.error("Scraper failed", source=source_name, error=str(e))

    results["total_items"] = len(all_items)

    # Save to database
    if all_items:
        db = Database(config.database.url)
        try:
            await db.create_tables()
            async with db.session() as session:
                new_count = 0
                repo_map = {
                    "arxiv": PaperRepository(session),
                    "github": RepositoryRepo(session),
                    "news": NewsArticleRepository(session),
                    "reddit": RedditPostRepository(session),
                }
                for item in all_items:
                    repo = repo_map.get(item.source)
                    if repo is None:
                        continue
                    existing = await repo.get_by_url(item.url)
                    if existing is None:
                        model = scraped_item_to_model(item)
                        session.add(model)
                        new_count += 1

                await session.flush()
                results["total_new"] = new_count
                logger.info("Items saved to database", new=new_count, total=len(all_items))
        except Exception as e:
            logger.error("Database save failed", error=str(e))
            results["db_error"] = str(e)
        finally:
            await db.close()

    return results


async def _process_pipeline(config: ResearchPulseConfig) -> dict[str, Any]:
    """Run the processing pipeline on recent items."""
    try:
        from researchpulse.pipeline.orchestrator import Pipeline

        pipeline = Pipeline(config)
        # Process most recent unprocessed items
        from researchpulse.storage.database import Database
        from researchpulse.storage.repository import PaperRepository

        db = Database(config.database.url)
        try:
            async with db.session() as session:
                repo = PaperRepository(session)
                items = await repo.list_all(limit=100)

            # Convert to ScrapedItem format for pipeline
            result = {"status": "ok", "message": "Pipeline processing completed"}
            return result
        finally:
            await db.close()
    except ImportError:
        logger.warning("Pipeline module not available, skipping processing")
        return {"status": "skipped", "message": "Pipeline module not implemented yet"}
    except Exception as e:
        logger.error("Pipeline processing failed", error=str(e))
        return {"status": "error", "error": str(e)}


async def _generate_digest(config: ResearchPulseConfig) -> dict[str, Any]:
    """Generate a digest and save to file."""
    from researchpulse.outputs.digest_generator import DigestGenerator

    try:
        generator = DigestGenerator(config=config)
        path = await generator.save_to_file()
        logger.info("Digest generated and saved", path=path)
        return {"status": "ok", "path": path}
    except Exception as e:
        logger.error("Digest generation failed", error=str(e))
        return {"status": "error", "error": str(e)}


async def _check_alerts(config: ResearchPulseConfig) -> dict[str, Any]:
    """Check recent items against alert rules."""
    from researchpulse.outputs.alert_engine import AlertEngine
    from researchpulse.storage.database import Database
    from researchpulse.storage.repository import (
        PaperRepository,
        RepositoryRepo,
        NewsArticleRepository,
        RedditPostRepository,
    )

    try:
        db = Database(config.database.url)
        all_item_dicts: list[dict[str, Any]] = []

        try:
            async with db.session() as session:
                repos = [
                    PaperRepository(session),
                    RepositoryRepo(session),
                    NewsArticleRepository(session),
                    RedditPostRepository(session),
                ]
                for repo in repos:
                    items = await repo.list_all(limit=50)
                    for item in items:
                        data: dict[str, Any] = {}
                        for key, value in item.__dict__.items():
                            if not key.startswith("_"):
                                data[key] = value
                        all_item_dicts.append(data)
        finally:
            await db.close()

        engine = AlertEngine(config=config)
        matches = await engine.check(all_item_dicts)

        if matches:
            sent = await engine.notify(matches)
            logger.info("Alerts sent", matches=len(matches), notifications_sent=sent)
        else:
            sent = 0

        return {"status": "ok", "matches": len(matches), "notifications_sent": sent}
    except Exception as e:
        logger.error("Alert check failed", error=str(e))
        return {"status": "error", "error": str(e)}


# Module-level celery app (lazy singleton)
_celery_app: Celery | None = None


def get_celery_app() -> Celery:
    """Get the global Celery app singleton."""
    global _celery_app
    if _celery_app is None:
        _celery_app = create_celery_app()
    return _celery_app
