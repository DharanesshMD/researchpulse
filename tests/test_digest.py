"""Tests for the digest generator."""

from __future__ import annotations

import pytest

from researchpulse.config import ResearchPulseConfig
from researchpulse.storage.database import Database
from researchpulse.storage.db_models import Paper, Repository, NewsArticle, RedditPost, SourceType
from researchpulse.outputs.digest_generator import DigestGenerator


class TestDigestGenerator:
    """Test digest generation with a real SQLite database."""

    @pytest.fixture
    async def seeded_db(self, sqlite_db_url: str):
        """Seed a test database with sample items."""
        db = Database(sqlite_db_url)
        await db.create_tables()

        async with db.session() as session:
            session.add(Paper(
                title="Attention Is All You Need",
                url="https://arxiv.org/abs/1706.03762",
                source=SourceType.ARXIV,
                arxiv_id="1706.03762",
                content="We propose a new architecture called the Transformer.",
                summary="• Introduces Transformer architecture\n• Self-attention mechanism\n• State-of-the-art results",
                categories="cs.CL,cs.AI",
            ))
            session.add(Repository(
                title="huggingface/transformers",
                url="https://github.com/huggingface/transformers",
                source=SourceType.GITHUB,
                full_name="huggingface/transformers",
                description="State-of-the-art NLP",
                stars=120000,
                language="Python",
            ))
            session.add(NewsArticle(
                title="AI Breakthrough in 2024",
                url="https://example.com/ai-2024",
                source=SourceType.NEWS,
                content="Major AI breakthroughs were announced.",
                feed_name="TechCrunch",
            ))
            session.add(RedditPost(
                title="[D] Best practices for fine-tuning",
                url="https://reddit.com/r/ML/finetuning",
                source=SourceType.REDDIT,
                reddit_id="ft001",
                subreddit="MachineLearning",
                score=350,
                content="Here are some tips for fine-tuning LLMs.",
            ))

        await db.close()
        return sqlite_db_url

    @pytest.mark.asyncio
    async def test_generate_markdown(self, seeded_db: str):
        config = ResearchPulseConfig()
        config.database.url = seeded_db
        generator = DigestGenerator(config=config, frequency="daily", fmt="markdown")

        digest = await generator.generate()

        assert "# ResearchPulse Daily Digest" in digest
        assert "Attention Is All You Need" in digest
        assert "huggingface/transformers" in digest
        assert "AI Breakthrough" in digest
        assert "fine-tuning" in digest

    @pytest.mark.asyncio
    async def test_generate_html(self, seeded_db: str):
        config = ResearchPulseConfig()
        config.database.url = seeded_db
        generator = DigestGenerator(config=config, frequency="weekly", fmt="html")

        digest = await generator.generate()

        assert "<!DOCTYPE html>" in digest
        assert "Weekly Digest" in digest
        assert "Attention Is All You Need" in digest
        assert '<div class="item">' in digest

    @pytest.mark.asyncio
    async def test_generate_empty_db(self, sqlite_db_url: str):
        """Empty database should produce a 'no items' digest."""
        db = Database(sqlite_db_url)
        await db.create_tables()
        await db.close()

        config = ResearchPulseConfig()
        config.database.url = sqlite_db_url
        generator = DigestGenerator(config=config)

        digest = await generator.generate()
        assert "No new items" in digest

    @pytest.mark.asyncio
    async def test_save_to_file(self, seeded_db: str, tmp_path):
        config = ResearchPulseConfig()
        config.database.url = seeded_db
        generator = DigestGenerator(config=config, fmt="markdown")

        path = await generator.save_to_file(str(tmp_path))
        assert path.endswith(".md")

        from pathlib import Path
        content = Path(path).read_text()
        assert "ResearchPulse" in content
