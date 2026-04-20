"""API browse routes."""

# ruff: noqa: B008 - Depends() is the standard FastAPI pattern

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apivault.database import get_db
from src.apivault.models.api import Api
from src.apivault.schemas import (
    ApiListItem,
    ApiListResponse,
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


@router.get("/apis", response_model=ApiListResponse)
async def list_apis(
    q: str | None = Query(None, description="Keyword search (full-text)"),
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
    """Browse APIs with filters, pagination, and sorting."""
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
