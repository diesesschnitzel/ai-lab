"""APScheduler-based task scheduler for API discovery and enrichment jobs.

Schedule overview:
- Every 1h:  process raw_candidates queue, run overdue validation
- Every 6h:  run Tier 1 scrapers, enrichment batch
- Every 24h: package registry scrapers, GitHub search, dead API retry
- Every 7d:  cert transparency, government portals, full re-validation
- Every 30d: Common Crawl, Wayback Machine, archive old health logs

All jobs use asyncio for I/O-bound tasks with enforced timeout limits.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.apivault.config import settings
from src.apivault.database import async_session_factory, engine
from src.apivault.models.api import Api
from src.apivault.models.raw_candidate import RawCandidate as RawCandidateModel
from src.apivault.pipeline.models import RawCandidate as RawCandidatePydantic
from src.apivault.pipeline.repository import PipelineRepository

logger = logging.getLogger(__name__)

# Job timeout limits (seconds)
TIMEOUTS = {
    "process_raw_candidates": 1800,  # 30 min
    "overdue_validation": 3600,  # 60 min
    "tier1_scrapers": 1800,  # 30 min
    "enrichment_batch": 3600,  # 60 min
    "package_registry_scrapers": 3600,  # 60 min
    "github_search": 1800,  # 30 min
    "dead_api_retry": 3600,  # 60 min
    "cert_transparency": 3600,  # 60 min
    "government_portals": 3600,  # 60 min
    "full_revalidation": 7200,  # 120 min
    "common_crawl": 7200,  # 120 min
    "wayback_machine": 7200,  # 120 min
    "archive_health_logs": 1800,  # 30 min
}


def _to_pydantic_candidate(model: RawCandidateModel) -> RawCandidatePydantic:
    """Convert SQLAlchemy RawCandidate to Pydantic RawCandidate."""
    return RawCandidatePydantic(
        name=model.raw_name,
        url=model.raw_base_url,
        description=model.raw_description,
        source=model.source_name,
        raw_data=model.raw_json or {},
    )


async def _run_with_timeout(coro: Any, job_name: str) -> Any:
    """Run a coroutine with a job-specific timeout."""
    timeout = TIMEOUTS.get(job_name, 3600)
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error("Job '%s' timed out after %d seconds", job_name, timeout)
        raise


async def process_raw_candidates() -> None:
    """Process pending raw_candidates through normalization pipeline."""
    logger.info("Starting raw_candidates processing")
    async with async_session_factory() as session:
        repo = PipelineRepository(session)
        pending_models = await repo.get_pending_candidates(limit=500)
        if not pending_models:
            logger.info("No pending raw candidates")
            return

        # Convert SQLAlchemy models to Pydantic models
        pending = [_to_pydantic_candidate(m) for m in pending_models]
        logger.info("Found %d pending raw candidates", len(pending))

        from src.apivault.pipeline.orchestrator import PipelineOrchestrator

        orchestrator = PipelineOrchestrator()
        result = await orchestrator.run(pending)

        if result.errors:
            for error in result.errors:
                logger.error("Pipeline error: %s", error)

        processed_ids = [m.id for m in pending_models if m.id]
        status = "failed" if result.errors else "done"
        await repo.mark_candidates_processed(processed_ids, status=status)
        await session.commit()

        logger.info(
            "Processed %d candidates: %d normalized, %d new, %d merged, %d errors",
            len(pending),
            len(result.normalized),
            len(result.new_records),
            len(result.merged_records),
            len(result.errors),
        )


async def overdue_validation() -> None:
    """Run validation on overdue APIs."""
    logger.info("Starting overdue validation")
    async with async_session_factory() as session:
        repo = PipelineRepository(session)
        due_apis = await repo.get_apis_due_for_validation(limit=50)
        if not due_apis:
            logger.info("No APIs due for validation")
            return

        logger.info("Found %d APIs due for validation", len(due_apis))

        from src.apivault.services.validation_service import probe_api

        validated = 0
        for api in due_apis:
            try:
                health_data = await probe_api(api)
                await repo.update_api_health(api.id, health_data)
                validated += 1
            except Exception as e:
                logger.error("Validation failed for API %s: %s", api.id, e)

        await session.commit()
        logger.info("Validated %d/%d APIs", validated, len(due_apis))


async def tier1_scrapers() -> None:
    """Run Tier 1 scrapers (high-priority, frequent sources)."""
    logger.info("Starting Tier 1 scrapers")
    async with async_session_factory() as session:
        repo = PipelineRepository(session)

        tier1_sources = [
            "rapidapi",
            "programmableweb",
            "publicapis",
            "apilist",
        ]

        from src.apivault.services.scraper_service import run_scraper

        for source in tier1_sources:
            try:
                run = await repo.create_scraper_run(source)
                candidates = await run_scraper(source)
                await repo.complete_scraper_run(
                    run.id,
                    candidates_found=len(candidates),
                    candidates_new=len(candidates),
                )
                await session.commit()
                logger.info("Tier 1 scraper '%s' found %d candidates", source, len(candidates))
            except Exception as e:
                logger.error("Tier 1 scraper '%s' failed: %s", source, e)
                await session.rollback()


async def enrichment_batch() -> None:
    """Run enrichment on unenriched APIs."""
    logger.info("Starting enrichment batch")
    async with async_session_factory() as session:
        repo = PipelineRepository(session)
        unenriched = await repo.get_unenriched_apis(limit=20)
        if not unenriched:
            logger.info("No APIs pending enrichment")
            return

        logger.info("Found %d APIs pending enrichment", len(unenriched))

        from src.apivault.services.enrichment_service import enrich_api

        enriched = 0
        for api in unenriched:
            try:
                enrichment_data = await enrich_api(api)
                await repo.update_api_enrichment(api.id, enrichment_data)
                enriched += 1
            except Exception as e:
                logger.error("Enrichment failed for API %s: %s", api.id, e)

        await session.commit()
        logger.info("Enriched %d/%d APIs", enriched, len(unenriched))


async def package_registry_scrapers() -> None:
    """Run package registry scrapers (npm, PyPI, etc.)."""
    logger.info("Starting package registry scrapers")
    async with async_session_factory() as session:
        repo = PipelineRepository(session)

        registries = ["registry_npm", "registry_pypi", "registry_rubygems", "registry_crates"]

        from src.apivault.services.scraper_service import run_scraper

        for registry in registries:
            try:
                run = await repo.create_scraper_run(registry)
                candidates = await run_scraper(registry)
                await repo.complete_scraper_run(
                    run.id,
                    candidates_found=len(candidates),
                    candidates_new=len(candidates),
                )
                await session.commit()
                logger.info("Registry scraper '%s' found %d candidates", registry, len(candidates))
            except Exception as e:
                logger.error("Registry scraper '%s' failed: %s", registry, e)
                await session.rollback()


async def github_search() -> None:
    """Run GitHub API search for new API candidates."""
    logger.info("Starting GitHub search scraper")
    async with async_session_factory() as session:
        repo = PipelineRepository(session)

        from src.apivault.services.scraper_service import run_scraper

        try:
            run = await repo.create_scraper_run("github_search")
            candidates = await run_scraper("github_search")
            await repo.complete_scraper_run(
                run.id,
                candidates_found=len(candidates),
                candidates_new=len(candidates),
            )
            await session.commit()
            logger.info("GitHub search found %d candidates", len(candidates))
        except Exception as e:
            logger.error("GitHub search scraper failed: %s", e)
            await session.rollback()


async def dead_api_retry() -> None:
    """Retry validation on dead APIs to check if they've recovered."""
    logger.info("Starting dead API retry")
    async with async_session_factory() as session:
        repo = PipelineRepository(session)
        dead_apis = await repo.get_dead_apis(limit=100)
        if not dead_apis:
            logger.info("No dead APIs to retry")
            return

        logger.info("Found %d dead APIs to retry", len(dead_apis))

        from src.apivault.services.validation_service import probe_api

        recovered = 0
        for api in dead_apis:
            try:
                health_data = await probe_api(api)
                if health_data.get("status") != "dead":
                    recovered += 1
                await repo.update_api_health(api.id, health_data)
            except Exception as e:
                logger.error("Dead API retry failed for %s: %s", api.id, e)

        await session.commit()
        logger.info("Dead API retry: %d/%d recovered", recovered, len(dead_apis))


async def cert_transparency() -> None:
    """Run certificate transparency log scraping."""
    logger.info("Starting certificate transparency scraper")
    async with async_session_factory() as session:
        repo = PipelineRepository(session)

        from src.apivault.services.scraper_service import run_scraper

        try:
            run = await repo.create_scraper_run("cert_transparency")
            candidates = await run_scraper("cert_transparency")
            await repo.complete_scraper_run(
                run.id,
                candidates_found=len(candidates),
                candidates_new=len(candidates),
            )
            await session.commit()
            logger.info("Cert transparency found %d candidates", len(candidates))
        except Exception as e:
            logger.error("Cert transparency scraper failed: %s", e)
            await session.rollback()


async def government_portals() -> None:
    """Run government portal scraping."""
    logger.info("Starting government portals scraper")
    async with async_session_factory() as session:
        repo = PipelineRepository(session)

        from src.apivault.services.scraper_service import run_scraper

        try:
            run = await repo.create_scraper_run("government_portals")
            candidates = await run_scraper("government_portals")
            await repo.complete_scraper_run(
                run.id,
                candidates_found=len(candidates),
                candidates_new=len(candidates),
            )
            await session.commit()
            logger.info("Government portals found %d candidates", len(candidates))
        except Exception as e:
            logger.error("Government portals scraper failed: %s", e)
            await session.rollback()


async def full_revalidation() -> None:
    """Run full re-validation on all active APIs."""
    logger.info("Starting full re-validation")
    async with async_session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(select(Api).where(Api.status.in_(["active", "degraded"])).limit(500))
        apis = list(result.scalars().all())

        if not apis:
            logger.info("No APIs to re-validate")
            return

        logger.info("Re-validating %d APIs", len(apis))

        from src.apivault.services.validation_service import probe_api

        repo = PipelineRepository(session)
        validated = 0
        for api in apis:
            try:
                health_data = await probe_api(api)
                await repo.update_api_health(api.id, health_data)
                validated += 1
            except Exception as e:
                logger.error("Re-validation failed for API %s: %s", api.id, e)

        await session.commit()
        logger.info("Full re-validation: %d/%d APIs validated", validated, len(apis))


async def common_crawl() -> None:
    """Run Common Crawl scraping for API discovery."""
    logger.info("Starting Common Crawl scraper")
    async with async_session_factory() as session:
        repo = PipelineRepository(session)

        from src.apivault.services.scraper_service import run_scraper

        try:
            run = await repo.create_scraper_run("common_crawl")
            candidates = await run_scraper("common_crawl")
            await repo.complete_scraper_run(
                run.id,
                candidates_found=len(candidates),
                candidates_new=len(candidates),
            )
            await session.commit()
            logger.info("Common Crawl found %d candidates", len(candidates))
        except Exception as e:
            logger.error("Common Crawl scraper failed: %s", e)
            await session.rollback()


async def wayback_machine() -> None:
    """Run Wayback Machine scraping for historical API discovery."""
    logger.info("Starting Wayback Machine scraper")
    async with async_session_factory() as session:
        repo = PipelineRepository(session)

        from src.apivault.services.scraper_service import run_scraper

        try:
            run = await repo.create_scraper_run("wayback_machine")
            candidates = await run_scraper("wayback_machine")
            await repo.complete_scraper_run(
                run.id,
                candidates_found=len(candidates),
                candidates_new=len(candidates),
            )
            await session.commit()
            logger.info("Wayback Machine found %d candidates", len(candidates))
        except Exception as e:
            logger.error("Wayback Machine scraper failed: %s", e)
            await session.rollback()


async def archive_health_logs() -> None:
    """Archive old health logs to reduce database size."""
    logger.info("Starting health log archival")
    async with async_session_factory() as session:
        from sqlalchemy import delete, select

        from src.apivault.models.api_health_log import ApiHealthLog

        cutoff = datetime.now(UTC) - timedelta(days=90)
        result = await session.execute(select(ApiHealthLog).where(ApiHealthLog.checked_at < cutoff).limit(1000))
        old_logs = list(result.scalars().all())

        if not old_logs:
            logger.info("No health logs to archive")
            return

        logger.info("Archiving %d old health logs", len(old_logs))

        await session.execute(delete(ApiHealthLog).where(ApiHealthLog.checked_at < cutoff))
        await session.commit()
        logger.info("Archived %d health logs", len(old_logs))


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = AsyncIOScheduler()

    hourly_jobs = [
        ("process_raw_candidates", process_raw_candidates),
        ("overdue_validation", overdue_validation),
    ]

    six_hour_jobs = [
        ("tier1_scrapers", tier1_scrapers),
        ("enrichment_batch", enrichment_batch),
    ]

    daily_jobs = [
        ("package_registry_scrapers", package_registry_scrapers),
        ("github_search", github_search),
        ("dead_api_retry", dead_api_retry),
    ]

    weekly_jobs = [
        ("cert_transparency", cert_transparency),
        ("government_portals", government_portals),
        ("full_revalidation", full_revalidation),
    ]

    monthly_jobs = [
        ("common_crawl", common_crawl),
        ("wayback_machine", wayback_machine),
        ("archive_health_logs", archive_health_logs),
    ]

    for job_name, func in hourly_jobs:
        scheduler.add_job(
            _run_with_timeout,
            trigger=IntervalTrigger(hours=1),
            id=job_name,
            name=job_name,
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=300,
            args=[func(), job_name],
        )

    for job_name, func in six_hour_jobs:
        scheduler.add_job(
            _run_with_timeout,
            trigger=IntervalTrigger(hours=6),
            id=job_name,
            name=job_name,
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=600,
            args=[func(), job_name],
        )

    for job_name, func in daily_jobs:
        scheduler.add_job(
            _run_with_timeout,
            trigger=IntervalTrigger(hours=24),
            id=job_name,
            name=job_name,
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=3600,
            args=[func(), job_name],
        )

    for job_name, func in weekly_jobs:
        scheduler.add_job(
            _run_with_timeout,
            trigger=IntervalTrigger(days=7),
            id=job_name,
            name=job_name,
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=7200,
            args=[func(), job_name],
        )

    for job_name, func in monthly_jobs:
        scheduler.add_job(
            _run_with_timeout,
            trigger=IntervalTrigger(days=30),
            id=job_name,
            name=job_name,
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=86400,
            args=[func(), job_name],
        )

    logger.info("Scheduler configured with %d jobs", len(scheduler.get_jobs()))
    return scheduler


async def main() -> None:
    """Run the scheduler process."""
    logging.basicConfig(
        level=logging.INFO if not settings.debug else logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown(wait=True)
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
