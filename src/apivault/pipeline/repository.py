"""Database repository for pipeline operations."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.apivault.models.api import Api
from src.apivault.models.raw_candidate import RawCandidate
from src.apivault.models.scraper_run import ScraperRun

logger = logging.getLogger(__name__)


class PipelineRepository:
    """Database operations for the data pipeline."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_pending_candidates(self, limit: int = 500) -> list[RawCandidate]:
        """Fetch pending raw candidates for normalization."""
        result = await self._session.execute(
            select(RawCandidate)
            .where(RawCandidate.status == "pending")
            .order_by(RawCandidate.discovered_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_candidates_processed(self, ids: list[str], status: str = "done") -> None:
        """Mark raw candidates as processed."""
        if not ids:
            return
        await self._session.execute(
            update(RawCandidate)
            .where(RawCandidate.id.in_(ids))
            .values(
                status=status,
                processed_at=datetime.now(UTC),
            )
        )

    async def mark_candidate_failed(self, candidate_id: str, error: str) -> None:
        """Mark a raw candidate as failed with an error message."""
        await self._session.execute(
            update(RawCandidate)
            .where(RawCandidate.id == candidate_id)
            .values(
                status="failed",
                error=error,
                processed_at=datetime.now(UTC),
            )
        )

    async def get_apis_due_for_validation(self, limit: int = 50) -> list[Api]:
        """Fetch APIs that need validation (pending or overdue)."""
        seven_days_ago = datetime.now(UTC) - timedelta(days=7)
        result = await self._session.execute(
            select(Api)
            .where(
                (Api.status == "pending_validation") | ((Api.status != "dead") & (Api.last_checked < seven_days_ago))
            )
            .order_by(Api.last_checked.asc().nullsfirst())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_unenriched_apis(self, limit: int = 20) -> list[Api]:
        """Fetch APIs that need enrichment."""
        result = await self._session.execute(
            select(Api)
            .where(
                Api.enriched_at.is_(None),
                Api.status != "dead",
            )
            .order_by(Api.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_dead_apis(self, limit: int = 100) -> list[Api]:
        """Fetch dead APIs for retry validation."""
        result = await self._session.execute(
            select(Api).where(Api.status == "dead").order_by(Api.last_checked.asc().nullsfirst()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_pending_count(self) -> int:
        """Count pending raw candidates."""
        from sqlalchemy import func

        result = await self._session.execute(
            select(func.count(RawCandidate.id)).where(RawCandidate.status == "pending")
        )
        return result.scalar() or 0

    async def get_validation_pending_count(self) -> int:
        """Count APIs pending validation."""
        from sqlalchemy import func

        seven_days_ago = datetime.now(UTC) - timedelta(days=7)
        result = await self._session.execute(
            select(func.count(Api.id)).where(
                (Api.status == "pending_validation") | ((Api.status != "dead") & (Api.last_checked < seven_days_ago))
            )
        )
        return result.scalar() or 0

    async def get_enrichment_pending_count(self) -> int:
        """Count APIs pending enrichment."""
        from sqlalchemy import func

        result = await self._session.execute(
            select(func.count(Api.id)).where(
                Api.enriched_at.is_(None),
                Api.status != "dead",
            )
        )
        return result.scalar() or 0

    async def create_scraper_run(self, scraper_name: str, config: dict[str, Any] | None = None) -> ScraperRun:
        """Create a new scraper run record."""
        run = ScraperRun(
            scraper_name=scraper_name,
            config_snapshot=config,
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def complete_scraper_run(
        self,
        run_id: str,
        status: str = "completed",
        candidates_found: int = 0,
        candidates_new: int = 0,
        candidates_updated: int = 0,
        error: str | None = None,
    ) -> None:
        """Mark a scraper run as completed or failed."""
        await self._session.execute(
            update(ScraperRun)
            .where(ScraperRun.id == run_id)
            .values(
                status=status,
                finished_at=datetime.now(UTC),
                candidates_found=candidates_found,
                candidates_new=candidates_new,
                candidates_updated=candidates_updated,
                error=error,
            )
        )

    async def update_api_health(
        self,
        api_id: str,
        health_data: dict[str, Any],
    ) -> None:
        """Update an API's health status after validation."""
        await self._session.execute(
            update(Api)
            .where(Api.id == api_id)
            .values(
                **health_data,
                last_checked=datetime.now(UTC),
            )
        )

    async def update_api_enrichment(
        self,
        api_id: str,
        enrichment_data: dict[str, Any],
    ) -> None:
        """Update an API after enrichment."""
        await self._session.execute(
            update(Api)
            .where(Api.id == api_id)
            .values(
                **enrichment_data,
                enriched_at=datetime.now(UTC),
            )
        )
