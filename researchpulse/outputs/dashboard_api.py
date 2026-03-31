"""
FastAPI dashboard API.

REST endpoints for the Next.js dashboard:
- GET  /api/items          — paginated feed of all items
- GET  /api/items/{source} — items filtered by source
- POST /api/ask            — RAG query endpoint
- GET  /api/stats          — dashboard statistics
- POST /api/alerts/check   — manually trigger alert check
- GET  /api/digest         — generate and return a digest
- GET  /api/health         — health check
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from researchpulse.config import get_config, reset_config
from researchpulse.utils.logging import get_logger

logger = get_logger("outputs.api")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str
    source_filter: Optional[str] = None
    top_k: int = 10


class AskResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]]
    question: str


class StatsResponse(BaseModel):
    papers: int
    repositories: int
    news_articles: int
    reddit_posts: int
    total: int


class ItemResponse(BaseModel):
    id: int
    title: str
    url: str
    source: str
    content: str
    summary: Optional[str] = None
    tags: Optional[str] = None
    relevance_score: Optional[float] = None
    published_at: Optional[str] = None
    scraped_at: Optional[str] = None


class PaginatedResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    offset: int
    limit: int


class DigestResponse(BaseModel):
    content: str
    format: str
    frequency: str


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(config_path: str | None = None) -> FastAPI:
    """
    Create the FastAPI application with all routes.

    Args:
        config_path: Optional path to config.yaml.

    Returns:
        Configured FastAPI app instance.
    """
    if config_path:
        reset_config()
        get_config(config_path)

    app = FastAPI(
        title="ResearchPulse API",
        description="Open Source AI Research Scraper — REST API",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -------------------------------------------------------------------
    # Health check
    # -------------------------------------------------------------------
    @app.get("/api/health")
    async def health():
        return {"status": "ok", "service": "researchpulse"}

    # -------------------------------------------------------------------
    # Items feed
    # -------------------------------------------------------------------
    @app.get("/api/items", response_model=PaginatedResponse)
    async def list_items(
        source: Optional[str] = Query(None, description="Filter by source"),
        offset: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
    ):
        """Get a paginated list of research items."""
        from researchpulse.storage.database import Database
        from researchpulse.storage.repository import (
            PaperRepository,
            RepositoryRepo,
            NewsArticleRepository,
            RedditPostRepository,
        )

        config = get_config()
        db = Database(config.database.url)

        try:
            async with db.session() as session:
                all_items: list[dict[str, Any]] = []
                total = 0

                repos_map = {
                    "arxiv": PaperRepository,
                    "github": RepositoryRepo,
                    "news": NewsArticleRepository,
                    "reddit": RedditPostRepository,
                }

                if source and source in repos_map:
                    repo = repos_map[source](session)
                    items = await repo.list_all(offset=offset, limit=limit)
                    total = await repo.count()
                    all_items = [_model_to_dict(i) for i in items]
                else:
                    # Fetch from all sources
                    for repo_cls in repos_map.values():
                        repo = repo_cls(session)
                        items = await repo.list_all(offset=offset, limit=limit)
                        count = await repo.count()
                        total += count
                        all_items.extend(_model_to_dict(i) for i in items)

                    # Sort by scraped_at descending, limit
                    all_items.sort(key=lambda x: x.get("scraped_at", ""), reverse=True)
                    all_items = all_items[:limit]

            return PaginatedResponse(
                items=all_items,
                total=total,
                offset=offset,
                limit=limit,
            )
        finally:
            await db.close()

    # -------------------------------------------------------------------
    # RAG query
    # -------------------------------------------------------------------
    @app.post("/api/ask", response_model=AskResponse)
    async def ask_question(request: AskRequest):
        """Ask a question using RAG over the knowledge base."""
        from researchpulse.outputs.rag_query import RAGQuery

        config = get_config()
        rag = RAGQuery(config=config)

        try:
            result = await rag.ask(
                question=request.question,
                source_filter=request.source_filter,
                top_k=request.top_k,
            )
            return AskResponse(**result)
        except Exception as e:
            logger.error("RAG query failed", error=str(e))
            raise HTTPException(status_code=500, detail=f"Query failed: {e}")
        finally:
            await rag.close()

    # -------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------
    @app.get("/api/stats", response_model=StatsResponse)
    async def get_stats():
        """Get counts of items by source."""
        from researchpulse.storage.database import Database
        from researchpulse.storage.repository import (
            PaperRepository,
            RepositoryRepo,
            NewsArticleRepository,
            RedditPostRepository,
        )

        config = get_config()
        db = Database(config.database.url)

        try:
            async with db.session() as session:
                papers = await PaperRepository(session).count()
                repos = await RepositoryRepo(session).count()
                news = await NewsArticleRepository(session).count()
                reddit = await RedditPostRepository(session).count()

            return StatsResponse(
                papers=papers,
                repositories=repos,
                news_articles=news,
                reddit_posts=reddit,
                total=papers + repos + news + reddit,
            )
        finally:
            await db.close()

    # -------------------------------------------------------------------
    # Digest
    # -------------------------------------------------------------------
    @app.get("/api/digest", response_model=DigestResponse)
    async def generate_digest(
        frequency: str = Query("daily", description="daily or weekly"),
        fmt: str = Query("markdown", description="markdown or html"),
    ):
        """Generate and return a research digest."""
        from researchpulse.outputs.digest_generator import DigestGenerator

        config = get_config()
        generator = DigestGenerator(config=config, frequency=frequency, fmt=fmt)

        try:
            content = await generator.generate()
            return DigestResponse(content=content, format=fmt, frequency=frequency)
        except Exception as e:
            logger.error("Digest generation failed", error=str(e))
            raise HTTPException(status_code=500, detail=f"Digest failed: {e}")

    # -------------------------------------------------------------------
    # Alerts
    # -------------------------------------------------------------------
    @app.post("/api/alerts/check")
    async def check_alerts(items: list[dict[str, Any]]):
        """Manually check items against alert rules."""
        from researchpulse.outputs.alert_engine import AlertEngine

        config = get_config()
        engine = AlertEngine(config=config)

        matches = await engine.check(items)
        return {
            "matches": len(matches),
            "items": matches,
        }

    return app


def _model_to_dict(item: Any) -> dict[str, Any]:
    """Convert a SQLModel instance to a dict for API responses."""
    from datetime import datetime

    data = {}
    for key, value in item.__dict__.items():
        if key.startswith("_"):
            continue
        if isinstance(value, datetime):
            data[key] = value.isoformat()
        else:
            data[key] = value
    return data
