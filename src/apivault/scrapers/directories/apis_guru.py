"""Scraper for apis.guru OpenAPI directory.

Source: https://apis.guru
Method: GET https://api.apis.guru/v2/list.json
Format: JSON object keyed by API name, each with versions and OpenAPI spec URLs.
Frequency: Every 6 hours
Est. yield: ~2,500 APIs with full OpenAPI specs
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from ..base import BaseScraper, RawCandidate
from ..http import make_client

logger = logging.getLogger("apivault.scrapers.apis_guru")

LIST_URL = "https://api.apis.guru/v2/list.json"
SOURCE_URL = "https://apis.guru"


class ApisGuru(BaseScraper):
    """Fetch all APIs from the apis.guru OpenAPI directory."""

    name = "apis_guru"
    frequency_hours = 6

    async def run(self) -> AsyncIterator[RawCandidate]:
        async with make_client() as client:
            try:
                resp = await client.get(LIST_URL)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error("Failed to fetch apis.guru list: %s", e)
                return

        for api_name, api_info in data.items():
            try:
                info = api_info.get("info", {})
                title = info.get("title", api_name)
                description = info.get("description", "")

                external_docs = api_info.get("externalDocs", {})
                docs_url: str | None = external_docs.get("url") if isinstance(external_docs, dict) else None

                preferred = api_info.get("preferred")
                versions = api_info.get("versions", {})

                swagger_url = ""
                openapi_url = ""
                if preferred and preferred in versions:
                    version_info = versions[preferred]
                    swagger_url = version_info.get("swaggerUrl", "")
                    openapi_url = version_info.get("openAPIUrl", "")
                elif versions:
                    latest_key = list(versions.keys())[-1]
                    version_info = versions[latest_key]
                    swagger_url = version_info.get("swaggerUrl", "")
                    openapi_url = version_info.get("openAPIUrl", "")

                categories = info.get("x-apisguru-categories", [])

                base_url: str | None = None
                if swagger_url:
                    for suffix in ("/swagger.json", "/openapi.json", "/swagger.yaml", "/openapi.yaml"):
                        if swagger_url.endswith(suffix):
                            base_url = swagger_url[: -len(suffix)]
                            break
                    if not base_url:
                        base_url = swagger_url

                yield RawCandidate(
                    source_name=self.name,
                    source_url=SOURCE_URL,
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
