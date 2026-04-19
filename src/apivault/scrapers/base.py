from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class RawCandidate:
    source_name: str
    source_url: str | None
    raw_name: str | None
    raw_description: str | None
    raw_base_url: str | None
    raw_docs_url: str | None
    raw_auth_type: str | None
    raw_json: dict = field(default_factory=dict)


@dataclass
class ScraperResult:
    scraper_name: str
    candidates: list[RawCandidate]
    errors: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class BaseScraper:
    name: str = "base"
    frequency_hours: int = 24
    timeout_seconds: int = 3600

    async def run(self) -> AsyncIterator[RawCandidate]:
        raise NotImplementedError
