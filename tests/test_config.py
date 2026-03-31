"""Tests for the configuration system."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from researchpulse.config import (
    ResearchPulseConfig,
    load_config,
    get_config,
    reset_config,
    _resolve_env_vars,
)


class TestConfigLoading:
    """Test config loading from YAML files."""

    def test_default_config(self):
        """Default config should have sensible defaults."""
        config = ResearchPulseConfig()
        assert config.scraping.sources.arxiv.enabled is True
        assert config.llm.provider == "anthropic"
        assert config.database.url.startswith("postgresql")

    def test_load_from_file(self, config_path: Path):
        """Load config from a YAML file."""
        config = load_config(config_path)
        assert config.scraping.sources.arxiv.max_results == 5
        assert config.scraping.sources.github.topics == ["llm"]
        assert config.database.url == "sqlite+aiosqlite:///test.db"

    def test_load_missing_file(self):
        """Loading a non-existent file should raise."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.yaml")

    def test_singleton_pattern(self, config_path: Path):
        """get_config() should return the same instance."""
        config1 = get_config(str(config_path))
        config2 = get_config()
        assert config1 is config2

    def test_reset_config(self, config_path: Path):
        """reset_config() should clear the singleton."""
        config1 = get_config(str(config_path))
        reset_config()
        config2 = get_config(str(config_path))
        assert config1 is not config2


class TestEnvVarResolution:
    """Test environment variable resolution in config values."""

    def test_resolve_env_var(self, monkeypatch):
        """${ENV_VAR} should be resolved from environment."""
        monkeypatch.setenv("TEST_DB_URL", "postgresql://test:test@localhost/test")
        result = _resolve_env_vars("${TEST_DB_URL}")
        assert result == "postgresql://test:test@localhost/test"

    def test_resolve_missing_env_var(self):
        """Missing env vars should keep the original string."""
        result = _resolve_env_vars("${NONEXISTENT_VAR_12345}")
        assert result == "${NONEXISTENT_VAR_12345}"

    def test_resolve_nested_dict(self, monkeypatch):
        """Env vars should be resolved recursively in dicts."""
        monkeypatch.setenv("TEST_VAL", "resolved")
        data = {"key": "${TEST_VAL}", "nested": {"inner": "${TEST_VAL}"}}
        result = _resolve_env_vars(data)
        assert result["key"] == "resolved"
        assert result["nested"]["inner"] == "resolved"

    def test_resolve_list(self, monkeypatch):
        """Env vars should be resolved in lists."""
        monkeypatch.setenv("TEST_ITEM", "resolved")
        data = ["${TEST_ITEM}", "plain"]
        result = _resolve_env_vars(data)
        assert result == ["resolved", "plain"]


class TestConfigValidation:
    """Test Pydantic validation of config fields."""

    def test_invalid_llm_provider(self):
        """Invalid LLM provider should fail validation."""
        with pytest.raises(Exception):
            ResearchPulseConfig(llm={"provider": "invalid_provider"})

    def test_arxiv_sort_by_validation(self):
        """Invalid sort_by should fail validation."""
        with pytest.raises(Exception):
            ResearchPulseConfig(
                scraping={"sources": {"arxiv": {"sort_by": "invalid"}}}
            )

    def test_valid_full_config(self, config_path: Path):
        """A complete config should load without errors."""
        config = load_config(config_path)
        assert config.scraping.max_items_per_source == 10
        assert len(config.scraping.sources.news.feeds) == 1
        assert config.scraping.sources.news.feeds[0].name == "Test Feed"
