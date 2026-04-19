"""Repository for enrichment queue management and database updates."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.apivault.models.api import Api

logger = logging.getLogger(__name__)


class EnrichmentRepository:
    """Database operations for the enrichment pipeline."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_enrichment_queue(
        self,
        batch_size: int = 20,
        status: str | None = None,
    ) -> list[Api]:
        """Get APIs pending enrichment, ordered by priority.

        Priority:
        1. Active APIs with descriptions (best enrichment candidates)
        2. Active APIs without descriptions
        3. Unknown status APIs
        """
        base_query = select(Api).where(Api.enriched_at.is_(None)).where(Api.status != "dead")

        if status:
            base_query = base_query.where(Api.status == status)

        # Priority ordering via separate queries
        queries = [
            base_query.where(Api.status == "active").where(Api.description.isnot(None)),
            base_query.where(Api.status == "active").where(Api.description.is_(None)),
            base_query.where(Api.status == "unknown"),
        ]

        apis: list[Api] = []
        for query in queries:
            remaining = batch_size - len(apis)
            if remaining <= 0:
                break
            result = await self.session.execute(query.limit(remaining))
            apis.extend(result.scalars().all())

        return apis

    async def get_apis_needing_reenrichment(
        self,
        batch_size: int = 20,
        description_change_threshold: float = 0.3,
    ) -> list[Api]:
        """Get APIs that need re-enrichment due to significant changes."""
        query = (
            select(Api)
            .where(Api.enriched_at.isnot(None))
            .where(Api.status == "active")
            .where(Api.description.isnot(None))
            .where(Api.description_llm.isnot(None))
            .order_by(Api.updated_at.desc())
            .limit(batch_size)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_enrichment(
        self,
        api_id: str,
        enrichment_data: dict[str, Any],
        embedding: list[float] | None = None,
        embedding_model: str | None = None,
    ) -> None:
        """Update an API record with enrichment results."""
        update_values: dict[str, Any] = {
            "enriched_at": datetime.now(UTC),
        }

        if enrichment_data.get("categories"):
            update_values["categories"] = enrichment_data["categories"]
        if enrichment_data.get("tags"):
            update_values["tags"] = enrichment_data["tags"]
        if enrichment_data.get("use_cases"):
            update_values["use_cases"] = enrichment_data["use_cases"]
        if enrichment_data.get("description_llm"):
            update_values["description_llm"] = enrichment_data["description_llm"]
        if enrichment_data.get("company"):
            update_values["company"] = enrichment_data["company"]
        if embedding is not None:
            update_values["embedding"] = embedding
        if embedding_model:
            update_values["embedding_model"] = embedding_model

        stmt = update(Api).where(Api.id == api_id).values(**update_values)
        await self.session.execute(stmt)
        await self.session.flush()

        logger.info("Updated enrichment for API %s", api_id)

    async def trigger_reenrichment(self, api_id: str) -> bool:
        """Reset enriched_at to trigger re-enrichment for a specific API."""
        stmt = update(Api).where(Api.id == api_id).values(enriched_at=None)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def trigger_bulk_reenrichment(
        self,
        status: str | None = None,
        category: str | None = None,
    ) -> int:
        """Reset enriched_at for bulk re-enrichment."""
        stmt = update(Api).values(enriched_at=None)
        conditions = [Api.status != "dead"]

        if status:
            conditions.append(Api.status == status)
        if category:
            conditions.append(Api.categories.contains([category]))

        for condition in conditions:
            stmt = stmt.where(condition)

        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def get_queue_size(self) -> dict[str, int]:
        """Get current enrichment queue sizes by priority."""
        base = select(Api).where(Api.enriched_at.is_(None)).where(Api.status != "dead")

        active_with_desc = await self.session.execute(
            base.where(Api.status == "active").where(Api.description.isnot(None))
        )
        active_no_desc = await self.session.execute(base.where(Api.status == "active").where(Api.description.is_(None)))
        unknown = await self.session.execute(base.where(Api.status == "unknown"))
        enriched = await self.session.execute(select(Api).where(Api.enriched_at.isnot(None)))

        return {
            "pending_active_with_desc": len(active_with_desc.scalars().all()),
            "pending_active_no_desc": len(active_no_desc.scalars().all()),
            "pending_unknown": len(unknown.scalars().all()),
            "enriched": len(enriched.scalars().all()),
        }

    async def get_embedding_stats(self) -> dict[str, Any]:
        """Get statistics about embedding coverage."""
        total_result = await self.session.execute(select(Api))
        total = len(total_result.scalars().all())

        with_embedding_result = await self.session.execute(select(Api).where(Api.embedding.isnot(None)))
        with_embedding = len(with_embedding_result.scalars().all())

        models_result = await self.session.execute(
            select(Api.embedding_model, text("COUNT(*)"))
            .where(Api.embedding_model.isnot(None))
            .group_by(Api.embedding_model)
        )
        by_model = {row[0]: row[1] for row in models_result.all()}

        return {
            "total_apis": total,
            "with_embeddings": with_embedding,
            "coverage_pct": round(with_embedding / total * 100, 1) if total > 0 else 0,
            "by_model": by_model,
        }
