"""API detail routes."""

# ruff: noqa: B008 - Depends() is the standard FastAPI pattern

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apivault.database import get_db
from src.apivault.models.api import Api
from src.apivault.models.api_endpoint import ApiEndpoint
from src.apivault.models.api_health_log import ApiHealthLog
from src.apivault.schemas import ApiDetailResponse

router = APIRouter()


def _api_to_detail_response(
    api: Api,
    endpoints: list[ApiEndpoint] | None = None,
    health_history: list[ApiHealthLog] | None = None,
) -> ApiDetailResponse:
    """Convert an Api model to an ApiDetailResponse schema."""
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
            for ep in endpoints
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
            for log in health_history
        ]
        if health_history is not None
        else None,
    )


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

    endpoints: list[ApiEndpoint] | None = None
    if include_endpoints:
        ep_query = (
            select(ApiEndpoint)
            .where(ApiEndpoint.api_id == api.id)
            .where(ApiEndpoint.deprecated.is_(False))
            .order_by(ApiEndpoint.method, ApiEndpoint.path)
        )
        ep_result = await db.execute(ep_query)
        endpoints = list(ep_result.scalars().all())

    health_history: list[ApiHealthLog] | None = None
    if include_health_history:
        hh_query = (
            select(ApiHealthLog).where(ApiHealthLog.api_id == api.id).order_by(ApiHealthLog.checked_at.desc()).limit(30)
        )
        hh_result = await db.execute(hh_query)
        health_history = list(hh_result.scalars().all())

    return _api_to_detail_response(api, endpoints=endpoints, health_history=health_history)
