"""Tests for the rate limiter utility."""

from __future__ import annotations

import asyncio
import time

import pytest

from researchpulse.utils.rate_limiter import AsyncRateLimiter


class TestAsyncRateLimiter:
    """Test the token bucket rate limiter."""

    @pytest.mark.asyncio
    async def test_single_acquire(self):
        """A single acquire should succeed immediately."""
        limiter = AsyncRateLimiter(rate=10.0)
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1  # Should be nearly instant

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Rapid requests should be delayed to respect rate limit."""
        limiter = AsyncRateLimiter(rate=5.0, burst=1)

        start = time.monotonic()
        for _ in range(3):
            await limiter.acquire()
        elapsed = time.monotonic() - start

        # 3 requests at 5/sec with burst=1 → first is instant, next 2 take ~0.4s
        assert elapsed >= 0.3

    @pytest.mark.asyncio
    async def test_burst_allows_immediate(self):
        """Burst capacity should allow multiple immediate requests."""
        limiter = AsyncRateLimiter(rate=1.0, burst=5)

        start = time.monotonic()
        for _ in range(5):
            await limiter.acquire()
        elapsed = time.monotonic() - start

        # All 5 should be served from burst bucket
        assert elapsed < 0.5

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Should work as an async context manager."""
        limiter = AsyncRateLimiter(rate=10.0)
        async with limiter:
            pass  # Should not raise
