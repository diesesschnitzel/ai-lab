import logging
import re
from typing import AsyncIterator

from bs4 import BeautifulSoup

from ..base import BaseScraper, RawCandidate
from ..http import make_client

logger = logging.getLogger("apivault.scrapers.any_api_com")


class AnyApiCom(BaseScraper):
    name = "any_api_com"
    frequency_hours = 24

    async def run(self) -> AsyncIterator[RawCandidate]:
        base_url = "https://any-api.com"
        async with make_client() as client:
            try:
                resp = await client.get(f"{base_url}/directory")
                resp.raise_for_status()
                html = resp.text
            except Exception as e:
                logger.error("Failed to fetch any-api.com directory: %s", e)
                return

        soup = BeautifulSoup(html, "html.parser")

        for link in soup.select("a[href^='/']"):
            href = link.get("href", "")
            title = link.get("title", "") or link.get_text(strip=True)

            if not href or not title:
                continue

            match = re.match(r"^/([^/]+)/?$", href)
            if not match:
                continue

            api_slug = match.group(1)
            if api_slug in ("directory", "about", "contact", ""):
                continue

            yield RawCandidate(
                source_name=self.name,
                source_url=f"{base_url}{href}",
                raw_name=title,
                raw_description=None,
                raw_base_url=None,
                raw_docs_url=f"{base_url}{href}",
                raw_auth_type=None,
                raw_json={"slug": api_slug},
            )
