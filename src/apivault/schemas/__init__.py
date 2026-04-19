"""Pydantic schemas for API request/response validation."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: dict[str, Any] = {}


class ApiListItem(BaseModel):
    id: str
    slug: str | None = None
    name: str
    description_llm: str | None = None
    base_url: str | None = None
    docs_url: str | None = None
    auth_type: str
    signup_required: bool
    categories: list[str] = []
    tags: list[str] = []
    use_cases: list[str] = []
    free_tier: str | None = None
    rate_limit: str | None = None
    formats: list[str] = []
    health_score: int | None = None
    status: str
    last_checked: datetime | None = None
    discovered_at: datetime


class ApiListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    results: list[ApiListItem]


class ApiDetailResponse(BaseModel):
    id: str
    slug: str | None = None
    name: str
    description: str | None = None
    description_llm: str | None = None
    version: str | None = None
    base_url: str | None = None
    docs_url: str | None = None
    spec_url: str | None = None
    postman_url: str | None = None
    signup_url: str | None = None
    auth_type: str
    auth_notes: str | None = None
    signup_required: bool
    login_required: bool
    free_tier: str | None = None
    rate_limit: str | None = None
    categories: list[str] = []
    tags: list[str] = []
    use_cases: list[str] = []
    formats: list[str] = []
    protocols: list[str] = []
    data_formats: list[str] = []
    company: str | None = None
    company_url: str | None = None
    country: str | None = None
    language: str | None = None
    status: str
    health_score: int | None = None
    last_checked: datetime | None = None
    http_status: int | None = None
    response_time_ms: int | None = None
    ssl_valid: bool | None = None
    ssl_expiry: date | None = None
    source_names: list[str] = []
    discovered_at: datetime
    endpoints: list[dict[str, Any]] | None = None
    health_history: list[dict[str, Any]] | None = None


class SearchItem(BaseModel):
    id: str
    name: str
    description_llm: str | None = None
    similarity: float
    auth_type: str
    base_url: str | None = None
    categories: list[str] = []


class SearchResponse(BaseModel):
    query: str
    results: list[SearchItem]


class CategoryItem(BaseModel):
    category: str
    api_count: int
    no_auth_count: int = 0
    active_count: int = 0


class CategoryResponse(BaseModel):
    categories: list[CategoryItem]


class HealthResponse(BaseModel):
    status: str
    database: str = "ok"
    pipeline: str = "ok"
    version: str
    uptime_seconds: int


class HealthDegradedResponse(BaseModel):
    status: str
    database: str = "ok"
    pipeline: str = "ok"
    error: str


class ScraperStat(BaseModel):
    scraper: str
    last_run: datetime | None = None
    apis_contributed: int = 0
    status: str


class StatsResponse(BaseModel):
    total_apis: int
    active_apis: int
    dead_apis: int
    unknown_apis: int
    no_auth_apis: int
    apis_with_spec: int
    categories_count: int
    sources_count: int
    last_scraped: datetime | None = None
    last_validated: datetime | None = None
    db_size_mb: int = 0
    scraper_stats: list[ScraperStat] = []
