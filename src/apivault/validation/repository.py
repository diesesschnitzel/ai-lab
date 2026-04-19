"""Database repository for the validation engine."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import text

from src.apivault.models.api import Api
from src.apivault.models.api_health_log import ApiHealthLog

from .models import ProbeResult

logger = logging.getLogger(__name__)

CHECKER_VERSION = "1.0.0"


class ValidationRepository:
    """Handles DB reads/writes for validation results."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def get_apis_due_for_validation(self, limit: int = 100) -> list[dict]:
        async with self._session_factory() as session:
            stmt = text(
                """
                SELECT id, base_url, docs_url, status, consecutive_failures, health_score
                FROM apis
                WHERE (last_checked < now() - INTERVAL '7 days' OR last_checked IS NULL)
                  AND status != 'dead'
                ORDER BY last_checked ASC NULLS FIRST
                LIMIT :limit
                """
            )
            result = await session.execute(stmt, {"limit": limit})
            rows = result.mappings().all()
            return [dict(row) for row in rows]

    async def get_pending_validation_apis(self, limit: int = 100) -> list[dict]:
        async with self._session_factory() as session:
            stmt = text(
                """
                SELECT id, base_url, docs_url, status, consecutive_failures, health_score
                FROM apis
                WHERE status = 'pending_validation'
                ORDER BY created_at ASC
                LIMIT :limit
                """
            )
            result = await session.execute(stmt, {"limit": limit})
            rows = result.mappings().all()
            return [dict(row) for row in rows]

    async def get_dead_apis_for_retry(self, limit: int = 50) -> list[dict]:
        async with self._session_factory() as session:
            stmt = text(
                """
                SELECT id, base_url, docs_url, status, consecutive_failures, health_score,
                       last_checked
                FROM apis
                WHERE status = 'dead'
                  AND consecutive_failures < 10
                  AND (
                    (consecutive_failures = 0 AND last_checked < now() - INTERVAL '1 day')
                    OR (consecutive_failures BETWEEN 1 AND 2 AND last_checked < now() - INTERVAL '3 days')
                    OR (consecutive_failures BETWEEN 3 AND 6 AND last_checked < now() - INTERVAL '7 days')
                    OR (consecutive_failures >= 7 AND last_checked < now() - INTERVAL '30 days')
                  )
                ORDER BY last_checked ASC
                LIMIT :limit
                """
            )
            result = await session.execute(stmt, {"limit": limit})
            rows = result.mappings().all()
            return [dict(row) for row in rows]

    async def save_probe_result(self, probe: ProbeResult) -> None:
        async with self._session_factory() as session:
            api = await session.get(Api, probe.api_id)
            if not api:
                logger.warning("API %s not found, skipping validation save", probe.api_id)
                return

            api.health_score = probe.health_score
            api.last_checked = datetime.now(UTC)
            api.http_status = probe.http_status
            api.response_time_ms = probe.response_time_ms
            api.dns_resolves = probe.dns_resolves
            api.ssl_valid = probe.ssl_valid
            api.ssl_expiry = probe.ssl_expiry

            if probe.auth_type_detected != "unknown":
                api.auth_type = probe.auth_type_detected

            if probe.rate_limit_detected:
                api.rate_limit_header = probe.rate_limit_detected

            if probe.dns_resolves and probe.http_status and probe.http_status >= 200:
                api.consecutive_failures = 0
            else:
                api.consecutive_failures = (api.consecutive_failures or 0) + 1

            api.status = self._derive_status(probe, api.consecutive_failures)

            health_log = ApiHealthLog(
                api_id=probe.api_id,
                status=self._derive_log_status(probe),
                http_status=probe.http_status,
                response_time_ms=probe.response_time_ms,
                dns_resolves=probe.dns_resolves,
                ssl_valid=probe.ssl_valid,
                auth_type_detected=probe.auth_type_detected,
                rate_limit_detected=probe.rate_limit_detected,
                error=probe.http_error or probe.dns_error or probe.ssl_error,
                checker_version=CHECKER_VERSION,
            )
            session.add(health_log)
            await session.commit()

            if probe.ssl_valid is False or (probe.ssl_days_remaining is not None and probe.ssl_days_remaining < 14):
                logger.warning(
                    "API %s SSL issue: valid=%s, days_remaining=%s",
                    probe.api_id,
                    probe.ssl_valid,
                    probe.ssl_days_remaining,
                )

    async def save_batch_results(self, probes: list[ProbeResult]) -> None:
        for probe in probes:
            await self.save_probe_result(probe)

    def _derive_status(self, probe: ProbeResult, consecutive_failures: int) -> str:
        if probe.health_score >= 50:
            return "active"
        if consecutive_failures >= 3:
            return "dead"
        return "degraded"

    def _derive_log_status(self, probe: ProbeResult) -> str:
        if probe.dns_resolves and probe.http_status:
            if 200 <= probe.http_status < 500:
                return "alive"
            return "degraded"
        if probe.http_status == 0 or not probe.dns_resolves:
            return "dead"
        return "error"
