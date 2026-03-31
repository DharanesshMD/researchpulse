# 🕷️ ResearchPulse

**Open Source AI Research Scraper** — a production-grade, multi-source research intelligence platform.

Scrape academic papers, GitHub repos, news articles, and Reddit posts. Process through an LLM pipeline for summarization, classification, and RAG-based querying.

## Quick Start

```bash
pip install -e ".[dev]"
cp config.yaml config.yaml  # edit your topics
researchpulse check          # verify setup
researchpulse run arxiv      # scrape ArXiv
researchpulse run-all --save # scrape everything + save to DB
```

## Architecture

```
Scrapers → Processing Pipeline → Output Layer
(ArXiv, GitHub, News, Reddit) → (Chunk, Embed, Summarize, Classify) → (Digest, RAG, Alerts, Dashboard)
```

See [CLAUDE.md](CLAUDE.md) for full developer documentation.

## License

MIT
