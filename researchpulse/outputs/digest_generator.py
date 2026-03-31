"""
Daily/weekly digest generator (Phase 3).

Will create formatted email/markdown digests of top research items
grouped by category.
"""

from __future__ import annotations


class DigestGenerator:
    """Generate periodic digests of top research items."""

    def __init__(self, frequency: str = "daily", format: str = "markdown") -> None:
        self.frequency = frequency
        self.format = format

    async def generate(self) -> str:
        """Generate a digest for the current period."""
        raise NotImplementedError("Digest generation is implemented in Phase 3")

    async def send(self, digest: str, recipients: list[str]) -> None:
        """Send the digest via configured channel (email, Slack)."""
        raise NotImplementedError("Digest sending is implemented in Phase 3")
