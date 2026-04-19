# Performance & Scalability
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## 1. Performance Targets

| Operation | P50 | P95 | P99 | Throughput |
|---|---|---|---|---|
| Keyword search | 15ms | 40ms | 100ms | 100 req/s |
| Semantic search | 100ms | 300ms | 500ms | 20 req/s |
| API detail GET | 5ms | 15ms | 30ms | 200 req/s |
| Category browse | 10ms | 25ms | 50ms | 100 req/s |
| Validation probe | 200ms | 2s | 5s | 5,000/hour |
| Normalization | 1ms | 5ms | 10ms | 10,000/hour |
| LLM enrichment | 2s | 5s | 10s | 1,000/hour |

---

## 2. Database Performance

### Query Analysis

The two most performance-critical queries are keyword and semantic search.

**Keyword search plan:**

```sql
EXPLAIN ANALYZE
SELECT id, name, description_llm, base_url, auth_type,
       ts_rank(fts, query) AS rank
FROM apis, to_tsquery('english', 'weather & forecast') query
WHERE fts @@ query
  AND status = 'active'
ORDER BY rank DESC
LIMIT 20;
```

Expected plan:
```
Limit (cost=...)
  -> Sort (cost=...)
    -> Bitmap Heap Scan on apis (cost=...)
       Recheck Cond: (fts @@ query)
       Filter: (status = 'active')
       -> Bitmap Index Scan on idx_apis_fts
```

The `idx_apis_fts` GIN index makes this O(log n) for term lookup.
At 90k APIs, expect <20ms.

**Semantic search plan:**

```sql
EXPLAIN ANALYZE
SELECT id, name, description_llm,
       1 - (embedding <=> $1::vector) AS similarity
FROM apis
WHERE status = 'active'
ORDER BY embedding <=> $1::vector
LIMIT 20;
```

Expected plan (with IVFFlat index):
```
Limit
  -> Index Scan using idx_apis_embedding on apis
     Order By: (embedding <=> $1)
```

IVFFlat with `lists=200` gives ~95% recall with ~10ms scan at 90k vectors.

### Index Maintenance

IVFFlat performance degrades when the index is stale relative to table data.
Rebuild when >20% new records since last build:

```sql
-- Check staleness
SELECT reltuples::bigint as indexed_rows,
       (SELECT count(*) FROM apis WHERE embedding IS NOT NULL) as actual_rows
FROM pg_class WHERE relname = 'idx_apis_embedding';

-- Rebuild if needed (takes ~30s at 90k rows, API stays up)
REINDEX INDEX CONCURRENTLY idx_apis_embedding;
```

Automate: trigger rebuild in the weekly maintenance job when staleness > 20%.

### Vacuum & Statistics

```sql
-- Run manually after bulk inserts
VACUUM ANALYZE apis;
VACUUM ANALYZE raw_candidates;

-- Ensure autovacuum is aggressive enough
ALTER TABLE apis SET (
    autovacuum_vacuum_scale_factor = 0.05,   -- vacuum when 5% dead
    autovacuum_analyze_scale_factor = 0.02   -- analyze when 2% changed
);
```

---

## 3. Connection Pooling

Use PgBouncer for connection multiplexing between many async workers:

```ini
# pgbouncer.ini
[databases]
apivault = host=db port=5432 dbname=apivault

[pgbouncer]
pool_mode = transaction          # Transaction-level pooling
max_client_conn = 200            # Max connections from app
default_pool_size = 20           # Actual PostgreSQL connections
min_pool_size = 5
server_idle_timeout = 600
```

Or use application-level pooling via asyncpg:

```python
pool = await asyncpg.create_pool(
    DATABASE_URL,
    min_size=2,
    max_size=20,
    command_timeout=30,
)
```

---

## 4. Caching

### Materialized View Caching

The `mv_category_counts` materialized view is refreshed every 6 hours:

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_category_counts;
```

`CONCURRENTLY` means no lock during refresh — the API continues to serve
the old view until the new one is ready.

### Application-Level Caching

For the `/categories` and `/stats` endpoints (rarely changing data):

```python
from functools import lru_cache
import time

class TTLCache:
    def __init__(self, ttl_seconds: int):
        self._cache = {}
        self._ttl = ttl_seconds
    
    def get(self, key):
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.time() < expiry:
                return value
        return None
    
    def set(self, key, value):
        self._cache[key] = (value, time.time() + self._ttl)

category_cache = TTLCache(ttl_seconds=3600)  # Cache for 1 hour
stats_cache = TTLCache(ttl_seconds=300)      # Cache for 5 minutes
```

### Query Result Cache

For repeated identical searches (common queries like "weather api"):

```python
# Simple in-memory LRU cache for hot searches
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_keyword_search(query: str, auth_type: str, page: int) -> dict:
    # Cache up to 1000 unique query combinations
    # Evicts LRU entries automatically
    ...
```

Cache TTL: 5 minutes for search results (balance freshness vs. performance).

---

## 5. Async I/O

All scraping and validation is async. Critical for throughput:

```python
# GOOD: 50 concurrent probes, total time ≈ slowest probe
async def validate_batch(apis: list[API]):
    semaphore = asyncio.Semaphore(50)
    async def probe(api):
        async with semaphore:
            return await probe_api(api)
    return await asyncio.gather(*[probe(api) for api in apis])

# BAD: 50 sequential probes, total time ≈ 50 × average probe time
for api in apis:
    await probe_api(api)
```

With 50 concurrent probes at 200ms average: 
- Sequential: 50 × 200ms = 10 seconds
- Concurrent: ~200ms

---

## 6. Batch Operations

Database writes should be batched:

```python
# GOOD: single multi-row INSERT
await db.executemany(
    "INSERT INTO raw_candidates (source_name, raw_base_url, ...) VALUES ($1, $2, ...)",
    [(c.source_name, c.raw_base_url, ...) for c in candidates]
)

# BAD: N individual INSERTs
for c in candidates:
    await db.execute("INSERT INTO raw_candidates ...", c.source_name, ...)
```

Batch size: 500 rows per INSERT for optimal performance.

---

## 7. Scaling Thresholds

### When to Scale Database

| Symptom | Threshold | Action |
|---|---|---|
| Query latency P99 | >500ms sustained | Add read replica |
| DB CPU | >70% sustained | Tune queries, add indexes |
| DB RAM | >80% | Increase `shared_buffers`, upgrade machine |
| Disk IOPS | >80% capacity | Move to NVMe SSD |
| Connection pool exhaustion | >90% pool used | Increase pool size or add PgBouncer |

### When to Scale Workers

| Symptom | Threshold | Action |
|---|---|---|
| Validation queue > 10k | Sustained | Add validation worker instances |
| Enrichment queue > 5k | Sustained | Increase LLM parallelism |
| Normalization queue > 50k | Sustained | Add pipeline worker |

### When to Scale API

| Symptom | Threshold | Action |
|---|---|---|
| API P99 latency > 1s | Sustained | Add uvicorn workers |
| CPU > 80% on API host | Sustained | Add API instances behind load balancer |

---

## 8. Performance Benchmarks

Run before major releases:

```bash
# Install: pip install locust

# locustfile.py test scenarios:
# - 70% keyword search (most common)
# - 20% API detail lookups
# - 5% semantic search
# - 5% category browse

locust --headless -u 100 -r 10 --run-time 60s
# Target: 0% failure rate, P99 < 500ms at 100 concurrent users
```

---

## 9. pgvector Index Strategy

IVFFlat vs HNSW trade-off:

| Index | Build Time | Search Time | Recall | Memory |
|---|---|---|---|---|
| None (exact scan) | 0 | O(n) | 100% | Low |
| IVFFlat lists=100 | Fast | Fast | ~95% | Low |
| IVFFlat lists=200 | Medium | Medium | ~97% | Medium |
| HNSW m=16 | Slow | Very fast | ~99% | High |

**Recommendation:**
- Up to 100k APIs: IVFFlat with lists=200 (good balance)
- Above 100k APIs: Switch to HNSW for better recall
- During bulk inserts: Drop index, insert, rebuild (faster than incremental)

```sql
-- Switch to HNSW at scale
DROP INDEX idx_apis_embedding;
CREATE INDEX idx_apis_embedding_hnsw ON apis
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
-- ef_search setting at query time:
SET hnsw.ef_search = 100;
```
