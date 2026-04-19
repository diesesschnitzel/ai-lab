"""Validation engine: probes APIs for DNS, HTTP, SSL, auth detection, and health scoring."""

from __future__ import annotations

import asyncio
import logging
import socket
import ssl
import time
from datetime import date, datetime
from urllib.parse import urlparse

import httpx

from .models import DNSResult, HTTPResult, ProbeResult, SSLResult

logger = logging.getLogger(__name__)

LIMIT_HEADERS = [
    "X-RateLimit-Limit",
    "X-Rate-Limit-Limit",
    "RateLimit-Limit",
    "X-RateLimit-Requests-Limit",
    "X-RateLimit-Day",
    "X-Daily-Rate-Limit",
]

REMAINING_HEADERS = [
    "X-RateLimit-Remaining",
    "X-Rate-Limit-Remaining",
    "RateLimit-Remaining",
]

WINDOW_HEADERS = [
    "X-RateLimit-Window",
    "X-RateLimit-Reset",
]

API_KEY_HINT_HEADERS = ["x-api-key", "x-rapidapi-key", "x-app-id"]


class ValidationService:
    """Async validation engine that probes APIs for health, auth, and SSL status."""

    def __init__(self, max_concurrent: int = 50) -> None:
        self._max_concurrent = max_concurrent
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                limits=httpx.Limits(max_connections=self._max_concurrent),
                timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0),
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def check_dns(self, hostname: str) -> DNSResult:
        try:
            loop = asyncio.get_event_loop()
            infos = await asyncio.wait_for(
                loop.getaddrinfo(
                    hostname,
                    None,
                    type=socket.SOCK_STREAM,
                    flags=socket.AI_ADDRCONFIG,
                ),
                timeout=3.0,
            )
            addresses = list({info[4][0] for info in infos})
            return DNSResult(resolves=True, addresses=addresses)
        except TimeoutError:
            return DNSResult(resolves=False, error="dns_timeout")
        except socket.gaierror as e:
            return DNSResult(resolves=False, error=str(e))
        except Exception as e:
            return DNSResult(resolves=False, error=str(e))

    async def check_http(self, url: str) -> HTTPResult:
        client = await self._get_client()
        start = time.monotonic()
        try:
            response = await client.get(
                url,
                headers={"Accept": "application/json, */*;q=0.8"},
                timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0),
            )
            elapsed = int((time.monotonic() - start) * 1000)
            return HTTPResult(
                status_code=response.status_code,
                response_time_ms=elapsed,
                headers=dict(response.headers),
                body_sample=response.text[:500],
                content_type=response.headers.get("content-type", ""),
            )
        except httpx.TimeoutException:
            return HTTPResult(status_code=0, error="timeout")
        except httpx.ConnectError:
            return HTTPResult(status_code=0, error="connect_error")
        except Exception as e:
            return HTTPResult(status_code=0, error=str(e))

    async def _check_multiple_endpoints(self, urls: list[str]) -> HTTPResult:
        results = await asyncio.gather(
            *[self.check_http(url) for url in urls],
            return_exceptions=True,
        )

        http_results: list[HTTPResult] = []
        for r in results:
            if isinstance(r, HTTPResult):
                http_results.append(r)

        if not http_results:
            return HTTPResult(status_code=0, error="all_endpoints_failed")

        def _rank(r: HTTPResult) -> int:
            code = r.status_code
            if 200 <= code < 300:
                return 4
            if 300 <= code < 400:
                return 3
            if 400 <= code < 500:
                return 2
            if 500 <= code < 600:
                return 1
            return 0

        return max(http_results, key=_rank)

    def _build_probe_urls(self, base_url: str | None, docs_url: str | None) -> list[str]:
        urls: list[str] = []
        if not base_url:
            return urls

        urls.append(base_url)

        parsed = urlparse(base_url)
        if parsed.path in ("", "/"):
            urls.append(f"{base_url}/")

        urls.append(f"{base_url.rstrip('/')}/health")

        if docs_url and docs_url != base_url:
            urls.append(docs_url)

        return urls

    def _get_cert(self, hostname: str, context: ssl.SSLContext) -> object:
        import socket as _socket

        with (
            _socket.create_connection((hostname, 443), timeout=5) as sock,
            context.wrap_socket(sock, server_hostname=hostname) as ssock,
        ):
            return ssock

    async def check_ssl(self, hostname: str) -> SSLResult:
        try:
            context = ssl.create_default_context()
            conn = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, self._get_cert, hostname, context),
                timeout=5.0,
            )
            cert = conn.getpeercert()  # type: ignore[union-attr]
            expiry = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")  # type: ignore[arg-type]
            expiry_date = expiry.date()
            days_remaining = (expiry_date - date.today()).days
            issuer_dict = dict(x[0] for x in cert.get("issuer", []))
            return SSLResult(
                valid=True,
                expiry=expiry_date,
                issuer=issuer_dict,
                days_remaining=days_remaining,
            )
        except ssl.SSLCertVerificationError as e:
            return SSLResult(valid=False, error=str(e))
        except TimeoutError:
            return SSLResult(valid=None, error="ssl_timeout")
        except Exception as e:
            return SSLResult(valid=None, error=str(e))

    def detect_auth_type(self, result: HTTPResult) -> str:
        status = result.status_code
        headers = result.headers
        body = result.body_sample.lower()

        if status == 200 and "application/json" in result.content_type:
            return "none"

        if status == 401:
            www_auth = headers.get("www-authenticate", "").lower()
            if "bearer" in www_auth:
                return "bearer"
            if "basic" in www_auth:
                return "basic"
            return "bearer"

        if status == 403:
            if any(kw in body for kw in ["api key", "apikey", "api_key", "unauthorized"]):
                return "apikey"
            return "apikey"

        headers_lower = {k.lower(): v for k, v in headers.items()}
        if any(h in headers_lower for h in API_KEY_HINT_HEADERS):
            return "apikey"

        if "oauth" in body or "access_token" in body:
            return "oauth2"

        return "unknown"

    def extract_rate_limit(self, headers: dict[str, str]) -> str | None:
        headers_lower = {k.lower(): v for k, v in headers.items()}
        limit_headers_lower = [h.lower() for h in LIMIT_HEADERS]
        window_headers_lower = [h.lower() for h in WINDOW_HEADERS]

        limit = None
        for h in limit_headers_lower:
            if h in headers_lower:
                limit = headers_lower[h]
                break

        if limit:
            reset = None
            for h in window_headers_lower:
                if h in headers_lower:
                    reset = headers_lower[h]
                    break
            return f"{limit}/window" if reset else f"{limit}/period"

        return None

    def compute_health_score(self, probe: ProbeResult) -> int:
        score = 0

        if probe.dns_resolves:
            score += 25
        else:
            return 0

        if probe.http_status is not None:
            if 200 <= probe.http_status < 300:
                score += 35
            elif 300 <= probe.http_status < 400:
                score += 25
            elif 400 <= probe.http_status < 500:
                score += 20
            elif 500 <= probe.http_status < 600:
                score += 5

        if probe.ssl_valid is True:
            score += 20
        elif probe.ssl_valid is None:
            score += 10

        if probe.response_time_ms is not None:
            if probe.response_time_ms < 300:
                score += 15
            elif probe.response_time_ms < 1000:
                score += 10
            elif probe.response_time_ms < 3000:
                score += 5

        if probe.previous_consecutive_successes >= 3:
            score += 5

        return min(score, 100)

    def _derive_status_from_score(self, score: int, consecutive_failures: int) -> str:
        if score >= 50:
            return "active"
        if consecutive_failures >= 3:
            return "dead"
        return "degraded"

    async def probe_api(
        self,
        api_id: str,
        base_url: str | None = None,
        docs_url: str | None = None,
        previous_consecutive_successes: int = 0,
    ) -> ProbeResult:
        probe = ProbeResult(
            api_id=api_id,
            base_url=base_url,
            docs_url=docs_url,
            previous_consecutive_successes=previous_consecutive_successes,
        )

        if not base_url:
            probe.http_error = "no_base_url"
            probe.health_score = 0
            return probe

        hostname = urlparse(base_url).hostname
        if not hostname:
            probe.http_error = "invalid_url"
            probe.health_score = 0
            return probe

        dns_result = await self.check_dns(hostname)
        probe.dns_resolves = dns_result.resolves
        probe.dns_addresses = dns_result.addresses
        probe.dns_error = dns_result.error

        if not dns_result.resolves:
            probe.health_score = 0
            return probe

        probe_urls = self._build_probe_urls(base_url, docs_url)
        http_result = await self._check_multiple_endpoints(probe_urls)
        probe.http_status = http_result.status_code
        probe.response_time_ms = http_result.response_time_ms
        probe.http_headers = http_result.headers
        probe.http_error = http_result.error
        probe.body_sample = http_result.body_sample
        probe.content_type = http_result.content_type

        ssl_result = await self.check_ssl(hostname)
        probe.ssl_valid = ssl_result.valid
        probe.ssl_expiry = ssl_result.expiry
        probe.ssl_days_remaining = ssl_result.days_remaining
        probe.ssl_error = ssl_result.error

        probe.auth_type_detected = self.detect_auth_type(http_result)
        probe.rate_limit_detected = self.extract_rate_limit(http_result.headers)

        probe.health_score = self.compute_health_score(probe)

        return probe

    async def validate_batch(
        self,
        apis: list[dict],
    ) -> list[ProbeResult]:
        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def probe_with_limit(api: dict) -> ProbeResult | Exception:
            async with semaphore:
                consecutive_failures = api.get("consecutive_failures", 0)
                return await self.probe_api(
                    api_id=api["id"],
                    base_url=api.get("base_url"),
                    docs_url=api.get("docs_url"),
                    previous_consecutive_successes=0 if consecutive_failures > 0 else 0,
                )

        results = await asyncio.gather(
            *[probe_with_limit(api) for api in apis],
            return_exceptions=True,
        )

        probe_results: list[ProbeResult] = []
        for r in results:
            if isinstance(r, ProbeResult):
                probe_results.append(r)
            elif isinstance(r, Exception):
                logger.error("Probe failed with exception: %s", r)

        return probe_results
