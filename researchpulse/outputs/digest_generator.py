"""
Daily/weekly digest generator.

Creates formatted markdown or HTML digests of top research items
grouped by topic and source. Reads from the database and produces
a digest string that can be emailed, posted to Slack, or saved to disk.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Sequence

from sqlmodel import SQLModel

from researchpulse.config import DigestOutputConfig, ResearchPulseConfig, get_config
from researchpulse.storage.database import Database
from researchpulse.storage.db_models import (
    NewsArticle,
    Paper,
    RedditPost,
    Repository,
)
from researchpulse.storage.repository import (
    NewsArticleRepository,
    PaperRepository,
    RedditPostRepository,
    RepositoryRepo,
)
from researchpulse.utils.logging import get_logger

logger = get_logger("outputs.digest")


def _truncate(text: str, max_len: int = 200) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


class DigestGenerator:
    """
    Generate periodic digests of top research items.

    Groups items by source, sorted by relevance/score,
    and formats them as markdown or HTML.
    """

    def __init__(
        self,
        config: ResearchPulseConfig | None = None,
        frequency: str | None = None,
        fmt: str | None = None,
    ) -> None:
        self.config = config or get_config()
        digest_cfg = self.config.outputs.digest
        self.frequency = frequency or digest_cfg.frequency
        self.fmt = fmt or digest_cfg.format
        self.max_items = digest_cfg.max_items_per_category

    def _get_cutoff(self) -> datetime:
        """Calculate the time cutoff based on digest frequency."""
        now = datetime.now(timezone.utc)
        if self.frequency == "weekly":
            return now - timedelta(days=7)
        return now - timedelta(days=1)

    async def generate(self) -> str:
        """
        Generate a digest for the current period.

        Reads recent items from the database, groups by source,
        and formats into markdown or HTML.

        Returns:
            The formatted digest string.
        """
        db = Database(self.config.database.url)

        try:
            sections: dict[str, list[dict[str, Any]]] = {
                "📄 ArXiv Papers": [],
                "🐙 GitHub Repos": [],
                "📰 News Articles": [],
                "💬 Reddit Posts": [],
            }

            async with db.session() as session:
                # Fetch papers
                paper_repo = PaperRepository(session)
                papers = await paper_repo.list_all(limit=self.max_items)
                for p in papers:
                    sections["📄 ArXiv Papers"].append({
                        "title": p.title,
                        "url": p.url,
                        "summary": p.summary or _truncate(p.content),
                        "meta": f"Categories: {p.categories}" if p.categories else "",
                    })

                # Fetch repos
                repo_repo = RepositoryRepo(session)
                repos = await repo_repo.list_all(limit=self.max_items)
                for r in repos:
                    sections["🐙 GitHub Repos"].append({
                        "title": r.full_name,
                        "url": r.url,
                        "summary": r.summary or r.description or "",
                        "meta": f"⭐ {r.stars} | {r.language or 'N/A'}",
                    })

                # Fetch news
                news_repo = NewsArticleRepository(session)
                articles = await news_repo.list_all(limit=self.max_items)
                for a in articles:
                    sections["📰 News Articles"].append({
                        "title": a.title,
                        "url": a.url,
                        "summary": a.summary or _truncate(a.content),
                        "meta": f"Feed: {a.feed_name}" if a.feed_name else "",
                    })

                # Fetch reddit
                reddit_repo = RedditPostRepository(session)
                posts = await reddit_repo.list_all(limit=self.max_items)
                for p in posts:
                    sections["💬 Reddit Posts"].append({
                        "title": p.title,
                        "url": p.url,
                        "summary": p.summary or _truncate(p.content),
                        "meta": f"r/{p.subreddit} | ⬆ {p.score}",
                    })

            # Format
            if self.fmt == "html":
                digest = self._format_html(sections)
            else:
                digest = self._format_markdown(sections)

            logger.info(
                "Digest generated",
                frequency=self.frequency,
                format=self.fmt,
                total_items=sum(len(v) for v in sections.values()),
            )
            return digest

        finally:
            await db.close()

    def _format_markdown(self, sections: dict[str, list[dict[str, Any]]]) -> str:
        """Format digest as markdown."""
        now = datetime.now(timezone.utc)
        period = "Weekly" if self.frequency == "weekly" else "Daily"

        lines = [
            f"# ResearchPulse {period} Digest",
            f"*{now.strftime('%B %d, %Y')}*\n",
        ]

        total = sum(len(items) for items in sections.values())
        if total == 0:
            lines.append("*No new items in this period.*")
            return "\n".join(lines)

        for section_title, items in sections.items():
            if not items:
                continue

            lines.append(f"\n## {section_title}\n")

            for item in items:
                lines.append(f"### [{item['title']}]({item['url']})")
                if item.get("meta"):
                    lines.append(f"*{item['meta']}*")
                if item.get("summary"):
                    lines.append(f"\n{item['summary']}\n")
                lines.append("---")

        lines.append(f"\n*Generated by ResearchPulse at {now.strftime('%H:%M UTC')}*")
        return "\n".join(lines)

    def _format_html(self, sections: dict[str, list[dict[str, Any]]]) -> str:
        """Format digest as HTML email."""
        now = datetime.now(timezone.utc)
        period = "Weekly" if self.frequency == "weekly" else "Daily"

        html_parts = [
            "<!DOCTYPE html>",
            '<html><head><meta charset="utf-8">',
            "<style>",
            "body { font-family: -apple-system, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; }",
            "h1 { color: #1a1a2e; }",
            "h2 { color: #16213e; border-bottom: 2px solid #0f3460; padding-bottom: 5px; }",
            ".item { margin-bottom: 20px; padding: 12px; background: #f8f9fa; border-radius: 8px; }",
            ".item h3 { margin: 0 0 5px 0; }",
            ".item a { color: #0f3460; text-decoration: none; }",
            ".item a:hover { text-decoration: underline; }",
            ".meta { color: #666; font-size: 0.9em; }",
            ".summary { margin-top: 8px; color: #333; }",
            ".footer { margin-top: 30px; color: #999; font-size: 0.85em; }",
            "</style></head><body>",
            f"<h1>ResearchPulse {period} Digest</h1>",
            f"<p><em>{now.strftime('%B %d, %Y')}</em></p>",
        ]

        total = sum(len(items) for items in sections.values())
        if total == 0:
            html_parts.append("<p><em>No new items in this period.</em></p>")
        else:
            for section_title, items in sections.items():
                if not items:
                    continue

                html_parts.append(f"<h2>{section_title}</h2>")

                for item in items:
                    html_parts.append('<div class="item">')
                    html_parts.append(f'<h3><a href="{item["url"]}">{item["title"]}</a></h3>')
                    if item.get("meta"):
                        html_parts.append(f'<div class="meta">{item["meta"]}</div>')
                    if item.get("summary"):
                        html_parts.append(f'<div class="summary">{item["summary"]}</div>')
                    html_parts.append("</div>")

        html_parts.append(f'<div class="footer">Generated by ResearchPulse at {now.strftime("%H:%M UTC")}</div>')
        html_parts.append("</body></html>")

        return "\n".join(html_parts)

    async def save_to_file(self, output_dir: str = "./exports") -> str:
        """Generate digest and save to file. Returns the file path."""
        from pathlib import Path

        digest = await self.generate()

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        ext = "html" if self.fmt == "html" else "md"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"digest_{self.frequency}_{timestamp}.{ext}"
        path = out / filename

        path.write_text(digest, encoding="utf-8")
        logger.info("Digest saved", path=str(path))
        return str(path)
