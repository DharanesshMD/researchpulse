"""Initial migration — create all tables.

Revision ID: 001_initial
Revises:
Create Date: 2026-03-31

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Papers table (ArXiv)
    op.create_table(
        "papers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("source", sa.VARCHAR(), nullable=False),
        sa.Column("content", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("summary", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("tags", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("arxiv_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("authors", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("categories", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("pdf_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("doi", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("journal_ref", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("comment", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index("ix_papers_title", "papers", ["title"])
    op.create_index("ix_papers_url", "papers", ["url"], unique=True)
    op.create_index("ix_papers_source", "papers", ["source"])
    op.create_index("ix_papers_arxiv_id", "papers", ["arxiv_id"], unique=True)

    # Repositories table (GitHub)
    op.create_table(
        "repositories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("source", sa.VARCHAR(), nullable=False),
        sa.Column("content", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("summary", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("tags", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("full_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("language", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("stars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("forks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("open_issues", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("topics", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("readme_content", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("last_pushed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_repositories_title", "repositories", ["title"])
    op.create_index("ix_repositories_url", "repositories", ["url"], unique=True)
    op.create_index("ix_repositories_source", "repositories", ["source"])
    op.create_index("ix_repositories_full_name", "repositories", ["full_name"], unique=True)

    # News articles table
    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("source", sa.VARCHAR(), nullable=False),
        sa.Column("content", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("summary", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("tags", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("feed_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("feed_url", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("author", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("full_text", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index("ix_news_articles_title", "news_articles", ["title"])
    op.create_index("ix_news_articles_url", "news_articles", ["url"], unique=True)
    op.create_index("ix_news_articles_source", "news_articles", ["source"])

    # Reddit posts table
    op.create_table(
        "reddit_posts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("source", sa.VARCHAR(), nullable=False),
        sa.Column("content", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("summary", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("tags", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("reddit_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("subreddit", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("author", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("num_comments", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("selftext", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("post_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index("ix_reddit_posts_title", "reddit_posts", ["title"])
    op.create_index("ix_reddit_posts_url", "reddit_posts", ["url"], unique=True)
    op.create_index("ix_reddit_posts_source", "reddit_posts", ["source"])
    op.create_index("ix_reddit_posts_reddit_id", "reddit_posts", ["reddit_id"], unique=True)
    op.create_index("ix_reddit_posts_subreddit", "reddit_posts", ["subreddit"])


def downgrade() -> None:
    op.drop_table("reddit_posts")
    op.drop_table("news_articles")
    op.drop_table("repositories")
    op.drop_table("papers")
