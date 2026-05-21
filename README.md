# 🕷️ ResearchPulse

**Open Source AI Research Scraper** — a production-grade, multi-source research intelligence platform.

Scrape academic papers, GitHub repos, news articles, and Reddit posts. Process through an LLM pipeline for semantic chunking, embedding generation, summarization, classification, and RAG-based querying.

---

## 🚀 Key Features

*   **Multi-Source Scrapers:** Integrates directly with ArXiv, GitHub, News/RSS feeds, and Reddit.
*   **Production-Grade Reliability:** 
    *   **Proxy Rotation:** Dynamic round-robin or random routing through proxy pools to bypass IP bans.
    *   **Session Isolation:** Automatic session resetting (clearing cookie jars and headers) on connection blocks.
    *   **User-Agent Spofing:** Rotates between realistic, modern browser User-Agent strings.
    *   **Exponential Backoff & Jitter:** Tenacity-backed retries on connection failures, `429 Too Many Requests`, and server errors.
*   **AI Processing Pipeline:** 
    *   Semantic text chunking and vector embedding generation.
    *   Automatic LLM-based categorization and summarization (Anthropic Claude & OpenAI GPT).
    *   Semantic deduplication to avoid archiving redundant information.
*   **Downstream Deliverables:**
    *   Interactive RAG-based search CLI and FastAPI Dashboard.
    *   Custom daily or weekly markdown digests.
    *   Automated notifications (Slack, ntfy, email) on keyword matches.

---

## ⚡ Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/DharanesshMD/researchpulse.git
cd researchpulse

# Set up virtual environment and install in developer mode
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Configuration & Run

```bash
# Setup config file
cp config.yaml config.yaml  # Edit topics, keywords, API credentials, and proxy settings

# Verify system connectivity & database settings
researchpulse check

# Verify proxy/IP quality & reachability to target platforms
researchpulse check-ips

# Run a specific scraper
researchpulse run arxiv

# Scrape all sources, process through LLM pipeline, and save to DB
researchpulse run-all --save
```

---

## 🛠️ Reliability & Scraping at Scale

When scraping under high load, websites detect and block simple bots. ResearchPulse is built for production environments:

```yaml
# config.yaml (Reliability Settings)
scraping:
  max_retries: 3                  # Retry up to 3 times on blockages/errors
  user_agent_rotation: true       # Randomize headers per run or on blocks
  proxies:
    enabled: true
    ips:
      - "http://username:password@proxy1.example.com:8080"
      - "http://username:password@proxy2.example.com:8080"
    rotation_strategy: "round_robin"
```

For a deep-dive into managing scraping nodes, residential vs. datacenter proxies, and session management, see the **[Production Scraping Guide](docs/scraping_production.md)**.

---

## 📋 Architecture

```
┌────────────────────────────────────────────────────────┐
│                        SOURCES                         │
│   (ArXiv API, GitHub Search, Reddit PRAW, RSS Feeds)   │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│                    SCRAPER ENGINE                      │
│     * Rate Limiting        * Proxy Rotation            │
│     * Header Spoofing      * Exponential Backoff       │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│                  PROCESSING PIPELINE                   │
│   (Chunking ➔ Embedding ➔ LLM Summarization ➔ Dedup)    │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│                     OUTPUT LAYER                       │
│    (PostgreSQL, Qdrant, Alerts, Digests, Dashboard)    │
└────────────────────────────────────────────────────────┘
```

For full details on development workflows, commands, and tests, see **[CLAUDE.md](CLAUDE.md)**.

## 📄 License

MIT
