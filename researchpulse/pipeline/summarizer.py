"""
LLM summarizer for research content (Phase 2).

Will generate concise summaries using configurable LLM providers
(Anthropic Claude or OpenAI GPT).
"""

from __future__ import annotations


class Summarizer:
    """
    Generate summaries of research items using LLMs.

    Output format: 3-bullet TL;DR + key entities extracted.
    """

    def __init__(self, provider: str = "anthropic", model: str | None = None) -> None:
        self.provider = provider
        self.model = model

    async def summarize(self, text: str, title: str = "") -> dict:
        """
        Generate a summary for a single item.

        Returns:
            {
                "summary": "3-bullet TL;DR",
                "entities": ["entity1", "entity2"],
                "key_findings": ["finding1", "finding2"],
            }
        """
        raise NotImplementedError("Summarization is implemented in Phase 2")

    async def summarize_batch(self, items: list[dict]) -> list[dict]:
        """Generate summaries for a batch of items."""
        raise NotImplementedError("Summarization is implemented in Phase 2")
