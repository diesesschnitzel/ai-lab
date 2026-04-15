# Validation & Health Check Engine
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## 1. Purpose

Validation answers three questions for every API:
1. **Is it alive?** — Can we reach it at all?
2. **What does it actually need?** — Auth type, in practice
3. **How healthy is it?** — Speed, reliability, SSL status

Without active validation, API directories go stale within months. Dead APIs
frustrate developers and destroy trust in the database.

---

## 2. Validation Schedule

| Trigger | Scope | Target |
|---|---|---|
| On discovery | Newly inserted APIs (status=pending_validation) | Within 24h |
| Weekly schedule | All APIs not checked in 7 days | Rolling, continuous |
| Dead retry | APIs with status=dead, consecutive_failures < 10 | Every 3 days |
| Manual trigger | Any API via admin API endpoint | Immediate |
| Post-maintenance | APIs whose docs_url returned 503 recently | After 1h |

---

## 3. Probe Sequence

Every validation run executes these checks in order:

### Step 1: DNS Resolution

```python
async def check_dns(self, hostname: str) -> DNSResult:
    try:
        loop = asyncio.get_event_loop()
        infos = await loop.getaddrinfo(
            hostname, None,
            type=socket.SOCK_STREAM,
            flags=socket.AI_ADDRCONFIG
        )
        return DNSResult(
            resolves=True,
            addresses=[info[4][0] for info in infos],
        )
    except socket.gaierror as e:
        return DNSResult(resolves=False, error=str(e))
```

**Timeout:** 3 seconds
**Failure action:** Mark `dns_resolves=False`, `status=dead`. Stop — do not probe further.

---

### Step 2: HTTP Reachability

```python
async def check_http(self, url: str) -> HTTPResult:
    start = time.monotonic()
    try:
        response = await self.client.get(
            url,
            headers={"Accept": "application/json, */*;q=0.8"},
            timeout=httpx.Timeout(connect=5.0, read=10.0),
        )
        return HTTPResult(
            status_code=response.status_code,
            response_time_ms=int((time.monotonic() - start) * 1000),
            headers=dict(response.headers),
            body_sample=response.text[:500],
            content_type=response.headers.get("content-type", ""),
        )
    except httpx.TimeoutException:
        return HTTPResult(status_code=0, error="timeout")
    except httpx.ConnectError:
        return HTTPResult(status_code=0, error="connect_error")
```

**Timeout:** 5s connect, 10s read
**Endpoints tried:**
1. `{base_url}` — the canonical base URL
2. `{base_url}/` — with trailing slash (if base has no path)
3. `{base_url}/health` — common health endpoint
4. `{docs_url}` — documentation page (to check if at least docs are up)

**Use the best result** (prefer 2xx, then 3xx, then 4xx, then 5xx).

---

### Step 3: SSL/TLS Validation

```python
async def check_ssl(self, hostname: str) -> SSLResult:
    try:
        context = ssl.create_default_context()
        conn = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, self._get_cert, hostname, context
            ),
            timeout=5.0
        )
        cert = conn.getpeercert()
        expiry = datetime.strptime(
            cert['notAfter'], '%b %d %H:%M:%S %Y %Z'
        )
        return SSLResult(
            valid=True,
            expiry=expiry.date(),
            issuer=dict(x[0] for x in cert.get('issuer', [])),
            days_remaining=(expiry.date() - date.today()).days,
        )
    except ssl.SSLCertVerificationError as e:
        return SSLResult(valid=False, error=str(e))
    except Exception as e:
        return SSLResult(valid=None, error=str(e))  # Unknown
```

**Alert threshold:** `days_remaining < 14` → flag in health log

---

### Step 4: Auth Type Detection

Infer auth requirements from the HTTP response without trying to authenticate:

```python
def detect_auth_type(self, result: HTTPResult) -> str:
    status = result.status_code
    headers = result.headers
    body = result.body_sample.lower()
    
    # 200 with JSON response → likely no auth (or open endpoint)
    if status == 200 and "application/json" in result.content_type:
        return "none"
    
    # 401 → auth required
    if status == 401:
        www_auth = headers.get("www-authenticate", "").lower()
        if "bearer" in www_auth:
            return "bearer"
        if "basic" in www_auth:
            return "basic"
        return "bearer"  # Default for 401
    
    # 403 → often API key required
    if status == 403:
        if any(kw in body for kw in ["api key", "apikey", "api_key", "unauthorized"]):
            return "apikey"
        return "apikey"  # Default for 403
    
    # Headers that indicate API key
    api_key_headers = ["x-api-key", "x-rapidapi-key", "x-app-id"]
    if any(h in headers for h in api_key_headers):
        return "apikey"
    
    # OAuth hints
    if "oauth" in body or "access_token" in body:
        return "oauth2"
    
    return "unknown"
```

---

### Step 5: Rate Limit Extraction

```python
def extract_rate_limit(self, headers: dict) -> str | None:
    # Standard and common rate limit headers
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
    
    limit = next(
        (headers[h] for h in LIMIT_HEADERS if h in headers),
        None
    )
    if limit:
        # Try to determine window (per second, minute, hour, day)
        reset = next(
            (headers[h] for h in WINDOW_HEADERS if h in headers),
            None
        )
        return f"{limit}/window" if reset else f"{limit}/period"
    
    return None
```

---

## 4. Health Score Calculation

The health score is a 0–100 integer summarizing overall API health:

```python
def compute_health_score(self, probe: ProbeResult) -> int:
    score = 0
    
    # DNS resolution is fundamental (without it, nothing works)
    if probe.dns_resolves:
        score += 25
    else:
        return 0  # Dead; no further scoring
    
    # HTTP response quality
    if probe.http_status:
        if 200 <= probe.http_status < 300:
            score += 35
        elif 300 <= probe.http_status < 400:
            score += 25
        elif 400 <= probe.http_status < 500:
            score += 20  # At least it responded (likely needs auth)
        elif 500 <= probe.http_status < 600:
            score += 5   # Responding but broken
        # 0 = no response = 0 points
    
    # SSL
    if probe.ssl_valid is True:
        score += 20
    elif probe.ssl_valid is None:
        score += 10  # Unknown, don't penalize
    # False = 0 points
    
    # Response time bonus
    if probe.response_time_ms is not None:
        if probe.response_time_ms < 300:
            score += 15
        elif probe.response_time_ms < 1000:
            score += 10
        elif probe.response_time_ms < 3000:
            score += 5
    
    # Consistency bonus (for APIs we've checked before)
    if probe.previous_consecutive_successes >= 3:
        score += 5
    
    return min(score, 100)
```

**Score interpretation:**
| Score | Label | Meaning |
|---|---|---|
| 90–100 | Excellent | Fast, reliable, valid SSL |
| 70–89 | Good | Healthy, minor issues |
| 50–69 | Fair | Reachable but slow or SSL issues |
| 20–49 | Poor | Degraded, intermittent |
| 0–19 | Dead | Unreachable |

---

## 5. Status State Machine

```
         [DISCOVERY]
              │
              ▼
         [unknown] ──────────────────────────────┐
              │                                  │
              │ validation probe runs             │
              ▼                                  │
    ┌────────────────┐                           │
    │  active (≥50)  │◄──── probe succeeds ──────┤
    └────────┬───────┘                           │
             │                                   │
             │ probe fails once                  │
             ▼                                   │
    ┌────────────────┐                           │
    │   degraded     │◄── probe fails 1-2x ──────┤
    └────────┬───────┘                           │
             │                                   │
             │ probe fails 3+ times              │
             ▼                                   │
    ┌────────────────┐                           │
    │     dead       │                           │
    └────────┬───────┘                           │
             │                                   │
             │ retry after 3 days, recovers      │
             └───────────────────────────────────┘
```

---

## 6. Batch Validation

Validation runs as concurrent async probes:

```python
async def validate_batch(self, apis: list[API]) -> list[ProbeResult]:
    semaphore = asyncio.Semaphore(50)  # Max 50 concurrent probes
    
    async def probe_with_limit(api):
        async with semaphore:
            return await self.probe_api(api)
    
    results = await asyncio.gather(
        *[probe_with_limit(api) for api in apis],
        return_exceptions=True
    )
    
    return [r for r in results if not isinstance(r, Exception)]
```

**Throughput:** ~50 concurrent × 10s max = 5,000+ probes/hour

---

## 7. Dead API Handling

Dead APIs are NOT deleted. They are retained because:
- They may come back (maintenance, domain changes)
- Historical data is valuable
- Merge target if same API rediscovered later

Dead API retry schedule:
- After 1 day: retry (may have been temporary)
- After 3 days: retry
- After 7 days: retry
- After 30 days: retry (slow degradation)
- After 90 days: stop retrying, set `consecutive_failures=99`
- Keep record indefinitely but suppress from search results

---

## 8. SSL Expiry Alerts

When ssl_expiry is within 14 days:
- Log a warning in `api_health_log`
- Set health_score penalty (−10)
- Include in monitoring dashboard "expiring soon" list

This helps identify APIs that are about to break (often abandoned projects).
