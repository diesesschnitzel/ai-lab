"""Tests for browse and detail routers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from src.apivault.database import get_db
from src.apivault.models.api import Api
from src.apivault.models.api_endpoint import ApiEndpoint
from src.apivault.models.api_health_log import ApiHealthLog
from src.apivault.routers.browse import router as browse_router
from src.apivault.routers.detail import router as detail_router


def _build_app(mock_session: AsyncMock) -> FastAPI:
    app = FastAPI()
    app.include_router(browse_router)
    app.include_router(detail_router)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    return app


def _make_api(**overrides: object) -> Api:
    defaults = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "slug": "test-api",
        "name": "Test API",
        "description": "A test API",
        "description_llm": "LLM description",
        "version": "v1",
        "base_url": "https://api.test.com",
        "docs_url": "https://docs.test.com",
        "spec_url": None,
        "postman_url": None,
        "signup_url": None,
        "auth_type": "none",
        "auth_notes": None,
        "signup_required": False,
        "login_required": False,
        "free_tier": "Free",
        "rate_limit": None,
        "categories": ["Developer Tools"],
        "tags": ["test"],
        "use_cases": ["Testing"],
        "formats": ["REST"],
        "protocols": ["HTTPS"],
        "data_formats": ["JSON"],
        "company": "Test Corp",
        "company_url": "https://test.com",
        "country": "US",
        "language": "en",
        "status": "active",
        "health_score": 90,
        "last_checked": datetime(2026, 4, 15, tzinfo=UTC),
        "http_status": 200,
        "response_time_ms": 100,
        "ssl_valid": True,
        "ssl_expiry": None,
        "source_names": ["test_source"],
        "discovered_at": datetime(2026, 1, 1, tzinfo=UTC),
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Api(**defaults)  # type: ignore[arg-type]


def _make_endpoint(**overrides: object) -> ApiEndpoint:
    defaults = {
        "id": "ep-001",
        "api_id": "550e8400-e29b-41d4-a716-446655440000",
        "method": "GET",
        "path": "/users",
        "summary": "List users",
        "description": None,
        "tags": [],
        "parameters": None,
        "request_body": None,
        "responses": None,
        "auth_required": False,
        "example_request": None,
        "example_response": None,
        "deprecated": False,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return ApiEndpoint(**defaults)  # type: ignore[arg-type]


def _make_health_log(**overrides: object) -> ApiHealthLog:
    defaults = {
        "id": "log-001",
        "api_id": "550e8400-e29b-41d4-a716-446655440000",
        "checked_at": datetime(2026, 4, 15, tzinfo=UTC),
        "status": "ok",
        "http_status": 200,
        "response_time_ms": 100,
        "dns_resolves": True,
        "ssl_valid": True,
        "auth_type_detected": "none",
        "rate_limit_detected": None,
        "error": None,
        "checker_version": "1.0",
    }
    defaults.update(overrides)
    return ApiHealthLog(**defaults)  # type: ignore[arg-type]


class MockScalarResult:
    def __init__(self, data: object) -> None:
        self._data = data

    def scalar(self) -> object:
        return self._data

    def scalar_one_or_none(self) -> object:
        return self._data

    def scalars(self) -> MagicMock:
        mock = MagicMock()
        mock.all.return_value = self._data if isinstance(self._data, list) else []
        return mock

    def all(self) -> list:
        return self._data if isinstance(self._data, list) else []


class TestListApis:
    @pytest.mark.asyncio
    async def test_list_apis_returns_paginated_results(self) -> None:
        api = _make_api()
        mock_session = AsyncMock(spec=AsyncSession)
        count_result = MockScalarResult(1)
        list_result = MockScalarResult([api])
        mock_session.execute = AsyncMock(side_effect=[count_result, list_result])

        app = _build_app(mock_session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/apis")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["per_page"] == 20
        assert len(data["results"]) == 1
        assert data["results"][0]["name"] == "Test API"

    @pytest.mark.asyncio
    async def test_list_apis_filters_by_status(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        count_result = MockScalarResult(0)
        list_result = MockScalarResult([])
        mock_session.execute = AsyncMock(side_effect=[count_result, list_result])

        app = _build_app(mock_session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/apis", params={"status": "dead"})

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_apis_rejects_invalid_auth_type(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        app = _build_app(mock_session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/apis", params={"auth": "invalid"})

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "invalid_parameter"

    @pytest.mark.asyncio
    async def test_list_apis_rejects_invalid_status(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        app = _build_app(mock_session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/apis", params={"status": "invalid"})

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_list_apis_rejects_invalid_sort(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        app = _build_app(mock_session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/apis", params={"sort": "invalid"})

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_list_apis_rejects_invalid_order(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        app = _build_app(mock_session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/apis", params={"order": "invalid"})

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_list_apis_rejects_invalid_format(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        app = _build_app(mock_session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/apis", params={"format": "XML"})

        assert response.status_code == 400


class TestGetApiDetail:
    @pytest.mark.asyncio
    async def test_get_detail_by_id(self) -> None:
        api = _make_api()
        mock_session = AsyncMock(spec=AsyncSession)
        id_result = MockScalarResult(api)
        mock_session.execute = AsyncMock(side_effect=[id_result])

        app = _build_app(mock_session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/apis/550e8400-e29b-41d4-a716-446655440000")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test API"
        assert data["slug"] == "test-api"

    @pytest.mark.asyncio
    async def test_get_detail_by_slug(self) -> None:
        api = _make_api()
        mock_session = AsyncMock(spec=AsyncSession)
        id_result = MockScalarResult(None)
        slug_result = MockScalarResult(api)
        mock_session.execute = AsyncMock(side_effect=[id_result, slug_result])

        app = _build_app(mock_session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/apis/test-api")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test API"

    @pytest.mark.asyncio
    async def test_get_detail_not_found(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute = AsyncMock(return_value=MockScalarResult(None))

        app = _build_app(mock_session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/apis/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_detail_with_endpoints(self) -> None:
        api = _make_api()
        endpoint = _make_endpoint()
        mock_session = AsyncMock(spec=AsyncSession)
        id_result = MockScalarResult(api)
        ep_result = MockScalarResult([endpoint])
        mock_session.execute = AsyncMock(side_effect=[id_result, ep_result])

        app = _build_app(mock_session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/apis/550e8400-e29b-41d4-a716-446655440000",
                params={"include_endpoints": "true"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["endpoints"] is not None
        assert len(data["endpoints"]) == 1
        assert data["endpoints"][0]["method"] == "GET"
        assert data["endpoints"][0]["path"] == "/users"

    @pytest.mark.asyncio
    async def test_get_detail_with_health_history(self) -> None:
        api = _make_api()
        log = _make_health_log()
        mock_session = AsyncMock(spec=AsyncSession)
        id_result = MockScalarResult(api)
        hh_result = MockScalarResult([log])
        mock_session.execute = AsyncMock(side_effect=[id_result, hh_result])

        app = _build_app(mock_session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/apis/550e8400-e29b-41d4-a716-446655440000",
                params={"include_health_history": "true"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["health_history"] is not None
        assert len(data["health_history"]) == 1
        assert data["health_history"][0]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_get_detail_without_optional_data(self) -> None:
        api = _make_api()
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute = AsyncMock(return_value=MockScalarResult(api))

        app = _build_app(mock_session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/apis/550e8400-e29b-41d4-a716-446655440000")

        assert response.status_code == 200
        data = response.json()
        assert data["endpoints"] is None
        assert data["health_history"] is None
