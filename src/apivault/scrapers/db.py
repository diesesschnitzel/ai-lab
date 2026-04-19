"""Minimal database interface for scraper candidate storage."""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.apivault.scrapers.base import RawCandidate

logger = logging.getLogger("apivault.scrapers.db")


class Database:
    """Database interface for scraper operations."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def start_scraper_run(self, scraper_name: str) -> str:
        run_id = str(uuid.uuid4())
        await self._session.execute(
            text(
                """
                INSERT INTO scraper_runs (id, scraper_name, status)
                VALUES (:run_id, :scraper_name, 'running')
                """
            ),
            {"run_id": run_id, "scraper_name": scraper_name},
        )
        await self._session.commit()
        return run_id

    async def finish_scraper_run(
        self,
        run_id: str,
        status: str,
        candidates_found: int,
        errors: list[str],
    ) -> None:
        error_text = "\n".join(errors) if errors else None
        await self._session.execute(
            text(
                """
                UPDATE scraper_runs
                SET finished_at = now(),
                    status = :status,
                    candidates_found = :candidates_found,
                    error = :error
                WHERE id = :run_id
                """
            ),
            {
                "run_id": run_id,
                "status": status,
                "candidates_found": candidates_found,
                "error": error_text,
            },
        )
        await self._session.commit()

    async def insert_raw_candidate(self, candidate: RawCandidate) -> None:
        await self._session.execute(
            text(
                """
                INSERT INTO raw_candidates
                    (source_name, source_url, raw_name, raw_description,
                     raw_base_url, raw_docs_url, raw_auth_type, raw_json)
                VALUES
                    (:source_name, :source_url, :raw_name, :raw_description,
                     :raw_base_url, :raw_docs_url, :raw_auth_type, :raw_json)
                """
            ),
            {
                "source_name": candidate.source_name,
                "source_url": candidate.source_url,
                "raw_name": candidate.raw_name,
                "raw_description": candidate.raw_description,
                "raw_base_url": candidate.raw_base_url,
                "raw_docs_url": candidate.raw_docs_url,
                "raw_auth_type": candidate.raw_auth_type,
                "raw_json": json.dumps(candidate.raw_json),
            },
        )
        await self._session.commit()
