# APIVault — The World's Most Complete Free API Database

APIVault is a self-hosted, continuously updated, semantically searchable database
of every free, publicly accessible API on the internet. It combines automated
multi-source discovery, active health validation, LLM-powered enrichment, and a
fast query API — so you always know what tools exist before you need them.

---

## What It Does

- Discovers APIs from 30+ source types: directories, package registries, GitHub,
  certificate transparency logs, government portals, community posts, and more
- Validates every API is alive, checks auth requirements, probes rate limits
- Enriches every entry with LLM-generated tags, use cases, and plain-language summaries
- Exposes a REST + semantic search API: query by keyword, category, or natural language
- Runs continuously, re-validating all entries on a schedule

---

## Target Scale

| Metric | Target |
|---|---|
| APIs indexed | 90,000+ verified |
| Raw candidates processed | 3,000,000+ |
| Sources monitored | 30+ types, 500+ individual sources |
| Validation frequency | Weekly per API |
| Query latency | <100ms keyword, <500ms semantic |

---

## Document Index

| Document | Description |
|---|---|
| [PRD](docs/01_PRD.md) | Product requirements, goals, user stories |
| [Architecture](docs/02_ARCHITECTURE.md) | System design, components, data flow overview |
| [Data Model](docs/03_DATA_MODEL.md) | Entities, relationships, field definitions |
| [Database Schema](docs/04_DATABASE_SCHEMA.md) | Full SQL — tables, indexes, constraints |
| [Taxonomy](docs/05_TAXONOMY.md) | Category tree, tag vocabulary, classification rules |
| [Source Catalog](docs/06_SOURCE_CATALOG.md) | Every discovery source with method and priority |
| [Scraper Design](docs/07_SCRAPER_DESIGN.md) | Scraper architecture, module specs, scheduling |
| [Data Pipeline](docs/08_DATA_PIPELINE.md) | End-to-end data flow from discovery to storage |
| [Validation](docs/09_VALIDATION.md) | Health check engine, probing strategy |
| [Enrichment](docs/10_ENRICHMENT.md) | LLM tagging, embedding, categorization pipeline |
| [Deduplication](docs/11_DEDUPLICATION.md) | Duplicate detection and merge strategy |
| [API Spec](docs/12_API_SPEC.md) | Public query API — endpoints, params, responses |
| [Infrastructure](docs/13_INFRASTRUCTURE.md) | Hosting, containers, deployment, scaling |
| [Configuration](docs/14_CONFIGURATION.md) | All env vars, config keys, defaults |
| [Security](docs/15_SECURITY.md) | Security model, ToS compliance, rate limiting |
| [Data Governance](docs/16_DATA_GOVERNANCE.md) | Legal, attribution, ethics, data lifecycle |
| [Testing](docs/17_TESTING.md) | Test strategy, coverage targets, test types |
| [Monitoring](docs/18_MONITORING.md) | Metrics, dashboards, alerting |
| [Error Handling](docs/19_ERROR_HANDLING.md) | Failure modes, retry logic, dead letter queues |
| [Performance](docs/20_PERFORMANCE.md) | Scale targets, query optimization, benchmarks |
| [Runbook](docs/21_RUNBOOK.md) | Day-to-day operations, maintenance procedures |
| [Roadmap](docs/22_ROADMAP.md) | Phases, milestones, delivery plan |

---

## Quick Start

```bash
# 1. Clone and enter
git clone https://github.com/diesesschnitzel/dummy apivault
cd apivault

# 2. Copy and configure environment
cp .env.example .env
# Edit .env with your settings

# 3. Start infrastructure
docker compose up -d

# 4. Run database migrations
make migrate

# 5. Run first ingest (starts with highest-yield sources)
make ingest-bootstrap

# 6. Start the API server
make serve

# 7. Query
curl "http://localhost:8000/apis?q=pdf+convert&auth=none"
curl "http://localhost:8000/apis/search?ask=extract+text+from+a+pdf+without+login"
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Database | PostgreSQL 16 + pgvector |
| Backend API | Python / FastAPI |
| Scrapers | Python / httpx / playwright / asyncio |
| Scheduler | APScheduler (embedded) or Celery + Redis |
| Embeddings | Ollama (local) or Claude API |
| Search | pgvector (semantic) + PostgreSQL FTS (keyword) |
| Deployment | Docker Compose (self-hosted) |

---

## Repository Structure

```
apivault/
├── README.md
├── docs/                        # All project documents
├── src/
│   ├── api/                     # FastAPI application
│   ├── scrapers/                # Discovery scrapers
│   │   ├── directories/
│   │   ├── registries/
│   │   ├── github/
│   │   ├── government/
│   │   ├── community/
│   │   └── deep/
│   ├── pipeline/                # Ingest, normalize, enrich
│   ├── validators/              # Health check engine
│   ├── enrichment/              # LLM tagging & embedding
│   ├── dedup/                   # Deduplication engine
│   ├── scheduler/               # Job scheduling
│   └── db/                      # Models, migrations, queries
├── tests/
├── migrations/
├── docker/
├── docker-compose.yml
├── Makefile
└── .env.example
```
