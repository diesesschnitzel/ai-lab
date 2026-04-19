# Data Pipeline
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## 1. Pipeline Overview

Data moves through five sequential stages from raw discovery to searchable record:

```
[DISCOVERY]  →  [NORMALIZE]  →  [DEDUPLICATE]  →  [VALIDATE]  →  [ENRICH]
     ↓               ↓                ↓                ↓              ↓
raw_candidates   normalized        merged or         health        active
   (pending)      record           inserted          score         record
                                   to apis           set         with tags
                                   table                        + embedding
```

Each stage processes records from the database queue, updates status fields,
and either passes the record to the next stage or marks it as failed.

---

## 2. Stage 1: Discovery

**Input:** Scheduler trigger (time-based)
**Output:** Rows in `raw_candidates` with `status='pending'`
**Workers:** One process per scraper type, all independent
**Throughput target:** 10,000 candidates/hour total across all scrapers

```
Scraper.run()
    → yields RawCandidate objects
    → Runner writes each to raw_candidates (status=pending)
    → Runner writes to scraper_runs (audit log)
```

**Idempotency:** Scrapers re-insert the same candidates on each run. The normalizer
handles deduplication — raw_candidates is a queue, not a unique store.

---

## 3. Stage 2: Normalization

**Input:** `raw_candidates WHERE status='pending'`
**Output:** `raw_candidates.status='done'` + normalized record ready for dedup
**Worker:** `pipeline/normalizer.py`
**Batch size:** 500 records/cycle
**Throughput target:** 5,000 records/hour

### Normalization Steps

```python
class Normalizer:
    def normalize(self, raw: RawCandidate) -> NormalizedRecord:
        return NormalizedRecord(
            name=self.clean_name(raw.raw_name),
            description=self.clean_text(raw.raw_description),
            base_url=self.canonicalize_url(raw.raw_base_url),
            docs_url=self.canonicalize_url(raw.raw_docs_url),
            auth_type=self.normalize_auth(raw.raw_auth_type),
            format=self.detect_format(raw.raw_base_url, raw.raw_json),
            source_name=raw.source_name,
            source_url=raw.source_url,
            raw_json=raw.raw_json,
        )
```

### URL Canonicalization

```python
def canonicalize_url(self, url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url.strip())
    
    # Force HTTPS
    scheme = "https"
    
    # Lowercase host
    host = parsed.netloc.lower()
    
    # Remove trailing slash from path
    path = parsed.path.rstrip("/")
    
    # Remove common noise parameters
    # (tracking params, cache busters)
    
    return urlunparse((scheme, host, path, "", "", ""))
```

### Auth Type Normalization

```
Source value → Normalized value
"No"         → "none"
"no"         → "none"
"None"       → "none"
"apiKey"     → "apikey"
"API Key"    → "apikey"
"OAuth"      → "oauth2"
"OAuth2"     → "oauth2"
"Bearer"     → "bearer"
"Basic"      → "basic"
""           → "unknown"
None         → "unknown"
```

### Format Detection

```python
def detect_format(self, url: str, raw: dict) -> list[str]:
    formats = []
    url_lower = (url or "").lower()
    
    if "graphql" in url_lower or raw.get("graphql"):
        formats.append("GraphQL")
    if "grpc" in url_lower or raw.get("grpc"):
        formats.append("gRPC")
    if raw.get("openapi") or raw.get("swagger"):
        formats.append("REST")  # OpenAPI implies REST
    if "soap" in url_lower or raw.get("wsdl"):
        formats.append("SOAP")
    if not formats:
        formats.append("REST")  # Default assumption
    
    return formats
```

---

## 4. Stage 3: Deduplication

**Input:** Normalized record
**Output:** Either merged into existing `apis` row OR new `apis` row inserted
**Worker:** `pipeline/deduplicator.py`
**Key guarantee:** No two `apis` rows share the same canonical base_url

### Deduplication Algorithm

```
GIVEN: normalized record N

STEP 1: Exact URL match
    SELECT id FROM apis WHERE base_url = N.base_url
    → FOUND: merge (update fields, append source_names, source_urls)
    → NOT FOUND: proceed to step 2

STEP 2: Domain match + similar name
    SELECT id FROM apis
    WHERE host(base_url::inet) = host(N.base_url::inet)
      AND similarity(name, N.name) > 0.8
    → FOUND: merge
    → NOT FOUND: proceed to step 3

STEP 3: Name fingerprint match
    fingerprint = normalize_name(N.name)
    SELECT id FROM apis
    WHERE normalize_name(name) = fingerprint
    → FOUND: merge (same API, different URL variant)
    → NOT FOUND: INSERT new record

MERGE strategy:
    - base_url: keep existing (first seen)
    - name: keep existing unless new is longer/better
    - description: keep longer of the two
    - source_names: ARRAY_APPEND
    - source_urls: ARRAY_APPEND
    - auth_type: update if existing is 'unknown' and new is known
    - all other fields: keep existing unless NULL
```

See `docs/11_DEDUPLICATION.md` for full strategy including edge cases.

---

## 5. Stage 4: Validation

**Input:** `apis WHERE status='pending_validation'` OR `last_checked < now() - 7 days`
**Output:** Updated `apis` record with health data + new `api_health_log` row
**Worker:** `validators/prober.py`
**Batch size:** 50 concurrent probes (async)
**Throughput target:** 5,000 APIs/hour

### Probe Sequence

```
For each API:
    1. DNS resolution check (1s timeout)
       → FAIL: status=dead, continue to next
    
    2. HTTP GET base_url (5s timeout)
       → record: http_status, response_time_ms, headers
    
    3. SSL check (if HTTPS)
       → record: ssl_valid, ssl_expiry
    
    4. Auth type detection from response
       → 200: auth_type=none (if we got a valid response)
       → 401: auth_type=bearer or basic (check WWW-Authenticate header)
       → 403: auth_type=apikey (check error body)
       → record detected auth_type
    
    5. Rate limit header extraction
       → check: X-RateLimit-Limit, X-RateLimit-Remaining,
                RateLimit-Limit, Retry-After, X-Rate-Limit
       → record rate_limit string
    
    6. Compute health_score (0-100)
       → dns_resolves: +30
       → http_status 2xx: +30
       → http_status 3xx: +20
       → ssl_valid: +20
       → response_time < 1000ms: +10
       → response_time < 500ms: +10
    
    7. Update apis record
    8. Insert api_health_log row
```

### Status Assignment

```
dns_resolves=False:              status=dead
http_status=0 (no response):    status=dead (increment consecutive_failures)
http_status 5xx:                 status=degraded (increment consecutive_failures)
http_status 2xx or 3xx or 4xx:  status=active (reset consecutive_failures=0)

consecutive_failures >= 3:       status=dead
```

---

## 6. Stage 5: Enrichment

**Input:** `apis WHERE enriched_at IS NULL AND status != 'dead'`
**Output:** Updated `apis` record with LLM-generated fields + embedding
**Worker:** `enrichment/enricher.py`
**Batch size:** 20 APIs per LLM call (batch API)
**Throughput target:** 1,000 APIs/hour (limited by LLM rate limits)

### Enrichment Steps

```
For each unenriched API:
    1. Assemble context:
       - name, description, base_url, auth_type, categories (if any)
       - Fetch docs_url page if available (extract text, truncate to 500 chars)
    
    2. LLM call (classify + describe):
       - Input: context
       - Output: categories[], tags[], use_cases[], description_llm
       - See docs/10_ENRICHMENT.md for full prompt
    
    3. Embedding generation:
       - Input: name + description_llm + tags joined as text
       - Output: vector(1536)
       - Model: nomic-embed-text (local) or text-embedding-3-small (OpenAI)
    
    4. Update apis record:
       - categories, tags, use_cases, description_llm
       - embedding, embedding_model
       - enriched_at = now()
```

---

## 7. Pipeline Worker

The pipeline worker polls the database and dispatches work:

```python
# src/pipeline/worker.py

class PipelineWorker:
    async def run_forever(self):
        while True:
            # Process normalization queue
            pending = await self.db.get_pending_candidates(limit=500)
            if pending:
                await self.process_normalization_batch(pending)
            
            # Process validation queue
            due = await self.db.get_apis_due_for_validation(limit=50)
            if due:
                await asyncio.gather(*[self.validate_api(api) for api in due])
            
            # Process enrichment queue
            unenriched = await self.db.get_unenriched_apis(limit=20)
            if unenriched:
                await self.enrich_batch(unenriched)
            
            # Sleep between cycles
            await asyncio.sleep(30)
```

---

## 8. Error Recovery

| Failure Point | Recovery |
|---|---|
| Scraper crashes | Scraper run logged as `failed`; other scrapers unaffected |
| Normalization fails | `raw_candidates.status='failed'`, error recorded; retried next cycle |
| Validation probe fails | Increment `consecutive_failures`; retry after 24h up to 3 times |
| Enrichment LLM fails | Log error, skip record, retry next enrichment cycle |
| DB write fails | Retry 3x with exponential backoff; alert if all fail |

---

## 9. Pipeline Monitoring

Key metrics emitted (Prometheus format):

```
apivault_raw_candidates_pending_total
apivault_raw_candidates_processed_per_hour
apivault_apis_pending_validation_total
apivault_apis_validated_per_hour
apivault_apis_pending_enrichment_total
apivault_apis_enriched_per_hour
apivault_pipeline_stage_duration_seconds{stage="normalize|dedup|validate|enrich"}
apivault_scraper_last_run_timestamp{scraper="..."}
apivault_scraper_candidates_found{scraper="..."}
```

See `docs/18_MONITORING.md` for full metrics list and alerting rules.
