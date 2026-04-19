"""Scraper for the public-apis GitHub repository.

Source: https://github.com/public-apis/public-apis
Method: Download README.md via raw GitHub URL, parse markdown tables.
Format: Markdown tables with columns: API | Description | Auth | HTTPS | CORS | Link
Frequency: Every 6 hours
Est. yield: ~1,500 APIs
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator

from ..base import BaseScraper, RawCandidate
from ..http import make_client

logger = logging.getLogger("apivault.scrapers.public_apis_github")

README_URL = "https://raw.githubusercontent.com/public-apis/public-apis/master/README.md"
SOURCE_URL = "https://github.com/public-apis/public-apis"


class PublicApisGitHub(BaseScraper):
    """Parse the public-apis GitHub README markdown table."""

    name = "public_apis_github"
    frequency_hours = 6

    async def run(self) -> AsyncIterator[RawCandidate]:
        async with make_client() as client:
            try:
                resp = await client.get(README_URL)
                resp.raise_for_status()
                content = resp.text
            except Exception as e:
                logger.error("Failed to fetch public-apis README: %s", e)
                return

        current_category = "Unknown"
        for line in content.splitlines():
            if line.startswith("## "):
                current_category = line[3:].strip()
                continue

            if not line.startswith("| ") or line.startswith("| API ") or "---" in line:
                continue

            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) < 4:
                continue

            name = parts[0]
            desc = parts[1]
            auth = parts[2]
            https_flag = parts[3] if len(parts) > 3 else ""
            link = parts[-1] if len(parts) >= 5 else ""

            url_match = re.search(r"\[.*?\]\((.*?)\)", link)
            base_url = url_match.group(1) if url_match else None

            if not name or name == "API":
                continue

            auth_normalized: str | None = None
            if auth and auth.lower() != "no":
                auth_normalized = auth.lower()

            yield RawCandidate(
                source_name=self.name,
                source_url=SOURCE_URL,
                raw_name=name,
                raw_description=desc,
                raw_base_url=base_url,
                raw_docs_url=base_url,
                raw_auth_type=auth_normalized,
                raw_json={"category": current_category, "https": https_flag},
            )
