"""Scraper runner with error isolation and structured logging."""

from __future__ import annotations

import asyncio
import logging

from src.apivault.scrapers.base import BaseScraper, ScraperResult
from src.apivault.scrapers.db import Database

logger = logging.getLogger("apivault.scrapers.runner")


async def run_scraper(scraper: BaseScraper, db: Database) -> ScraperResult:
    """Execute a scraper, inserting candidates into the database.

    Handles timeouts and per-item errors without aborting the run.
    """
    run_id = await db.start_scraper_run(scraper.name)
    found = 0
    errors: list[str] = []

    try:
        async with asyncio.timeout(scraper.timeout_seconds):
            async for candidate in scraper.run():
                try:
                    await db.insert_raw_candidate(candidate)
                    found += 1
                except Exception as e:
                    errors.append(str(e))
                    logger.warning(
                        "Failed to insert candidate from %s: %s",
                        scraper.name,
                        e,
                    )

        await db.finish_scraper_run(run_id, "success", found, errors)

    except TimeoutError:
        await db.finish_scraper_run(run_id, "timeout", found, errors)
        logger.error("Scraper %s timed out after %ds", scraper.name, scraper.timeout_seconds)
    except Exception as e:
        errors.append(str(e))
        await db.finish_scraper_run(run_id, "failed", found, errors)
        logger.error("Scraper %s failed: %s", scraper.name, e)

    return ScraperResult(
        scraper_name=scraper.name,
        candidates=[],
        errors=errors,
        metadata={"found": found},
    )
