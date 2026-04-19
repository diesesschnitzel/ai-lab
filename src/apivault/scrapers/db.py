import logging
from typing import Any

logger = logging.getLogger("apivault.scrapers")


class Database:
    """Minimal database interface for scraper candidate storage."""

    def __init__(self, dsn: str | None = None):
        self.dsn = dsn
        self._pool: Any = None

    async def connect(self):
        import asyncpg

        self._pool = await asyncpg.create_pool(dsn=self.dsn)

    async def close(self):
        if self._pool:
            await self._pool.close()

    async def start_scraper_run(self, scraper_name: str) -> str:
        import uuid

        run_id = str(uuid.uuid4())
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO scraper_runs (id, scraper_name, status)
                VALUES ($1, $2, 'running')
                """,
                run_id,
                scraper_name,
            )
        return run_id

    async def finish_scraper_run(
        self,
        run_id: str,
        status: str,
        candidates_found: int,
        errors: list[str],
    ):
        error_text = "\n".join(errors) if errors else None
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE scraper_runs
                SET finished_at = now(),
                    status = $2,
                    candidates_found = $3,
                    error = $4
                WHERE id = $1
                """,
                run_id,
                status,
                candidates_found,
                error_text,
            )

    async def insert_raw_candidate(self, candidate) -> None:
        import json

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO raw_candidates
                    (source_name, source_url, raw_name, raw_description,
                     raw_base_url, raw_docs_url, raw_auth_type, raw_json)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                candidate.source_name,
                candidate.source_url,
                candidate.raw_name,
                candidate.raw_description,
                candidate.raw_base_url,
                candidate.raw_docs_url,
                candidate.raw_auth_type,
                json.dumps(candidate.raw_json),
            )
