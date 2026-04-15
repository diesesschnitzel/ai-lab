# Monitoring & Observability
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## 1. Overview

Three pillars of observability:
- **Metrics** — Prometheus counters/gauges/histograms, scraped by Prometheus
- **Logs** — Structured JSON logs, written to stdout, collected by Docker
- **Alerts** — Prometheus alerting rules, sent via Alertmanager

---

## 2. Prometheus Metrics

Metrics are exposed at `http://localhost:9000/metrics` (configurable).

### Database Metrics

```
# Gauge: current size of each queue
apivault_raw_candidates_pending_total
apivault_apis_pending_validation_total
apivault_apis_pending_enrichment_total
apivault_dedup_manual_review_queue_size

# Gauge: API counts by status and auth
apivault_apis_total{status="active|dead|unknown|degraded"}
apivault_apis_by_auth_total{auth_type="none|apikey|oauth2|..."}
apivault_apis_by_category_total{category="..."}

# Gauge: database health
apivault_db_size_bytes
apivault_db_connections_active
apivault_db_connections_idle
```

### Pipeline Metrics

```
# Counter: records processed
apivault_candidates_processed_total{result="normalized|failed|duplicate"}
apivault_apis_validated_total{result="alive|dead|degraded|error"}
apivault_apis_enriched_total{model="ollama|claude|openai|rule_based"}

# Histogram: processing durations
apivault_normalization_duration_seconds
apivault_validation_duration_seconds
apivault_enrichment_duration_seconds

# Gauge: pipeline throughput (rolling 1h)
apivault_candidates_per_hour
apivault_validations_per_hour
apivault_enrichments_per_hour
```

### Scraper Metrics

```
# Counter: scraper runs by outcome
apivault_scraper_runs_total{scraper="...", status="success|failed|timeout"}
apivault_scraper_candidates_found_total{scraper="..."}
apivault_scraper_candidates_new_total{scraper="..."}

# Gauge: time since last successful run (staleness)
apivault_scraper_last_success_age_seconds{scraper="..."}

# Histogram: scraper run durations
apivault_scraper_duration_seconds{scraper="..."}
```

### API Server Metrics

```
# Standard HTTP metrics (from FastAPI middleware)
http_requests_total{method, path, status_code}
http_request_duration_seconds{method, path}
http_requests_in_progress{method, path}

# Search-specific
apivault_search_queries_total{type="keyword|semantic"}
apivault_search_results_empty_total{type="keyword|semantic"}
apivault_search_duration_seconds{type="keyword|semantic"}
```

### Health Check Metrics

```
# Gauge: overall API ecosystem health
apivault_ecosystem_alive_pct       # % of indexed APIs currently alive
apivault_ecosystem_avg_health_score
apivault_ecosystem_ssl_expiring_soon_count  # APIs with SSL expiring <14 days

# Gauge: validation freshness
apivault_validation_overdue_count  # APIs not checked in >7 days
```

---

## 3. Key Dashboards (Grafana)

### Dashboard 1: System Overview

Panels:
- Total APIs indexed (gauge, big number)
- Active / Dead / Unknown breakdown (pie chart)
- No-auth APIs count (big number, key metric)
- Validation queue depth (time series)
- Enrichment queue depth (time series)
- APIs added last 24h / 7d / 30d (stat panel)

### Dashboard 2: Pipeline Health

Panels:
- Pipeline throughput: candidates/hour, validations/hour, enrichments/hour
- Queue depths over time (stacked area chart)
- Processing error rate (time series)
- Stage durations p50/p95 (time series)
- LLM call latency and cost (if using paid LLM)

### Dashboard 3: Scraper Activity

Panels:
- Last run time for each scraper (table with green/yellow/red staleness)
- Candidates found per scraper (bar chart)
- New APIs discovered per scraper (bar chart, total + last 7d)
- Scraper error log (table)
- Source distribution of current database (pie chart)

### Dashboard 4: API Server Performance

Panels:
- Request rate (req/sec) time series
- Error rate (5xx) time series
- P50/P95/P99 latency by endpoint
- Rate-limited requests count
- Most common search queries (table)
- Zero-result searches (indicator of gaps in coverage)

### Dashboard 5: API Ecosystem Health

Panels:
- % of indexed APIs alive over time
- APIs going dead over time (daily)
- SSL certificate expiry calendar heatmap
- Health score distribution (histogram)
- Category coverage (how many APIs per category)

---

## 4. Alerting Rules

```yaml
# docker/prometheus/alerts.yml

groups:
  - name: apivault_pipeline
    rules:

      - alert: PipelineWorkerDown
        expr: up{job="apivault_worker"} == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Pipeline worker is down"
          description: "No metrics from worker for 5 minutes"

      - alert: ValidationQueueBacklog
        expr: apivault_apis_pending_validation_total > 5000
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Large validation backlog"
          description: "{{ $value }} APIs waiting for validation"

      - alert: ScraperStale
        expr: apivault_scraper_last_success_age_seconds > 86400  # 24 hours
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Scraper {{ $labels.scraper }} hasn't run in 24h"

      - alert: HighErrorRate
        expr: rate(http_requests_total{status_code=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High API error rate: {{ $value }} errors/sec"

      - alert: DatabaseDown
        expr: pg_up == 0
        for: 1m
        labels:
          severity: critical

      - alert: APIEcosystemHealthDrop
        expr: apivault_ecosystem_alive_pct < 0.70
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Less than 70% of indexed APIs are alive"
          description: "Possible mass scraping issue or network problem"

      - alert: SSLExpiringBatch
        expr: apivault_ecosystem_ssl_expiring_soon_count > 100
        for: 6h
        labels:
          severity: info
        annotations:
          summary: "{{ $value }} APIs have SSL expiring within 14 days"
```

---

## 5. Structured Logging

All components emit JSON logs to stdout:

```json
{
  "timestamp": "2026-04-15T08:00:00.000Z",
  "level": "INFO",
  "service": "scraper",
  "scraper": "public_apis_github",
  "event": "scraper_complete",
  "candidates_found": 1487,
  "duration_seconds": 12.4,
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

```json
{
  "timestamp": "2026-04-15T08:00:01.234Z",
  "level": "WARNING",
  "service": "validator",
  "api_id": "...",
  "api_name": "SomeAPI",
  "event": "validation_failed",
  "http_status": 0,
  "error": "Connection timeout",
  "consecutive_failures": 2
}
```

Log fields present in all records:
- `timestamp` — ISO 8601 UTC
- `level` — DEBUG/INFO/WARNING/ERROR
- `service` — scraper/validator/enrichment/api/scheduler
- `event` — snake_case event identifier
- `request_id` — (API service only) trace ID

---

## 6. Health Endpoint

The `/health` endpoint is designed for load balancers and uptime monitors:

```python
@app.get("/health")
async def health():
    db_ok = await check_db_connection()
    worker_ok = await check_worker_heartbeat()  # Worker updates a heartbeat timestamp
    
    status = "ok" if (db_ok and worker_ok) else "degraded"
    http_status = 200 if status == "ok" else 503
    
    return JSONResponse(
        status_code=http_status,
        content={
            "status": status,
            "database": "ok" if db_ok else "error",
            "pipeline": "ok" if worker_ok else "error",
            "version": settings.VERSION,
        }
    )
```

Monitor this endpoint with any uptime service (UptimeRobot free tier, Uptime Kuma, etc.)

---

## 7. Prometheus Scrape Config

```yaml
# docker/prometheus/prometheus.yml

global:
  scrape_interval: 30s
  evaluation_interval: 30s

rule_files:
  - "alerts.yml"

scrape_configs:
  - job_name: "apivault_api"
    static_configs:
      - targets: ["api:9000"]

  - job_name: "apivault_worker"
    static_configs:
      - targets: ["worker:9001"]

  - job_name: "apivault_scheduler"
    static_configs:
      - targets: ["scheduler:9002"]

  - job_name: "postgres"
    static_configs:
      - targets: ["postgres_exporter:9187"]
```
