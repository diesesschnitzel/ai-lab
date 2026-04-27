"""Playwright-based scraper for JavaScript-rendered pages.

Uses a real browser to scrape sites that require JavaScript execution,
such as Google Maps, Yelp, and other SPA-based directories.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from src.apivault.prospecting.scrapers.base import (
    BaseScraper,
    RateLimitConfig,
    ScraperResult,
)

logger = logging.getLogger(__name__)


class PlaywrightScraper(BaseScraper):
    """Scraper using Playwright for JavaScript-rendered pages.

    Handles dynamic content, infinite scroll, and click-to-reveal
    content that httpx alone cannot access.
    """

    def __init__(
        self,
        rate_limit: RateLimitConfig | None = None,
        headless: bool = True,
        proxy_url: str | None = None,
    ):
        super().__init__(rate_limit=rate_limit)
        self.headless = headless
        self.proxy_url = proxy_url
        self._browser = None

    async def scrape(
        self,
        url: str,
        selector: str | None = None,
        wait_for: str | None = None,
        scroll: bool = False,
        **kwargs: Any,
    ) -> ScraperResult:
        """Scrape a page using Playwright browser.

        Args:
            url: Page URL to scrape
            selector: CSS selector to extract data from
            wait_for: CSS selector to wait for before scraping
            scroll: Whether to scroll to load lazy content
        """
        import time
        start = time.monotonic()
        results: list[dict[str, Any]] = []
        errors: list[str] = []

        try:
            async with self._browser_context() as context:
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                if wait_for:
                    await page.wait_for_selector(wait_for, timeout=10000)

                if scroll:
                    await self._auto_scroll(page)

                content = await page.content()
                status = 200

                if selector:
                    elements = await page.query_selector_all(selector)
                    for el in elements:
                        data = await self._extract_element_data(el)
                        if data:
                            results.append(data)
                else:
                    results.append({
                        "url": url,
                        "content": content[:10000],  # Truncate
                        "status": status,
                    })

        except Exception as e:
            logger.error("Playwright scrape failed for %s: %s", url, e)
            errors.append(f"Playwright scrape failed: {e}")

        duration = (time.monotonic() - start) * 1000
        return ScraperResult(
            success=len(results) > 0,
            data=results,
            errors=errors,
            source="playwright",
            items_found=len(results),
            duration_ms=duration,
        )

    async def get_page_content(
        self,
        url: str,
        wait_for: str | None = None,
        timeout: float = 30000,
    ) -> tuple[int, bytes]:
        """Fetch page content with optional wait condition.

        Returns (status_code, html_bytes).
        """
        async with self._browser_context() as context:
            page = await context.new_page()
            response = await page.goto(
                url, wait_until="domcontentloaded", timeout=int(timeout)
            )

            if wait_for:
                await page.wait_for_selector(wait_for, timeout=10000)

            content = await page.content()
            status = response.status if response else 0
            return status, content.encode("utf-8")

    async def get_performance_metrics(
        self,
        url: str,
    ) -> dict[str, Any]:
        """Extract performance metrics using browser Performance API."""
        async with self._browser_context() as context:
            page = await context.new_page()
            await page.goto(url, wait_until="load", timeout=30000)

            # Get Performance API metrics
            metrics = await page.evaluate("""
                () => {
                    const timing = performance.getEntriesByType('navigation')[0];
                    const paint = performance.getEntriesByType('paint');
                    let fcp = 0;
                    paint.forEach(entry => {
                        if (entry.name === 'first-contentful-paint') {
                            fcp = entry.startTime;
                        }
                    });
                    return {
                        firstContentfulPaint: fcp,
                        domContentLoaded: timing ? timing.domContentLoadedEventEnd : 0,
                        loadComplete: timing ? timing.loadEventEnd : 0,
                        ttfb: timing ? timing.responseStart : 0,
                        domInteractive: timing ? timing.domInteractive : 0,
                    };
                }
            """)

            # Get resource summary
            resources = await page.evaluate("""
                () => {
                    const entries = performance.getEntriesByType('resource');
                    return {
                        requestCount: entries.length,
                        totalSize: entries.reduce((sum, e) => sum + (e.transferSize || 0), 0),
                    };
                }
            """)

            return {
                "firstContentfulPaint": metrics.get("firstContentfulPaint", 0),
                "loadTime": metrics.get("loadComplete", 0),
                "ttfb": metrics.get("ttfb", 0),
                "requestCount": resources.get("requestCount", 0),
                "pageSizeKb": resources.get("totalSize", 0) / 1024,
            }

    async def check_mobile_responsive(
        self,
        url: str,
    ) -> dict[str, Any]:
        """Test page responsiveness on mobile viewport."""
        async with self._browser_context() as context:
            page = await context.new_page()

            # Set mobile viewport
            await page.set_viewport_size({"width": 375, "height": 667})
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Check for horizontal overflow
            has_horizontal_scroll = await page.evaluate("""
                () => document.documentElement.scrollWidth > document.documentElement.clientWidth
            """)

            # Check viewport meta
            has_viewport = await page.evaluate("""
                () => !!document.querySelector('meta[name="viewport"]')
            """)

            return {
                "has_horizontal_scroll": has_horizontal_scroll,
                "has_viewport_meta": has_viewport,
                "no_horizontal_scroll": not has_horizontal_scroll,
            }

    @asynccontextmanager
    async def _browser_context(self):
        """Manage browser lifecycle with resource cleanup."""
        from playwright.async_api import async_playwright

        if self._browser is None:
            pw = await async_playwright().start()
            launch_kwargs = {"headless": self.headless}
            if self.proxy_url:
                launch_kwargs["proxy"] = {"server": self.proxy_url}
            self._browser = await pw.chromium.launch(**launch_kwargs)

        try:
            context = await self._browser.new_context(
                user_agent=self.user_agent,
                viewport={"width": 1920, "height": 1080},
                ignore_https_errors=True,
            )
            try:
                yield context
            finally:
                await context.close()
        except Exception:
            # Don't let context errors kill the browser
            raise

    async def _auto_scroll(self, page, max_scrolls: int = 50) -> None:
        """Scroll down a page to trigger lazy loading."""
        await page.evaluate("""
            async (max_scrolls) => {
                await new Promise((resolve) => {
                    let scrollCount = 0;
                    const interval = setInterval(() => {
                        window.scrollBy(0, window.innerHeight);
                        scrollCount++;
                        if (scrollCount >= max_scrolls) {
                            clearInterval(interval);
                            resolve();
                        }
                    }, 200);
                });
            }
        """, max_scrolls)

    async def _extract_element_data(self, element) -> dict[str, Any] | None:
        """Extract structured data from a DOM element."""
        try:
            return await element.evaluate("""
                (el) => {
                    const data = {};
                    // Extract text content
                    data.text = el.textContent?.trim()?.substring(0, 500);
                    // Extract links
                    const links = el.querySelectorAll('a[href]');
                    data.links = Array.from(links).map(a => a.href);
                    // Extract images
                    const images = el.querySelectorAll('img[src]');
                    data.images = Array.from(images).map(img => img.src);
                    return data;
                }
            """)
        except Exception:
            return None

    async def close(self) -> None:
        """Close the browser and clean up resources."""
        if self._browser:
            await self._browser.close()
            self._browser = None
