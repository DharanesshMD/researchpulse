"""
FastAPI dashboard routes (Phase 4).

Will provide REST + WebSocket endpoints for the Next.js dashboard:
- GET /api/items — paginated feed
- GET /api/items/{id} — single item detail
- POST /api/ask — RAG query
- WS /api/feed — live feed updates
- GET /api/stats — dashboard statistics
"""

from __future__ import annotations


def create_app():
    """Create the FastAPI application."""
    raise NotImplementedError("Dashboard API is implemented in Phase 4")
