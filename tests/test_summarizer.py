"""Tests for the LLM summarizer."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from researchpulse.pipeline.summarizer import Summarizer, _parse_summary_response


class TestParseSummaryResponse:
    """Test the JSON response parser."""

    def test_valid_json(self):
        response = json.dumps({
            "summary": "• Point 1\n• Point 2\n• Point 3",
            "entities": ["LLM", "GPT"],
            "key_findings": ["Finding 1"],
        })
        result = _parse_summary_response(response)
        assert "Point 1" in result["summary"]
        assert "LLM" in result["entities"]
        assert len(result["key_findings"]) == 1

    def test_json_with_code_fences(self):
        response = '```json\n{"summary": "test", "entities": [], "key_findings": []}\n```'
        result = _parse_summary_response(response)
        assert result["summary"] == "test"

    def test_invalid_json_fallback(self):
        response = "This is not JSON, just a plain text summary."
        result = _parse_summary_response(response)
        assert "plain text summary" in result["summary"]
        assert result["entities"] == []

    def test_partial_json(self):
        response = json.dumps({"summary": "Only summary, missing other keys"})
        result = _parse_summary_response(response)
        assert result["summary"] == "Only summary, missing other keys"
        assert result["entities"] == []
        assert result["key_findings"] == []


class TestSummarizer:
    """Test summarizer with mocked LLM."""

    @pytest.fixture
    def summarizer(self) -> Summarizer:
        """Create a summarizer with a mocked LLM."""
        s = Summarizer(provider="anthropic")
        # Replace LLM with mock
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "summary": "• This paper introduces X.\n• It achieves Y.\n• Impact is Z.",
                "entities": ["X", "Y", "Z"],
                "key_findings": ["X outperforms baselines"],
            })
        ))
        s._llm = mock_llm
        return s

    @pytest.mark.asyncio
    async def test_summarize_single(self, summarizer: Summarizer):
        result = await summarizer.summarize(
            text="This is a paper about large language models.",
            title="Test Paper",
            source="arxiv",
        )
        assert "summary" in result
        assert len(result["entities"]) > 0
        assert len(result["key_findings"]) > 0

    @pytest.mark.asyncio
    async def test_summarize_empty_text(self, summarizer: Summarizer):
        result = await summarizer.summarize(text="", title="")
        assert result["summary"] == ""
        assert result["entities"] == []

    @pytest.mark.asyncio
    async def test_summarize_batch(self, summarizer: Summarizer):
        items = [
            {"text": "Paper about LLMs.", "title": "Paper 1", "source": "arxiv"},
            {"text": "GitHub repo for RAG.", "title": "Repo 1", "source": "github"},
        ]
        results = await summarizer.summarize_batch(items)
        assert len(results) == 2
        assert all("summary" in r for r in results)

    @pytest.mark.asyncio
    async def test_summarize_batch_handles_errors(self, monkeypatch):
        """Should handle LLM errors gracefully in batch mode."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-test-key")
        s = Summarizer(provider="openai")
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("API error"))
        s._llm = mock_llm

        results = await s.summarize_batch([
            {"text": "Some text", "title": "Test", "source": "news"},
        ])
        assert len(results) == 1
        assert results[0]["summary"] == ""
