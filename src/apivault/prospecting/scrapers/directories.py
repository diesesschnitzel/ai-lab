"""Business directory scrapers for prospect discovery."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote, urljoin

from src.apivault.prospecting.scrapers.base import (
    BaseScraper,
    RateLimitConfig,
    ScraperResult,
)

logger = logging.getLogger(__name__)


class BusinessDirectoryScraper(BaseScraper):
    """Scrape business directories for prospect discovery.

    Supports multiple directories:
    - Yelp
    - Yellow Pages
    - Thomson Local
    - Europages
    - Industry-specific directories

    Example usage:
        scraper = BusinessDirectoryScraper()
        result = await scraper.scrape(
            directory="yelp",
            category="restaurants",
            location="Berlin",
            max_results=30,
        )
    """

    # Directory configurations
    DIRECTORIES = {
        "yelp": {
            "base_url": "https://www.yelp.com",
            "search_url": "/search?find_desc={category}&find_loc={location}&start={offset}",
            "selectors": {
                "listings": "[data-testid='serp-featured-list-item'], [class*='container'] [class*='lemon']",
                "name": "h3 a, h3 span",
                "website": "a[href*='biz_redir']",
                "phone": "[class*='phone']",
            },
            "max_offset": 200,
        },
        "yellow_pages": {
            "base_url": "https://www.yellowpages.com",
            "search_url": "/search?search_terms={category}&geo_location_terms={location}",
            "selectors": {
                "listings": ".search-results .organic, .result",
                "name": ".business-name, .info h2 a",
                "website": ".track-visit-website, .info a[href]:not(.business-name)",
                "phone": ".phone, .info .primary",
                "address": ".info .street-address",
            },
            "max_offset": 100,
        },
        "europages": {
            "base_url": "https://www.europages.co.uk",
            "search_url": "/{category}/{location}.html",
            "selectors": {
                "listings": ".company-list-item",
                "name": ".company-name a",
                "website": ".company-website",
                "phone": ".company-phone",
                "address": ".company-address",
            },
            "max_offset": 50,
        },
    }

    def __init__(
        self,
        rate_limit: RateLimitConfig | None = None,
    ):
        super().__init__(
            rate_limit=rate_limit or RateLimitConfig(
                requests_per_minute=20,
                requests_per_hour=300,
                delay_between_requests=2.5,
            ),
        )

    async def scrape(
        self,
        directory: str,
        category: str,
        location: str,
        max_results: int = 30,
        **kwargs: Any,
    ) -> ScraperResult:
        """Scrape a business directory for prospects.

        Args:
            directory: Directory name (yelp, yellow_pages, europages)
            category: Business category to search for
            location: Geographic location
            max_results: Maximum results to return
        """
        start_time = __import__("time").monotonic()
        results: list[dict[str, Any]] = []
        errors: list[str] = []

        if directory not in self.DIRECTORIES:
            available = ", ".join(self.DIRECTORIES.keys())
            errors.append(
                f"Unknown directory: {directory}. Available: {available}"
            )
            return self._make_result(results, errors, directory, start_time)

        try:
            results, errors = await self._scrape_directory(
                directory, category, location, max_results
            )
        except Exception as e:
            logger.error("Directory scraper failed: %s", e)
            errors.append(f"Directory scrape failed: {e}")

        return self._make_result(results, errors, directory, start_time)

    async def _scrape_directory(
        self,
        directory: str,
        category: str,
        location: str,
        max_results: int,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Scrape a specific directory."""
        config = self.DIRECTORIES[directory]
        results: list[dict[str, Any]] = []
        errors: list[str] = []

        # Build search URL
        search_url = config["search_url"].format(
            category=quote(category),
            location=quote(location),
            offset=0,
        )
        full_url = urljoin(config["base_url"], search_url)

        status, content = await self.fetch_url(full_url)
        if status != 200:
            errors.append(
                f"{directory} returned status {status} for URL: {full_url}"
            )
            return results, errors

        # Parse HTML
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, "html.parser")
        selectors = config["selectors"]

        listings = soup.select(selectors.get("listings", "li"))
        for listing in listings:
            if len(results) >= max_results:
                break

            prospect = self._extract_prospect(listing, selectors, config)
            if prospect and prospect.get("name"):
                results.append(prospect)

        return results, errors

    def _extract_prospect(
        self,
        listing: Any,
        selectors: dict[str, str],
        config: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Extract a single prospect from a directory listing element."""
        try:
            name_el = listing.select_one(selectors.get("name", "h3 a"))
            website_el = listing.select_one(selectors.get("website", "a"))
            phone_el = listing.select_one(selectors.get("phone", ""))
            address_el = listing.select_one(selectors.get("address", ""))

            name = name_el.get_text(strip=True) if name_el else None
            website = website_el.get("href", "") if website_el else None

            # Resolve relative URLs
            if website and not website.startswith("http"):
                website = urljoin(config["base_url"], website)

            phone = phone_el.get_text(strip=True) if phone_el else None
            address = address_el.get_text(strip=True) if address_el else None

            if not name:
                return None

            return {
                "name": name,
                "website": website if website else None,
                "phone": phone,
                "address": address,
                "source": config.get("base_url", "").replace("https://", "").split("/")[0],
                "source_type": "directory",
            }
        except Exception as e:
            logger.debug("Failed to extract prospect: %s", e)
            return None

    def _make_result(
        self,
        data: list[dict[str, Any]],
        errors: list[str],
        source: str,
        start_time: float,
    ) -> ScraperResult:
        """Build a ScraperResult from collected data."""
        duration = (__import__("time").monotonic() - start_time) * 1000
        return ScraperResult(
            success=len(data) > 0,
            data=data,
            errors=errors,
            source=source,
            items_found=len(data),
            duration_ms=duration,
        )
