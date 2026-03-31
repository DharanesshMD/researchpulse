"""
Celery task definitions and beat schedule (Phase 2).

Will define periodic scraping tasks and processing pipeline triggers.
"""

from __future__ import annotations


def create_celery_app():
    """Create and configure the Celery application."""
    raise NotImplementedError("Celery task scheduler is implemented in Phase 2")


# Task schedule (to be configured via config.yaml):
# - scrape_all: Run all scrapers on configured schedule
# - process_pipeline: Run chunking → embedding → summarization → classification
# - generate_digest: Daily/weekly digest generation
# - check_alerts: Check new items against alert rules
