"""Tests for the validation engine."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.apivault.validation.models import DNSResult, HTTPResult, ProbeResult, SSLResult
from src.apivault.validation.service import ValidationService


class TestDNSResult:
    def test_default(self):
        result = DNSResult()
        assert result.resolves is False
        assert result.addresses == []
        assert result.error is None

    def test_with_addresses(self):
        result = DNSResult(resolves=True, addresses=["1.2.3.4"])
        assert result.resolves is True
        assert result.addresses == ["1.2.3.4"]


class TestHTTPResult:
    def test_default(self):
        result = HTTPResult()
        assert result.status_code == 0
        assert result.response_time_ms is None
        assert result.headers == {}

    def test_with_data(self):
        result = HTTPResult(
            status_code=200,
            response_time_ms=150,
            headers={"content-type": "application/json"},
            body_sample='{"ok": true}',
            content_type="application/json",
        )
        assert result.status_code == 200
        assert result.response_time_ms == 150
        assert result.content_type == "application/json"


class TestSSLResult:
    def test_default(self):
        result = SSLResult()
        assert result.valid is None
        assert result.expiry is None

    def test_valid_cert(self):
        result = SSLResult(
            valid=True,
            expiry=date(2027, 1, 1),
            days_remaining=365,
            issuer={"CN": "Let's Encrypt"},
        )
        assert result.valid is True
        assert result.days_remaining == 365


class TestProbeResult:
    def test_default(self):
        result = ProbeResult(api_id="test-id")
        assert result.api_id == "test-id"
        assert result.health_score == 0
        assert result.auth_type_detected == "unknown"


class TestValidationService:
    @pytest.fixture
    def service(self):
        return ValidationService(max_concurrent=10)

    @pytest.mark.asyncio
    async def test_check_dns_resolves(self, service):
        with patch.object(
            service,
            "check_dns",
            new=AsyncMock(return_value=DNSResult(resolves=True, addresses=["1.2.3.4"])),
        ):
            result = await service.check_dns("example.com")
            assert result.resolves is True
            assert "1.2.3.4" in result.addresses

    @pytest.mark.asyncio
    async def test_check_dns_fails(self, service):
        with patch.object(
            service,
            "check_dns",
            new=AsyncMock(return_value=DNSResult(resolves=False, error="gaierror")),
        ):
            result = await service.check_dns("nonexistent.invalid")
            assert result.resolves is False
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_check_http_success(self, service):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "ok"}'
        mock_response.headers = {"content-type": "application/json"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with patch.object(service, "_get_client", new=AsyncMock(return_value=mock_client)):
            result = await service.check_http("https://api.example.com")
            assert result.status_code == 200
            assert result.content_type == "application/json"
            assert result.body_sample == '{"status": "ok"}'

    @pytest.mark.asyncio
    async def test_check_http_timeout(self, service):
        import httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.is_closed = False

        with patch.object(service, "_get_client", new=AsyncMock(return_value=mock_client)):
            result = await service.check_http("https://slow.example.com")
            assert result.status_code == 0
            assert result.error == "timeout"

    @pytest.mark.asyncio
    async def test_check_http_connect_error(self, service):
        import httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        mock_client.is_closed = False

        with patch.object(service, "_get_client", new=AsyncMock(return_value=mock_client)):
            result = await service.check_http("https://down.example.com")
            assert result.status_code == 0
            assert result.error == "connect_error"

    def test_detect_auth_type_none(self, service):
        result = HTTPResult(
            status_code=200,
            content_type="application/json",
            body_sample='{"data": []}',
        )
        assert service.detect_auth_type(result) == "none"

    def test_detect_auth_type_bearer(self, service):
        result = HTTPResult(
            status_code=401,
            headers={"www-authenticate": "Bearer realm=api"},
            body_sample="",
        )
        assert service.detect_auth_type(result) == "bearer"

    def test_detect_auth_type_basic(self, service):
        result = HTTPResult(
            status_code=401,
            headers={"www-authenticate": "Basic realm=api"},
            body_sample="",
        )
        assert service.detect_auth_type(result) == "basic"

    def test_detect_auth_type_401_default(self, service):
        result = HTTPResult(
            status_code=401,
            headers={},
            body_sample="",
        )
        assert service.detect_auth_type(result) == "bearer"

    def test_detect_auth_type_apikey_403(self, service):
        result = HTTPResult(
            status_code=403,
            headers={},
            body_sample="api key required",
        )
        assert service.detect_auth_type(result) == "apikey"

    def test_detect_auth_type_apikey_default_403(self, service):
        result = HTTPResult(
            status_code=403,
            headers={},
            body_sample="",
        )
        assert service.detect_auth_type(result) == "apikey"

    def test_detect_auth_type_apikey_header(self, service):
        result = HTTPResult(
            status_code=200,
            headers={"X-API-Key": "required"},
            content_type="text/html",
            body_sample="",
        )
        assert service.detect_auth_type(result) == "apikey"

    def test_detect_auth_type_oauth2(self, service):
        result = HTTPResult(
            status_code=200,
            content_type="text/html",
            body_sample="oauth2 access_token required",
        )
        assert service.detect_auth_type(result) == "oauth2"

    def test_detect_auth_type_unknown(self, service):
        result = HTTPResult(
            status_code=500,
            content_type="text/html",
            body_sample="internal server error",
        )
        assert service.detect_auth_type(result) == "unknown"

    def test_extract_rate_limit_with_window(self, service):
        headers = {"X-RateLimit-Limit": "1000", "X-RateLimit-Reset": "3600"}
        assert service.extract_rate_limit(headers) == "1000/window"

    def test_extract_rate_limit_without_window(self, service):
        headers = {"X-RateLimit-Limit": "1000"}
        assert service.extract_rate_limit(headers) == "1000/period"

    def test_extract_rate_limit_rapidapi(self, service):
        headers = {"X-RateLimit-Day": "500", "X-RateLimit-Window": "86400"}
        assert service.extract_rate_limit(headers) == "500/window"

    def test_extract_rate_limit_none(self, service):
        headers = {"Content-Type": "application/json"}
        assert service.extract_rate_limit(headers) is None

    def test_compute_health_score_excellent(self, service):
        probe = ProbeResult(
            api_id="test",
            dns_resolves=True,
            http_status=200,
            ssl_valid=True,
            response_time_ms=100,
            previous_consecutive_successes=5,
        )
        score = service.compute_health_score(probe)
        assert score == 100

    def test_compute_health_score_good(self, service):
        probe = ProbeResult(
            api_id="test",
            dns_resolves=True,
            http_status=200,
            ssl_valid=True,
            response_time_ms=500,
        )
        score = service.compute_health_score(probe)
        assert 80 <= score <= 95

    def test_compute_health_score_dead_dns(self, service):
        probe = ProbeResult(
            api_id="test",
            dns_resolves=False,
        )
        score = service.compute_health_score(probe)
        assert score == 0

    def test_compute_health_score_404(self, service):
        probe = ProbeResult(
            api_id="test",
            dns_resolves=True,
            http_status=404,
            ssl_valid=True,
            response_time_ms=200,
        )
        score = service.compute_health_score(probe)
        assert 70 <= score <= 85

    def test_compute_health_score_500(self, service):
        probe = ProbeResult(
            api_id="test",
            dns_resolves=True,
            http_status=500,
            ssl_valid=True,
            response_time_ms=200,
        )
        score = service.compute_health_score(probe)
        assert 60 <= score <= 70

    def test_compute_health_score_no_ssl(self, service):
        probe = ProbeResult(
            api_id="test",
            dns_resolves=True,
            http_status=200,
            ssl_valid=False,
            response_time_ms=100,
        )
        score = service.compute_health_score(probe)
        assert 60 <= score <= 80

    def test_compute_health_score_unknown_ssl(self, service):
        probe = ProbeResult(
            api_id="test",
            dns_resolves=True,
            http_status=200,
            ssl_valid=None,
            response_time_ms=100,
        )
        score = service.compute_health_score(probe)
        assert 80 <= score <= 95

    @pytest.mark.asyncio
    async def test_probe_api_no_url(self, service):
        result = await service.probe_api(api_id="test", base_url=None)
        assert result.health_score == 0
        assert result.http_error == "no_base_url"

    @pytest.mark.asyncio
    async def test_probe_api_dns_failure(self, service):
        with patch.object(
            service,
            "check_dns",
            new=AsyncMock(return_value=DNSResult(resolves=False, error="no resolution")),
        ):
            result = await service.probe_api(
                api_id="test",
                base_url="https://api.example.com",
            )
            assert result.dns_resolves is False
            assert result.health_score == 0

    def test_build_probe_urls_base_only(self, service):
        urls = service._build_probe_urls("https://api.example.com", None)
        assert "https://api.example.com" in urls
        assert "https://api.example.com/" in urls
        assert "https://api.example.com/health" in urls

    def test_build_probe_urls_with_docs(self, service):
        urls = service._build_probe_urls(
            "https://api.example.com",
            "https://docs.example.com",
        )
        assert "https://docs.example.com" in urls

    def test_build_probe_urls_with_path(self, service):
        urls = service._build_probe_urls("https://api.example.com/v1", None)
        assert "https://api.example.com/v1" in urls
        assert "https://api.example.com/v1/health" in urls

    def test_derive_status_active(self, service):
        assert service._derive_status_from_score(score=75, consecutive_failures=0) == "active"

    def test_derive_status_degraded(self, service):
        assert service._derive_status_from_score(score=30, consecutive_failures=1) == "degraded"

    def test_derive_status_dead(self, service):
        assert service._derive_status_from_score(score=30, consecutive_failures=5) == "dead"

    @pytest.mark.asyncio
    async def test_validate_batch_empty(self, service):
        results = await service.validate_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_close(self, service):
        mock_client = AsyncMock()
        mock_client.is_closed = False
        service._client = mock_client
        await service.close()
        mock_client.aclose.assert_called_once()
