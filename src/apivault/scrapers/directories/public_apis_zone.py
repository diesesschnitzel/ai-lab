import logging
from typing import AsyncIterator

from ..base import BaseScraper, RawCandidate
from ..http import make_client

logger = logging.getLogger("apivault.scrapers.public_apis_zone")


class PublicApisZone(BaseScraper):
    name = "public_apis_zone"
    frequency_hours = 24

    async def run(self) -> AsyncIterator[RawCandidate]:
        url = "https://public.apis.zone/api/v1/apis"
        async with make_client() as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error("Failed to fetch public.apis.zone: %s", e)
                return

        apis = data if isinstance(data, list) else data.get("apis", data.get("data", []))

        for api in apis:
            try:
                name = api.get("name", "")
                description = api.get("description", "")
                base_url = api.get("base_url") or api.get("url")
                docs_url = api.get("docs_url") or api.get("documentation_url")
                auth_type = api.get("auth_type") or api.get("auth")
                category = api.get("category")

                if not name:
                    continue

                yield RawCandidate(
                    source_name=self.name,
                    source_url="https://public.apis.zone",
                    raw_name=name,
                    raw_description=description,
                    raw_base_url=base_url,
                    raw_docs_url=docs_url,
                    raw_auth_type=auth_type,
                    raw_json={"category": category, **api},
                )
            except Exception as e:
                logger.warning("Failed to parse public.apis.zone entry: %s", e)
                continue
