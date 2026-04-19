import logging
import re
from typing import AsyncIterator

from ..base import BaseScraper, RawCandidate
from ..http import make_client

logger = logging.getLogger("apivault.scrapers.rubygems")

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


class RubyGemsRegistry(BaseScraper):
    name = "rubygems"
    frequency_hours = 24

    async def run(self) -> AsyncIterator[RawCandidate]:
        async with make_client() as client:
            for term in SEARCH_TERMS:
                try:
                    url = f"https://rubygems.org/api/v1/search.json?query={term}&page=1"
                    resp = await client.get(url)
                    resp.raise_for_status()
                    gems = resp.json()
                except Exception as e:
                    logger.warning("Failed to search RubyGems for '%s': %s", term, e)
                    continue

                if not isinstance(gems, list):
                    continue

                for gem in gems:
                    try:
                        name = gem.get("name", "")
                        description = gem.get("description", "") or gem.get("info", "")
                        homepage = gem.get("homepage_uri", "")
                        docs_url = gem.get("documentation_uri", "") or homepage
                        gem_url = gem.get("gem_uri", "")

                        if not name:
                            continue

                        base_url = self._extract_base_url(homepage, description)

                        yield RawCandidate(
                            source_name=self.name,
                            source_url=gem_url or f"https://rubygems.org/gems/{name}",
                            raw_name=name,
                            raw_description=description,
                            raw_base_url=base_url,
                            raw_docs_url=docs_url,
                            raw_auth_type=None,
                            raw_json={
                                "version": gem.get("version"),
                                "downloads": gem.get("downloads"),
                                "search_term": term,
                            },
                        )
                    except Exception as e:
                        logger.warning("Failed to parse RubyGem %s: %s", name, e)
                        continue

    def _extract_base_url(self, homepage: str, description: str) -> str | None:
        for text in [homepage, description]:
            if text:
                match = URL_PATTERN.search(text)
                if match:
                    return match.group(0)
        return None
