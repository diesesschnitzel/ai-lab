import logging
import re
from typing import AsyncIterator
from urllib.parse import quote

from ..base import BaseScraper, RawCandidate
from ..http import make_client

logger = logging.getLogger("apivault.scrapers.nuget")

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
]

URL_PATTERN = re.compile(r"https?://(?:api|developer|dev)\.[\w.-]+/?[\w/.-]*")


class NuGetRegistry(BaseScraper):
    name = "nuget"
    frequency_hours = 24

    async def run(self) -> AsyncIterator[RawCandidate]:
        async with make_client() as client:
            for term in SEARCH_TERMS:
                try:
                    url = (
                        f"https://azuresearch-usnc.nuget.org/query"
                        f"?q={quote(term)}&take=200&prerelease=false"
                    )
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    logger.warning("Failed to search NuGet for '%s': %s", term, e)
                    continue

                packages = data.get("data", [])

                for pkg in packages:
                    try:
                        name = pkg.get("id", "")
                        description = pkg.get("description", "") or pkg.get("summary", "")
                        project_url = pkg.get("projectUrl", "")
                        package_url = f"https://www.nuget.org/packages/{name}"

                        if not name:
                            continue

                        base_url = self._extract_base_url(project_url, description)

                        yield RawCandidate(
                            source_name=self.name,
                            source_url=package_url,
                            raw_name=name,
                            raw_description=description,
                            raw_base_url=base_url,
                            raw_docs_url=project_url,
                            raw_auth_type=None,
                            raw_json={
                                "version": pkg.get("version"),
                                "total_downloads": pkg.get("totalDownloads"),
                                "tags": pkg.get("tags", []),
                                "search_term": term,
                            },
                        )
                    except Exception as e:
                        logger.warning("Failed to parse NuGet package %s: %s", name, e)
                        continue

    def _extract_base_url(self, project_url: str, description: str) -> str | None:
        for text in [project_url, description]:
            if text:
                match = URL_PATTERN.search(text)
                if match:
                    return match.group(0)
        return None
