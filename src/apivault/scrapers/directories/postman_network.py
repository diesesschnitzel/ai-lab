import logging
from typing import AsyncIterator

from ..base import BaseScraper, RawCandidate
from ..http import make_client

logger = logging.getLogger("apivault.scrapers.postman_network")


class PostmanNetwork(BaseScraper):
    name = "postman_network"
    frequency_hours = 24

    async def run(self) -> AsyncIterator[RawCandidate]:
        async with make_client() as client:
            try:
                resp = await client.get(
                    "https://api.getpostman.com/workspaces?type=public",
                    headers={"X-Api-Key": ""},
                )
                if resp.status_code == 401:
                    logger.info("Postman API requires key; skipping authenticated endpoint")
                    workspaces = []
                else:
                    resp.raise_for_status()
                    data = resp.json()
                    workspaces = data.get("workspaces", [])
            except Exception as e:
                logger.error("Failed to fetch Postman workspaces: %s", e)
                workspaces = []

            for workspace in workspaces:
                try:
                    ws_name = workspace.get("name", "")
                    ws_id = workspace.get("id", "")
                    ws_type = workspace.get("type", "")

                    collections_resp = await client.get(
                        f"https://api.getpostman.com/collections?workspace={ws_id}",
                        headers={"X-Api-Key": ""},
                    )
                    if collections_resp.status_code != 200:
                        continue

                    collections_data = collections_resp.json()
                    collections = collections_data.get("collections", [])

                    for collection in collections:
                        col_name = collection.get("name", "")
                        col_uid = collection.get("uid", "")
                        col_desc = collection.get("description", "")

                        if not col_name:
                            continue

                        yield RawCandidate(
                            source_name=self.name,
                            source_url=f"https://www.postman.com/{ws_id}/collection/{col_uid}",
                            raw_name=col_name,
                            raw_description=col_desc,
                            raw_base_url=None,
                            raw_docs_url=f"https://www.postman.com/{ws_id}/collection/{col_uid}",
                            raw_auth_type=None,
                            raw_json={
                                "workspace": ws_name,
                                "workspace_id": ws_id,
                                "workspace_type": ws_type,
                                "collection_uid": col_uid,
                            },
                        )
                except Exception as e:
                    logger.warning("Failed to parse Postman workspace: %s", e)
                    continue
