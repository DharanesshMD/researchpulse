"""Tests for the topic classifier."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from researchpulse.config import InterestsConfig
from researchpulse.pipeline.classifier import TopicClassifier, _parse_classification_response


class TestParseClassificationResponse:
    """Test the JSON classification parser."""

    def test_valid_json(self):
        response = json.dumps({
            "topic": "Large language models",
            "confidence": 0.95,
            "relevance_score": 0.85,
            "reasoning": "Clearly about LLMs.",
        })
        result = _parse_classification_response(response)
        assert result["topic"] == "Large language models"
        assert result["confidence"] == 0.95
        assert result["relevance_score"] == 0.85

    def test_json_with_code_fences(self):
        response = '```json\n{"topic": "AI agents", "confidence": 0.9, "relevance_score": 0.8, "reasoning": "test"}\n```'
        result = _parse_classification_response(response)
        assert result["topic"] == "AI agents"

    def test_invalid_json_defaults(self):
        response = "Not valid JSON at all"
        result = _parse_classification_response(response)
        assert result["topic"] == "Other"
        assert result["confidence"] == 0.0


class TestTopicClassifier:
    """Test classifier with mocked LLM."""

    @pytest.fixture
    def classifier(self) -> TopicClassifier:
        c = TopicClassifier(
            interests=InterestsConfig(topics=["AI agents", "edge inference"]),
        )
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "topic": "AI agents",
                "confidence": 0.92,
                "relevance_score": 0.88,
                "reasoning": "Paper discusses autonomous AI agent architectures.",
            })
        ))
        c._llm = mock_llm
        return c

    @pytest.mark.asyncio
    async def test_classify_single(self, classifier: TopicClassifier):
        result = await classifier.classify(
            text="This paper presents a new framework for autonomous AI agents.",
            title="AgentBench",
            source="arxiv",
        )
        assert result["topic"] == "AI agents"
        assert result["confidence"] >= 0.8
        assert result["relevance_score"] > 0

    @pytest.mark.asyncio
    async def test_classify_empty_content(self, classifier: TopicClassifier):
        result = await classifier.classify(text="", title="")
        assert result["topic"] == "Other"
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_classify_batch(self, classifier: TopicClassifier):
        items = [
            {"text": "AI agent framework.", "title": "Paper 1", "source": "arxiv"},
            {"text": "Edge ML inference.", "title": "Paper 2", "source": "news"},
        ]
        results = await classifier.classify_batch(items)
        assert len(results) == 2
        assert all("topic" in r for r in results)

    @pytest.mark.asyncio
    async def test_classify_batch_handles_errors(self):
        c = TopicClassifier()
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("API error"))
        c._llm = mock_llm

        results = await c.classify_batch([
            {"text": "Some text", "title": "Test", "source": "news"},
        ])
        assert len(results) == 1
        assert results[0]["topic"] == "Other"

    def test_build_system_prompt(self, classifier: TopicClassifier):
        prompt = classifier._build_system_prompt()
        assert "AI agents" in prompt
        assert "edge inference" in prompt
        assert "Large language models" in prompt  # From default topics
