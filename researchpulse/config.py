"""
ResearchPulse configuration system.

Loads config.yaml and validates it with Pydantic models.
Supports environment variable overrides.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Source configs
# ---------------------------------------------------------------------------

class ArxivSourceConfig(BaseModel):
    enabled: bool = True
    categories: list[str] = Field(default_factory=lambda: ["cs.AI", "cs.LG", "cs.CL"])
    keywords: list[str] = Field(default_factory=list)
    max_results: int = 50
    sort_by: Literal["submitted", "relevance", "lastUpdatedDate"] = "submitted"


class GitHubSourceConfig(BaseModel):
    enabled: bool = True
    topics: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    min_stars: int = 50
    sort_by: Literal["stars", "forks", "updated"] = "stars"
    max_results: int = 30


class RedditSourceConfig(BaseModel):
    enabled: bool = True
    subreddits: list[str] = Field(default_factory=lambda: ["MachineLearning"])
    min_score: int = 50
    sort_by: Literal["hot", "new", "top", "rising"] = "hot"
    time_filter: Literal["hour", "day", "week", "month", "year", "all"] = "week"
    max_results: int = 30


class NewsFeedEntry(BaseModel):
    url: str
    name: str = ""


class NewsSourceConfig(BaseModel):
    enabled: bool = True
    feeds: list[NewsFeedEntry] = Field(default_factory=list)
    max_results_per_feed: int = 20
    use_full_extraction: bool = False


class SourcesConfig(BaseModel):
    arxiv: ArxivSourceConfig = Field(default_factory=ArxivSourceConfig)
    github: GitHubSourceConfig = Field(default_factory=GitHubSourceConfig)
    reddit: RedditSourceConfig = Field(default_factory=RedditSourceConfig)
    news: NewsSourceConfig = Field(default_factory=NewsSourceConfig)


class ScrapingConfig(BaseModel):
    schedule: str = "every 6 hours"
    max_items_per_source: int = 50
    request_timeout: int = 30
    sources: SourcesConfig = Field(default_factory=SourcesConfig)


# ---------------------------------------------------------------------------
# Interest & relevance
# ---------------------------------------------------------------------------

class InterestsConfig(BaseModel):
    topics: list[str] = Field(default_factory=list)
    relevance_threshold: float = 0.75


# ---------------------------------------------------------------------------
# LLM provider configs
# ---------------------------------------------------------------------------

class AnthropicLLMConfig(BaseModel):
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 1024


class OpenAILLMConfig(BaseModel):
    model: str = "gpt-4o-mini"
    max_tokens: int = 1024


class LLMConfig(BaseModel):
    provider: Literal["anthropic", "openai"] = "anthropic"
    anthropic: AnthropicLLMConfig = Field(default_factory=AnthropicLLMConfig)
    openai: OpenAILLMConfig = Field(default_factory=OpenAILLMConfig)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class AlertsConfig(BaseModel):
    enabled: bool = True
    keywords: list[str] = Field(default_factory=list)
    notify_via: Literal["slack", "ntfy", "email", "log"] = "slack"
    min_relevance: float = 0.8


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

class DigestOutputConfig(BaseModel):
    enabled: bool = True
    frequency: Literal["daily", "weekly"] = "daily"
    format: Literal["markdown", "html"] = "markdown"
    max_items_per_category: int = 10


class ExportOutputConfig(BaseModel):
    formats: list[str] = Field(default_factory=lambda: ["json", "parquet"])
    output_dir: str = "./exports"


class RAGOutputConfig(BaseModel):
    enabled: bool = True
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k: int = 10


class OutputsConfig(BaseModel):
    digest: DigestOutputConfig = Field(default_factory=DigestOutputConfig)
    export: ExportOutputConfig = Field(default_factory=ExportOutputConfig)
    rag: RAGOutputConfig = Field(default_factory=RAGOutputConfig)


# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------

class DatabaseConfig(BaseModel):
    url: str = "postgresql+asyncpg://researchpulse:researchpulse@localhost:5432/researchpulse"


class VectorStoreConfig(BaseModel):
    url: str = "http://localhost:6333"
    collection_name: str = "research_items"


class RedisConfig(BaseModel):
    url: str = "redis://localhost:6379/0"


# ---------------------------------------------------------------------------
# Root config
# ---------------------------------------------------------------------------

class ResearchPulseConfig(BaseModel):
    """Root configuration model for the entire application."""

    scraping: ScrapingConfig = Field(default_factory=ScrapingConfig)
    interests: InterestsConfig = Field(default_factory=InterestsConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    alerts: AlertsConfig = Field(default_factory=AlertsConfig)
    outputs: OutputsConfig = Field(default_factory=OutputsConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)


def _resolve_env_vars(data: dict | list | str) -> dict | list | str:
    """Recursively resolve ${ENV_VAR} references in config values."""
    if isinstance(data, dict):
        return {k: _resolve_env_vars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_resolve_env_vars(item) for item in data]
    if isinstance(data, str) and data.startswith("${") and data.endswith("}"):
        env_var = data[2:-1]
        return os.environ.get(env_var, data)
    return data


def load_config(config_path: str | Path | None = None) -> ResearchPulseConfig:
    """
    Load and validate configuration from a YAML file.

    Looks for config.yaml in the following order:
    1. Explicit path argument
    2. RESEARCHPULSE_CONFIG env var
    3. ./config.yaml (current working directory)
    4. Falls back to default config
    """
    if config_path is None:
        config_path = os.environ.get("RESEARCHPULSE_CONFIG")

    if config_path is None:
        default_path = Path.cwd() / "config.yaml"
        if default_path.exists():
            config_path = default_path

    if config_path is not None:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path) as f:
            raw_data = yaml.safe_load(f) or {}

        resolved_data = _resolve_env_vars(raw_data)
        return ResearchPulseConfig.model_validate(resolved_data)

    # No config file found — use defaults
    return ResearchPulseConfig()


# Module-level singleton (lazy)
_config: ResearchPulseConfig | None = None


def get_config(config_path: str | Path | None = None) -> ResearchPulseConfig:
    """Get the global config singleton. Loads on first call."""
    global _config
    if _config is None:
        _config = load_config(config_path)
    return _config


def reset_config() -> None:
    """Reset the global config singleton (useful for testing)."""
    global _config
    _config = None
