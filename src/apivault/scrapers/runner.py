import asyncio
import logging

from .base import BaseScraper, ScraperResult
from .db import Database

logger = logging.getLogger("apivault.scrapers.runner")


async def run_scraper(scraper: BaseScraper, db: Database) -> ScraperResult:
    run_id = await db.start_scraper_run(scraper.name)
    found = 0
    errors = []

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

    except asyncio.TimeoutError:
        await db.finish_scraper_run(run_id, "timeout", found, errors)
        logger.error("Scraper %s timed out after %ds", scraper.name, scraper.timeout_seconds)
    except Exception as e:
        await db.finish_scraper_run(run_id, "failed", found, errors + [str(e)])
        logger.error("Scraper %s failed: %s", scraper.name, e)

    return ScraperResult(
        scraper_name=scraper.name,
        candidates=[],
        errors=errors,
        metadata={"found": found},
    )
