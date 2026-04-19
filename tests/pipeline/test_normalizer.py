"""Tests for the normalizer module."""


from src.apivault.pipeline.models import ApiFormat, RawCandidate
from src.apivault.pipeline.normalizer import (
    detect_api_format,
    extract_api_base_path,
    is_valid_url,
    normalize_candidate,
    normalize_candidates,
)


class TestIsValidUrl:
    def test_valid_https(self):
        assert is_valid_url("https://api.example.com")

    def test_valid_http(self):
        assert is_valid_url("http://api.example.com")

    def test_invalid_no_scheme(self):
        assert not is_valid_url("api.example.com")

    def test_invalid_none(self):
        assert not is_valid_url(None)

    def test_invalid_empty(self):
        assert not is_valid_url("")

    def test_invalid_ftp(self):
        assert not is_valid_url("ftp://example.com")


class TestDetectApiFormat:
    def test_graphql_from_url(self):
        assert detect_api_format("https://api.example.com/graphql") == ApiFormat.GRAPHQL

    def test_graphql_from_raw_data(self):
        assert detect_api_format("https://api.example.com", {"has_graphql": True}) == ApiFormat.GRAPHQL

    def test_grpc_from_url(self):
        assert detect_api_format("https://api.example.com/grpc") == ApiFormat.GRPC

    def test_openapi_from_url(self):
        assert detect_api_format("https://api.example.com/openapi.json") == ApiFormat.OPENAPI

    def test_swagger(self):
        assert detect_api_format("https://api.example.com/swagger") == ApiFormat.OPENAPI

    def test_soap_from_url(self):
        assert detect_api_format("https://api.example.com/soap") == ApiFormat.SOAP

    def test_websocket_from_url(self):
        assert detect_api_format("wss://api.example.com/ws") == ApiFormat.WEBSOCKET

    def test_rest_from_url(self):
        assert detect_api_format("https://api.example.com/api/v1") == ApiFormat.REST

    def test_rest_versioned(self):
        assert detect_api_format("https://api.example.com/v2/users") == ApiFormat.REST

    def test_unknown(self):
        assert detect_api_format("https://example.com") == ApiFormat.UNKNOWN

    def test_format_hint_from_raw_data(self):
        assert detect_api_format("https://api.example.com", {"api_format": "graphql"}) == ApiFormat.GRAPHQL


class TestExtractApiBasePath:
    def test_strips_docs_path(self):
        assert extract_api_base_path("https://api.example.com/docs") == "/"

    def test_strips_documentation_path(self):
        assert extract_api_base_path("https://api.example.com/documentation") == "/"

    def test_keeps_api_path(self):
        assert extract_api_base_path("https://api.example.com/api/v1") == "/api/v1"

    def test_keeps_versioned_path(self):
        assert extract_api_base_path("https://api.example.com/v2/users") == "/v2/users"


class TestNormalizeCandidate:
    def test_basic_normalization(self):
        candidate = RawCandidate(
            name="Test API",
            url="https://api.example.com/v1",
            source="manual",
        )
        result = normalize_candidate(candidate)
        assert result is not None
        assert result.name == "Test API"
        assert result.base_url == "https://api.example.com"
        assert result.canonical_domain == "api.example.com"
        assert result.url_fingerprint is not None
        assert len(result.sources) == 1
        assert result.sources[0].source == "manual"

    def test_derives_name_from_domain(self):
        candidate = RawCandidate(
            url="https://api.example.com/v1",
            source="manual",
        )
        result = normalize_candidate(candidate)
        assert result is not None
        assert result.name == "Api Example"

    def test_extracts_docs_url(self):
        candidate = RawCandidate(
            name="Test API",
            url="https://api.example.com/v1",
            raw_data={"docs_url": "https://docs.example.com"},
            source="manual",
        )
        result = normalize_candidate(candidate)
        assert result is not None
        assert result.docs_url == "https://docs.example.com"

    def test_detects_graphql(self):
        candidate = RawCandidate(
            name="GraphQL API",
            url="https://api.example.com/graphql",
            source="manual",
        )
        result = normalize_candidate(candidate)
        assert result is not None
        assert result.api_format == ApiFormat.GRAPHQL

    def test_returns_none_for_invalid_url(self):
        candidate = RawCandidate(
            name="Bad API",
            url="not-a-url",
            source="manual",
        )
        assert normalize_candidate(candidate) is None

    def test_returns_none_for_no_url(self):
        candidate = RawCandidate(name="No URL API", source="manual")
        assert normalize_candidate(candidate) is None

    def test_uses_endpoint_from_raw_data(self):
        candidate = RawCandidate(
            name="Test API",
            raw_data={"endpoint": "https://api.example.com/v1"},
            source="manual",
        )
        result = normalize_candidate(candidate)
        assert result is not None
        assert result.base_url == "https://api.example.com"

    def test_uses_name_from_raw_data(self):
        candidate = RawCandidate(
            url="https://api.example.com/v1",
            raw_data={"name": "From Raw Data"},
            source="manual",
        )
        result = normalize_candidate(candidate)
        assert result is not None
        assert result.name == "From Raw Data"

    def test_uses_title_from_raw_data(self):
        candidate = RawCandidate(
            url="https://api.example.com/v1",
            raw_data={"title": "From Title"},
            source="manual",
        )
        result = normalize_candidate(candidate)
        assert result is not None
        assert result.name == "From Title"

    def test_uses_description_from_raw_data(self):
        candidate = RawCandidate(
            name="Test API",
            url="https://api.example.com/v1",
            raw_data={"description": "A great API"},
            source="manual",
        )
        result = normalize_candidate(candidate)
        assert result is not None
        assert result.description == "A great API"

    def test_normalizes_www_domain(self):
        candidate = RawCandidate(
            name="Test API",
            url="https://www.example.com/api",
            source="manual",
        )
        result = normalize_candidate(candidate)
        assert result is not None
        assert result.canonical_domain == "example.com"
        assert result.base_url == "https://example.com"


class TestNormalizeCandidates:
    def test_batch_normalization(self):
        candidates = [
            RawCandidate(name="API 1", url="https://api1.com/v1", source="test"),
            RawCandidate(name="API 2", url="https://api2.com/v1", source="test"),
        ]
        results = normalize_candidates(candidates)
        assert len(results) == 2

    def test_skips_invalid(self):
        candidates = [
            RawCandidate(name="Valid", url="https://api.com/v1", source="test"),
            RawCandidate(name="Invalid", url="not-a-url", source="test"),
        ]
        results = normalize_candidates(candidates)
        assert len(results) == 1
        assert results[0].name == "Valid"

    def test_empty_list(self):
        assert normalize_candidates([]) == []
