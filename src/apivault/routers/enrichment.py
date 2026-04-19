"""Enrichment admin routes for managing the enrichment pipeline."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.apivault.database import get_db
from src.apivault.enrichment.repository import EnrichmentRepository

router = APIRouter(prefix="/enrichment", tags=["enrichment"])


@router.get("/queue")
async def get_enrichment_queue_status(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get current enrichment queue sizes by priority."""
    repo = EnrichmentRepository(db)
    return await repo.get_queue_size()


@router.get("/stats")
async def get_enrichment_stats(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get enrichment and embedding statistics."""
    repo = EnrichmentRepository(db)
    queue = await repo.get_queue_size()
    embeddings = await repo.get_embedding_stats()
    return {
        "queue": queue,
        "embeddings": embeddings,
    }


@router.post("/trigger/{api_id}")
async def trigger_reenrichment(
    api_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger re-enrichment for a specific API."""
    repo = EnrichmentRepository(db)
    success = await repo.trigger_reenrichment(api_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": f"API {api_id} not found"},
        )
    return {"message": f"Re-enrichment triggered for API {api_id}"}


@router.post("/trigger-bulk")
async def trigger_bulk_reenrichment(
    status: str | None = Query(None, description="Filter by status"),
    category: str | None = Query(None, description="Filter by category"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger bulk re-enrichment for matching APIs."""
    repo = EnrichmentRepository(db)
    count = await repo.trigger_bulk_reenrichment(status=status, category=category)
    return {"message": f"Re-enrichment triggered for {count} APIs", "count": count}


@router.post("/process")
async def process_enrichment_queue(
    batch_size: int = Query(20, ge=1, le=100, description="Number of APIs to process"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Manually trigger enrichment processing for the next batch."""
    from src.apivault.services.enrichment_service import EnrichmentService

    repo = EnrichmentRepository(db)
    apis = await repo.get_enrichment_queue(batch_size=batch_size)

    if not apis:
        return {"message": "No APIs pending enrichment", "processed": 0}

    service = EnrichmentService()
    try:
        results = await service.enrich_batch(apis)
        return {
            "message": f"Enriched {len(results)} APIs",
            "processed": len(results),
        }
    finally:
        await service.close()
