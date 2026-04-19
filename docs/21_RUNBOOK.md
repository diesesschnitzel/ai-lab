# Operations Runbook
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## Daily Checks

### Morning Checklist (5 minutes)

```bash
# 1. Check all services are running
docker compose ps

# Expected: db, api, worker, scheduler all "Up"
# Action if down: docker compose up -d <service>

# 2. Check API health
curl http://localhost:8000/health

# Expected: {"status": "ok", ...}
# Action if degraded: check docker compose logs api

# 3. Check stats
curl http://localhost:8000/stats | jq .

# Watch for:
# - active_apis declining (may indicate validation issue)
# - last_scraped more than 6h ago (scraper may have failed)

# 4. Check validation queue depth
docker compose exec db psql -U apivault -c \
  "SELECT count(*) FROM apis WHERE status='pending_validation';"
# Alert if > 10,000
```

---

## Weekly Checks

```bash
# 1. Check scraper run history (past 7 days)
docker compose exec db psql -U apivault -c "
SELECT scraper_name, count(*), max(started_at) as last_run,
       avg(candidates_found) as avg_yield, sum(candidates_new) as new_apis
FROM scraper_runs
WHERE started_at > now() - interval '7 days'
GROUP BY 1 ORDER BY last_run DESC;"

# 2. Check dead API count trend
docker compose exec db psql -U apivault -c "
SELECT date_trunc('day', last_checked) as day,
       count(*) filter (where status='dead') as dead,
       count(*) filter (where status='active') as active
FROM apis
WHERE last_checked > now() - interval '7 days'
GROUP BY 1 ORDER BY 1;"

# 3. Refresh materialized views
docker compose exec db psql -U apivault -c \
  "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_category_counts;"

# 4. Check disk usage
docker compose exec db psql -U apivault -c \
  "SELECT pg_size_pretty(pg_database_size('apivault'));"
df -h /var/lib/docker/volumes/

# 5. Run database VACUUM ANALYZE
docker compose exec db psql -U apivault -c "VACUUM ANALYZE apis;"
docker compose exec db psql -U apivault -c "VACUUM ANALYZE raw_candidates;"
```

---

## Monthly Maintenance

```bash
# 1. Archive old health log entries (>90 days)
docker compose exec db psql -U apivault -c "
DELETE FROM api_health_log
WHERE checked_at < now() - interval '90 days';"

# 2. Archive old raw candidates (>30 days, done/failed)
docker compose exec db psql -U apivault -c "
DELETE FROM raw_candidates
WHERE discovered_at < now() - interval '30 days'
AND status IN ('done', 'failed', 'dead_letter');"

# 3. Archive old scraper_runs (>90 days)
docker compose exec db psql -U apivault -c "
DELETE FROM scraper_runs
WHERE started_at < now() - interval '90 days';"

# 4. Rebuild pgvector index (if >20% new records since last build)
docker compose exec db psql -U apivault -c \
  "REINDEX INDEX CONCURRENTLY idx_apis_embedding;"

# 5. Backup database
docker compose exec db pg_dump -U apivault -Fc apivault > \
  backup_$(date +%Y%m%d).dump

# 6. Check for dependency updates
docker compose run --rm api uv run pip-audit
```

---

## Incident Procedures

### API is returning 503

```bash
# 1. Check if API container is running
docker compose ps api
# If not running: docker compose up -d api

# 2. Check API logs for error
docker compose logs api --since=1h

# 3. Check if database is reachable
docker compose exec api python -c "
import asyncio, asyncpg, os
async def test():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    print(await conn.fetchval('SELECT 1'))
asyncio.run(test())"

# 4. Check resource usage
docker stats --no-stream

# 5. Restart API (rolling, zero downtime if multiple replicas)
docker compose up -d --no-deps api
```

### Scraper not running / stale data

```bash
# 1. Check scheduler logs
docker compose logs scheduler --since=24h | grep ERROR

# 2. Check last scraper runs
docker compose exec db psql -U apivault -c "
SELECT scraper_name, status, started_at, error
FROM scraper_runs
ORDER BY started_at DESC LIMIT 20;"

# 3. Manually trigger a scraper
docker compose exec scheduler python -m src.scheduler.run_scraper public_apis_github

# 4. If scheduler container crashed, restart it
docker compose up -d --no-deps scheduler
```

### Validation queue backup (>10k pending)

```bash
# Check current queue
docker compose exec db psql -U apivault -c \
  "SELECT count(*) FROM apis WHERE status='pending_validation';"

# Check if validator is running
docker compose logs worker --since=1h | grep "validator"

# Temporarily increase validation concurrency
# Edit .env: VALIDATION_CONCURRENCY=100
docker compose up -d --no-deps worker

# Or manually trigger validation batch
docker compose exec worker python -m src.validators.run_batch --limit 5000
```

### Database disk nearly full (>80%)

```bash
# 1. Check what's taking space
docker compose exec db psql -U apivault -c "
SELECT
    relname,
    pg_size_pretty(pg_total_relation_size(relid)) as total_size,
    pg_size_pretty(pg_relation_size(relid)) as table_size,
    pg_size_pretty(pg_total_relation_size(relid) - pg_relation_size(relid)) as index_size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;"

# 2. Immediate cleanup: archive health log
docker compose exec db psql -U apivault -c "
DELETE FROM api_health_log WHERE checked_at < now() - interval '30 days';"

# 3. Archive raw candidates
docker compose exec db psql -U apivault -c "
DELETE FROM raw_candidates
WHERE discovered_at < now() - interval '14 days'
AND status IN ('done', 'failed');"

# 4. Run VACUUM to reclaim space
docker compose exec db psql -U apivault -c "VACUUM FULL api_health_log;"
# Note: VACUUM FULL locks the table. Run during low-traffic window.

# 5. If still critical: resize the disk volume
```

### LLM enrichment stopped working

```bash
# Check enrichment queue
docker compose exec db psql -U apivault -c \
  "SELECT count(*) FROM apis WHERE enriched_at IS NULL AND status != 'dead';"

# Check enrichment worker logs
docker compose logs worker --since=2h | grep "enrichment"

# If using Ollama: check Ollama is running
curl http://localhost:11434/api/tags

# If using Claude API: check API key is valid
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $CLAUDE_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-haiku-4-5-20251001","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}'

# Fallback: switch to rule-based enrichment temporarily
# Edit .env: LLM_BACKEND=none
docker compose up -d --no-deps worker

# This uses keyword-based categorization without LLM
# Lower quality but keeps the queue moving
```

---

## Useful Queries

### Find APIs with no enrichment
```sql
SELECT count(*) FROM apis WHERE enriched_at IS NULL AND status != 'dead';
```

### Top sources by unique APIs contributed
```sql
SELECT unnest(source_names) as source, count(*) as apis
FROM apis GROUP BY 1 ORDER BY 2 DESC LIMIT 20;
```

### APIs dying fastest (most frequent failures)
```sql
SELECT a.name, a.base_url, a.consecutive_failures, a.last_checked
FROM apis a
WHERE a.status = 'dead'
ORDER BY a.consecutive_failures DESC LIMIT 20;
```

### Search performance check
```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, name, ts_rank(fts, query) rank
FROM apis, plainto_tsquery('english', 'weather forecast') query
WHERE fts @@ query AND status = 'active'
ORDER BY rank DESC LIMIT 20;
```

### Find duplicate base URLs
```sql
SELECT base_url, count(*), array_agg(id) as ids
FROM apis
GROUP BY base_url
HAVING count(*) > 1;
```

### Category coverage gaps
```sql
SELECT c.category, coalesce(counts.api_count, 0) as api_count
FROM (VALUES
    ('Weather & Environment > Current Weather'),
    ('Geographic & Location > Mapping'),
    -- ... all expected categories
) c(category)
LEFT JOIN mv_category_counts counts USING (category)
ORDER BY api_count ASC;
```

---

## Log Locations

| Service | Log command |
|---|---|
| API | `docker compose logs api` |
| Worker | `docker compose logs worker` |
| Scheduler | `docker compose logs scheduler` |
| Database | `docker compose logs db` |
| All services | `docker compose logs -f` |

---

## Configuration Changes

When changing `.env`:
1. Edit `.env`
2. Restart affected services: `docker compose up -d --no-deps <service>`
3. Verify: `docker compose logs <service> --since=2m`

**Never restart all services at once** if traffic is active — restart
`worker`, `scheduler`, and `api` one at a time.
