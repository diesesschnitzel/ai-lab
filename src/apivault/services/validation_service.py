"""Validation service for API health checking."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from src.apivault.models.api import Api

logger = logging.getLogger(__name__)


async def probe_api(api: Api) -> dict[str, Any]:
    """Probe an API endpoint and return health data.

    Probe sequence:
    1. DNS resolution check (1s timeout)
    2. HTTP GET base_url (5s timeout)
    3. SSL check (if HTTPS)
    4. Auth type detection from response
    5. Rate limit header extraction
    6. Compute health_score (0-100)
    """
    health_data: dict[str, Any] = {
        "dns_resolves": False,
        "http_status": 0,
        "response_time_ms": 0,
        "ssl_valid": False,
        "ssl_expiry": None,
        "health_score": 0,
        "status": "dead",
        "consecutive_failures": api.consecutive_failures or 0,
    }

    if not api.base_url:
        health_data["consecutive_failures"] += 1
        if health_data["consecutive_failures"] >= 3:
            health_data["status"] = "dead"
        return health_data

    # Step 1: DNS resolution
    try:
        import socket

        from urllib.parse import urlparse

        parsed = urlparse(api.base_url)
        socket.getaddrinfo(parsed.hostname, 443 if parsed.scheme == "https" else 80)
        health_data["dns_resolves"] = True
    except Exception:
        health_data["consecutive_failures"] += 1
        if health_data["consecutive_failures"] >= 3:
            health_data["status"] = "dead"
        return health_data

    # Step 2: HTTP GET
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=1.0),
            follow_redirects=True,
            verify=True,
        ) as client:
            start = datetime.now(UTC)
            response = await client.get(api.base_url)
            elapsed = (datetime.now(UTC) - start).total_seconds() * 1000

            health_data["http_status"] = response.status_code
            health_data["response_time_ms"] = int(elapsed)

            # Step 4: Auth type detection
            if response.status_code == 200:
                if api.auth_type == "unknown":
                    health_data["auth_type"] = "none"
            elif response.status_code == 401:
                www_auth = response.headers.get("WWW-Authenticate", "")
                if "bearer" in www_auth.lower():
                    health_data["auth_type"] = "bearer"
                elif "basic" in www_auth.lower():
                    health_data["auth_type"] = "basic"
            elif response.status_code == 403:
                health_data["auth_type"] = "apikey"

            # Step 5: Rate limit headers
            rate_headers = [
                "X-RateLimit-Limit",
                "X-RateLimit-Remaining",
                "RateLimit-Limit",
                "Retry-After",
                "X-Rate-Limit",
            ]
            rate_info = []
            for header in rate_headers:
                if header in response.headers:
                    rate_info.append(f"{header}={response.headers[header]}")
            if rate_info:
                health_data["rate_limit"] = "; ".join(rate_info)

    except httpx.ConnectTimeout:
        health_data["consecutive_failures"] += 1
        if health_data["consecutive_failures"] >= 3:
            health_data["status"] = "dead"
        return health_data
    except httpx.ConnectError:
        health_data["consecutive_failures"] += 1
        if health_data["consecutive_failures"] >= 3:
            health_data["status"] = "dead"
        return health_data
    except Exception as e:
        logger.error("Unexpected error probing %s: %s", api.base_url, e)
        health_data["consecutive_failures"] += 1
        if health_data["consecutive_failures"] >= 3:
            health_data["status"] = "dead"
        return health_data

    # Step 3: SSL check (if HTTPS)
    if api.base_url.startswith("https"):
        try:
            import ssl

            from urllib.parse import urlparse

            parsed = urlparse(api.base_url)
            context = ssl.create_default_context()
            with context.wrap_socket(
                socket.socket(socket.AF_INET),
                server_hostname=parsed.hostname,
            ) as s:
                s.settimeout(2.0)
                s.connect((parsed.hostname, 443))
                cert = s.getpeercert()
                health_data["ssl_valid"] = True
                if "notAfter" in cert:
                    health_data["ssl_expiry"] = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").date()
        except Exception:
            health_data["ssl_valid"] = False

    # Step 6: Compute health_score
    score = 0
    if health_data["dns_resolves"]:
        score += 30
    if 200 <= health_data["http_status"] < 300:
        score += 30
    elif 300 <= health_data["http_status"] < 400:
        score += 20
    if health_data["ssl_valid"]:
        score += 20
    if health_data["response_time_ms"] < 1000:
        score += 10
    if health_data["response_time_ms"] < 500:
        score += 10
    health_data["health_score"] = score

    # Step 7: Status assignment
    if not health_data["dns_resolves"]:
        health_data["status"] = "dead"
    elif health_data["http_status"] == 0:
        health_data["status"] = "dead"
        health_data["consecutive_failures"] += 1
    elif 500 <= health_data["http_status"] < 600:
        health_data["status"] = "degraded"
        health_data["consecutive_failures"] += 1
    else:
        health_data["status"] = "active"
        health_data["consecutive_failures"] = 0

    if health_data["consecutive_failures"] >= 3:
        health_data["status"] = "dead"

    return health_data


async def probe_api_batch(apis: list[Api], concurrency: int = 50) -> list[dict[str, Any]]:
    """Probe multiple APIs concurrently."""
    semaphore = asyncio.Semaphore(concurrency)

    async def probe_with_semaphore(api: Api) -> dict[str, Any]:
        async with semaphore:
            return await probe_api(api)

    tasks = [probe_with_semaphore(api) for api in apis]
    return await asyncio.gather(*tasks, return_exceptions=True)
