"""Tests for the validation repository."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.apivault.validation.models import ProbeResult
from src.apivault.validation.repository import ValidationRepository


class TestValidationRepository:
    @pytest.fixture
    def mock_session_factory(self):
        session = AsyncMock()
        factory = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=session), __aexit__=AsyncMock(return_value=None))
        )
        factory.return_value.__aenter__.return_value = session
        return factory, session

    @pytest.fixture
    def repo(self, mock_session_factory):
        factory, _ = mock_session_factory
        return ValidationRepository(session_factory=factory)

    def test_derive_status_active(self, repo):
        probe = ProbeResult(api_id="test", health_score=75, dns_resolves=True, http_status=200)
        assert repo._derive_status(probe, consecutive_failures=0) == "active"

    def test_derive_status_degraded(self, repo):
        probe = ProbeResult(api_id="test", health_score=30, dns_resolves=True, http_status=404)
        assert repo._derive_status(probe, consecutive_failures=1) == "degraded"

    def test_derive_status_dead(self, repo):
        probe = ProbeResult(api_id="test", health_score=0, dns_resolves=False)
        assert repo._derive_status(probe, consecutive_failures=5) == "dead"

    def test_derive_log_status_alive(self, repo):
        probe = ProbeResult(api_id="test", dns_resolves=True, http_status=200)
        assert repo._derive_log_status(probe) == "alive"

    def test_derive_log_status_alive_404(self, repo):
        probe = ProbeResult(api_id="test", dns_resolves=True, http_status=404)
        assert repo._derive_log_status(probe) == "alive"

    def test_derive_log_status_degraded(self, repo):
        probe = ProbeResult(api_id="test", dns_resolves=True, http_status=503)
        assert repo._derive_log_status(probe) == "degraded"

    def test_derive_log_status_dead_no_dns(self, repo):
        probe = ProbeResult(api_id="test", dns_resolves=False, http_status=None)
        assert repo._derive_log_status(probe) == "dead"

    def test_derive_log_status_dead_no_response(self, repo):
        probe = ProbeResult(api_id="test", dns_resolves=True, http_status=0)
        assert repo._derive_log_status(probe) == "dead"

    def test_derive_log_status_error(self, repo):
        probe = ProbeResult(api_id="test", dns_resolves=True, http_status=None)
        assert repo._derive_log_status(probe) == "error"

    @pytest.mark.asyncio
    async def test_save_probe_result_updates_api(self, mock_session_factory):
        factory, session = mock_session_factory
        repo = ValidationRepository(session_factory=factory)

        api_id = str(uuid.uuid4())
        mock_api = MagicMock()
        mock_api.consecutive_failures = 0
        session.get = AsyncMock(return_value=mock_api)

        probe = ProbeResult(
            api_id=api_id,
            dns_resolves=True,
            http_status=200,
            response_time_ms=150,
            ssl_valid=True,
            ssl_expiry=date(2027, 1, 1),
            auth_type_detected="none",
            rate_limit_detected="1000/period",
            health_score=95,
        )

        await repo.save_probe_result(probe)

        session.get.assert_called_once()
        assert mock_api.health_score == 95
        assert mock_api.http_status == 200
        assert mock_api.response_time_ms == 150
        assert mock_api.dns_resolves is True
        assert mock_api.ssl_valid is True
        assert mock_api.auth_type == "none"
        assert mock_api.consecutive_failures == 0
        assert mock_api.status == "active"
        session.add.assert_called_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_probe_result_api_not_found(self, mock_session_factory, caplog):
        factory, session = mock_session_factory
        repo = ValidationRepository(session_factory=factory)

        api_id = str(uuid.uuid4())
        session.get = AsyncMock(return_value=None)

        probe = ProbeResult(api_id=api_id, health_score=0)

        await repo.save_probe_result(probe)

        session.get.assert_called_once()
        session.add.assert_not_called()
        session.commit.assert_not_awaited()
        assert "not found" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_save_probe_result_increments_failures(self, mock_session_factory):
        factory, session = mock_session_factory
        repo = ValidationRepository(session_factory=factory)

        api_id = str(uuid.uuid4())
        mock_api = MagicMock()
        mock_api.consecutive_failures = 2
        session.get = AsyncMock(return_value=mock_api)

        probe = ProbeResult(
            api_id=api_id,
            dns_resolves=False,
            http_status=None,
            health_score=0,
        )

        await repo.save_probe_result(probe)

        assert mock_api.consecutive_failures == 3
        assert mock_api.status == "dead"

    @pytest.mark.asyncio
    async def test_save_probe_result_ssl_expiry_warning(self, mock_session_factory, caplog):
        factory, session = mock_session_factory
        repo = ValidationRepository(session_factory=factory)

        api_id = str(uuid.uuid4())
        mock_api = MagicMock()
        mock_api.consecutive_failures = 0
        session.get = AsyncMock(return_value=mock_api)

        probe = ProbeResult(
            api_id=api_id,
            dns_resolves=True,
            http_status=200,
            ssl_valid=False,
            ssl_days_remaining=5,
            health_score=60,
        )

        await repo.save_probe_result(probe)

        assert "SSL issue" in caplog.text

    @pytest.mark.asyncio
    async def test_get_apis_due_for_validation(self, mock_session_factory):
        factory, session = mock_session_factory
        repo = ValidationRepository(session_factory=factory)

        mock_result = MagicMock()
        mock_row = {
            "id": "abc",
            "base_url": "https://api.example.com",
            "docs_url": None,
            "status": "active",
            "consecutive_failures": 0,
            "health_score": 80,
        }
        mock_result.mappings.return_value.all.return_value = [mock_row]
        session.execute = AsyncMock(return_value=mock_result)

        apis = await repo.get_apis_due_for_validation(limit=50)

        assert len(apis) == 1
        assert apis[0]["id"] == "abc"
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_pending_validation_apis(self, mock_session_factory):
        factory, session = mock_session_factory
        repo = ValidationRepository(session_factory=factory)

        mock_result = MagicMock()
        mock_row = {
            "id": "xyz",
            "base_url": "https://new.api.com",
            "docs_url": None,
            "status": "pending_validation",
            "consecutive_failures": 0,
            "health_score": None,
        }
        mock_result.mappings.return_value.all.return_value = [mock_row]
        session.execute = AsyncMock(return_value=mock_result)

        apis = await repo.get_pending_validation_apis(limit=25)

        assert len(apis) == 1
        assert apis[0]["status"] == "pending_validation"

    @pytest.mark.asyncio
    async def test_get_dead_apis_for_retry(self, mock_session_factory):
        factory, session = mock_session_factory
        repo = ValidationRepository(session_factory=factory)

        mock_result = MagicMock()
        mock_row = {
            "id": "dead1",
            "base_url": "https://dead.api.com",
            "docs_url": None,
            "status": "dead",
            "consecutive_failures": 1,
            "health_score": 0,
            "last_checked": datetime.now(UTC),
        }
        mock_result.mappings.return_value.all.return_value = [mock_row]
        session.execute = AsyncMock(return_value=mock_result)

        apis = await repo.get_dead_apis_for_retry(limit=10)

        assert len(apis) == 1
        assert apis[0]["status"] == "dead"

    @pytest.mark.asyncio
    async def test_save_batch_results(self, mock_session_factory):
        factory, session = mock_session_factory
        repo = ValidationRepository(session_factory=factory)

        api_id = str(uuid.uuid4())
        mock_api = MagicMock()
        mock_api.consecutive_failures = 0
        session.get = AsyncMock(return_value=mock_api)

        probes = [
            ProbeResult(api_id=api_id, dns_resolves=True, http_status=200, health_score=90),
            ProbeResult(api_id=api_id, dns_resolves=True, http_status=200, health_score=85),
        ]

        await repo.save_batch_results(probes)

        assert session.add.call_count == 2
        assert session.commit.await_count == 2
