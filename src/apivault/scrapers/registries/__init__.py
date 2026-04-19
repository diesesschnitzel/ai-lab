import logging
import re
from typing import AsyncIterator

from ..base import BaseScraper, RawCandidate
from ..http import make_client

logger = logging.getLogger("apivault.scrapers.crates_io")

SEARCH_TERMS = [
    "api-client",
    "api-wrapper",
    "api-sdk",
    "rest-client",
    "graphql-client",
    "openapi",
    "swagger",
    "weather-api",
    "payment-api",
]

URL_PATTERN = re.compile(r"https?://(?:api|developer|dev)\.[\w.-]+/?[\w/.-]*")


class CratesIoRegistry(BaseScraper):
    name = "crates_io"
    frequency_hours = 24

    async def run(self) -> AsyncIterator[RawCandidate]:
        async with make_client() as client:
            for term in SEARCH_TERMS:
                try:
                    url = f"https://crates.io/api/v1/crates?q={term}&per_page=100"
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    logger.warning("Failed to search crates.io for '%s': %s", term, e)
                    continue

                crates = data.get("crates", [])

                for crate in crates:
                    try:
                        name = crate.get("name", "")
                        description = crate.get("description", "")
                        homepage = crate.get("homepage", "")
                        docs_url = crate.get("documentation", "") or homepage
                        crate_url = f"https://crates.io/crates/{name}"

                        if not name:
                            continue

                        base_url = self._extract_base_url(homepage, description)

                        yield RawCandidate(
                            source_name=self.name,
                            source_url=crate_url,
                            raw_name=name,
                            raw_description=description,
                            raw_base_url=base_url,
                            raw_docs_url=docs_url,
                            raw_auth_type=None,
                            raw_json={
                                "version": crate.get("newest_version"),
                                "downloads": crate.get("downloads"),
                                "keywords": crate.get("keywords", []),
                                "categories": crate.get("categories", []),
                                "search_term": term,
                            },
                        )
                    except Exception as e:
                        logger.warning("Failed to parse crate %s: %s", name, e)
                        continue

    def _extract_base_url(self, homepage: str, description: str) -> str | None:
        for text in [homepage, description]:
            if text:
                match = URL_PATTERN.search(text)
                if match:
                    return match.group(0)
        return None
