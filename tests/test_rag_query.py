"""Tests for the RAG query interface."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from researchpulse.config import ResearchPulseConfig
from researchpulse.outputs.rag_query import RAGQuery, _format_context


class TestFormatContext:
    """Test context formatting for LLM."""

    def test_formats_results(self):
        results = [
            {
                "title": "Paper A",
                "source": "arxiv",
                "content_preview": "About transformers.",
                "summary": "",
                "url": "https://arxiv.org/abs/1",
                "score": 0.95,
            },
            {
                "title": "Repo B",
                "source": "github",
                "content_preview": "LLM toolkit.",
                "summary": "A toolkit for LLMs.",
                "url": "https://github.com/b",
                "score": 0.88,
            },
        ]
        ctx = _format_context(results)
        assert "Paper A" in ctx
        assert "Repo B" in ctx
        assert "0.95" in ctx
        # Should prefer summary over content_preview
        assert "A toolkit for LLMs." in ctx

    def test_empty_results(self):
        ctx = _format_context([])
        assert "No relevant documents" in ctx


class TestRAGQuery:
    """Test RAG query with mocked embedder, vector store, and LLM."""

    @pytest.fixture
    def rag(self) -> RAGQuery:
        config = ResearchPulseConfig()
        r = RAGQuery.__new__(RAGQuery)
        r.config = config
        r.top_k = 5

        # Mock embedder
        r._embedder = AsyncMock()
        r._embedder.embed = AsyncMock(return_value=[0.1] * 1536)
        r._embedder.close = AsyncMock()

        # Mock vector store
        r._vector_store = AsyncMock()
        r._vector_store.search = AsyncMock(return_value=[
            {
                "title": "Found Paper",
                "source": "arxiv",
                "content_preview": "About language models.",
                "summary": "A paper about LLMs.",
                "url": "https://arxiv.org/abs/123",
                "score": 0.92,
            },
        ])
        r._vector_store.close = AsyncMock()

        # Mock LLM
        r._llm = AsyncMock()
        r._llm.ainvoke = AsyncMock(return_value=MagicMock(
            content="Based on the retrieved paper, language models are..."
        ))

        return r

    @pytest.mark.asyncio
    async def test_ask_returns_answer(self, rag: RAGQuery):
        result = await rag.ask("What are language models?")

        assert "answer" in result
        assert "sources" in result
        assert "question" in result
        assert result["question"] == "What are language models?"
        assert "language models" in result["answer"]
        assert len(result["sources"]) == 1
        assert result["sources"][0]["title"] == "Found Paper"

    @pytest.mark.asyncio
    async def test_ask_empty_question(self, rag: RAGQuery):
        result = await rag.ask("")
        assert "Please provide" in result["answer"]
        assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_ask_no_results(self, rag: RAGQuery):
        rag._vector_store.search = AsyncMock(return_value=[])
        result = await rag.ask("Something obscure?")
        assert "couldn't find" in result["answer"]

    @pytest.mark.asyncio
    async def test_ask_passes_source_filter(self, rag: RAGQuery):
        await rag.ask("test", source_filter="arxiv")
        rag._vector_store.search.assert_called_once()
        call_kwargs = rag._vector_store.search.call_args
        assert call_kwargs.kwargs.get("source_filter") == "arxiv"

    @pytest.mark.asyncio
    async def test_close(self, rag: RAGQuery):
        await rag.close()
        rag._embedder.close.assert_called_once()
        rag._vector_store.close.assert_called_once()
