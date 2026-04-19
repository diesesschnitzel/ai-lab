import logging
from typing import AsyncIterator

from ..base import BaseScraper, RawCandidate
from ..http import make_client

logger = logging.getLogger("apivault.scrapers.apis_guru")


class ApisGuru(BaseScraper):
    name = "apis_guru"
    frequency_hours = 6

    async def run(self) -> AsyncIterator[RawCandidate]:
        url = "https://api.apis.guru/v2/list.json"
        async with make_client() as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error("Failed to fetch apis.guru list: %s", e)
                return

        for api_name, api_info in data.items():
            try:
                title = api_info.get("info", {}).get("title", api_name)
                description = api_info.get("info", {}).get("description", "")
                external_docs = api_info.get("externalDocs", {})
                docs_url = external_docs.get("url") if isinstance(external_docs, dict) else None

                preferred = api_info.get("preferred", None)
                versions = api_info.get("versions", {})

                if preferred and preferred in versions:
                    version_info = versions[preferred]
                    swagger_url = version_info.get("swaggerUrl", "")
                    openapi_url = version_info.get("openAPIUrl", "")
                elif versions:
                    latest_key = list(versions.keys())[-1]
                    version_info = versions[latest_key]
                    swagger_url = version_info.get("swaggerUrl", "")
                    openapi_url = version_info.get("openAPIUrl", "")
                else:
                    swagger_url = ""
                    openapi_url = ""

                categories = api_info.get("info", {}).get("x-apisguru-categories", [])

                base_url = None
                if swagger_url:
                    base_url = swagger_url.split("/swagger.json")[0]
                    if not base_url:
                        base_url = swagger_url.split("/openapi.json")[0]

                yield RawCandidate(
                    source_name=self.name,
                    source_url="https://apis.guru",
                    raw_name=title,
                    raw_description=description,
                    raw_base_url=base_url,
                    raw_docs_url=docs_url,
                    raw_auth_type=None,
                    raw_json={
                        "api_name": api_name,
                        "swagger_url": swagger_url,
                        "openapi_url": openapi_url,
                        "categories": categories,
                        "versions": list(versions.keys()),
                    },
                )
            except Exception as e:
                logger.warning("Failed to parse apis.guru entry %s: %s", api_name, e)
                continue
