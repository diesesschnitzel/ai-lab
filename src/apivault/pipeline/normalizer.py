"""Normalizer: transforms raw API candidates into normalized records.

Handles:
- URL extraction and validation
- Base URL extraction
- Documentation URL detection
- Domain canonicalization
- API format detection
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from .fingerprint import (
    canonicalize_domain,
    detect_api_path,
    extract_base_url,
    extract_docs_url,
    fingerprint_url,
    normalize_url,
)
from .models import ApiFormat, DataSource, NormalizedApi, RawCandidate

# Patterns for detecting API formats from URLs and content
GRAPHQL_PATTERNS = [
    r"/graphql",
    r"/graphiql",
    r"/playground",
]

GRPC_PATTERNS = [
    r"/grpc",
    r"\.proto$",
]

OPENAPI_PATTERNS = [
    r"/openapi",
    r"/swagger",
    r"/redoc",
    r"/api-docs",
    r"openapi\.json",
    r"swagger\.json",
]

SOAP_PATTERNS = [
    r"/soap",
    r"\.wsdl$",
    r"/wsdl",
]

WEBSOCKET_PATTERNS = [
    r"^ws://",
    r"^wss://",
    r"/ws/",
    r"/websocket",
]

REST_PATTERNS = [
    r"/api/",
    r"/v\d+/",
    r"/rest/",
]

# Common non-API paths to strip
NON_API_PATHS = frozenset(
    {
        "/docs",
        "/documentation",
        "/api-docs",
        "/swagger",
        "/redoc",
        "/graphql",
        "/graphiql",
        "/playground",
        "/blog",
        "/about",
        "/contact",
        "/pricing",
        "/login",
        "/signup",
        "/register",
        "/status",
        "/health",
    }
)


def is_valid_url(url: str | None) -> bool:
    """Check if a string is a valid HTTP/HTTPS URL."""
    if not url:
        return False
    try:
        parsed = urlsplit(url)
        return parsed.scheme in ("http", "https") and bool(parsed.hostname)
    except Exception:
        return False


def detect_api_format(url: str, raw_data: dict[str, Any] | None = None) -> ApiFormat:
    """Detect the API format from URL patterns and raw data hints."""
    url_lower = url.lower()

    # Check raw data hints first
    if raw_data:
        format_hint = str(raw_data.get("api_format") or raw_data.get("format") or "").lower()
        if format_hint:
            try:
                return ApiFormat(format_hint)
            except ValueError:
                pass

        # Check for format indicators in raw data
        for key, fmt in [
            ("has_graphql", ApiFormat.GRAPHQL),
            ("has_grpc", ApiFormat.GRPC),
            ("has_openapi", ApiFormat.OPENAPI),
            ("has_soap", ApiFormat.SOAP),
        ]:
            if raw_data.get(key):
                return fmt

    # Check URL patterns
    for pattern in GRAPHQL_PATTERNS:
        if re.search(pattern, url_lower):
            return ApiFormat.GRAPHQL

    for pattern in GRPC_PATTERNS:
        if re.search(pattern, url_lower):
            return ApiFormat.GRPC

    for pattern in OPENAPI_PATTERNS:
        if re.search(pattern, url_lower):
            return ApiFormat.OPENAPI

    for pattern in SOAP_PATTERNS:
        if re.search(pattern, url_lower):
            return ApiFormat.SOAP

    for pattern in WEBSOCKET_PATTERNS:
        if re.search(pattern, url_lower):
            return ApiFormat.WEBSOCKET

    for pattern in REST_PATTERNS:
        if re.search(pattern, url_lower):
            return ApiFormat.REST

    return ApiFormat.UNKNOWN


def extract_api_base_path(url: str) -> str:
    """Extract the base API path, stripping documentation and non-API segments.

    If the URL points to docs, return the base domain path instead.
    """
    parsed = urlsplit(url)
    path = parsed.path.lower()

    # If URL is a docs URL, strip to base
    for docs_path in NON_API_PATHS:
        if path.startswith(docs_path):
            return "/"

    # Extract API path
    api_path = detect_api_path(url)
    if api_path and api_path != path:
        return api_path

    return path


def normalize_candidate(candidate: RawCandidate) -> NormalizedApi | None:
    """Normalize a raw candidate into a standardized API record.

    Returns None if the candidate cannot be normalized (e.g., no valid URL).
    """
    # Determine the primary URL
    url = candidate.url
    if not url and candidate.raw_data.get("url"):
        url = candidate.raw_data["url"]
    if not url and candidate.raw_data.get("endpoint"):
        url = candidate.raw_data["endpoint"]

    if not url or not is_valid_url(url):
        return None

    assert isinstance(url, str)
    parsed = urlsplit(url)
    hostname = str(parsed.hostname or "")

    # Extract name
    name = candidate.name
    if not name and candidate.raw_data.get("name"):
        name = str(candidate.raw_data["name"])
    if not name and candidate.raw_data.get("title"):
        name = str(candidate.raw_data["title"])
    if not name:
        parts = hostname.split(".")
        common_tlds = {"com", "org", "net", "io", "dev", "app", "co", "info"}
        if parts and parts[-1] in common_tlds:
            parts = parts[:-1]
        name = " ".join(parts).title()

    # Normalize the URL
    normalized_url = normalize_url(url)

    # Extract components
    base_url = extract_base_url(normalized_url)
    canonical_domain = canonicalize_domain(hostname)
    docs_url = extract_docs_url(normalized_url, candidate.raw_data)
    api_format = detect_api_format(normalized_url, candidate.raw_data)

    # Create data source
    source = DataSource(
        source=candidate.source,
        raw_data=candidate.raw_data,
    )

    # Compute fingerprint
    url_fp = fingerprint_url(normalized_url)

    # Extract description
    description = candidate.description
    if not description and candidate.raw_data.get("description"):
        description = candidate.raw_data["description"]

    return NormalizedApi(
        name=name.strip(),
        base_url=base_url,
        docs_url=docs_url,
        canonical_domain=canonical_domain,
        api_format=api_format,
        description=description,
        sources=[source],
        url_fingerprint=url_fp,
        metadata={
            "original_url": normalized_url,
            "api_path": extract_api_base_path(normalized_url),
        },
    )


def normalize_candidates(candidates: list[RawCandidate]) -> list[NormalizedApi]:
    """Normalize a batch of raw candidates.

    Skips invalid candidates and logs errors in the result metadata.
    """
    results = []
    for candidate in candidates:
        try:
            normalized = normalize_candidate(candidate)
            if normalized:
                results.append(normalized)
        except Exception:
            # Skip invalid candidates silently
            continue
    return results
