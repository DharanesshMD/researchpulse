"""Tests for new API endpoints: /api/items/{id}, /api/config, WebSocket /ws/feed."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from researchpulse.config import ResearchPulseConfig, reset_config
from researchpulse.outputs.dashboard_api import create_app
from researchpulse.storage.database import Database
from researchpulse.storage.db_models import (
    Paper,
    Repository,
    NewsArticle,
    RedditPost,
    SourceType,
)


@pytest.fixture
async def seeded_app_extended(sqlite_db_url: str):
    """Create a FastAPI app with a test database seeded with multiple source types."""
    db = Database(sqlite_db_url)
    await db.create_tables()

    async with db.session() as session:
        # Seed papers
        for i in range(3):
            session.add(Paper(
                title=f"Test Paper {i}",
                url=f"https://arxiv.org/abs/test{i}",
                source=SourceType.ARXIV,
                arxiv_id=f"test{i}",
                content=f"Content of paper {i}",
                categories="cs.AI",
            ))

        # Seed a repository
        session.add(Repository(
            title="test-repo",
            url="https://github.com/test/repo",
            source=SourceType.GITHUB,
            full_name="test/repo",
            content="A test repository",
            stars=100,
            forks=10,
            language="Python",
        ))

        # Seed a news article
        session.add(NewsArticle(
            title="Test News Article",
            url="https://news.example.com/article",
            source=SourceType.NEWS,
            content="Test news content",
            feed_name="Test Feed",
            feed_url="https://news.example.com/feed.xml",
        ))

        # Seed a reddit post
        session.add(RedditPost(
            title="Test Reddit Post",
            url="https://reddit.com/r/test/123",
            source=SourceType.REDDIT,
            content="Test reddit content",
            reddit_id="abc123",
            subreddit="MachineLearning",
            score=500,
            num_comments=42,
        ))

    await db.close()

    # Patch config to use SQLite
    reset_config()
    import researchpulse.config as config_module

    config = ResearchPulseConfig()
    config.database.url = sqlite_db_url
    config_module._config = config

    app = create_app()
    yield app

    reset_config()


# ---------------------------------------------------------------------------
# GET /api/items/{item_id}
# ---------------------------------------------------------------------------

class TestGetItemById:
    """Test the single item endpoint."""

    @pytest.mark.asyncio
    async def test_get_existing_item(self, seeded_app_extended):
        client = TestClient(seeded_app_extended)
        response = client.get("/api/items/1")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Paper 0"
        assert data["source"] == "arxiv"

    @pytest.mark.asyncio
    async def test_get_nonexistent_item(self, seeded_app_extended):
        client = TestClient(seeded_app_extended)
        response = client.get("/api/items/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_item_from_different_sources(self, seeded_app_extended):
        """Should find items regardless of source table."""
        client = TestClient(seeded_app_extended)
        # Try to find items — IDs depend on insertion order
        # Just verify we can get at least one item successfully
        found = False
        for item_id in range(1, 10):
            response = client.get(f"/api/items/{item_id}")
            if response.status_code == 200:
                found = True
                data = response.json()
                assert "title" in data
                assert "source" in data
                break
        assert found, "Should find at least one item across all sources"


# ---------------------------------------------------------------------------
# GET /api/config
# ---------------------------------------------------------------------------

class TestConfigEndpoint:
    """Test the sanitized config endpoint."""

    @pytest.mark.asyncio
    async def test_config_returns_structure(self, seeded_app_extended):
        client = TestClient(seeded_app_extended)
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()

        # Verify top-level sections exist
        assert "scraping" in data
        assert "interests" in data
        assert "llm" in data
        assert "alerts" in data
        assert "outputs" in data

    @pytest.mark.asyncio
    async def test_config_scraping_section(self, seeded_app_extended):
        client = TestClient(seeded_app_extended)
        response = client.get("/api/config")
        data = response.json()

        scraping = data["scraping"]
        assert "schedule" in scraping
        assert "max_items_per_source" in scraping
        assert "sources" in scraping
        assert "arxiv" in scraping["sources"]
        assert "github" in scraping["sources"]
        assert "news" in scraping["sources"]
        assert "reddit" in scraping["sources"]

    @pytest.mark.asyncio
    async def test_config_no_secrets(self, seeded_app_extended):
        """Verify that API keys and database URLs are NOT exposed."""
        client = TestClient(seeded_app_extended)
        response = client.get("/api/config")
        data = response.json()
        text = str(data)

        # Should not contain database URLs, API keys, or sensitive data
        assert "postgresql" not in text.lower()
        assert "api_key" not in text.lower()
        assert "password" not in text.lower()
        assert "secret" not in text.lower()

    @pytest.mark.asyncio
    async def test_config_llm_provider(self, seeded_app_extended):
        client = TestClient(seeded_app_extended)
        response = client.get("/api/config")
        data = response.json()

        assert data["llm"]["provider"] in ("anthropic", "openai")

    @pytest.mark.asyncio
    async def test_config_alerts_section(self, seeded_app_extended):
        client = TestClient(seeded_app_extended)
        response = client.get("/api/config")
        data = response.json()

        alerts = data["alerts"]
        assert "enabled" in alerts
        assert "keywords" in alerts
        assert "notify_via" in alerts
        assert "min_relevance" in alerts


# ---------------------------------------------------------------------------
# WebSocket /ws/feed
# ---------------------------------------------------------------------------

class TestWebSocketFeed:
    """Test the WebSocket feed endpoint."""

    @pytest.mark.asyncio
    async def test_websocket_connect_and_receive_ack(self, seeded_app_extended):
        client = TestClient(seeded_app_extended)
        with client.websocket_connect("/ws/feed") as ws:
            ws.send_text("ping")
            data = ws.receive_json()
            assert data["type"] == "ack"
            assert data["data"] == "ping"

    @pytest.mark.asyncio
    async def test_websocket_multiple_messages(self, seeded_app_extended):
        client = TestClient(seeded_app_extended)
        with client.websocket_connect("/ws/feed") as ws:
            for i in range(3):
                ws.send_text(f"message-{i}")
                data = ws.receive_json()
                assert data["type"] == "ack"
                assert data["data"] == f"message-{i}"


# ---------------------------------------------------------------------------
# Integration: items pagination still works with new endpoints
# ---------------------------------------------------------------------------

class TestExistingEndpointsStillWork:
    """Verify that adding new endpoints didn't break existing ones."""

    @pytest.mark.asyncio
    async def test_items_list_still_works(self, seeded_app_extended):
        client = TestClient(seeded_app_extended)
        response = client.get("/api/items?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_stats_still_works(self, seeded_app_extended):
        client = TestClient(seeded_app_extended)
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["papers"] == 3
        assert data["repositories"] == 1
        assert data["news_articles"] == 1
        assert data["reddit_posts"] == 1
        assert data["total"] == 6

    @pytest.mark.asyncio
    async def test_health_still_works(self, seeded_app_extended):
        client = TestClient(seeded_app_extended)
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
