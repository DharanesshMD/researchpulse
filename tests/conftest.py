"""
Shared test fixtures and configuration for ResearchPulse test suite.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from researchpulse.config import ResearchPulseConfig, load_config, reset_config


@pytest.fixture(autouse=True)
def _reset_config():
    """Reset the global config singleton before each test."""
    reset_config()
    yield
    reset_config()


@pytest.fixture
def sample_config() -> ResearchPulseConfig:
    """Provide a default test config (no file needed)."""
    return ResearchPulseConfig()


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    """Create a minimal config.yaml for testing."""
    config_content = """\
scraping:
  schedule: "every 6 hours"
  max_items_per_source: 10
  request_timeout: 10
  sources:
    arxiv:
      enabled: true
      categories: ["cs.AI"]
      keywords: ["test"]
      max_results: 5
    github:
      enabled: true
      topics: ["llm"]
      min_stars: 10
      max_results: 5
    reddit:
      enabled: true
      subreddits: ["MachineLearning"]
      min_score: 10
      max_results: 5
    news:
      enabled: true
      feeds:
        - url: "https://example.com/feed.xml"
          name: "Test Feed"
      max_results_per_feed: 5

llm:
  provider: "anthropic"

database:
  url: "sqlite+aiosqlite:///test.db"
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def sqlite_db_url(tmp_path: Path) -> str:
    """Provide a SQLite database URL for testing."""
    return f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
