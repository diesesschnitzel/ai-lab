"""Base scraper class with rate limiting, retries, and error recovery."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ScraperResult:
    """Result from a single scraper execution."""

    success: bool
    data: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    source: str = ""
    items_found: int = 0
    duration_ms: float = 0.0


@dataclass
class RateLimitConfig:
    """Rate limiting configuration for a scraper."""

    requests_per_minute: int = 30
    requests_per_hour: int = 500
    delay_between_requests: float = 1.0  # base delay in seconds
    jitter_factor: float = 0.3  # random jitter multiplier (0-1)
    max_retries: int = 3
    retry_backoff_base: float = 2.0  # exponential backoff base


class BaseScraper(ABC):
    """Abstract base class for all prospecting scrapers.

    Handles rate limiting, retries, and error recovery so subclasses
    only need to implement the actual scraping logic.
    """

    def __init__(
        self,
        rate_limit: RateLimitConfig | None = None,
        user_agent: str | None = None,
        timeout: float = 30.0,
    ):
        self.rate_limit = rate_limit or RateLimitConfig()
        self.user_agent = user_agent or (
            "Mozilla/5.0 (compatible; CodechoProspector/1.0; "
            "+https://codecho.de/bot)"
        )
        self.timeout = timeout
        self._request_timestamps: list[float] = []

    @abstractmethod
    async def scrape(self, **kwargs: Any) -> ScraperResult:
        """Execute the scraper and return results.

        Subclasses must implement this method.
        """
        ...

    async def fetch_url(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> tuple[int, bytes]:
        """Fetch a URL with rate limiting and retries.

        Returns (status_code, body_bytes).
        """
        last_error = None
        for attempt in range(self.rate_limit.max_retries + 1):
            try:
                await self._wait_for_rate_limit()
                status, body = await self._do_fetch(
                    url, method, headers, **kwargs
                )

                if status == 429:
                    # Rate limited — back off and retry
                    wait = self.rate_limit.retry_backoff_base ** (attempt + 1)
                    logger.warning(
                        "Rate limited on %s, retrying in %.1fs (attempt %d)",
                        url, wait, attempt + 1,
                    )
                    await asyncio.sleep(wait)
                    continue

                if status >= 500 and attempt < self.rate_limit.max_retries:
                    # Server error — retry with backoff
                    wait = self.rate_limit.retry_backoff_base ** attempt
                    logger.warning(
                        "Server error %d on %s, retrying in %.1fs",
                        status, url, wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                return status, body

            except Exception as e:
                last_error = e
                if attempt < self.rate_limit.max_retries:
                    wait = self.rate_limit.retry_backoff_base ** attempt
                    logger.warning(
                        "Fetch error on %s: %s, retrying in %.1fs",
                        url, e, wait,
                    )
                    await asyncio.sleep(wait)

        error_msg = f"All {self.rate_limit.max_retries + 1} attempts failed for {url}"
        if last_error:
            error_msg += f": {last_error}"
        logger.error(error_msg)
        return 0, b""

    async def _wait_for_rate_limit(self) -> None:
        """Enforce rate limiting before making a request."""
        now = time.monotonic()

        # Clean old timestamps (older than 1 minute)
        cutoff = now - 60
        self._request_timestamps = [
            t for t in self._request_timestamps if t > cutoff
        ]

        # Check per-minute limit
        if len(self._request_timestamps) >= self.rate_limit.requests_per_minute:
            wait = 60 - (now - self._request_timestamps[0])
            if wait > 0:
                logger.debug("Rate limit hit, waiting %.1fs", wait)
                await asyncio.sleep(wait)

        # Add base delay with jitter
        jitter = random.uniform(
            1 - self.rate_limit.jitter_factor,
            1 + self.rate_limit.jitter_factor,
        )
        delay = self.rate_limit.delay_between_requests * jitter
        if delay > 0:
            await asyncio.sleep(delay)

        self._request_timestamps.append(time.monotonic())

    async def _do_fetch(
        self,
        url: str,
        method: str,
        headers: dict[str, str] | None,
        **kwargs: Any,
    ) -> tuple[int, bytes]:
        """Perform the actual HTTP fetch. Uses httpx if available."""
        import httpx

        request_headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if headers:
            request_headers.update(headers)

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            verify=True,
        ) as client:
            response = await client.request(
                method, url, headers=request_headers, **kwargs
            )
            return response.status_code, response.content

    def default_headers(self) -> dict[str, str]:
        """Return default headers for requests."""
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }
