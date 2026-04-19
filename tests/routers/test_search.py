"""Tests for the semantic search endpoint."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from src.apivault.main import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


class TestSearchValidation:
    def test_missing_ask_parameter(self, client):
        response = client.get("/apis/search")
        assert response.status_code == 422

    def test_valid_auth_types_accepted(self, client):
        for auth in ["none", "apikey", "oauth2", "basic", "bearer", "unknown"]:
            with patch("src.apivault.routers.search.get_embedding", return_value=None):
                response = client.get("/apis/search", params={"ask": "test", "auth": auth})
                assert response.status_code == 503

    def test_limit_too_low(self, client):
        with patch("src.apivault.routers.search.get_embedding", return_value=None):
            response = client.get("/apis/search", params={"ask": "test", "limit": 0})
            assert response.status_code == 422

    def test_limit_too_high(self, client):
        with patch("src.apivault.routers.search.get_embedding", return_value=None):
            response = client.get("/apis/search", params={"ask": "test", "limit": 51})
            assert response.status_code == 422

    def test_min_similarity_too_low(self, client):
        with patch("src.apivault.routers.search.get_embedding", return_value=None):
            response = client.get("/apis/search", params={"ask": "test", "min_similarity": -0.1})
            assert response.status_code == 422

    def test_min_similarity_too_high(self, client):
        with patch("src.apivault.routers.search.get_embedding", return_value=None):
            response = client.get("/apis/search", params={"ask": "test", "min_similarity": 1.1})
            assert response.status_code == 422


class TestSearchEmbeddingFailure:
    def test_embedding_service_unavailable(self, client):
        with patch("src.apivault.routers.search.get_embedding", side_effect=ImportError("no module")):
            response = client.get("/apis/search", params={"ask": "test"})
            assert response.status_code == 503
            data = response.json()
            assert data["detail"]["error"] == "search_unavailable"

    def test_embedding_returns_none(self, client):
        with patch("src.apivault.routers.search.get_embedding", return_value=None):
            response = client.get("/apis/search", params={"ask": "test"})
            assert response.status_code == 503
            data = response.json()
            assert data["detail"]["error"] == "search_unavailable"

    def test_embedding_raises_exception(self, client):
        with patch("src.apivault.routers.search.get_embedding", side_effect=Exception("connection failed")):
            response = client.get("/apis/search", params={"ask": "test"})
            assert response.status_code == 503
            data = response.json()
            assert data["detail"]["error"] == "search_unavailable"


class TestSearchEndpointRegistered:
    def test_search_route_exists_in_openapi(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        spec = response.json()
        assert "/apis/search" in spec["paths"]
        assert "get" in spec["paths"]["/apis/search"]

    def test_search_has_required_parameters(self, client):
        response = client.get("/openapi.json")
        spec = response.json()
        params = {p["name"]: p for p in spec["paths"]["/apis/search"]["get"]["parameters"]}
        assert "ask" in params
        assert params["ask"]["required"] is True
        assert "auth" in params
        assert "limit" in params
        assert "min_similarity" in params
