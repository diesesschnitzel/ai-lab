import logging
import re
from typing import AsyncIterator

from ..base import BaseScraper, RawCandidate
from ..http import make_client

logger = logging.getLogger("apivault.scrapers.npm")

SEARCH_TERMS = [
    "api-client",
    "api-wrapper",
    "api-sdk",
    "rest-client",
    "graphql-client",
    "openapi-client",
    "swagger-client",
    "weather-api",
    "payment-api",
    "maps-api",
    "sms-api",
]

URL_PATTERN = re.compile(r"https?://(?:api|developer|dev)\.[\w.-]+/?[\w/.-]*")
BASE_URL_PATTERN = re.compile(
    r"""(?:BASE_URL|API_ENDPOINT|base_url|apiUrl)\s*=\s*["']([^"']+)["']"""
)


class NpmRegistry(BaseScraper):
    name = "npm"
    frequency_hours = 24

    async def run(self) -> AsyncIterator[RawCandidate]:
        async with make_client() as client:
            for term in SEARCH_TERMS:
                try:
                    url = (
                        f"https://registry.npmjs.org/-/v1/search"
                        f"?text={term}&size=200"
                    )
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    logger.warning("Failed to search npm for '%s': %s", term, e)
                    continue

                for pkg_obj in data.get("objects", []):
                    pkg = pkg_obj.get("package", {})
                    try:
                        name = pkg.get("name", "")
                        description = pkg.get("description", "")
                        homepage = pkg.get("links", {}).get("homepage", "")
                        npm_link = pkg.get("links", {}).get("npm", "")
                        keywords = pkg.get("keywords", [])

                        if not name:
                            continue

                        docs_url = homepage or npm_link
                        base_url = self._extract_base_url(homepage, description)

                        yield RawCandidate(
                            source_name=self.name,
                            source_url=npm_link,
                            raw_name=name,
                            raw_description=description,
                            raw_base_url=base_url,
                            raw_docs_url=docs_url,
                            raw_auth_type=None,
                            raw_json={
                                "keywords": keywords,
                                "version": pkg.get("version"),
                                "scope": pkg.get("scope"),
                                "search_term": term,
                            },
                        )
                    except Exception as e:
                        logger.warning("Failed to parse npm package %s: %s", name, e)
                        continue

    def _extract_base_url(self, homepage: str, description: str) -> str | None:
        if homepage:
            match = URL_PATTERN.search(homepage)
            if match:
                return match.group(0)

        if description:
            match = URL_PATTERN.search(description)
            if match:
                return match.group(0)

        return None
