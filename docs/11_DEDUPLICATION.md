# Deduplication Strategy
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## 1. Problem

The same API will be discovered from many sources:
- The OpenWeatherMap API appears in: public-apis repo, apis.guru, npm packages,
  GitHub READMEs, HackerNews posts, Reddit threads, and more.
- The same API may have slightly different names: "OpenWeather", "Open Weather Map",
  "OpenWeatherMap API", "OWM API"
- The same API may have different base URLs: `api.openweathermap.org`,
  `api.openweathermap.org/data/2.5`, `openweathermap.org/api`

Without deduplication, the database fills with hundreds of duplicate entries,
degrading search quality and wasting storage.

---

## 2. Deduplication Stages

Deduplication runs at two points:
1. **At ingest time** (per record, real-time) — catches most duplicates
2. **As a batch job** (weekly) — catches duplicates that slipped through

---

## 3. Match Criteria (In Priority Order)

### Level 1: Exact URL Match (Fastest)

```sql
SELECT id FROM apis
WHERE base_url = normalize_url($1)
LIMIT 1;
```

Catches: Same API discovered from two different sources with identical URL.
Frequency: ~70% of duplicates caught here.

### Level 2: Domain + Name Similarity

```sql
SELECT id FROM apis
WHERE
    -- Same registered domain (ignores subdomain differences)
    registered_domain(base_url) = registered_domain($1)
    AND
    -- Similar name (trigram similarity > 0.7)
    similarity(lower(name), lower($2)) > 0.7
LIMIT 1;
```

Where `registered_domain()` extracts the eTLD+1:
- `api.openweathermap.org` → `openweathermap.org`
- `v2.api.stripe.com` → `stripe.com`

Catches: Same API, version-different URLs. E.g.:
- `api.example.com/v1` vs `api.example.com/v2`
- `api.example.com` vs `developer.example.com`

### Level 3: Name Fingerprint Match

```python
def name_fingerprint(name: str) -> str:
    # Lowercase, remove common suffixes/prefixes, normalize spaces
    name = name.lower()
    for noise in ["api", "sdk", "rest", "http", "service", "public", "free", "-", "_", " "]:
        name = name.replace(noise, "")
    return name.strip()
```

```sql
SELECT id FROM apis
WHERE name_fingerprint(name) = name_fingerprint($1)
  AND name_fingerprint($1) != ''  -- Don't match empty fingerprints
LIMIT 1;
```

Catches: "Stripe API" vs "Stripe REST API" vs "Stripe SDK"

### Level 4: Semantic Match (Batch Only)

Run in the weekly dedup batch job — not at real-time ingest:

```sql
SELECT id, name, base_url,
       1 - (embedding <=> $1::vector) AS similarity
FROM apis
WHERE 1 - (embedding <=> $1::vector) > 0.95
  AND id != $2
ORDER BY similarity DESC
LIMIT 5;
```

Catches: Same API described very differently at source, missed by levels 1-3.
Requires manual review before merging (high similarity but not exact).

---

## 4. Merge Strategy

When a duplicate is found, merge into the existing record (never create new):

```python
def merge_records(existing: API, incoming: NormalizedRecord) -> APIUpdate:
    return APIUpdate(
        # Name: keep existing unless incoming is longer (more descriptive)
        name=existing.name if len(existing.name) >= len(incoming.name)
             else incoming.name,
        
        # Description: keep longer of the two
        description=max(
            [existing.description or "", incoming.description or ""],
            key=len
        ) or None,
        
        # Base URL: keep existing (first discovery is canonical)
        base_url=existing.base_url,
        
        # Docs URL: keep existing unless NULL
        docs_url=existing.docs_url or incoming.docs_url,
        
        # Spec URL: keep existing unless NULL
        spec_url=existing.spec_url or incoming.spec_url,
        
        # Auth type: update only if existing is 'unknown'
        auth_type=existing.auth_type
                  if existing.auth_type != 'unknown'
                  else incoming.auth_type,
        
        # Sources: always append
        source_names=list(set(existing.source_names + [incoming.source_name])),
        source_urls=list(set(existing.source_urls + [incoming.source_url or ""])),
        
        # Categories/tags: only update if currently empty
        categories=existing.categories or [],
        tags=existing.tags or [],
    )
```

---

## 5. Conflict Resolution Rules

| Field | Rule | Rationale |
|---|---|---|
| `base_url` | Keep earliest discovered | First is canonical |
| `name` | Keep longer | More descriptive usually wins |
| `description` | Keep longer | More content = better |
| `auth_type` | Prefer known over 'unknown' | Validated info wins |
| `docs_url` | Prefer non-null | Any link is better than none |
| `categories` | Keep existing if non-empty | LLM enrichment is idempotent |
| `health_score` | Keep latest from validation | Always current |
| `source_names` | Union of all | Preserve full provenance |

---

## 6. Batch Dedup Job

Weekly job to catch near-duplicates:

```python
async def run_batch_dedup(self):
    # 1. Find clusters of APIs with same registered domain
    clusters = await self.db.fetch_same_domain_clusters()
    
    for cluster in clusters:
        if len(cluster) <= 1:
            continue
        
        # 2. Within cluster, compute pairwise name similarity
        pairs = [
            (a, b, similarity(a.name, b.name))
            for a, b in itertools.combinations(cluster, 2)
        ]
        
        # 3. High-confidence auto-merge (similarity > 0.85)
        for a, b, score in pairs:
            if score > 0.85:
                await self.merge_into_primary(a, b)
        
        # 4. Medium-confidence candidates queued for review (0.6 < score < 0.85)
        candidates = [(a, b, score) for a, b, score in pairs
                      if 0.6 < score <= 0.85]
        if candidates:
            await self.queue_for_manual_review(candidates)
    
    # 5. Semantic similarity pass (embedding-based)
    # Find pairs with cosine similarity > 0.95 not already merged
    semantic_pairs = await self.db.find_semantic_near_duplicates(threshold=0.95)
    for a, b, sim in semantic_pairs:
        await self.queue_for_manual_review([(a, b, sim)])
```

---

## 7. URL Normalization for Matching

Before any URL comparison, normalize:

```python
def normalize_url_for_matching(url: str) -> str:
    parsed = urlparse(url.lower().strip())
    
    # Force scheme to https
    scheme = "https"
    
    # Strip www. prefix
    host = parsed.netloc.lstrip("www.")
    
    # Remove known version path components for matching
    # /v1/ /v2/ /api/ at root level
    path = re.sub(r'^/(v\d+|api|rest|public)/?$', '', parsed.path)
    
    # Remove trailing slash
    path = path.rstrip("/")
    
    # Remove port if standard (443 for https, 80 for http)
    if ":" in host:
        host_part, port = host.rsplit(":", 1)
        if port in ("443", "80"):
            host = host_part
    
    return urlunparse((scheme, host, path, "", "", ""))
```

---

## 8. Anti-Patterns to Avoid

**Do NOT merge:**
- Two APIs from the same company that do different things
  (e.g., Twilio SMS API and Twilio Voice API are different APIs)
- An API and its sandbox/test variant
  (api.stripe.com vs api.stripe.com — test mode is a flag, not a duplicate)
- An API and its documentation page
  (docs.example.com is not the same as api.example.com)

**Detection:** The name similarity threshold (0.7+) plus domain match prevents
most false merges. When names are clearly different, merge is blocked.

---

## 9. Dedup Metrics

```
apivault_dedup_exact_matches_total
apivault_dedup_domain_name_matches_total
apivault_dedup_fingerprint_matches_total
apivault_dedup_semantic_matches_total
apivault_dedup_manual_review_queue_size
apivault_dedup_merges_total
apivault_dedup_batch_job_duration_seconds
```
