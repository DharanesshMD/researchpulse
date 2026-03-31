"""
Semantic deduplication via cosine similarity.

Identifies and merges duplicate content that appears across multiple sources
(e.g., same story on HN + Reddit + TechCrunch).

URL-based exact dedup is handled at the database layer.
This module handles semantic (near-duplicate) detection via embeddings.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from researchpulse.utils.logging import get_logger

logger = get_logger("pipeline.deduplicator")


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0

    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)


@dataclass
class DuplicateGroup:
    """A group of semantically duplicate items."""

    indices: list[int] = field(default_factory=list)
    primary_index: int = 0  # Index of the highest-quality item
    max_similarity: float = 0.0


class SemanticDeduplicator:
    """
    Detect and merge semantically duplicate items.

    Uses embedding cosine similarity to find near-duplicates.
    Groups items that exceed the similarity threshold, then keeps
    the highest-quality version from each group.

    Quality heuristic: longer content + more metadata = higher quality.
    """

    def __init__(self, similarity_threshold: float = 0.92) -> None:
        self.similarity_threshold = similarity_threshold

    async def find_duplicates(
        self,
        items: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> list[DuplicateGroup]:
        """
        Find groups of duplicate items based on embedding similarity.

        Args:
            items: List of item dicts (must have "title", "content", "source" keys).
            embeddings: Corresponding embedding vectors for each item.

        Returns:
            List of DuplicateGroup instances. Items not in any group are unique.
        """
        n = len(items)
        if n != len(embeddings):
            raise ValueError(f"Items ({n}) and embeddings ({len(embeddings)}) must have same length")

        if n <= 1:
            return []

        # Track which items have been assigned to a group
        assigned: set[int] = set()
        groups: list[DuplicateGroup] = []

        # O(n²) pairwise comparison — fine for typical batch sizes (<1000)
        for i in range(n):
            if i in assigned:
                continue

            group_indices = [i]
            max_sim = 0.0

            for j in range(i + 1, n):
                if j in assigned:
                    continue

                sim = _cosine_similarity(embeddings[i], embeddings[j])
                if sim >= self.similarity_threshold:
                    group_indices.append(j)
                    max_sim = max(max_sim, sim)

            if len(group_indices) > 1:
                # Find the highest quality item in the group
                primary = self._pick_primary(items, group_indices)
                groups.append(DuplicateGroup(
                    indices=group_indices,
                    primary_index=primary,
                    max_similarity=max_sim,
                ))
                assigned.update(group_indices)

        if groups:
            total_dupes = sum(len(g.indices) - 1 for g in groups)
            logger.info(
                "Duplicates found",
                groups=len(groups),
                total_duplicates=total_dupes,
                threshold=self.similarity_threshold,
            )

        return groups

    async def deduplicate(
        self,
        items: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> list[dict[str, Any]]:
        """
        Remove duplicates, keeping the highest-quality version from each group.

        Args:
            items: List of item dicts.
            embeddings: Corresponding embedding vectors.

        Returns:
            Deduplicated list of items.
        """
        groups = await self.find_duplicates(items, embeddings)

        if not groups:
            return items

        # Collect indices to remove (non-primary members of each group)
        remove_indices: set[int] = set()
        for group in groups:
            for idx in group.indices:
                if idx != group.primary_index:
                    remove_indices.add(idx)

        # Keep items not in remove set
        result = [item for i, item in enumerate(items) if i not in remove_indices]

        logger.info(
            "Deduplication complete",
            original=len(items),
            deduplicated=len(result),
            removed=len(remove_indices),
        )

        return result

    def _pick_primary(self, items: list[dict[str, Any]], indices: list[int]) -> int:
        """
        Pick the highest-quality item from a group of duplicates.

        Quality heuristic (in order of priority):
        1. Longer content is better (more info)
        2. Items with summaries already are better
        3. Prefer certain sources: arxiv > news > github > reddit
        """
        source_priority = {"arxiv": 4, "news": 3, "github": 2, "reddit": 1}

        best_idx = indices[0]
        best_score = -1.0

        for idx in indices:
            item = items[idx]
            content_len = len(item.get("content", ""))
            has_summary = 1.0 if item.get("summary") else 0.0
            source_score = source_priority.get(item.get("source", ""), 0)

            # Weighted quality score
            score = (content_len / 1000.0) + (has_summary * 2.0) + source_score

            if score > best_score:
                best_score = score
                best_idx = idx

        return best_idx
