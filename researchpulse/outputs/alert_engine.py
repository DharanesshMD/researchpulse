"""
Alert engine — triggers notifications on keyword match or relevance threshold.

Monitors new items and sends alerts via Slack webhook, ntfy.sh, or logs.
Supports keyword matching (case-insensitive, partial), topic matching,
and relevance threshold filtering.
"""

from __future__ import annotations

import os
import re
from typing import Any

import httpx

from researchpulse.config import AlertsConfig, ResearchPulseConfig, get_config
from researchpulse.utils.logging import get_logger

logger = get_logger("outputs.alerts")


class AlertEngine:
    """
    Monitor new items and trigger alerts.

    Alert types:
    - Keyword match (case-insensitive substring)
    - Relevance threshold (items above min_relevance)
    - Topic match (items matching specific topics)
    """

    def __init__(
        self,
        config: ResearchPulseConfig | None = None,
        keywords: list[str] | None = None,
        min_relevance: float | None = None,
        notify_via: str | None = None,
    ) -> None:
        cfg = (config or get_config()).alerts
        self.keywords = keywords or cfg.keywords
        self.min_relevance = min_relevance if min_relevance is not None else cfg.min_relevance
        self.notify_via = notify_via or cfg.notify_via
        self.enabled = cfg.enabled

        # Pre-compile keyword patterns for performance
        self._patterns = [
            re.compile(re.escape(kw), re.IGNORECASE) for kw in self.keywords
        ]

    async def check(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Check items against alert rules and return matches.

        Each item dict should have: title, content, source, url,
        and optionally relevance_score and topic.

        Returns:
            List of matching items with an added "alert_reasons" field.
        """
        if not self.enabled:
            return []

        matches: list[dict[str, Any]] = []

        for item in items:
            reasons = self._check_item(item)
            if reasons:
                match = {**item, "alert_reasons": reasons}
                matches.append(match)

        if matches:
            logger.info("Alerts triggered", matches=len(matches), total_checked=len(items))

        return matches

    def _check_item(self, item: dict[str, Any]) -> list[str]:
        """Check a single item against all rules. Returns list of trigger reasons."""
        reasons: list[str] = []

        title = item.get("title", "")
        content = item.get("content", "")
        searchable = f"{title} {content}"

        # Keyword matching
        for pattern, keyword in zip(self._patterns, self.keywords):
            if pattern.search(searchable):
                reasons.append(f"Keyword match: '{keyword}'")

        # Relevance threshold
        relevance = item.get("relevance_score", 0.0)
        if isinstance(relevance, (int, float)) and relevance >= self.min_relevance:
            reasons.append(f"High relevance: {relevance:.2f}")

        return reasons

    async def notify(
        self,
        matches: list[dict[str, Any]],
        channel: str | None = None,
    ) -> int:
        """
        Send notifications for matched items.

        Args:
            matches: List of matched items (from check()).
            channel: Override notification channel (slack, ntfy, log).

        Returns:
            Number of notifications sent.
        """
        ch = channel or self.notify_via

        if not matches:
            return 0

        if ch == "slack":
            return await self._notify_slack(matches)
        elif ch == "ntfy":
            return await self._notify_ntfy(matches)
        else:
            return self._notify_log(matches)

    async def _notify_slack(self, matches: list[dict[str, Any]]) -> int:
        """Send alerts to Slack via webhook."""
        webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
        if not webhook_url:
            logger.warning("SLACK_WEBHOOK_URL not set, falling back to log")
            return self._notify_log(matches)

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🔔 ResearchPulse Alert — {len(matches)} new match{'es' if len(matches) != 1 else ''}",
                },
            }
        ]

        for item in matches[:10]:  # Slack limits blocks
            reasons = ", ".join(item.get("alert_reasons", []))
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*<{item.get('url', '')}|{item.get('title', 'Untitled')}>*\n"
                        f"_{item.get('source', 'unknown')}_ — {reasons}\n"
                        f"{(item.get('summary') or item.get('content', ''))[:200]}"
                    ),
                },
            })

        payload = {"blocks": blocks}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload, timeout=10)
                response.raise_for_status()

            logger.info("Slack notification sent", count=len(matches))
            return len(matches)
        except Exception as e:
            logger.error("Slack notification failed", error=str(e))
            return 0

    async def _notify_ntfy(self, matches: list[dict[str, Any]]) -> int:
        """Send alerts via ntfy.sh."""
        topic = os.environ.get("NTFY_TOPIC", "researchpulse")
        ntfy_url = f"https://ntfy.sh/{topic}"

        sent = 0
        try:
            async with httpx.AsyncClient() as client:
                for item in matches[:20]:
                    reasons = ", ".join(item.get("alert_reasons", []))
                    title = item.get("title", "Untitled")

                    response = await client.post(
                        ntfy_url,
                        content=f"{title}\n{reasons}\n{item.get('url', '')}",
                        headers={
                            "Title": f"ResearchPulse: {title[:60]}",
                            "Tags": "research,alert",
                            "Click": item.get("url", ""),
                        },
                        timeout=10,
                    )
                    if response.status_code == 200:
                        sent += 1

            logger.info("ntfy notifications sent", count=sent)
        except Exception as e:
            logger.error("ntfy notification failed", error=str(e))

        return sent

    def _notify_log(self, matches: list[dict[str, Any]]) -> int:
        """Log alerts (fallback / testing)."""
        for item in matches:
            reasons = ", ".join(item.get("alert_reasons", []))
            logger.info(
                "ALERT",
                title=item.get("title", ""),
                source=item.get("source", ""),
                url=item.get("url", ""),
                reasons=reasons,
            )
        return len(matches)

    async def check_and_notify(self, items: list[dict[str, Any]]) -> int:
        """Convenience: check items and send notifications for matches."""
        matches = await self.check(items)
        if matches:
            return await self.notify(matches)
        return 0
