"""Google Maps scraper for local business discovery."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote

from src.apivault.prospecting.models import ProspectSource
from src.apivault.prospecting.scrapers.base import (
    BaseScraper,
    RateLimitConfig,
    ScraperResult,
)

logger = logging.getLogger(__name__)


class GoogleMapsScraper(BaseScraper):
    """Scrape Google Maps for local business prospects.

    Uses a combination of Google Places API (if key provided) and
    organic search scraping for business discovery.

    Example usage:
        scraper = GoogleMapsScraper(api_key="...")
        result = await scraper.scrape(
            query="restaurants",
            location="Berlin, Germany",
            max_results=50,
        )
    """

    def __init__(
        self,
        api_key: str | None = None,
        rate_limit: RateLimitConfig | None = None,
    ):
        super().__init__(
            rate_limit=rate_limit or RateLimitConfig(
                requests_per_minute=10,  # Google Places API limit
                requests_per_hour=500,
                delay_between_requests=2.0,
            ),
        )
        self.api_key = api_key

    async def scrape(
        self,
        query: str,
        location: str,
        max_results: int = 20,
        **kwargs: Any,
    ) -> ScraperResult:
        """Scrape Google Maps for businesses matching the query in a location.

        Args:
            query: Business type/category (e.g., "restaurant", "plumber")
            location: Geographic location (e.g., "Berlin, Germany")
            max_results: Maximum number of results to return
        """
        start_time = __import__("time").monotonic()
        results: list[dict[str, Any]] = []
        errors: list[str] = []

        try:
            if self.api_key:
                results, errors = await self._scrape_via_api(
                    query, location, max_results
                )
            else:
                results, errors = await self._scrape_organic(
                    query, location, max_results
                )
        except Exception as e:
            logger.error("Google Maps scraper failed: %s", e)
            errors.append(f"Google Maps scrape failed: {e}")

        duration = (__import__("time").monotonic() - start_time) * 1000

        return ScraperResult(
            success=len(results) > 0,
            data=results,
            errors=errors,
            source="google_maps",
            items_found=len(results),
            duration_ms=duration,
        )

    async def _scrape_via_api(
        self,
        query: str,
        location: str,
        max_results: int,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Use the Google Places API for structured results."""
        import httpx

        results: list[dict[str, Any]] = []
        errors: list[str] = []

        # Text Search
        search_url = "https://places.googleapis.com/v1/places:searchText"
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.displayName,places.formattedAddress,"
                "places.websiteUri,places.internationalPhoneNumber,"
                "places.types,places.rating,places.userRatingCount,"
                "places.businessStatus,places.priceLevel"
            ),
            "Content-Type": "application/json",
        }
        body = {
            "textQuery": f"{query} in {location}",
            "maxResultCount": min(max_results, 20),
        }

        try:
            await self._wait_for_rate_limit()
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    search_url, headers=headers, json=body
                )

                if response.status_code != 200:
                    errors.append(
                        f"Places API error {response.status_code}: "
                        f"{response.text[:200]}"
                    )
                    return results, errors

                data = response.json()
                places = data.get("places", [])

                for place in places:
                    results.append({
                        "name": place.get("displayName", {}).get("text", ""),
                        "website": place.get("websiteUri"),
                        "phone": place.get("internationalPhoneNumber"),
                        "address": place.get("formattedAddress"),
                        "source": "google_maps",
                        "source_type": "api",
                        "rating": place.get("rating"),
                        "review_count": place.get("userRatingCount"),
                        "types": place.get("types", []),
                        "business_status": place.get("businessStatus"),
                        "price_level": place.get("priceLevel"),
                    })

        except Exception as e:
            errors.append(f"Places API request failed: {e}")

        return results, errors

    async def _scrape_organic(
        self,
        query: str,
        location: str,
        max_results: int,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Fallback organic search when no API key is provided.

        This uses a lightweight approach — searching for Google Maps
        URLs and extracting business data from the search results.
        Note: This is less reliable than the API approach and should
        only be used for development/testing.
        """
        results: list[dict[str, Any]] = []
        errors: list[str] = []

        search_query = quote(f"{query} {location} site:google.com/maps")
        url = f"https://www.google.com/search?q={search_query}&num={max_results}"

        try:
            status, content = await self.fetch_url(url)
            if status != 200:
                errors.append(f"Google search returned status {status}")
                return results, errors

            # Parse results from HTML
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(content, "html.parser")

            # Extract business listings from organic results
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                if "google.com/maps/place" in href:
                    # Extract business name from link text
                    name = link.get_text(strip=True)
                    if name and len(name) > 2:
                        results.append({
                            "name": name,
                            "source": "google_maps",
                            "source_type": "organic",
                            "source_url": href,
                        })

                        if len(results) >= max_results:
                            break

        except Exception as e:
            errors.append(f"Organic search failed: {e}")

        if not results:
            logger.warning(
                "No Google Maps results found for '%s' in '%s'. "
                "Consider using the Places API with an API key.",
                query, location,
            )

        return results, errors
