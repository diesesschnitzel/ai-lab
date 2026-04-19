"""Data models for the validation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class DNSResult:
    resolves: bool = False
    addresses: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class HTTPResult:
    status_code: int = 0
    response_time_ms: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    body_sample: str = ""
    content_type: str = ""
    error: str | None = None


@dataclass
class SSLResult:
    valid: bool | None = None
    expiry: date | None = None
    issuer: dict[str, str] = field(default_factory=dict)
    days_remaining: int | None = None
    error: str | None = None


@dataclass
class ProbeResult:
    api_id: str
    base_url: str | None = None
    docs_url: str | None = None

    dns_resolves: bool = False
    dns_addresses: list[str] = field(default_factory=list)
    dns_error: str | None = None

    http_status: int | None = None
    response_time_ms: int | None = None
    http_headers: dict[str, str] = field(default_factory=dict)
    http_error: str | None = None
    body_sample: str = ""
    content_type: str = ""

    ssl_valid: bool | None = None
    ssl_expiry: date | None = None
    ssl_days_remaining: int | None = None
    ssl_error: str | None = None

    auth_type_detected: str = "unknown"
    rate_limit_detected: str | None = None

    health_score: int = 0
    previous_consecutive_successes: int = 0
