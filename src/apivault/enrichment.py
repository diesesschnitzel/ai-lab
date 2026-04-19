"""Enrichment worker — processes the enrichment queue in batches.

This worker runs as a background process, periodically checking for APIs
that need enrichment and processing them using LLM classification and
embedding generation.

Usage:
    python -m src.apivault.enrichment

Configuration via environment variables:
    LLM_PROVIDER: "ollama" | "openai" | "none"
    EMBEDDING_PROVIDER: "ollama" | "openai" | "none"
    ENRICHMENT_BATCH_SIZE: number of APIs per batch (default: 20)
    ENRICHMENT_POLL_INTERVAL: seconds between queue checks (default: 30)
"""

from __future__ import annotations

import asyncio
import logging
import signal
from datetime import UTC, datetime

from src.apivault.config import settings
from src.apivault.database import async_session_factory
from src.apivault.enrichment.repository import EnrichmentRepository
from src.apivault.services.enrichment_service import EnrichmentService

logger = logging.getLogger(__name__)


class EnrichmentWorker:
    """Background worker that processes the enrichment queue."""

    def __init__(self) -> None:
        self._running = False
        self._service: EnrichmentService | None = None
        self._processed_count = 0
        self._error_count = 0
        self._start_time: datetime | None = None

    async def start(self) -> None:
        """Start the enrichment worker loop."""
        self._running = True
        self._start_time = datetime.now(UTC)
        self._service = EnrichmentService()

        logger.info(
            "Enrichment worker started (LLM=%s, Embedding=%s, batch_size=%d)",
            settings.llm_provider,
            settings.embedding_provider,
            settings.enrichment_batch_size,
        )

        try:
            while self._running:
                await self._process_queue()
                await asyncio.sleep(settings.enrichment_poll_interval)
        except asyncio.CancelledError:
            logger.info("Enrichment worker cancelled")
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the enrichment worker."""
        self._running = False
        if self._service:
            await self._service.close()
            self._service = None
        logger.info(
            "Enrichment worker stopped (processed=%d, errors=%d)",
            self._processed_count,
            self._error_count,
        )

    async def _process_queue(self) -> None:
        """Process one batch from the enrichment queue."""
        async with async_session_factory() as session:
            repo = EnrichmentRepository(session)
            apis = await repo.get_enrichment_queue(
                batch_size=settings.enrichment_batch_size,
            )

        if not apis:
            return

        logger.info("Found %d APIs pending enrichment", len(apis))

        if not self._service:
            self._service = EnrichmentService()

        try:
            results = await self._service.enrich_batch(apis)
            self._processed_count += len(results)
            logger.info("Enriched %d APIs", len(results))
        except Exception:
            self._error_count += len(apis)
            logger.exception("Error processing enrichment batch")

    def get_stats(self) -> dict:
        """Get worker statistics."""
        uptime = None
        if self._start_time:
            uptime = int((datetime.now(UTC) - self._start_time).total_seconds())

        return {
            "running": self._running,
            "processed_total": self._processed_count,
            "errors_total": self._error_count,
            "uptime_seconds": uptime,
            "llm_provider": settings.llm_provider,
            "embedding_provider": settings.embedding_provider,
            "batch_size": settings.enrichment_batch_size,
        }


async def main() -> None:
    """Run the enrichment worker process."""
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    worker = EnrichmentWorker()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(worker.stop()))

    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
