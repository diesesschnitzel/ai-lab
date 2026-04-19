import httpx

DEFAULT_HEADERS = {
    "User-Agent": "APIVault/1.0 (api-discovery-bot; +https://github.com/diesesschnitzel/dummy)",
    "Accept": "application/json, text/html;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
}

DEFAULT_LIMITS = httpx.Limits(
    max_connections=100,
    max_keepalive_connections=20,
    keepalive_expiry=30,
)


def make_client(timeout: float = 15.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers=DEFAULT_HEADERS,
        limits=DEFAULT_LIMITS,
        timeout=httpx.Timeout(timeout),
        follow_redirects=True,
        max_redirects=5,
        http2=True,
    )
