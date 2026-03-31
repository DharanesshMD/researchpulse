"""
Topic and relevance classifier for research content.

Classifies items by topic using LLM zero-shot classification
and scores relevance against user-defined interest profiles from config.yaml.
"""

from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

from researchpulse.config import LLMConfig, InterestsConfig
from researchpulse.utils.logging import get_logger
from researchpulse.utils.rate_limiter import AsyncRateLimiter

logger = get_logger("pipeline.classifier")

# Predefined topic taxonomy
DEFAULT_TOPICS = [
    "AI agents",
    "Large language models",
    "Computer vision",
    "Natural language processing",
    "Reinforcement learning",
    "Edge inference",
    "Healthcare AI",
    "Finance AI",
    "Legal AI",
    "Robotics",
    "Data engineering",
    "MLOps",
    "AI safety",
    "Other",
]

CLASSIFY_SYSTEM_PROMPT = """\
You are a research classifier. Given a research item (title + content), you must:

1. Assign the single most relevant topic from this list:
{topics}

2. Rate your confidence in the topic assignment (0.0 to 1.0).

3. Rate how relevant this item is to these user interests:
{interests}
If no interests are specified, set relevance_score to 0.5.

Respond with ONLY valid JSON in this exact format:
{{
  "topic": "the assigned topic",
  "confidence": 0.85,
  "relevance_score": 0.75,
  "reasoning": "Brief one-sentence explanation"
}}
"""

CLASSIFY_USER_TEMPLATE = """\
Title: {title}
Source: {source}

Content (first 2000 chars):
{content}
"""


def _create_llm(config: LLMConfig) -> BaseChatModel:
    """Create the appropriate LangChain LLM from config."""
    if config.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=config.anthropic.model,
            max_tokens=config.anthropic.max_tokens,
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
    else:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=config.openai.model,
            max_tokens=config.openai.max_tokens,
            api_key=os.environ.get("OPENAI_API_KEY", ""),
        )


def _parse_classification_response(text: str) -> dict[str, Any]:
    """Parse the LLM's JSON classification response."""
    text = text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        text = text.strip()

    try:
        result = json.loads(text)
        return {
            "topic": result.get("topic", "Other"),
            "confidence": float(result.get("confidence", 0.5)),
            "relevance_score": float(result.get("relevance_score", 0.5)),
            "reasoning": result.get("reasoning", ""),
        }
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse classification JSON, using defaults")
        return {
            "topic": "Other",
            "confidence": 0.0,
            "relevance_score": 0.5,
            "reasoning": "Classification failed",
        }


class TopicClassifier:
    """
    Classify research items by topic and relevance.

    Uses LLM for zero-shot classification against a predefined topic list.
    Scores relevance against user-defined interest profiles.
    """

    def __init__(
        self,
        config: LLMConfig | None = None,
        interests: InterestsConfig | None = None,
        topics: list[str] | None = None,
        rate_limit: float = 5.0,
    ) -> None:
        self.topics = topics or DEFAULT_TOPICS
        self.interests = interests or InterestsConfig()

        if config:
            self._llm = _create_llm(config)
        else:
            # Default to anthropic
            from researchpulse.config import LLMConfig as LC

            self._llm = _create_llm(LC())

        self._rate_limiter = AsyncRateLimiter(rate=rate_limit)

    @classmethod
    def from_config(
        cls,
        llm_config: LLMConfig,
        interests_config: InterestsConfig,
    ) -> TopicClassifier:
        """Create a TopicClassifier from app config."""
        return cls(config=llm_config, interests=interests_config)

    def _build_system_prompt(self) -> str:
        """Build the system prompt with current topics and interests."""
        topics_str = "\n".join(f"- {t}" for t in self.topics)
        interests_str = ", ".join(self.interests.topics) if self.interests.topics else "None specified"
        return CLASSIFY_SYSTEM_PROMPT.format(
            topics=topics_str,
            interests=interests_str,
        )

    async def classify(
        self,
        text: str,
        title: str = "",
        source: str = "",
    ) -> dict[str, Any]:
        """
        Classify a single item.

        Args:
            text: The content to classify.
            title: The item title.
            source: The source type.

        Returns:
            {
                "topic": "AI agents",
                "confidence": 0.92,
                "relevance_score": 0.85,
                "reasoning": "Brief explanation",
            }
        """
        if not text and not title:
            return {
                "topic": "Other",
                "confidence": 0.0,
                "relevance_score": 0.0,
                "reasoning": "No content provided",
            }

        # Truncate content for classification (doesn't need full text)
        truncated = text[:2000] if text else ""

        user_message = CLASSIFY_USER_TEMPLATE.format(
            title=title or "Untitled",
            source=source or "unknown",
            content=truncated,
        )

        async with self._rate_limiter:
            response = await self._llm.ainvoke([
                SystemMessage(content=self._build_system_prompt()),
                HumanMessage(content=user_message),
            ])

        return _parse_classification_response(response.content)

    async def classify_batch(
        self,
        items: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """
        Classify a batch of items.

        Args:
            items: List of dicts with keys: "text"/"content", "title", "source".

        Returns:
            List of classification dicts (same order as input).
        """
        results: list[dict[str, Any]] = []

        for item in items:
            try:
                result = await self.classify(
                    text=item.get("text", item.get("content", "")),
                    title=item.get("title", ""),
                    source=item.get("source", ""),
                )
                results.append(result)
            except Exception as e:
                logger.warning(
                    "Classification failed for item",
                    title=item.get("title", "unknown"),
                    error=str(e),
                )
                results.append({
                    "topic": "Other",
                    "confidence": 0.0,
                    "relevance_score": 0.5,
                    "reasoning": f"Error: {e}",
                })

        logger.info(
            "Batch classification complete",
            total=len(items),
            topics_found=len(set(r["topic"] for r in results)),
        )
        return results
