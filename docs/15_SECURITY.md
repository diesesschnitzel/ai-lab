# Security
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## 1. Threat Model

APIVault is a data collection and serving system. The primary threats are:

| Threat | Risk | Mitigation |
|---|---|---|
| SQL injection via search queries | High impact | Parameterized queries only; ORM |
| API abuse (scraping our own API) | Medium | Rate limiting per IP |
| SSRF via user-supplied URLs | Medium | We don't fetch user-supplied URLs |
| Credential leakage from env vars | High | Never log env vars; use secrets |
| Getting our scrapers blocked | Medium | Rate limiting, User-Agent, robots.txt |
| Legal risk from scraping | Medium | See docs/16_DATA_GOVERNANCE.md |
| Scraped credentials in raw_json | Low | Sanitization at ingest |
| DDoS from scrapers against target APIs | Medium | Per-domain rate limiting |

---

## 2. API Security

### SQL Injection Prevention

All database queries use parameterized queries exclusively. No string formatting
into SQL. Example:

```python
# CORRECT — parameterized
await db.execute(
    "SELECT * FROM apis WHERE auth_type = $1 AND status = $2",
    auth_type, status
)

# NEVER DO THIS
await db.execute(
    f"SELECT * FROM apis WHERE auth_type = '{auth_type}'"
)
```

Full-text search uses PostgreSQL's built-in `plainto_tsquery()` which is safe:
```python
"SELECT * FROM apis WHERE fts @@ plainto_tsquery('english', $1)", query
```

### Rate Limiting

```python
# Per-IP rate limiting using token bucket algorithm
# Applied at application layer (not nginx, to avoid bypassing)

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/apis")
@limiter.limit("100/minute")
async def search_apis(request: Request, ...):
    ...

@app.get("/apis/search")
@limiter.limit("20/minute")
async def semantic_search(request: Request, ...):
    ...
```

When rate limited, return 429 with Retry-After header.

### Admin Endpoint Protection

Admin endpoints (`/admin/*`) require the `X-Admin-Key` header:

```python
def require_admin(request: Request):
    if not settings.ADMIN_KEY:
        raise HTTPException(403, "Admin endpoints disabled")
    key = request.headers.get("X-Admin-Key", "")
    if not secrets.compare_digest(key, settings.ADMIN_KEY):
        raise HTTPException(403, "Invalid admin key")
```

Use `secrets.compare_digest` to prevent timing attacks.

### Input Validation

```python
class SearchParams(BaseModel):
    q: str | None = Field(None, max_length=500)
    ask: str | None = Field(None, max_length=500)
    auth: Literal["none","apikey","oauth2","basic","bearer"] | None = None
    page: int = Field(1, ge=1, le=1000)
    per_page: int = Field(20, ge=1, le=100)
```

Pydantic validates all inputs. Invalid inputs return 422 before touching the DB.

---

## 3. Scraper Security

### Outbound Request Limits

Never make requests that could be harmful to target servers:
- Max 1 request/second per domain (hard limit)
- Timeout all requests (max 30s)
- Never follow more than 5 redirects
- Never send credentials to unknown hosts

### robots.txt Compliance

All scrapers check robots.txt before fetching any URL.
Violations are logged and skipped, not silently fetched.

```python
# robots.py
async def is_allowed(url: str) -> bool:
    # Cache robots.txt per domain (1 hour TTL)
    # Return True if robots.txt is unreachable (fail open)
    # Return False if disallowed
```

### User-Agent Transparency

The scraper uses a descriptive, honest User-Agent:
```
APIVault/1.0 (api-discovery-bot; contact: your@email.com)
```

Never impersonate a browser or another crawler.

### Sensitive Data Scraping

Scrapers may encounter credentials in wild (GitHub .env files, etc.).
Sanitization at ingest:

```python
SENSITIVE_PATTERNS = [
    r'sk-[a-zA-Z0-9]{32,}',          # OpenAI keys
    r'sk-ant-[a-zA-Z0-9-_]{90,}',    # Anthropic keys
    r'ghp_[a-zA-Z0-9]{36}',          # GitHub tokens
    r'[a-zA-Z0-9]{32,}',             # Generic long tokens
]

def sanitize_raw_json(data: dict) -> dict:
    text = json.dumps(data)
    for pattern in SENSITIVE_PATTERNS:
        text = re.sub(pattern, '[REDACTED]', text)
    return json.loads(text)
```

---

## 4. Infrastructure Security

### Database Access

- PostgreSQL only listens on `127.0.0.1:5432` (not exposed externally)
- No superuser credentials in application config
- Application database user has minimal privileges:

```sql
-- Create application user with minimal privileges
CREATE USER apivault_app WITH PASSWORD '...';
GRANT CONNECT ON DATABASE apivault TO apivault_app;
GRANT USAGE ON SCHEMA public TO apivault_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO apivault_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO apivault_app;
```

### Secrets Management

- All secrets in `.env` file, never in source code
- `.env` in `.gitignore` — never committed
- Docker Compose passes secrets as environment variables to containers
- Log levels should never log environment variable values

### Network Isolation

```yaml
# docker-compose.yml network isolation
services:
  db:
    networks:
      - internal
    # NOT on public network — only accessible by other services

  api:
    networks:
      - internal
      - public

  worker:
    networks:
      - internal
      - public  # Needs internet access for scraping

networks:
  internal:
    internal: true  # No external access
  public:
    driver: bridge
```

---

## 5. Dependency Security

```bash
# Run weekly
pip-audit  # Check for vulnerabilities in Python deps
uv lock    # Ensure lockfile is current

# Docker image scanning
docker scout cves apivault:latest
```

Pin all dependencies to exact versions in `pyproject.toml`.
Review dependency updates before applying.

---

## 6. Logging Security

Never log:
- API keys or secrets (even in debug mode)
- Full request bodies
- Database connection strings
- User IP addresses (for privacy)

Do log:
- Request method + path (without query params containing sensitive data)
- Response status code
- Errors with stack traces
- Scraper run outcomes

---

## 7. HTTPS / TLS

For production deployments, put a reverse proxy in front:

```nginx
# nginx.conf example
server {
    listen 443 ssl;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Use Let's Encrypt (certbot) for free TLS certificates.

---

## 8. Security Checklist

Before going live:

- [ ] `.env` not committed to git
- [ ] `ADMIN_KEY` set to strong random value (or disabled)
- [ ] Database not externally accessible
- [ ] Rate limiting enabled
- [ ] CORS restricted to known origins (if not public)
- [ ] TLS configured on reverse proxy
- [ ] Dependency audit run (`pip-audit`)
- [ ] Log level set to `INFO` (not `DEBUG` in production)
- [ ] `POSTGRES_PASSWORD` changed from default
- [ ] Backup procedure in place
