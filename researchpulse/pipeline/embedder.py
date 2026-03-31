"""
Embedding generator for research content.

Generates vector embeddings using configurable providers:
- OpenAI (text-embedding-3-small / text-embedding-3-large)
- Anthropic (via Voyager embeddings or fallback to OpenAI)

Supports single and batch embedding with automatic rate limiting.
"""

from __future__ import annotations

import os
from typing import Literal

from researchpulse.config import LLMConfig
from researchpulse.utils.logging import get_logger
from researchpulse.utils.rate_limiter import AsyncRateLimiter

logger = get_logger("pipeline.embedder")

# Embedding dimensions by model
MODEL_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

DEFAULT_MODEL = "text-embedding-3-small"


class EmbeddingGenerator:
    """
    Generate embeddings for text chunks.

    Uses OpenAI's embedding API by default (works with both
    anthropic and openai LLM provider configs — embeddings always use OpenAI).
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        batch_size: int = 100,
        rate_limit: float = 50.0,
    ) -> None:
        self.model = model
        self.batch_size = batch_size
        self.dimensions = MODEL_DIMENSIONS.get(model, 1536)
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._rate_limiter = AsyncRateLimiter(rate=rate_limit)
        self._client = None

    @classmethod
    def from_config(cls, llm_config: LLMConfig) -> EmbeddingGenerator:
        """Create an EmbeddingGenerator from the app's LLM config."""
        # Embeddings always use OpenAI API regardless of LLM provider
        return cls(model=DEFAULT_MODEL)

    def _get_client(self):
        """Lazy-init the OpenAI async client."""
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def embed(self, text: str) -> list[float]:
        """
        Generate an embedding for a single text string.

        Args:
            text: The text to embed. Will be truncated if too long.

        Returns:
            List of floats representing the embedding vector.
        """
        if not text or not text.strip():
            return [0.0] * self.dimensions

        # Truncate to ~8000 tokens (~32000 chars) to stay within API limits
        truncated = text[:32000]

        async with self._rate_limiter:
            client = self._get_client()
            response = await client.embeddings.create(
                model=self.model,
                input=truncated,
            )

        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a batch of texts.

        Automatically splits into sub-batches to respect API limits.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (same order as input).
        """
        if not texts:
            return []

        all_embeddings: list[list[float]] = []

        # Process in sub-batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]

            # Prepare: truncate and handle empties
            processed = []
            empty_indices = set()
            for j, text in enumerate(batch):
                if not text or not text.strip():
                    empty_indices.add(j)
                    processed.append("empty")  # Placeholder — won't be sent
                else:
                    processed.append(text[:32000])

            # Filter out empties for the API call
            real_texts = [t for j, t in enumerate(processed) if j not in empty_indices]

            if real_texts:
                async with self._rate_limiter:
                    client = self._get_client()
                    response = await client.embeddings.create(
                        model=self.model,
                        input=real_texts,
                    )

                real_embeddings = [item.embedding for item in response.data]
            else:
                real_embeddings = []

            # Reconstruct full batch with zeros for empty texts
            real_idx = 0
            for j in range(len(batch)):
                if j in empty_indices:
                    all_embeddings.append([0.0] * self.dimensions)
                else:
                    all_embeddings.append(real_embeddings[real_idx])
                    real_idx += 1

            logger.debug(
                "Batch embedded",
                batch_index=i // self.batch_size,
                batch_size=len(batch),
                real_count=len(real_texts),
            )

        logger.info("Embedding complete", total=len(texts), model=self.model)
        return all_embeddings

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.close()
            self._client = None
