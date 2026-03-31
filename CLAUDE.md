# ResearchPulse — Claude Code Integration

## Project Overview
ResearchPulse is an open-source, multi-source research intelligence platform that scrapes academic papers, GitHub repos, news articles, and Reddit posts, then processes them through an LLM pipeline for summarization, classification, and RAG-based querying.

## Architecture
- **Scrapers** (`researchpulse/scrapers/`): Async scrapers for ArXiv, GitHub, News/RSS, Reddit
- **Pipeline** (`researchpulse/pipeline/`): Chunking, embedding, summarization, classification, dedup
- **Storage** (`researchpulse/storage/`): PostgreSQL (SQLModel) + Qdrant (vectors)
- **Outputs** (`researchpulse/outputs/`): Digests, RAG, alerts, dashboard API
- **Scheduler** (`researchpulse/scheduler/`): Celery beat tasks

## Key Commands
```bash
# Install in dev mode
pip install -e ".[dev]"

# Run all scrapers
researchpulse run-all --save

# Run a specific scraper
researchpulse run arxiv
researchpulse run github
researchpulse run news
researchpulse run reddit

# Initialize database
researchpulse init-db

# Run tests
pytest tests/ -v

# Lint
ruff check researchpulse/
```

## Config
All configuration lives in `config.yaml`. Edit this to add sources, topics, keywords, or change scraping schedules. The config is validated at startup by Pydantic models in `researchpulse/config.py`.

## Code Patterns
- All scrapers extend `BaseScraper` (in `researchpulse/scrapers/base.py`)
- Scrapers output `ScrapedItem` dataclasses (source-agnostic)
- Database models use SQLModel (in `researchpulse/storage/db_models.py`)
- Async-first: all I/O uses `asyncio` + `httpx`
- Rate limiting is built into `BaseScraper` via `AsyncRateLimiter`
- Config is loaded once and injected via dependency injection

## Environment Variables
- `DATABASE_URL`: PostgreSQL connection string
- `ANTHROPIC_API_KEY`: For Claude-based summarization
- `OPENAI_API_KEY`: For OpenAI-based summarization
- `GITHUB_TOKEN`: For GitHub API (higher rate limits)
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`: For Reddit API
- `QDRANT_URL`: Qdrant vector DB endpoint

## Testing
- Tests use `pytest` + `pytest-asyncio`
- HTTP mocking via `respx`
- Database tests use `aiosqlite` (no PostgreSQL required)
- Run with: `pytest tests/ -v --cov=researchpulse`
