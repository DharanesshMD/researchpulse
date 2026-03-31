"""Tests for the FastAPI dashboard API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from researchpulse.config import ResearchPulseConfig, reset_config
from researchpulse.outputs.dashboard_api import create_app
from researchpulse.storage.database import Database
from researchpulse.storage.db_models import Paper, SourceType


@pytest.fixture
async def seeded_app(sqlite_db_url: str):
    """Create a FastAPI app with a seeded test database."""
    # Seed DB
    db = Database(sqlite_db_url)
    await db.create_tables()

    async with db.session() as session:
        for i in range(5):
            session.add(Paper(
                title=f"Test Paper {i}",
                url=f"https://arxiv.org/abs/{i}",
                source=SourceType.ARXIV,
                arxiv_id=str(i),
                content=f"Content of paper {i}",
            ))

    await db.close()

    # Patch config to use SQLite
    reset_config()
    from researchpulse.config import get_config, _config
    import researchpulse.config as config_module

    config = ResearchPulseConfig()
    config.database.url = sqlite_db_url
    config_module._config = config

    app = create_app()
    yield app

    reset_config()


class TestHealthEndpoint:
    """Test the health check endpoint."""

    def test_health(self):
        app = create_app()
        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestItemsEndpoint:
    """Test the items feed endpoint."""

    @pytest.mark.asyncio
    async def test_list_items(self, seeded_app):
        client = TestClient(seeded_app)
        response = client.get("/api/items?limit=3")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["limit"] == 3

    @pytest.mark.asyncio
    async def test_list_items_with_source_filter(self, seeded_app):
        client = TestClient(seeded_app)
        response = client.get("/api/items?source=arxiv&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5  # We seeded 5 papers


class TestStatsEndpoint:
    """Test the stats endpoint."""

    @pytest.mark.asyncio
    async def test_stats(self, seeded_app):
        client = TestClient(seeded_app)
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["papers"] == 5
        assert data["total"] == 5
