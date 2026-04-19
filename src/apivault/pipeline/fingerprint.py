"""URL fingerprinting for fast deduplication lookups.

Generates deterministic fingerprints from URLs to enable O(1) lookups
during deduplication.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

# Common URL parameters that don't affect identity
IGNORED_QUERY_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "ref",
        "referrer",
        "fbclid",
        "gclid",
        "utm_id",
    }
)

# URL patterns that indicate documentation pages
DOCS_PATH_PATTERNS = [
    r"^/docs",
    r"^/documentation",
    r"^/api-docs",
    r"^/swagger",
    r"^/redoc",
    r"^/graphql",
    r"^/graphiql",
    r"^/playground",
    r"^/api-reference",
    r"^/reference",
    r"^/openapi",
]

# URL patterns that indicate API endpoints
API_PATH_PATTERNS = [
    r"^/api/",
    r"^/v\d+/",
    r"^/graphql",
    r"^/grpc",
    r"^/rest/",
    r"^/soap",
    r"^/ws/",
    r"^/websocket",
]


def normalize_url(url: str) -> str:
    """Normalize a URL for consistent fingerprinting.

    - Lowercase scheme and host
    - Remove trailing slashes (except root)
    - Remove ignored query parameters
    - Sort remaining query parameters
    - Remove default ports
    - Remove fragments
    """
    parsed = urlsplit(url)

    # Lowercase scheme and host
    scheme = parsed.scheme.lower()
    netloc = parsed.hostname.lower() if parsed.hostname else ""

    # Remove default ports
    if parsed.port:
        if (scheme == "http" and parsed.port == 80) or (scheme == "https" and parsed.port == 443):
            netloc = netloc.split(":")[0]
        else:
            netloc = f"{netloc}:{parsed.port}"

    # Remove 'www.' prefix
    if netloc.startswith("www."):
        netloc = netloc[4:]

    # Normalize path: remove trailing slash (except for root)
    path = parsed.path.rstrip("/") or "/"

    # Process query parameters
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    filtered_params = {k: v for k, v in query_params.items() if k not in IGNORED_QUERY_PARAMS}
    query = urlencode(sorted(filtered_params.items()), doseq=True)

    # Remove fragment
    normalized = urlunsplit((scheme, netloc, path, query, ""))
    return normalized


def fingerprint_url(url: str) -> str:
    """Generate a SHA-256 fingerprint from a normalized URL.

    Returns a 16-character hex string for efficient storage and comparison.
    """
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def fingerprint_domain(domain: str) -> str:
    """Generate a fingerprint from a canonical domain."""
    canonical = canonicalize_domain(domain)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def canonicalize_domain(domain: str) -> str:
    """Canonicalize a domain for comparison.

    - Lowercase
    - Remove 'www.' prefix
    - Remove trailing dots
    - Strip whitespace
    """
    domain = domain.lower().strip().rstrip(".")
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def extract_base_url(url: str) -> str:
    """Extract the base URL (scheme + domain) from a full URL.

    Examples:
        https://api.example.com/v1/users -> https://api.example.com
        http://docs.example.com/api/v2   -> http://docs.example.com
    """
    parsed = urlsplit(url)
    netloc = parsed.hostname.lower() if parsed.hostname else ""
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return f"{parsed.scheme.lower()}://{netloc}"


def extract_docs_url(url: str, raw_data: dict[str, Any] | None = None) -> str | None:
    """Attempt to extract a documentation URL from the candidate URL or raw data.

    Checks for common documentation path patterns in the URL and raw data fields.
    """
    if raw_data:
        for key in ("docs_url", "documentation_url", "doc_url", "api_docs_url"):
            if raw_data.get(key):
                return str(raw_data[key])

    parsed = urlsplit(url)
    path = parsed.path.lower()

    # If URL already points to docs, return normalized version
    for pattern in DOCS_PATH_PATTERNS:
        if re.match(pattern, path):
            return normalize_url(url)

    # Generate a likely docs URL
    base_url = extract_base_url(url)
    for docs_path in ("/docs", "/api-docs", "/documentation"):
        return f"{base_url}{docs_path}"

    return None


def detect_api_path(url: str) -> str:
    """Extract the API path portion from a URL."""
    parsed = urlsplit(url)
    path = parsed.path

    for pattern in API_PATH_PATTERNS:
        match = re.match(pattern, path)
        if match:
            return path

    # Return the path up to common non-API segments
    segments = [s for s in path.split("/") if s]
    api_segments: list[str] = []
    for segment in segments:
        if segment.startswith(("v", "api", "rest", "graphql", "grpc")) or api_segments:
            api_segments.append(segment)
        else:
            break

    return "/" + "/".join(api_segments) if api_segments else path


def get_domain_path_prefix(url: str) -> tuple[str, str]:
    """Extract (canonical_domain, path_prefix) for prefix matching.

    The path prefix is the first two path segments (or fewer if not available).
    """
    parsed = urlsplit(url)
    domain = canonicalize_domain(parsed.hostname or "")
    segments = [s for s in parsed.path.split("/") if s][:2]
    path_prefix = "/" + "/".join(segments) if segments else "/"
    return domain, path_prefix
