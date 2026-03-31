"""
Async rate limiter using the token bucket algorithm.

Built into BaseScraper to ensure all HTTP calls respect per-source rate limits.
"""

from __future__ import annotations

import asyncio
import time


class AsyncRateLimiter:
    """
    Token bucket rate limiter for async operations.

    Args:
        rate: Maximum number of requests per second.
        burst: Maximum burst size (tokens that can accumulate). Defaults to rate.
    """

    def __init__(self, rate: float = 1.0, burst: int | None = None) -> None:
        self.rate = rate
        self.burst = burst if burst is not None else max(1, int(rate))
        self._tokens = float(self.burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a token is available, then consume it."""
        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                # Calculate wait time until next token
                wait_time = (1.0 - self._tokens) / self.rate
                await asyncio.sleep(wait_time)

    def _refill(self) -> None:
        """Add tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_refill = now

    async def __aenter__(self) -> AsyncRateLimiter:
        await self.acquire()
        return self

    async def __aexit__(self, *args: object) -> None:
        pass
