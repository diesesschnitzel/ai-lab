import logging
import re
import xmlrpc.client
from typing import AsyncIterator

from ..base import BaseScraper, RawCandidate
from ..http import make_client

logger = logging.getLogger("apivault.scrapers.pypi")

SEARCH_TERMS = [
    "api client",
    "api wrapper",
    "api sdk",
    "rest client",
    "graphql client",
    "openapi",
    "swagger",
    "weather api",
    "payment api",
    "maps api",
]

URL_PATTERN = re.compile(r"https?://(?:api|developer|dev)\.[\w.-]+/?[\w/.-]*")


class PypiRegistry(BaseScraper):
    name = "pypi"
    frequency_hours = 24

    async def run(self) -> AsyncIterator[RawCandidate]:
        async with make_client() as client:
            for term in SEARCH_TERMS:
                try:
                    url = f"https://pypi.org/search/?q={term.replace(' ', '+')}&page=1"
                    resp = await client.get(url)
                    resp.raise_for_status()
                    html = resp.text
                except Exception as e:
                    logger.warning("Failed to search PyPI for '%s': %s", term, e)
                    continue

                packages = self._parse_search_results(html)

                for pkg_name, pkg_url in packages:
                    try:
                        pkg_data = await self._fetch_package(client, pkg_name)
                        if not pkg_data:
                            continue

                        info = pkg_data.get("info", {})
                        description = info.get("summary", "")
                        homepage = info.get("home_page", "")
                        project_urls = info.get("project_urls", {}) or {}
                        docs_url = (
                            project_urls.get("Documentation")
                            or project_urls.get("docs")
                            or homepage
                        )

                        base_url = self._extract_base_url(
                            homepage, description, str(project_urls)
                        )

                        yield RawCandidate(
                            source_name=self.name,
                            source_url=f"https://pypi.org/project/{pkg_name}/",
                            raw_name=pkg_name,
                            raw_description=description,
                            raw_base_url=base_url,
                            raw_docs_url=docs_url,
                            raw_auth_type=None,
                            raw_json={
                                "version": info.get("version"),
                                "keywords": info.get("keywords", ""),
                                "search_term": term,
                            },
                        )
                    except Exception as e:
                        logger.warning("Failed to parse PyPI package %s: %s", pkg_name, e)
                        continue

    def _parse_search_results(self, html: str) -> list[tuple[str, str]]:
        import re

        pattern = re.compile(r'<a\s+href="/project/([^/]+)/"')
        results = []
        for match in pattern.finditer(html):
            name = match.group(1)
            results.append((name, f"https://pypi.org/project/{name}/"))
        return results

    async def _fetch_package(self, client, name: str) -> dict | None:
        try:
            resp = await client.get(f"https://pypi.org/pypi/{name}/json")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("Failed to fetch PyPI package %s: %s", name, e)
            return None

    def _extract_base_url(self, homepage: str, description: str, project_urls: str) -> str | None:
        for text in [homepage, description, project_urls]:
            if text:
                match = URL_PATTERN.search(text)
                if match:
                    return match.group(0)
        return None
