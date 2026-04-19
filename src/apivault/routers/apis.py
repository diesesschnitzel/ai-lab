"""API browse and search routes."""

# ruff: noqa: B008 - Depends() is the standard FastAPI pattern

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.apivault.database import get_db
from src.apivault.models.api import Api
from src.apivault.models.api_endpoint import ApiEndpoint
from src.apivault.models.api_health_log import ApiHealthLog
from src.apivault.models.scraper_run import ScraperRun
from src.apivault.schemas import (
    ApiDetailResponse,
    ApiListItem,
    ApiListResponse,
    CategoryItem,
    CategoryResponse,
    HealthDegradedResponse,
    HealthResponse,
    ScraperStat,
    SearchItem,
    SearchResponse,
    StatsResponse,
)

router = APIRouter()

VALID_AUTH_TYPES = {"none", "apikey", "oauth2", "basic", "bearer", "unknown"}
VALID_STATUSES = {"active", "dead", "all"}
VALID_FORMATS = {"REST", "GraphQL", "SOAP", "gRPC"}
VALID_SORT_FIELDS = {"relevance", "health_score", "discovered_at", "name"}
VALID_ORDERS = {"asc", "desc"}


def _api_to_list_item(api: Api) -> ApiListItem:
    return ApiListItem(
        id=api.id,
        slug=api.slug,
        name=api.name,
        description_llm=api.description_llm,
        base_url=api.base_url,
        docs_url=api.docs_url,
        auth_type=api.auth_type,
        signup_required=api.signup_required,
        categories=api.categories or [],
        tags=api.tags or [],
        use_cases=api.use_cases or [],
        free_tier=api.free_tier,
        rate_limit=api.rate_limit,
        formats=api.formats or [],
        health_score=api.health_score,
        status=api.status,
        last_checked=api.last_checked,
        discovered_at=api.discovered_at,
    )


def _api_to_detail_response(
    api: Api,
    endpoints: list[ApiEndpoint] | None = None,
    health_history: list[ApiHealthLog] | None = None,
) -> ApiDetailResponse:
    return ApiDetailResponse(
        id=api.id,
        slug=api.slug,
        name=api.name,
        description=api.description,
        description_llm=api.description_llm,
        version=api.version,
        base_url=api.base_url,
        docs_url=api.docs_url,
        spec_url=api.spec_url,
        postman_url=api.postman_url,
        signup_url=api.signup_url,
        auth_type=api.auth_type,
        auth_notes=api.auth_notes,
        signup_required=api.signup_required,
        login_required=api.login_required,
        free_tier=api.free_tier,
        rate_limit=api.rate_limit,
        categories=api.categories or [],
        tags=api.tags or [],
        use_cases=api.use_cases or [],
        formats=api.formats or [],
        protocols=api.protocols or [],
        data_formats=api.data_formats or [],
        company=api.company,
        company_url=api.company_url,
        country=api.country,
        language=api.language,
        status=api.status,
        health_score=api.health_score,
        last_checked=api.last_checked,
        http_status=api.http_status,
        response_time_ms=api.response_time_ms,
        ssl_valid=api.ssl_valid,
        ssl_expiry=api.ssl_expiry,
        source_names=api.source_names or [],
        discovered_at=api.discovered_at,
        endpoints=[
            {
                "id": ep.id,
                "method": ep.method,
                "path": ep.path,
                "summary": ep.summary,
                "description": ep.description,
                "tags": ep.tags or [],
                "deprecated": ep.deprecated,
            }
            for ep in (endpoints or [])
        ]
        if endpoints is not None
        else None,
        health_history=[
            {
                "id": log.id,
                "checked_at": log.checked_at,
                "status": log.status,
                "http_status": log.http_status,
                "response_time_ms": log.response_time_ms,
                "dns_resolves": log.dns_resolves,
                "ssl_valid": log.ssl_valid,
                "error": log.error,
            }
            for log in (health_history or [])
        ]
        if health_history is not None
        else None,
    )


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """System health check for monitoring/load balancers."""
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
    """Database-wide statistics."""
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
    """List all categories with API counts."""
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


@router.get("/apis", response_model=ApiListResponse)
async def list_apis(
    q: str | None = Query(None, description="Keyword search (full-text)"),
    ask: str | None = Query(None, description="Semantic / natural language search"),
    category: str | None = Query(None, description="Filter by category"),
    tag: str | None = Query(None, description="Filter by tag"),
    auth: str | None = Query(None, description="Filter by auth_type"),
    status: str = Query("active", description="Filter by status"),
    format: str | None = Query(None, description="Filter by format"),
    country: str | None = Query(None, description="Filter by country code"),
    has_spec: bool | None = Query(None, description="Filter to APIs with OpenAPI spec"),
    min_health: int = Query(50, ge=0, le=100, description="Minimum health score"),
    sort: str = Query("relevance", description="Sort field"),
    order: str = Query("desc", description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Results per page"),
    db: AsyncSession = Depends(get_db),
) -> ApiListResponse:
    """Search and browse APIs with filters."""
    if auth and auth not in VALID_AUTH_TYPES:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_parameter", "message": f"Invalid auth type: {auth}"},
        )

    if status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_parameter", "message": f"Invalid status: {status}"},
        )

    if format and format not in VALID_FORMATS:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_parameter", "message": f"Invalid format: {format}"},
        )

    if sort not in VALID_SORT_FIELDS:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_parameter", "message": f"Invalid sort field: {sort}"},
        )

    if order not in VALID_ORDERS:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_parameter", "message": f"Invalid order: {order}"},
        )

    query = select(Api)

    if status != "all":
        query = query.where(Api.status == status)

    if auth:
        query = query.where(Api.auth_type == auth)

    if category:
        query = query.where(Api.categories.contains([category]))

    if tag:
        query = query.where(Api.tags.contains([tag]))

    if format:
        query = query.where(Api.formats.contains([format]))

    if country:
        query = query.where(Api.country == country.upper())

    if has_spec is not None:
        query = query.where(Api.spec_url.isnot(None) if has_spec else Api.spec_url.is_(None))

    if min_health:
        query = query.where(Api.health_score >= min_health)

    if q:
        query = query.where(Api.fts.op("@@")(func.websearch_to_tsquery("english", q)))

    if sort == "health_score":
        query = query.order_by(Api.health_score.desc() if order == "desc" else Api.health_score.asc())
    elif sort == "discovered_at":
        query = query.order_by(Api.discovered_at.desc() if order == "desc" else Api.discovered_at.asc())
    elif sort == "name":
        query = query.order_by(Api.name.desc() if order == "desc" else Api.name.asc())
    else:
        query = query.order_by(Api.health_score.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    apis = result.scalars().all()

    return ApiListResponse(
        total=total,
        page=page,
        per_page=per_page,
        results=[_api_to_list_item(api) for api in apis],
    )


@router.get("/apis/search", response_model=SearchResponse)
async def search_apis(
    ask: str = Query(..., description="Required. Natural language query"),
    auth: str | None = Query(None, description="Optional filter by auth type"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    min_similarity: float = Query(0.5, ge=0, le=1, description="Min cosine similarity"),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Semantic / natural language search using embeddings."""
    try:
        from src.apivault.enrichment import get_embedding
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "search_unavailable",
                "message": "Semantic search is not available (embedding service not implemented)",
            },
        ) from e

    try:
        query_embedding = await get_embedding(ask)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "search_unavailable",
                "message": "Semantic search is not available (embedding service unavailable)",
            },
        ) from e

    if query_embedding is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "search_unavailable",
                "message": "Semantic search is not available (no embeddings yet)",
            },
        )

    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    auth_filter = "AND auth_type = :auth " if auth else ""
    similarity_query = text(f"""
        SELECT
            id, name, description_llm, auth_type, base_url, categories,
            1 - (embedding <=> :embedding) AS similarity
        FROM apis
        WHERE embedding IS NOT NULL
          AND status = 'active'
          AND 1 - (embedding <=> :embedding) >= :min_similarity
          {auth_filter}
        ORDER BY embedding <=> :embedding
        LIMIT :limit
    """)

    params: dict = {
        "embedding": embedding_str,
        "min_similarity": min_similarity,
        "limit": limit,
    }
    if auth:
        params["auth"] = auth

    result = await db.execute(similarity_query, params)
    rows = result.all()

    results = [
        SearchItem(
            id=row[0],
            name=row[1],
            description_llm=row[2],
            similarity=round(row[6], 4),
            auth_type=row[3],
            base_url=row[4],
            categories=row[5] or [],
        )
        for row in rows
    ]

    return SearchResponse(query=ask, results=results)


@router.get("/apis/{api_id}", response_model=ApiDetailResponse)
async def get_api_detail(
    api_id: str,
    include_endpoints: bool = Query(False, description="Include api_endpoints"),
    include_health_history: bool = Query(False, description="Include last 30 health_log entries"),
    db: AsyncSession = Depends(get_db),
) -> ApiDetailResponse:
    """Get full details for a single API by ID or slug."""
    api = None

    try:
        query = select(Api).where(Api.id == api_id)
        result = await db.execute(query)
        api = result.scalar_one_or_none()
    except Exception:
        pass

    if api is None:
        query = select(Api).where(Api.slug == api_id)
        result = await db.execute(query)
        api = result.scalar_one_or_none()

    if api is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": f"API with id or slug '{api_id}' not found",
            },
        )

    endpoints = None
    if include_endpoints:
        ep_query = (
            select(ApiEndpoint)
            .where(ApiEndpoint.api_id == api.id)
            .where(not ApiEndpoint.deprecated)
            .order_by(ApiEndpoint.method, ApiEndpoint.path)
        )
        ep_result = await db.execute(ep_query)
        endpoints = ep_result.scalars().all()

    health_history = None
    if include_health_history:
        hh_query = (
            select(ApiHealthLog).where(ApiHealthLog.api_id == api.id).order_by(ApiHealthLog.checked_at.desc()).limit(30)
        )
        hh_result = await db.execute(hh_query)
        health_history = hh_result.scalars().all()

    return _api_to_detail_response(api, endpoints=endpoints, health_history=health_history)
