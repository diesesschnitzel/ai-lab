"""Scraper for API Ninjas directory.

Source: https://api-ninjas.com/api
Method: Scrape the API directory page to extract individual API listings.
Frequency: Every 24 hours
Est. yield: ~125 APIs
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator

from bs4 import BeautifulSoup

from ..base import BaseScraper, RawCandidate
from ..http import make_client

logger = logging.getLogger("apivault.scrapers.api_ninjas")

DIRECTORY_URL = "https://api-ninjas.com/api"
SOURCE_URL = "https://api-ninjas.com"
BASE_API_URL = "https://api.api-ninjas.com/v1"


class ApiNinjas(BaseScraper):
    """Scrape API Ninjas directory for available APIs."""

    name = "api_ninjas"
    frequency_hours = 24

    async def run(self) -> AsyncIterator[RawCandidate]:
        async with make_client() as client:
            try:
                resp = await client.get(DIRECTORY_URL)
                resp.raise_for_status()
                html = resp.text
            except Exception as e:
                logger.error("Failed to fetch API Ninjas directory: %s", e)
                return

        soup = BeautifulSoup(html, "html.parser")

        api_links = soup.find_all("a", href=re.compile(r"^/api/"))
        seen: set[str] = set()

        for link in api_links:
            href = link.get("href", "")
            api_path = href.strip("/").replace("api/", "")
            if not api_path or api_path in seen:
                continue
            seen.add(api_path)

            name = link.get_text(strip=True)
            if not name:
                continue

            api_url = f"{BASE_API_URL}/{api_path}"
            docs_url = f"{SOURCE_URL}/api/{api_path}"

            parent = link.find_parent()
            description = ""
            if parent:
                desc_elem = parent.find("p")
                if desc_elem:
                    description = desc_elem.get_text(strip=True)
                else:
                    desc_elem = link.find_next_sibling("p")
                    if desc_elem:
                        description = desc_elem.get_text(strip=True)

            yield RawCandidate(
                source_name=self.name,
                source_url=SOURCE_URL,
                raw_name=name,
                raw_description=description or None,
                raw_base_url=api_url,
                raw_docs_url=docs_url,
                raw_auth_type="apikey",
                raw_json={"api_path": api_path},
            )
