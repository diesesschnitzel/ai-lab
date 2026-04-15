# System Architecture
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## 1. Overview

APIVault is a data pipeline system with a read-optimized query layer. It has four
primary concerns:

1. **Discovery** — finding APIs from as many sources as possible
2. **Processing** — normalizing, deduplicating, validating, enriching
3. **Storage** — keeping a single authoritative record per API
4. **Serving** — fast, flexible querying by developers and agents

These concerns are separated into distinct layers that communicate through a shared
PostgreSQL database and an async task queue.

---

## 2. High-Level Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════╗
║                        DISCOVERY LAYER                           ║
║                                                                  ║
║  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌─────────────┐  ║
║  │ Directory  │ │  Package   │ │   GitHub   │ │    Cert     │  ║
║  │ Scrapers   │ │  Registry  │ │   Search   │ │Transparency │  ║
║  │            │ │  Miners    │ │   Bot      │ │   Crawler   │  ║
║  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └──────┬──────┘  ║
║        │              │              │               │          ║
║  ┌─────┴──────┐ ┌─────┴──────┐ ┌─────┴──────┐ ┌──────┴──────┐  ║
║  │Government  │ │ Community  │ │   Common   │ │    Deep     │  ║
║  │  Crawlers  │ │   Intel    │ │   Crawl    │ │   Probers   │  ║
║  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └──────┬──────┘  ║
╚════════╪══════════════╪══════════════╪════════════════╪═════════╝
         └──────────────┴──────────────┴────────────────┘
                                  │
                          RAW CANDIDATE
                            QUEUE (DB)
                                  │
╔═════════════════════════════════╪════════════════════════════════╗
║                     PROCESSING LAYER                             ║
║                                │                                 ║
║                    ┌───────────▼───────────┐                    ║
║                    │     NORMALIZER         │                    ║
║                    │  • extract base_url    │                    ║
║                    │  • extract docs_url    │                    ║
║                    │  • canonicalize domain │                    ║
║                    │  • detect format       │                    ║
║                    └───────────┬───────────┘                    ║
║                                │                                 ║
║                    ┌───────────▼───────────┐                    ║
║                    │    DEDUPLICATOR        │                    ║
║                    │  • URL fingerprint     │                    ║
║                    │  • name similarity     │                    ║
║                    │  • merge sources       │                    ║
║                    └───────────┬───────────┘                    ║
║                                │                                 ║
║              ┌─────────────────┼─────────────────┐              ║
║              │                 │                 │              ║
║   ┌──────────▼──────┐ ┌────────▼────────┐ ┌─────▼──────────┐  ║
║   │   VALIDATOR      │ │   ENRICHMENT    │ │  SPEC PARSER   │  ║
║   │  • DNS probe     │ │  • LLM tagging  │ │  • OpenAPI     │  ║
║   │  • HTTP probe    │ │  • use cases    │ │  • Swagger     │  ║
║   │  • auth detect   │ │  • embedding    │ │  • Postman     │  ║
║   │  • SSL check     │ │  • summary gen  │ │  • GraphQL     │  ║
║   │  • rate limits   │ │  • categorize   │ │                │  ║
║   └──────────┬───────┘ └────────┬────────┘ └─────┬──────────┘  ║
║              └─────────────────┬─────────────────┘              ║
╚════════════════════════════════╪═══════════════════════════════╝
                                 │
╔════════════════════════════════╪═══════════════════════════════╗
║                      STORAGE LAYER                              ║
║                                │                                ║
║              ┌─────────────────▼──────────────────┐            ║
║              │           PostgreSQL 16              │            ║
║              │                                     │            ║
║              │  ┌─────────────┐ ┌───────────────┐ │            ║
║              │  │   apis      │ │ api_endpoints  │ │            ║
║              │  │   table     │ │    table       │ │            ║
║              │  └─────────────┘ └───────────────┘ │            ║
║              │  ┌─────────────┐ ┌───────────────┐ │            ║
║              │  │ health_log  │ │  raw_candidates│ │            ║
║              │  │   table     │ │    table       │ │            ║
║              │  └─────────────┘ └───────────────┘ │            ║
║              │  ┌─────────────┐ ┌───────────────┐ │            ║
║              │  │  pgvector   │ │  scraper_runs  │ │            ║
║              │  │  (embeddings│ │    table       │ │            ║
║              │  └─────────────┘ └───────────────┘ │            ║
║              └─────────────────────────────────────┘            ║
╚════════════════════════════════╪═══════════════════════════════╝
                                 │
╔════════════════════════════════╪═══════════════════════════════╗
║                      SERVING LAYER                              ║
║                                │                                ║
║              ┌─────────────────▼──────────────────┐            ║
║              │           FastAPI App               │            ║
║              │                                     │            ║
║              │  GET /apis              (browse)    │            ║
║              │  GET /apis/{id}         (detail)    │            ║
║              │  GET /apis/search       (semantic)  │            ║
║              │  GET /categories        (browse)    │            ║
║              │  GET /health            (status)    │            ║
║              │  GET /stats             (metrics)   │            ║
║              └─────────────────────────────────────┘            ║
╚════════════════════════════════════════════════════════════════╝
```

---

## 3. Component Descriptions

### 3.1 Discovery Layer

The discovery layer is a collection of independent scraper workers. Each scraper:
- Has a single responsibility (one source type)
- Writes raw candidates to the `raw_candidates` table
- Records its run in the `scraper_runs` table
- Is scheduled independently
- Fails in isolation — one crashing scraper does not affect others

Scrapers are designed to be stateless and idempotent. They can be re-run at any
time without producing corrupted data.

### 3.2 Normalizer

Takes a raw candidate record and produces a normalized API record:
- Extracts and canonicalizes the base URL (strip trailing slashes, force HTTPS)
- Extracts documentation URL
- Detects API format (REST/GraphQL/SOAP/gRPC) from spec files or URL patterns
- Extracts any structured metadata present in the source (auth type, description)
- Outputs a pre-dedup record

### 3.3 Deduplicator

Before inserting a normalized record, checks for existing records:
1. Exact URL match (fastest)
2. Domain + path prefix match (catches version differences)
3. Name similarity match (catches same API from different sources)

On match: merges source references, updates fields with higher-confidence data.
On no match: inserts new record.

See `docs/11_DEDUPLICATION.md` for full strategy.

### 3.4 Validator

An async probe engine that checks API health:
- Runs on newly inserted APIs within 24h
- Re-runs on all APIs on a weekly schedule
- Probes: DNS, HTTP, SSL, auth detection, rate limit headers
- Writes results to `api_health_log` and updates `apis` table

### 3.5 Enrichment Pipeline

An LLM-powered worker that processes APIs missing enrichment:
- Generates: tags, categories, use cases, plain-language summary
- Generates embedding vector from description + tags
- Stores embedding in pgvector column for semantic search
- Processes in batches for efficiency
- Supports both local (Ollama) and remote (Claude API) models

### 3.6 Spec Parser

When an OpenAPI/Swagger/Postman spec URL is known:
- Downloads and parses the spec
- Extracts: all endpoints, parameters, response schemas
- Inserts into `api_endpoints` table
- Extracts auth schemes, server URLs, rate limit extensions

### 3.7 PostgreSQL + pgvector

Single database serving all layers:
- `raw_candidates` — scraper output queue
- `apis` — primary API record store
- `api_endpoints` — endpoint catalog from specs
- `api_health_log` — time-series health history
- `scraper_runs` — audit log of all scraper executions

pgvector extension powers semantic similarity search over the embedding column.
Full-text search uses native PostgreSQL `tsvector` / `tsquery`.

### 3.8 FastAPI Application

Read-only query layer exposing the database:
- Standard keyword search with filters
- Semantic (vector) search via pgvector
- Category and tag browsing
- Individual API detail
- Stats and aggregate endpoints
- Self-documenting via OpenAPI

---

## 4. Data Flow

### Ingest Flow
```
Scraper runs
    → writes to raw_candidates (status=pending)
    → Normalizer picks up (status=normalizing)
    → Deduplicator checks for existing record
        → match: merge and update
        → no match: insert new apis record (status=pending_validation)
    → Validator probes (status=validating)
        → updates apis record with health data
        → inserts health_log row
    → Enrichment worker generates LLM data (status=pending_enrichment)
        → updates apis record with tags, embedding, summary
        → sets status=active (or status=dead if validation failed)
```

### Query Flow
```
Client request
    → FastAPI route handler
    → Build SQL query with filters
        → keyword: WHERE fts @@ to_tsquery(...)
        → semantic: ORDER BY embedding <=> query_embedding
    → Execute against PostgreSQL
    → Serialize results
    → Return JSON response
```

---

## 5. Process Model

All components run as separate processes, managed by Docker Compose:

| Service | Process | Restart Policy |
|---|---|---|
| `db` | PostgreSQL 16 | always |
| `api` | FastAPI (uvicorn) | always |
| `scheduler` | APScheduler | always |
| `worker` | Async pipeline worker | always |
| `enrichment` | LLM enrichment worker | on-failure |
| `ollama` | Ollama (local LLM) | always (if local mode) |

Workers use asyncio for I/O-bound scraping and probing. CPU-bound tasks
(parsing, dedup hashing) use thread pools.

---

## 6. Scheduling Model

The scheduler service manages all periodic jobs:

```
Every 1 hour:
  - Process raw_candidates queue (normalizer + dedup)
  - Run validation on overdue APIs

Every 6 hours:
  - Run all Tier 1 directory scrapers (fast, structured)
  - Run enrichment batch

Every 24 hours:
  - Run package registry scrapers (npm, PyPI, etc.)
  - Run GitHub search scrapers
  - Retry dead APIs (may have come back)

Every 7 days:
  - Run cert transparency query
  - Run government portal crawlers
  - Run community intelligence scrapers
  - Full re-validation of all APIs

Every 30 days:
  - Run Common Crawl index search
  - Run Wayback Machine mining
  - Archive old health log entries (>90 days)
```

---

## 7. Technology Choices

| Decision | Choice | Rationale |
|---|---|---|
| Database | PostgreSQL 16 | pgvector support, full-text search, JSONB, mature |
| Vector extension | pgvector | Avoids a separate vector DB; co-located with data |
| Web framework | FastAPI | Async, auto-docs, typed, fast |
| HTTP client | httpx | Async, connection pooling, timeout handling |
| Browser automation | Playwright | Needed for JS-rendered API directories |
| Scheduling | APScheduler | Embedded, no external broker needed at small scale |
| LLM (local) | Ollama + nomic-embed | Free, private, no API costs |
| LLM (remote) | Claude API | Higher quality; used when local is insufficient |
| Containerization | Docker Compose | Simple, self-hosted friendly, no k8s needed |

---

## 8. Deployment Architecture

Single-host deployment (minimum viable):

```
┌─────────────────────────────────────────┐
│              Docker Host                │
│                                         │
│  ┌─────────┐  ┌─────────┐  ┌────────┐  │
│  │   db    │  │   api   │  │  ollama│  │
│  │  :5432  │  │  :8000  │  │ :11434 │  │
│  └─────────┘  └─────────┘  └────────┘  │
│                                         │
│  ┌─────────┐  ┌─────────┐  ┌────────┐  │
│  │scheduler│  │ worker  │  │enrich- │  │
│  │         │  │         │  │  ment  │  │
│  └─────────┘  └─────────┘  └────────┘  │
│                                         │
│  Volumes:                               │
│    pgdata:/var/lib/postgresql/data      │
│    ollamadata:/root/.ollama             │
└─────────────────────────────────────────┘
```

See `docs/13_INFRASTRUCTURE.md` for extended deployment options.

---

## 9. Key Design Decisions

### Why PostgreSQL for everything (not a separate queue/vector DB)?

At the target scale (90k APIs, 3M candidates), PostgreSQL handles all workloads
comfortably. A separate Redis queue, Elasticsearch, and Pinecone would add
operational complexity for no functional benefit. pgvector delivers semantic
search at this scale without a dedicated vector database.

### Why not a distributed scraping framework (Scrapy, etc.)?

Scrapy adds significant complexity. Our scrapers are simple enough to run as
async functions. Each scraper is just a Python async function that writes to
the database — trivially testable and portable.

### Why async for scrapers?

Scraping and probing are almost entirely I/O bound (waiting for HTTP responses).
Async with httpx allows hundreds of concurrent requests per process without
threads, which is efficient and low-overhead.

### Why local LLM support?

To make the system usable without ongoing API costs. Ollama + nomic-embed-text
runs on a machine with 8GB RAM and produces good-enough embeddings for this
use case. Users can upgrade to Claude API for higher quality enrichment.
