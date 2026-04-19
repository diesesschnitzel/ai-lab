"""Background worker for processing API scraping and validation tasks.

The worker polls the database and dispatches work across pipeline stages:
- Normalization: process raw_candidates queue (batch size: 500)
- Validation: probe APIs due for validation (concurrent: 50)
- Enrichment: enrich unenriched APIs (batch size: 20)

All I/O-bound tasks use asyncio for concurrent execution.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from src.apivault.config import settings
from src.apivault.database import async_session_factory, engine
from src.apivault.models.api import Api
from src.apivault.models.raw_candidate import RawCandidate as RawCandidateModel
from src.apivault.pipeline.models import RawCandidate as RawCandidatePydantic
from src.apivault.pipeline.repository import PipelineRepository

logger = logging.getLogger(__name__)

# Worker configuration
CYCLE_INTERVAL = 30  # seconds between polling cycles
NORMALIZATION_BATCH_SIZE = 500
VALIDATION_CONCURRENCY = 50
ENRICHMENT_BATCH_SIZE = 20
JOB_TIMEOUT = 3600  # 60 min default timeout


def _to_pydantic_candidate(model: RawCandidateModel) -> RawCandidatePydantic:
    """Convert SQLAlchemy RawCandidate to Pydantic RawCandidate."""
    return RawCandidatePydantic(
        name=model.raw_name,
        url=model.raw_base_url,
        description=model.raw_description,
        source=model.source_name,
        raw_data=model.raw_json or {},
    )


class PipelineWorker:
    """Background worker that processes the data pipeline stages."""

    def __init__(
        self,
        cycle_interval: int = CYCLE_INTERVAL,
        normalization_batch_size: int = NORMALIZATION_BATCH_SIZE,
        validation_concurrency: int = VALIDATION_CONCURRENCY,
        enrichment_batch_size: int = ENRICHMENT_BATCH_SIZE,
    ) -> None:
        self.cycle_interval = cycle_interval
        self.normalization_batch_size = normalization_batch_size
        self.validation_concurrency = validation_concurrency
        self.enrichment_batch_size = enrichment_batch_size
        self._running = False
        self._stats: dict[str, Any] = {
            "cycles_completed": 0,
            "candidates_processed": 0,
            "apis_validated": 0,
            "apis_enriched": 0,
            "errors": 0,
            "started_at": None,
        }

    async def run_forever(self) -> None:
        """Run the worker indefinitely, processing pipeline stages."""
        self._running = True
        self._stats["started_at"] = datetime.now(UTC).isoformat()
        logger.info("Worker started (cycle interval: %ds)", self.cycle_interval)

        try:
            while self._running:
                await self._run_cycle()
                await asyncio.sleep(self.cycle_interval)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Worker shutting down...")
        finally:
            self._running = False
            await engine.dispose()

    async def _run_cycle(self) -> None:
        """Execute one full pipeline cycle."""
        self._stats["cycles_completed"] += 1
        cycle_start = datetime.now(UTC)
        logger.info("Starting pipeline cycle #%d", self._stats["cycles_completed"])

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    self._process_normalization(),
                    self._process_validation(),
                    self._process_enrichment(),
                    return_exceptions=True,
                ),
                timeout=JOB_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error("Pipeline cycle timed out after %d seconds", JOB_TIMEOUT)
            self._stats["errors"] += 1

        cycle_duration = (datetime.now(UTC) - cycle_start).total_seconds()
        logger.info("Pipeline cycle #%d completed in %.1fs", self._stats["cycles_completed"], cycle_duration)

    async def _process_normalization(self) -> None:
        """Process pending raw_candidates through normalization pipeline."""
        async with async_session_factory() as session:
            repo = PipelineRepository(session)
            pending_models = await repo.get_pending_candidates(limit=self.normalization_batch_size)

            if not pending_models:
                return

            # Convert SQLAlchemy models to Pydantic models
            pending = [_to_pydantic_candidate(m) for m in pending_models]
            logger.info("Normalizing %d raw candidates", len(pending))

            from src.apivault.pipeline.orchestrator import PipelineOrchestrator

            orchestrator = PipelineOrchestrator()
            result = await orchestrator.run(pending)

            if result.errors:
                for error in result.errors:
                    logger.error("Normalization error: %s", error)
                self._stats["errors"] += len(result.errors)

            processed_ids = [m.id for m in pending_models if m.id]
            status = "failed" if result.errors else "done"
            await repo.mark_candidates_processed(processed_ids, status=status)
            await session.commit()

            self._stats["candidates_processed"] += len(pending)
            logger.info(
                "Normalized %d candidates: %d new, %d merged",
                len(pending),
                len(result.new_records),
                len(result.merged_records),
            )

    async def _process_validation(self) -> None:
        """Validate APIs that are due for health checking."""
        async with async_session_factory() as session:
            repo = PipelineRepository(session)
            due_apis = await repo.get_apis_due_for_validation(limit=self.validation_concurrency)

            if not due_apis:
                return

            logger.info("Validating %d APIs", len(due_apis))

            from src.apivault.services.validation_service import probe_api_batch

            results = await probe_api_batch(due_apis, concurrency=self.validation_concurrency)

            validated = 0
            for api, health_data in zip(due_apis, results):
                if isinstance(health_data, Exception):
                    logger.error("Validation failed for API %s: %s", api.id, health_data)
                    self._stats["errors"] += 1
                    continue

                await repo.update_api_health(api.id, health_data)
                validated += 1

            await session.commit()
            self._stats["apis_validated"] += validated
            logger.info("Validated %d/%d APIs", validated, len(due_apis))

    async def _process_enrichment(self) -> None:
        """Enrich APIs that haven't been enriched yet."""
        async with async_session_factory() as session:
            repo = PipelineRepository(session)
            unenriched = await repo.get_unenriched_apis(limit=self.enrichment_batch_size)

            if not unenriched:
                return

            logger.info("Enriching %d APIs", len(unenriched))

            from src.apivault.services.enrichment_service import enrich_api

            enriched = 0
            for api in unenriched:
                try:
                    enrichment_data = await enrich_api(api)
                    await repo.update_api_enrichment(api.id, enrichment_data)
                    enriched += 1
                except Exception as e:
                    logger.error("Enrichment failed for API %s: %s", api.id, e)
                    self._stats["errors"] += 1

            await session.commit()
            self._stats["apis_enriched"] += enriched
            logger.info("Enriched %d/%d APIs", enriched, len(unenriched))

    def stop(self) -> None:
        """Signal the worker to stop after the current cycle."""
        self._running = False

    def get_stats(self) -> dict[str, Any]:
        """Get worker statistics."""
        return {**self._stats}


async def main() -> None:
    """Run the worker process."""
    logging.basicConfig(
        level=logging.INFO if not settings.debug else logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    worker = PipelineWorker()
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
