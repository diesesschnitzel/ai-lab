"""Semantic search routes for API discovery."""

# ruff: noqa: B008 - Depends() is the standard FastAPI pattern

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.apivault.database import get_db
from src.apivault.schemas import SearchItem, SearchResponse

try:
    from src.apivault.services.enrichment_service import get_embedding
except ImportError:
    get_embedding = None  # type: ignore[misc,assignment]

router = APIRouter()

VALID_AUTH_TYPES = {"none", "apikey", "oauth2", "basic", "bearer", "unknown"}


@router.get("/apis/search", response_model=SearchResponse)
async def search_apis(
    ask: str = Query(..., description="Required. Natural language query"),
    auth: str | None = Query(None, description="Optional filter by auth type"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    min_similarity: float = Query(0.5, ge=0, le=1, description="Min cosine similarity"),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Semantic / natural language search. Finds APIs by meaning, not keywords."""
    if auth and auth not in VALID_AUTH_TYPES:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_parameter", "message": f"Invalid auth type: {auth}"},
        )

    if get_embedding is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "search_unavailable",
                "message": "Semantic search is not available (embedding service not implemented)",
            },
        )

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

    params: dict[str, object] = {
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
