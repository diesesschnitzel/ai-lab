"""API utility routes: health, stats, categories."""

# ruff: noqa: B008 - Depends() is the standard FastAPI pattern

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.apivault.database import get_db
from src.apivault.models.api import Api
from src.apivault.models.scraper_run import ScraperRun
from src.apivault.schemas import (
    CategoryItem,
    CategoryResponse,
    HealthDegradedResponse,
    HealthResponse,
    ScraperStat,
    StatsResponse,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    db_ok = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = "error"

    start_time = datetime.now(UTC)
    uptime = int((start_time - datetime(2026, 4, 15, tzinfo=UTC)).total_seconds())

    status = "ok" if db_ok == "ok" else "degraded"

    if status == "degraded":
        raise HTTPException(
            status_code=503,
            detail=HealthDegradedResponse(
                status="degraded",
                database=db_ok,
                pipeline="unknown",
                error="Database connection failed",
            ).model_dump(),
        )

    return HealthResponse(
        status=status,
        database=db_ok,
        pipeline="ok",
        version="1.0.0",
        uptime_seconds=uptime if uptime > 0 else 0,
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)) -> StatsResponse:
    total_result = await db.execute(select(func.count(Api.id)))
    total_apis = total_result.scalar() or 0

    active_result = await db.execute(select(func.count(Api.id)).where(Api.status == "active"))
    active_apis = active_result.scalar() or 0

    dead_result = await db.execute(select(func.count(Api.id)).where(Api.status == "dead"))
    dead_apis = dead_result.scalar() or 0

    unknown_result = await db.execute(select(func.count(Api.id)).where(Api.status == "unknown"))
    unknown_apis = unknown_result.scalar() or 0

    no_auth_result = await db.execute(select(func.count(Api.id)).where(Api.auth_type == "none"))
    no_auth_apis = no_auth_result.scalar() or 0

    with_spec_result = await db.execute(select(func.count(Api.id)).where(Api.spec_url.isnot(None)))
    apis_with_spec = with_spec_result.scalar() or 0

    categories_result = await db.execute(select(func.count(func.unnest(Api.categories))).distinct())
    categories_count = categories_result.scalar() or 0

    sources_result = await db.execute(select(func.count(func.unnest(Api.source_names))).distinct())
    sources_count = sources_result.scalar() or 0

    last_validated_result = await db.execute(select(func.max(Api.last_checked)).where(Api.last_checked.isnot(None)))
    last_validated = last_validated_result.scalar()

    last_scraped_result = await db.execute(
        select(func.max(ScraperRun.started_at)).where(ScraperRun.finished_at.isnot(None))
    )
    last_scraped = last_scraped_result.scalar()

    db_size_result = await db.execute(
        text("""
        SELECT pg_database_size(current_database()) / (1024 * 1024) AS size_mb
    """)
    )
    db_size_mb = db_size_result.scalar() or 0

    scraper_runs_result = await db.execute(
        select(
            ScraperRun.scraper_name,
            func.max(ScraperRun.finished_at).label("last_run"),
            func.coalesce(func.sum(ScraperRun.candidates_new), 0).label("apis_contributed"),
            func.max(ScraperRun.status).label("status"),
        )
        .where(ScraperRun.finished_at.isnot(None))
        .group_by(ScraperRun.scraper_name)
        .order_by(func.max(ScraperRun.finished_at).desc())
    )
    scraper_stats = [
        ScraperStat(
            scraper=row[0],
            last_run=row[1],
            apis_contributed=row[2],
            status=row[3],
        )
        for row in scraper_runs_result.all()
    ]

    return StatsResponse(
        total_apis=total_apis,
        active_apis=active_apis,
        dead_apis=dead_apis,
        unknown_apis=unknown_apis,
        no_auth_apis=no_auth_apis,
        apis_with_spec=apis_with_spec,
        categories_count=categories_count,
        sources_count=sources_count,
        last_scraped=last_scraped,
        last_validated=last_validated,
        db_size_mb=db_size_mb,
        scraper_stats=scraper_stats,
    )


@router.get("/categories", response_model=CategoryResponse)
async def get_categories(
    auth: str | None = Query(None, description="Filter counts to APIs with this auth type"),
    min_count: int = Query(1, ge=0, description="Minimum API count to include"),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    query = select(
        func.unnest(Api.categories).label("category"),
        func.count(Api.id).label("api_count"),
        func.count(Api.id).filter(Api.auth_type == "none").label("no_auth_count"),
        func.count(Api.id).filter(Api.status == "active").label("active_count"),
    ).group_by(text("category"))

    if auth:
        query = query.where(Api.auth_type == auth)

    result = await db.execute(query)
    rows = result.all()

    categories = [
        CategoryItem(
            category=row[0],
            api_count=row[1],
            no_auth_count=row[2],
            active_count=row[3],
        )
        for row in rows
        if row[1] >= min_count
    ]

    categories.sort(key=lambda c: c.api_count, reverse=True)

    return CategoryResponse(categories=categories)
