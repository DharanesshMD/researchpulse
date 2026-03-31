"""
ResearchPulse CLI — command-line interface for running scrapers and managing the system.

Usage:
    researchpulse run arxiv          # Run ArXiv scraper
    researchpulse run github         # Run GitHub scraper
    researchpulse run news           # Run News/RSS scraper
    researchpulse run reddit         # Run Reddit scraper
    researchpulse run-all            # Run all enabled scrapers
    researchpulse run-all --save     # Run all and save to database
    researchpulse init-db            # Create database tables
    researchpulse export             # Export data to configured formats
    researchpulse check              # Verify config and connectivity
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from researchpulse.config import get_config, load_config, reset_config
from researchpulse.utils.logging import setup_logging

app = typer.Typer(
    name="researchpulse",
    help="🕷️ ResearchPulse — Open Source AI Research Scraper",
    add_completion=False,
)
console = Console()


def _get_scraper(source: str):
    """Import and instantiate a scraper by source name."""
    config = get_config()

    if source == "arxiv":
        from researchpulse.scrapers.arxiv_scraper import ArxivScraper
        return ArxivScraper(config)
    elif source == "github":
        from researchpulse.scrapers.github_scraper import GitHubScraper
        return GitHubScraper(config)
    elif source == "news":
        from researchpulse.scrapers.news_scraper import NewsScraper
        return NewsScraper(config)
    elif source == "reddit":
        from researchpulse.scrapers.reddit_scraper import RedditScraper
        return RedditScraper(config)
    else:
        console.print(f"[red]Unknown source: {source}[/red]")
        console.print("Available sources: arxiv, github, news, reddit")
        raise typer.Exit(1)


async def _run_scraper(source: str, save: bool = False) -> list:
    """Run a single scraper and optionally save results."""
    from researchpulse.scrapers.models import ScrapedItem

    scraper = _get_scraper(source)
    items = await scraper.run()

    # Display results
    if items:
        table = Table(title=f"📄 {source.upper()} Results ({len(items)} items)")
        table.add_column("Title", style="cyan", max_width=60)
        table.add_column("URL", style="blue", max_width=50)
        table.add_column("Date", style="green", max_width=12)

        for item in items[:20]:  # Show top 20
            date_str = item.published_at.strftime("%Y-%m-%d") if item.published_at else "N/A"
            table.add_row(
                item.title[:60],
                item.url[:50],
                date_str,
            )

        console.print(table)

        if len(items) > 20:
            console.print(f"  ... and {len(items) - 20} more items")
    else:
        console.print(f"[yellow]No items found for {source}[/yellow]")

    # Save to database if requested
    if save and items:
        await _save_items(items)

    return items


async def _save_items(items: list) -> None:
    """Save scraped items to the database."""
    from researchpulse.storage.database import Database
    from researchpulse.storage.repository import (
        scraped_item_to_model,
        PaperRepository,
        RepositoryRepo,
        NewsArticleRepository,
        RedditPostRepository,
    )

    config = get_config()
    db = Database(config.database.url)

    try:
        await db.create_tables()

        async with db.session() as session:
            new_count = 0
            for item in items:
                model = scraped_item_to_model(item)
                # Check if already exists
                source = item.source
                if source == "arxiv":
                    repo = PaperRepository(session)
                elif source == "github":
                    repo = RepositoryRepo(session)
                elif source == "news":
                    repo = NewsArticleRepository(session)
                elif source == "reddit":
                    repo = RedditPostRepository(session)
                else:
                    continue

                existing = await repo.get_by_url(item.url)
                if existing is None:
                    session.add(model)
                    new_count += 1

            await session.flush()
            console.print(f"[green]✅ Saved {new_count} new items to database[/green]")
    except Exception as e:
        console.print(f"[red]❌ Database error: {e}[/red]")
        console.print("[yellow]Hint: Make sure PostgreSQL is running and DATABASE_URL is set[/yellow]")
    finally:
        await db.close()


@app.command()
def run(
    source: str = typer.Argument(help="Source to scrape: arxiv, github, news, reddit"),
    save: bool = typer.Option(False, "--save", "-s", help="Save results to database"),
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config.yaml"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Run a specific scraper."""
    setup_logging(level="DEBUG" if verbose else "INFO")
    if config_path:
        reset_config()
        get_config(config_path)

    console.print(f"🕷️ Running [bold]{source}[/bold] scraper...")
    asyncio.run(_run_scraper(source, save=save))


@app.command("run-all")
def run_all(
    save: bool = typer.Option(False, "--save", "-s", help="Save results to database"),
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config.yaml"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Run all enabled scrapers."""
    setup_logging(level="DEBUG" if verbose else "INFO")
    if config_path:
        reset_config()
        get_config(config_path)

    async def _run_all():
        config = get_config()
        sources = []

        if config.scraping.sources.arxiv.enabled:
            sources.append("arxiv")
        if config.scraping.sources.github.enabled:
            sources.append("github")
        if config.scraping.sources.news.enabled:
            sources.append("news")
        if config.scraping.sources.reddit.enabled:
            sources.append("reddit")

        console.print(f"🕷️ Running [bold]{len(sources)}[/bold] scrapers: {', '.join(sources)}")

        all_items = []
        for source in sources:
            try:
                items = await _run_scraper(source, save=False)
                all_items.extend(items)
            except Exception as e:
                console.print(f"[red]❌ {source} failed: {e}[/red]")

        if save and all_items:
            await _save_items(all_items)

        console.print(f"\n🎉 [bold green]Total: {len(all_items)} items scraped[/bold green]")

    asyncio.run(_run_all())


@app.command("init-db")
def init_db(
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config.yaml"),
) -> None:
    """Initialize the database (create tables)."""
    setup_logging()
    if config_path:
        reset_config()
        get_config(config_path)

    async def _init():
        from researchpulse.storage.database import Database

        config = get_config()
        db = Database(config.database.url)
        try:
            await db.create_tables()
            console.print("[green]✅ Database tables created successfully[/green]")
        except Exception as e:
            console.print(f"[red]❌ Failed to initialize database: {e}[/red]")
        finally:
            await db.close()

    asyncio.run(_init())


@app.command("export")
def export_data(
    source: Optional[str] = typer.Option(None, "--source", help="Filter by source"),
    output_dir: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory"),
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config.yaml"),
) -> None:
    """Export scraped data to configured formats."""
    setup_logging()
    if config_path:
        reset_config()
        get_config(config_path)

    async def _export():
        from researchpulse.storage.database import Database
        from researchpulse.storage.repository import (
            PaperRepository,
            RepositoryRepo,
            NewsArticleRepository,
            RedditPostRepository,
        )
        from researchpulse.storage.dataset_exporter import export_items

        config = get_config()
        db = Database(config.database.url)
        out_dir = output_dir or config.outputs.export.output_dir

        try:
            async with db.session() as session:
                all_items = []

                if source is None or source == "arxiv":
                    repo = PaperRepository(session)
                    all_items.extend(await repo.list_all(limit=1000))

                if source is None or source == "github":
                    repo = RepositoryRepo(session)
                    all_items.extend(await repo.list_all(limit=1000))

                if source is None or source == "news":
                    repo = NewsArticleRepository(session)
                    all_items.extend(await repo.list_all(limit=1000))

                if source is None or source == "reddit":
                    repo = RedditPostRepository(session)
                    all_items.extend(await repo.list_all(limit=1000))

                if all_items:
                    paths = export_items(
                        all_items,
                        output_dir=out_dir,
                        formats=config.outputs.export.formats,
                    )
                    for p in paths:
                        console.print(f"[green]📁 Exported: {p}[/green]")
                else:
                    console.print("[yellow]No items to export[/yellow]")
        except Exception as e:
            console.print(f"[red]❌ Export failed: {e}[/red]")
        finally:
            await db.close()

    asyncio.run(_export())


@app.command("check")
def check(
    config_path: Optional[str] = typer.Option(None, "--config", "-c", help="Path to config.yaml"),
) -> None:
    """Verify configuration and show system status."""
    setup_logging()
    if config_path:
        reset_config()

    console.print("🔍 [bold]ResearchPulse System Check[/bold]\n")

    # Check config
    try:
        config = get_config(config_path)
        console.print("[green]✅ Configuration loaded successfully[/green]")
    except Exception as e:
        console.print(f"[red]❌ Configuration error: {e}[/red]")
        raise typer.Exit(1)

    # Show enabled sources
    sources_table = Table(title="Configured Sources")
    sources_table.add_column("Source", style="cyan")
    sources_table.add_column("Enabled", style="green")
    sources_table.add_column("Details")

    sources_table.add_row(
        "ArXiv",
        "✅" if config.scraping.sources.arxiv.enabled else "❌",
        f"{len(config.scraping.sources.arxiv.categories)} categories, "
        f"{len(config.scraping.sources.arxiv.keywords)} keywords",
    )
    sources_table.add_row(
        "GitHub",
        "✅" if config.scraping.sources.github.enabled else "❌",
        f"{len(config.scraping.sources.github.topics)} topics, "
        f"min {config.scraping.sources.github.min_stars}⭐",
    )
    sources_table.add_row(
        "Reddit",
        "✅" if config.scraping.sources.reddit.enabled else "❌",
        f"{len(config.scraping.sources.reddit.subreddits)} subreddits, "
        f"min score {config.scraping.sources.reddit.min_score}",
    )
    sources_table.add_row(
        "News",
        "✅" if config.scraping.sources.news.enabled else "❌",
        f"{len(config.scraping.sources.news.feeds)} feeds",
    )

    console.print(sources_table)

    # Show LLM config
    console.print(f"\n🤖 LLM Provider: [bold]{config.llm.provider}[/bold]")
    if config.llm.provider == "anthropic":
        console.print(f"   Model: {config.llm.anthropic.model}")
    else:
        console.print(f"   Model: {config.llm.openai.model}")

    # Check env vars
    import os

    env_table = Table(title="\nEnvironment Variables")
    env_table.add_column("Variable", style="cyan")
    env_table.add_column("Status")

    env_vars = [
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GITHUB_TOKEN",
        "REDDIT_CLIENT_ID",
        "REDDIT_CLIENT_SECRET",
        "DATABASE_URL",
    ]

    for var in env_vars:
        if os.environ.get(var):
            env_table.add_row(var, "[green]Set ✅[/green]")
        else:
            env_table.add_row(var, "[yellow]Not set[/yellow]")

    console.print(env_table)
    console.print("\n[green]✅ System check complete[/green]")


if __name__ == "__main__":
    app()
