"""
GitHub scraper — searches for trending repositories by topic and keyword.

Uses the GitHub REST API via httpx for async access.
Optionally fetches README content for each repository.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from typing import Any

from researchpulse.config import ResearchPulseConfig
from researchpulse.scrapers.base import BaseScraper
from researchpulse.scrapers.models import ScrapedItem


class GitHubScraper(BaseScraper):
    """Scrape trending GitHub repositories by topic and keyword."""

    source_name = "github"

    SEARCH_URL = "https://api.github.com/search/repositories"
    README_URL = "https://api.github.com/repos/{full_name}/readme"

    def __init__(self, config: ResearchPulseConfig, **kwargs: Any) -> None:
        # GitHub API: 10 requests/min unauthenticated, 30/min authenticated
        super().__init__(config, rate_limit=0.5, **kwargs)
        self.github_config = config.scraping.sources.github
        self._setup_auth()

    def _setup_auth(self) -> None:
        """Set up GitHub token authentication if available."""
        import os

        token = os.environ.get("GITHUB_TOKEN")
        if token:
            self.client.headers["Authorization"] = f"token {token}"
            self.logger.info("GitHub authentication configured")

    def _build_queries(self) -> list[str]:
        """Build GitHub search queries from config."""
        queries: list[str] = []

        # Calculate date for "recently created/updated" filter
        since_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

        # Topic-based queries
        for topic in self.github_config.topics:
            q = f"topic:{topic} stars:>={self.github_config.min_stars} pushed:>{since_date}"
            queries.append(q)

        # Keyword-based queries
        for keyword in self.github_config.keywords:
            q = f"{keyword} in:name,description,readme stars:>={self.github_config.min_stars}"
            queries.append(q)

        if not queries:
            queries.append(f"stars:>={self.github_config.min_stars} pushed:>{since_date}")

        return queries

    def _get_sort_param(self) -> str:
        """Map config sort_by to GitHub API sort parameter."""
        return self.github_config.sort_by

    async def scrape(self) -> list[ScrapedItem]:
        """Fetch repositories from GitHub Search API."""
        if not self.github_config.enabled:
            self.logger.info("GitHub scraper is disabled")
            return []

        queries = self._build_queries()
        seen_urls: set[str] = set()
        items: list[ScrapedItem] = []

        for query in queries:
            try:
                new_items = await self._search_repos(query, seen_urls)
                items.extend(new_items)
            except Exception as e:
                self.logger.warning("GitHub search query failed", query=query, error=str(e))

            if len(items) >= self.github_config.max_results:
                break

        return items[: self.github_config.max_results]

    async def _search_repos(
        self, query: str, seen_urls: set[str]
    ) -> list[ScrapedItem]:
        """Execute a single search query and return new items."""
        self.logger.debug("Searching GitHub", query=query)

        response = await self._get(
            self.SEARCH_URL,
            params={
                "q": query,
                "sort": self._get_sort_param(),
                "order": "desc",
                "per_page": min(30, self.github_config.max_results),
            },
        )

        data = response.json()
        repos = data.get("items", [])
        items: list[ScrapedItem] = []

        for repo in repos:
            html_url = repo.get("html_url", "")
            if html_url in seen_urls:
                continue
            seen_urls.add(html_url)

            try:
                item = await self._repo_to_item(repo)
                items.append(item)
            except Exception as e:
                self.logger.warning(
                    "Failed to process repo",
                    repo=repo.get("full_name", "unknown"),
                    error=str(e),
                )

        return items

    async def _repo_to_item(self, repo: dict[str, Any]) -> ScrapedItem:
        """Convert a GitHub API repo object to a ScrapedItem."""
        full_name = repo.get("full_name", "")
        topics = repo.get("topics", [])

        # Parse dates
        published_at = None
        created_at_str = repo.get("created_at")
        if created_at_str:
            published_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))

        last_pushed = None
        pushed_at_str = repo.get("pushed_at")
        if pushed_at_str:
            last_pushed = datetime.fromisoformat(pushed_at_str.replace("Z", "+00:00"))

        # Optionally fetch README
        readme_content = await self._fetch_readme(full_name)

        content = repo.get("description", "") or ""
        if readme_content:
            # Use first 2000 chars of README as extended content
            content = f"{content}\n\n---\n\n{readme_content[:2000]}"

        return ScrapedItem(
            title=full_name,
            url=repo.get("html_url", ""),
            source="github",
            content=content,
            published_at=published_at,
            tags=topics,
            extra={
                "full_name": full_name,
                "description": repo.get("description"),
                "language": repo.get("language"),
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "open_issues": repo.get("open_issues_count", 0),
                "topics": ",".join(topics),
                "readme_content": readme_content,
                "last_pushed_at": last_pushed,
            },
        )

    async def _fetch_readme(self, full_name: str) -> str | None:
        """Fetch and decode README content for a repository."""
        try:
            response = await self._get(
                self.README_URL.format(full_name=full_name),
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            data = response.json()
            content_b64 = data.get("content", "")
            if content_b64:
                return base64.b64decode(content_b64).decode("utf-8", errors="replace")
        except Exception:
            self.logger.debug("Could not fetch README", repo=full_name)

        return None
