# Roadmap — Phased Delivery Plan
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## Overview

Three phases, each delivering a usable, valuable system.
Each phase builds on the previous without requiring rewrites.

```
Phase 1: Foundation (Weeks 1-4)
  → Working database + search + Tier 1 scrapers + validation
  → Goal: 15,000 verified APIs indexed, keyword search live

Phase 2: Scale (Weeks 5-10)
  → Package registries + GitHub search + enrichment + semantic search
  → Goal: 50,000 verified APIs, semantic search live

Phase 3: Comprehensive (Weeks 11-20)
  → All source types + monitoring + deep discovery
  → Goal: 90,000+ verified APIs, full observability
```

---

## Phase 1: Foundation

**Goal:** A working, queryable database with the most important sources.
**Target:** 15,000 verified APIs, keyword search, basic validation.

### Week 1: Database & Infrastructure

**Tasks:**
- [ ] Set up PostgreSQL + pgvector container
- [ ] Write and run all migrations (schema from docs/04_DATABASE_SCHEMA.md)
- [ ] Write `.env.example` and configuration system
- [ ] Write Docker Compose config
- [ ] Basic FastAPI app skeleton with `/health` endpoint
- [ ] Database connection pooling

**Milestone:** `docker compose up` starts a working empty system.

---

### Week 2: First Scrapers + Pipeline

**Tasks:**
- [ ] Implement base scraper interface (BaseScraper, RawCandidate, runner)
- [ ] `public_apis_github.py` — 1,500 APIs in one run
- [ ] `apis_guru.py` — 2,500 APIs with OpenAPI specs
- [ ] `apilist_fun.py` — 600 APIs
- [ ] Normalizer (URL canonicalization, auth normalization)
- [ ] Deduplicator (exact URL match + name fingerprint, levels 1 & 2)
- [ ] Pipeline worker (polls queue, runs normalization + dedup)
- [ ] Insert normalized records into `apis` table

**Milestone:** Run scrapers, see 4,000+ records in `apis` table.

---

### Week 3: Validation + Basic API

**Tasks:**
- [ ] HTTP prober (DNS check, HTTP probe, auth detection)
- [ ] SSL checker
- [ ] Health score calculation
- [ ] `api_health_log` writes
- [ ] Validation worker (runs on pending_validation queue)
- [ ] FastAPI routes: `GET /apis`, `GET /apis/{id}`, `GET /stats`
- [ ] Keyword search (`fts` column + `to_tsquery`)
- [ ] Pagination + basic filters (auth, status)

**Milestone:** `curl "http://localhost:8000/apis?q=weather&auth=none"` returns results.

---

### Week 4: Scheduler + More Sources + Polish

**Tasks:**
- [ ] APScheduler setup for recurring runs
- [ ] `postman_network.py` — 50,000 candidates from Postman
- [ ] `openapi_directory.py` — 3,000 more with specs
- [ ] `any_api_com.py`, `rapidapi_free.py`
- [ ] Rate limiting middleware for API
- [ ] `/categories` endpoint
- [ ] Input validation (Pydantic models for all query params)
- [ ] Structured JSON logging
- [ ] README with quick-start instructions

**Phase 1 Milestone:** 15,000 verified APIs, keyword search live, system running continuously.

---

## Phase 2: Scale

**Goal:** Massive scale through package registries and GitHub. Semantic search.
**Target:** 50,000 verified APIs, natural language search live.

### Week 5-6: Package Registry Miners

**Tasks:**
- [ ] `npm.py` — npm search API (daily) + CouchDB dump parser
- [ ] `pypi.py` — PyPI XML-RPC + bulk download
- [ ] `rubygems.py`
- [ ] `nuget.py`
- [ ] `crates_io.py`
- [ ] URL extraction from package README (regex + heuristics)
- [ ] Handle high-volume inserts efficiently (batch operations)

**Expected yield:** +30,000 candidates; after dedup/validation: +15,000 new APIs

---

### Week 7: GitHub Search

**Tasks:**
- [ ] `search_openapi.py` — GitHub search for swagger/openapi files
- [ ] OpenAPI spec parser (extract base URL, auth, endpoints)
- [ ] `api_endpoints` table population
- [ ] `awesome_lists.py` — clone and parse all awesome-* repos
- [ ] `readme_extractor.py` — extract API URLs from READMEs
- [ ] GitHub rate limit handling (respect search API limits)

**Expected yield:** +20,000 candidates; after filtering: +10,000 new APIs

---

### Week 8: LLM Enrichment

**Tasks:**
- [ ] Ollama integration (local embedding with nomic-embed-text)
- [ ] Embedding generation pipeline
- [ ] pgvector index creation (`USING ivfflat`)
- [ ] Classification prompt implementation
- [ ] Enrichment worker (processes unenriched APIs)
- [ ] Rule-based fallback (no-LLM path)
- [ ] Semantic search endpoint (`GET /apis/search?ask=...`)
- [ ] `GET /apis/{id}/similar` endpoint

**Milestone:** Natural language search working.

---

### Week 9-10: Government Sources + Robustness

**Tasks:**
- [ ] `ckan_crawler.py` — all CKAN instances worldwide
- [ ] Specialized government scrapers (NASA, NOAA, Census, etc.)
- [ ] `academic/` scrapers (arXiv, PubMed, Semantic Scholar, etc.)
- [ ] Level 3 deduplication (domain name similarity)
- [ ] Batch dedup job (weekly, catches stragglers)
- [ ] Improved error handling throughout pipeline
- [ ] Playwright setup for JS-rendered sites

**Phase 2 Milestone:** 50,000 verified APIs, semantic search live, government data indexed.

---

## Phase 3: Comprehensive

**Goal:** Every possible source. Full observability. Production hardiness.
**Target:** 90,000+ verified APIs, all monitoring live, all sources active.

### Week 11-13: Deep Discovery

**Tasks:**
- [ ] `cert_transparency.py` — crt.sh PostgreSQL query
- [ ] DNS probe pipeline for CT results (bulk async probing)
- [ ] `common_crawl.py` — CC index search
- [ ] `community/` scrapers (HackerNews, Reddit, dev.to, Product Hunt)
- [ ] `pub_dev.py`, `maven.py`, `packagist.py` (remaining registries)
- [ ] `deep/shodan.py` (for swagger-ui exposed instances)
- [ ] `deep/wikidata.py` (query for company APIs)
- [ ] ProgrammableWeb archive mining (Wayback Machine)

**Expected yield:** +40,000 candidates; after filtering: +25,000 new APIs

---

### Week 14-15: Monitoring & Alerting

**Tasks:**
- [ ] Prometheus metrics instrumentation throughout codebase
- [ ] Grafana dashboards (all 5 dashboards from docs/18_MONITORING.md)
- [ ] Alertmanager configuration
- [ ] Health check endpoint improvements
- [ ] Structured logging audit (ensure all components log consistently)
- [ ] Log aggregation setup (optional: Loki)
- [ ] Uptime monitoring for the API itself

**Milestone:** Full observability with dashboards and alerts.

---

### Week 16-17: Performance & Reliability

**Tasks:**
- [ ] Load testing (Locust) — verify targets from docs/20_PERFORMANCE.md
- [ ] Query optimization (EXPLAIN ANALYZE on all endpoints)
- [ ] IVFFlat → HNSW migration (if >100k vectors)
- [ ] Connection pooling audit (PgBouncer if needed)
- [ ] Application-level caching for hot endpoints
- [ ] Dead letter queue handling
- [ ] Circuit breakers for external APIs
- [ ] Startup validation (fail fast on misconfig)

---

### Week 18-20: Documentation, Admin & Polish

**Tasks:**
- [ ] Admin UI (simple, read-only dashboard showing system state)
- [ ] `/admin/validate/{id}` and `/admin/enrich/{id}` endpoints
- [ ] Manual dedup review interface (for medium-confidence matches)
- [ ] Export endpoint (`GET /apis/export.csv` or `.json`)
- [ ] Complete API documentation (all endpoints documented)
- [ ] Smoke test suite for all scrapers
- [ ] Operational runbook review and update
- [ ] Security audit checklist (docs/15_SECURITY.md)
- [ ] Final benchmark run

**Phase 3 Milestone:** 90,000+ APIs, full monitoring, all source types active, production ready.

---

## Milestone Summary

| Milestone | When | APIs Indexed | Key Features |
|---|---|---|---|
| M1: First search | End of Week 3 | 4,000 | Keyword search, basic filters |
| M2: Foundation complete | End of Week 4 | 15,000 | Scheduler, all Tier 1 sources |
| M3: Scale achieved | End of Week 8 | 30,000 | Package registries, GitHub, semantic search |
| M4: Government indexed | End of Week 10 | 50,000 | CKAN, government portals, academic |
| M5: Deep discovery | End of Week 13 | 75,000 | Cert transparency, community, rare sources |
| M6: Production ready | End of Week 20 | 90,000+ | Full monitoring, alerts, admin tools |

---

## Prioritization Logic

**Why Tier 1 directories first?**
They provide the fastest "time to first result" with minimal implementation cost.
One afternoon's work (public-apis + apis.guru) delivers 4,000 high-quality APIs.

**Why package registries second?**
They provide the largest yield but require more sophisticated URL extraction.
Worth the complexity because they find APIs that no directory lists.

**Why GitHub search third?**
Requires a GitHub token and rate limit handling. Worth it because it finds
private/obscure APIs that have OpenAPI specs but no directory presence.

**Why enrichment before more scrapers?**
Semantic search dramatically improves usefulness. Better to have 30,000
well-enriched APIs than 90,000 poorly-tagged ones.

**Why cert transparency and Common Crawl last?**
These are the highest-effort, lowest-precision sources. They generate millions
of candidates that need heavy filtering. Run these only after the pipeline is
proven to handle volume efficiently.

---

## What's Not In Scope (Future Phases)

These are valid ideas for future phases, not in scope for the current plan:
- Public API for submitting new APIs (community contributions)
- API changelog tracking (detect when APIs change their specs)
- Integration testing of indexed APIs (actually call them, not just probe)
- Browser extension for auto-detecting APIs while browsing
- Notification system ("this API you saved came back online")
- Comparison view (compare two APIs side-by-side)
- GraphQL interface for the query API
