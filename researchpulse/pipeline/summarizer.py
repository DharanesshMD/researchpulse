"""
LLM summarizer for research content.

Generates concise summaries using configurable LLM providers
(Anthropic Claude or OpenAI GPT) via LangChain.

Output: 3-bullet TL;DR + key entities + key findings.
"""

from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

from researchpulse.config import LLMConfig
from researchpulse.utils.logging import get_logger
from researchpulse.utils.rate_limiter import AsyncRateLimiter

logger = get_logger("pipeline.summarizer")

SUMMARIZE_SYSTEM_PROMPT = """\
You are a research assistant that creates concise, structured summaries of \
academic papers, GitHub repositories, news articles, and Reddit discussions.

For each item, you MUST respond with valid JSON (no markdown, no explanation) \
in exactly this format:
{
  "summary": "• Bullet 1\\n• Bullet 2\\n• Bullet 3",
  "entities": ["entity1", "entity2", "entity3"],
  "key_findings": ["finding1", "finding2"]
}

Rules:
- "summary": Exactly 3 bullet points (use • as bullet character). Each bullet \
should be one concise sentence.
- "entities": 3-6 key entities (people, organizations, technologies, concepts).
- "key_findings": 1-3 main takeaways or contributions.
- Be specific and technical. Avoid vague language.
- Respond ONLY with the JSON object, nothing else.
"""

SUMMARIZE_USER_TEMPLATE = """\
Title: {title}
Source: {source}

Content:
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


def _parse_summary_response(text: str) -> dict[str, Any]:
    """Parse the LLM's JSON response, with fallback for non-JSON output."""
    text = text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        text = text.strip()

    try:
        result = json.loads(text)
        return {
            "summary": result.get("summary", ""),
            "entities": result.get("entities", []),
            "key_findings": result.get("key_findings", []),
        }
    except json.JSONDecodeError:
        # Fallback: use the raw text as summary
        logger.warning("Failed to parse JSON summary, using raw text")
        return {
            "summary": text[:500],
            "entities": [],
            "key_findings": [],
        }


class Summarizer:
    """
    Generate summaries of research items using LLMs.

    Output format: 3-bullet TL;DR + key entities + key findings.
    Supports both Anthropic Claude and OpenAI GPT via LangChain.
    """

    def __init__(
        self,
        config: LLMConfig | None = None,
        provider: str = "anthropic",
        model: str | None = None,
        rate_limit: float = 5.0,
    ) -> None:
        if config:
            self._llm = _create_llm(config)
            self.provider = config.provider
        else:
            # Backwards-compatible: create from explicit params
            from researchpulse.config import LLMConfig as LC, AnthropicLLMConfig, OpenAILLMConfig

            if provider == "anthropic":
                cfg = LC(provider="anthropic", anthropic=AnthropicLLMConfig(model=model or "claude-sonnet-4-20250514"))
            else:
                cfg = LC(provider="openai", openai=OpenAILLMConfig(model=model or "gpt-4o-mini"))
            self._llm = _create_llm(cfg)
            self.provider = provider

        self._rate_limiter = AsyncRateLimiter(rate=rate_limit)

    @classmethod
    def from_config(cls, llm_config: LLMConfig) -> Summarizer:
        """Create a Summarizer from the app's LLM config."""
        return cls(config=llm_config)

    async def summarize(
        self,
        text: str,
        title: str = "",
        source: str = "",
    ) -> dict[str, Any]:
        """
        Generate a summary for a single item.

        Args:
            text: The content to summarize.
            title: The item title (provides context).
            source: The source type (arxiv, github, news, reddit).

        Returns:
            {
                "summary": "• Bullet 1\\n• Bullet 2\\n• Bullet 3",
                "entities": ["entity1", "entity2"],
                "key_findings": ["finding1", "finding2"],
            }
        """
        if not text or not text.strip():
            return {"summary": "", "entities": [], "key_findings": []}

        # Truncate to avoid token limits (~6000 words ≈ ~8000 tokens)
        truncated_content = text[:24000]

        user_message = SUMMARIZE_USER_TEMPLATE.format(
            title=title or "Untitled",
            source=source or "unknown",
            content=truncated_content,
        )

        async with self._rate_limiter:
            response = await self._llm.ainvoke([
                SystemMessage(content=SUMMARIZE_SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ])

        return _parse_summary_response(response.content)

    async def summarize_batch(
        self,
        items: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """
        Generate summaries for a batch of items.

        Args:
            items: List of dicts with keys: "text", "title", "source".

        Returns:
            List of summary dicts (same order as input).
        """
        results: list[dict[str, Any]] = []

        for item in items:
            try:
                result = await self.summarize(
                    text=item.get("text", item.get("content", "")),
                    title=item.get("title", ""),
                    source=item.get("source", ""),
                )
                results.append(result)
            except Exception as e:
                logger.warning(
                    "Summarization failed for item",
                    title=item.get("title", "unknown"),
                    error=str(e),
                )
                results.append({"summary": "", "entities": [], "key_findings": []})

        logger.info("Batch summarization complete", total=len(items), successful=sum(1 for r in results if r["summary"]))
        return results
