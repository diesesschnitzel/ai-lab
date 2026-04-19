import logging
from typing import AsyncIterator

from ..base import BaseScraper, RawCandidate
from ..http import make_client

logger = logging.getLogger("apivault.scrapers.swaggerhub")


class SwaggerHub(BaseScraper):
    name = "swaggerhub"
    frequency_hours = 24
    PAGE_SIZE = 100

    async def run(self) -> AsyncIterator[RawCandidate]:
        base_url = "https://api.swaggerhub.com"
        async with make_client() as client:
            page = 1
            while True:
                try:
                    url = (
                        f"{base_url}/apis/search"
                        f"?limit={self.PAGE_SIZE}&offset={(page - 1) * self.PAGE_SIZE}"
                        f"&type=api&visibility=public"
                    )
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    logger.error("Failed to fetch SwaggerHub page %d: %s", page, e)
                    break

                apis = data.get("apis", [])
                if not apis:
                    break

                for api in apis:
                    try:
                        name = api.get("name", "")
                        owner = api.get("owner", "")
                        description = api.get("description", "")
                        version = api.get("version", "")

                        if not name:
                            continue

                        docs_url = f"https://app.swaggerhub.com/apis/{owner}/{name}"
                        if version:
                            docs_url += f"/{version}"

                        yield RawCandidate(
                            source_name=self.name,
                            source_url=docs_url,
                            raw_name=f"{owner}/{name}",
                            raw_description=description,
                            raw_base_url=None,
                            raw_docs_url=docs_url,
                            raw_auth_type=None,
                            raw_json={
                                "owner": owner,
                                "version": version,
                                "swaggerhub_id": api.get("id"),
                            },
                        )
                    except Exception as e:
                        logger.warning("Failed to parse SwaggerHub entry: %s", e)
                        continue

                total = data.get("total", 0)
                if page * self.PAGE_SIZE >= total:
                    break
                page += 1
