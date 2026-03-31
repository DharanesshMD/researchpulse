"""
Topic and relevance classifier for research content (Phase 2).

Will classify items by topic and score relevance against
user-defined interest profiles from config.yaml.
"""

from __future__ import annotations


class TopicClassifier:
    """
    Classify research items by topic and relevance.

    Uses LLM for zero-shot classification or embedding similarity
    against the user's interest profile.
    """

    TOPICS = [
        "AI agents",
        "Large language models",
        "Computer vision",
        "NLP",
        "Reinforcement learning",
        "Edge inference",
        "Healthcare AI",
        "Finance AI",
        "Legal AI",
        "Robotics",
        "Other",
    ]

    def __init__(self, interest_topics: list[str] | None = None) -> None:
        self.interest_topics = interest_topics or []

    async def classify(self, text: str, title: str = "") -> dict:
        """
        Classify a single item.

        Returns:
            {
                "topic": "AI agents",
                "confidence": 0.92,
                "relevance_score": 0.85,
            }
        """
        raise NotImplementedError("Classification is implemented in Phase 2")

    async def classify_batch(self, items: list[dict]) -> list[dict]:
        """Classify a batch of items."""
        raise NotImplementedError("Classification is implemented in Phase 2")
