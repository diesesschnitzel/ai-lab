# Error Handling
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## 1. Design Philosophy

- **Fail gracefully** — one broken scraper never brings down the whole system
- **Never lose work** — failed records are retryable, not discarded
- **Be transparent** — all failures are logged with context
- **Retry intelligently** — exponential backoff, not hammering
- **Alert on patterns** — a single failure is noise; persistent failure is a signal

---

## 2. Error Categories

| Category | Examples | Behavior |
|---|---|---|
| Transient network | Timeout, connection refused, DNS failure | Retry with backoff |
| Rate limited | 429 Too Many Requests | Back off, respect Retry-After |
| Scraper-side bug | Parse error, unexpected format | Log, skip record, continue |
| Target API changed | Source format changed, auth now required | Log warning, mark for review |
| LLM failure | API error, bad JSON response | Retry once; fallback to rule-based |
| Database error | Connection pool exhausted, deadlock | Retry 3x; alert if persistent |
| Configuration error | Missing env var, bad URL | Fail fast at startup, clear message |

---

## 3. Retry Strategy

### HTTP Retries (Scrapers)

```python
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}

async def fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    max_retries: int = 3,
) -> httpx.Response:
    for attempt in range(max_retries + 1):
        try:
            response = await client.get(url)
            
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                await asyncio.sleep(retry_after)
                continue
            
            if response.status_code in RETRY_STATUS_CODES and attempt < max_retries:
                wait = 2 ** attempt  # 1s, 2s, 4s
                await asyncio.sleep(wait)
                continue
            
            return response
            
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt == max_retries:
                raise
            wait = 2 ** attempt
            log.warning(f"Request failed (attempt {attempt+1}), retrying in {wait}s", error=str(e))
            await asyncio.sleep(wait)
```

### Database Retries

```python
async def execute_with_retry(db, query, *args, max_retries=3):
    for attempt in range(max_retries + 1):
        try:
            return await db.execute(query, *args)
        except asyncpg.TooManyConnectionsError:
            if attempt == max_retries:
                raise
            await asyncio.sleep(2 ** attempt)
        except asyncpg.DeadlockDetectedError:
            if attempt == max_retries:
                raise
            await asyncio.sleep(0.1 * (attempt + 1))  # Short backoff for deadlocks
```

---

## 4. Scraper Error Handling

Scrapers must handle their own errors and continue. A scraper should never
crash the runner due to bad data:

```python
async def run(self) -> AsyncIterator[RawCandidate]:
    pages = await self.get_page_count()
    
    for page in range(1, pages + 1):
        try:
            data = await self.fetch_page(page)
        except httpx.TimeoutException:
            log.warning("Timeout fetching page", page=page, scraper=self.name)
            continue  # Skip this page, try the next
        except Exception as e:
            log.error("Unexpected error fetching page", page=page, error=str(e))
            continue
        
        for item in data.get("items", []):
            try:
                yield self.parse_item(item)
            except (KeyError, ValueError, AttributeError) as e:
                log.warning("Failed to parse item", item=str(item)[:100], error=str(e))
                # Continue — don't let one bad record abort the whole run
```

---

## 5. Pipeline Error States

Each database record has a status field that tracks error states:

### raw_candidates

```
pending     → normalizer picks up
processing  → normalizer working
done        → normalized and sent to dedup
failed      → normalization error (retryable after 1h)
```

Failed raw_candidates are retried by the normalizer after a delay.
After 5 failures, they are archived and an alert fires.

### apis

```
unknown              → not yet validated
pending_validation   → queued for validation
active               → healthy
degraded             → reachable but errors
dead                 → unreachable (consecutive_failures >= 3)
```

---

## 6. LLM Failure Handling

The enrichment pipeline must handle LLM failures without blocking the queue:

```python
async def enrich_api(self, api: API) -> EnrichmentResult:
    try:
        context = await self.assemble_context(api)
        result = await asyncio.wait_for(
            self.llm_client.classify(context),
            timeout=60.0
        )
        return self.validate_enrichment(result)
    
    except asyncio.TimeoutError:
        log.warning("LLM timeout", api_id=str(api.id))
        # Try once more with a shorter context
        try:
            result = await self.llm_client.classify_minimal(api.name, api.description)
            return self.validate_enrichment(result)
        except Exception:
            return self.rule_based_enrich(api)  # Final fallback
    
    except json.JSONDecodeError:
        log.warning("LLM returned invalid JSON", api_id=str(api.id))
        return self.rule_based_enrich(api)
    
    except Exception as e:
        log.error("LLM enrichment failed", api_id=str(api.id), error=str(e))
        return self.rule_based_enrich(api)
```

Rule-based enrichment (no LLM) is always available as a fallback.
It produces lower quality tags but ensures the enrichment queue never blocks.

---

## 7. Validation Error Handling

```python
async def probe_api(self, api: API) -> ProbeResult:
    result = ProbeResult(api_id=api.id)
    
    # DNS — catch all exceptions, mark result
    try:
        dns = await asyncio.wait_for(check_dns(api.base_url), timeout=3.0)
        result.dns_resolves = dns.resolves
    except asyncio.TimeoutError:
        result.dns_resolves = False
        result.error = "dns_timeout"
    except Exception as e:
        result.dns_resolves = False
        result.error = f"dns_error: {type(e).__name__}"
    
    # If DNS fails, stop here
    if not result.dns_resolves:
        result.status = "dead"
        await self.save_probe_result(result)
        return result
    
    # HTTP — multiple fallback endpoints
    for url in self.probe_urls(api):
        try:
            http = await asyncio.wait_for(
                self.client.get(url),
                timeout=15.0
            )
            result.http_status = http.status_code
            result.response_time_ms = http.elapsed_ms
            result.headers = dict(http.headers)
            break  # Got a response, stop trying
        except asyncio.TimeoutError:
            continue
        except Exception:
            continue
    
    result.status = self.compute_status(result)
    result.health_score = compute_health_score(result)
    await self.save_probe_result(result)
    return result
```

Key principle: validation **never throws**. It catches everything and records
the error state. A crashed validation would leave APIs stuck in `pending_validation`.

---

## 8. Scheduler Error Handling

If a scheduled job crashes:

```python
async def run_job_safely(job_func, job_name: str):
    try:
        await asyncio.wait_for(job_func(), timeout=JOB_TIMEOUTS[job_name])
    except asyncio.TimeoutError:
        log.error(f"Job {job_name} timed out")
        metrics.increment(f"scheduler.job.timeout", tags={"job": job_name})
    except Exception as e:
        log.error(f"Job {job_name} failed", error=str(e), exc_info=True)
        metrics.increment(f"scheduler.job.error", tags={"job": job_name})
    # Always continue to next scheduled job
```

Jobs are independent. A failing job does not cancel subsequent jobs.

---

## 9. Startup Error Handling

On startup, fail fast with clear messages for configuration errors:

```python
def validate_config():
    errors = []
    
    if not settings.DATABASE_URL:
        errors.append("DATABASE_URL is required")
    
    if settings.LLM_BACKEND == "claude" and not settings.CLAUDE_API_KEY:
        errors.append("CLAUDE_API_KEY required when LLM_BACKEND=claude")
    
    if settings.LLM_BACKEND == "ollama":
        # Check Ollama is reachable
        try:
            httpx.get(f"{settings.OLLAMA_URL}/api/tags", timeout=5)
        except Exception:
            errors.append(f"Ollama not reachable at {settings.OLLAMA_URL}")
    
    if errors:
        for e in errors:
            print(f"[CONFIG ERROR] {e}", file=sys.stderr)
        sys.exit(1)
```

---

## 10. Dead Letter Queue

Raw candidates that repeatedly fail normalization are moved to a "dead letter" state:

```sql
-- Mark as permanently failed after 5 retries
UPDATE raw_candidates
SET status = 'dead_letter',
    error = 'Max retries exceeded: ' || error
WHERE status = 'failed'
  AND retry_count >= 5;
```

Dead letter records are:
- Kept for 30 days for debugging
- Included in daily admin digest email
- Cleared in monthly maintenance job

---

## 11. Circuit Breaker for External APIs

For frequently-failing external sources, use a circuit breaker:

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=300):
        self.failures = 0
        self.threshold = failure_threshold
        self.last_failure_time = None
        self.state = "closed"  # closed=normal, open=blocking, half-open=testing
    
    async def call(self, func, *args):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
            else:
                raise CircuitOpenError(f"Circuit open, skipping call")
        
        try:
            result = await func(*args)
            if self.state == "half-open":
                self.state = "closed"
                self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.threshold:
                self.state = "open"
                log.warning(f"Circuit breaker opened after {self.failures} failures")
            raise
```

Applied to: cert transparency DB connection, external API directories.
