# Configuration Reference
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## Overview

All configuration is via environment variables. No config files need editing.
Copy `.env.example` to `.env` and set values.

Values marked **REQUIRED** must be set. Everything else has a default.

---

## Database

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | YES | — | Full PostgreSQL connection string |
| `DATABASE_POOL_MIN` | No | `2` | Minimum connection pool size |
| `DATABASE_POOL_MAX` | No | `20` | Maximum connection pool size |
| `DATABASE_POOL_TIMEOUT` | No | `30` | Seconds to wait for a connection |
| `POSTGRES_PASSWORD` | YES* | — | *Only needed if using docker-compose db service |

**Example:**
```
DATABASE_URL=postgresql://apivault:yourpassword@localhost:5432/apivault
```

---

## API Server

| Variable | Required | Default | Description |
|---|---|---|---|
| `API_HOST` | No | `0.0.0.0` | Bind address |
| `API_PORT` | No | `8000` | Listen port |
| `API_WORKERS` | No | `2` | Uvicorn worker count |
| `ADMIN_KEY` | No | `""` (disabled) | Key for admin endpoints. Empty = admin disabled |
| `CORS_ORIGINS` | No | `*` | Comma-separated allowed origins |
| `RATE_LIMIT_PER_MINUTE` | No | `100` | Requests/minute per IP |
| `SEMANTIC_RATE_LIMIT_PER_MINUTE` | No | `20` | Requests/minute for /search |
| `MAX_PAGE_SIZE` | No | `100` | Maximum per_page value |
| `DEFAULT_MIN_HEALTH_SCORE` | No | `50` | Default minimum health score in queries |

---

## LLM / Enrichment

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_BACKEND` | No | `ollama` | `ollama` \| `claude` \| `openai` \| `none` |
| `OLLAMA_URL` | No | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_EMBED_MODEL` | No | `nomic-embed-text` | Model for embeddings |
| `OLLAMA_CHAT_MODEL` | No | `llama3.2` | Model for classification |
| `CLAUDE_API_KEY` | If LLM_BACKEND=claude | — | Anthropic API key |
| `CLAUDE_MODEL` | No | `claude-haiku-4-5-20251001` | Claude model for enrichment |
| `OPENAI_API_KEY` | If LLM_BACKEND=openai | — | OpenAI API key |
| `OPENAI_EMBED_MODEL` | No | `text-embedding-3-small` | OpenAI embedding model |
| `OPENAI_CHAT_MODEL` | No | `gpt-4o-mini` | OpenAI model for classification |
| `EMBEDDING_DIMENSIONS` | No | `1536` | Vector dimensions (must match model) |
| `ENRICHMENT_BATCH_SIZE` | No | `20` | APIs per LLM batch call |
| `ENRICHMENT_WORKERS` | No | `2` | Concurrent enrichment workers |

**LLM_BACKEND options:**
- `ollama` — Local, free, requires Ollama running (default)
- `claude` — Best quality, requires API key, has cost
- `openai` — Good quality, requires API key, has cost
- `none` — No LLM enrichment; uses rule-based fallback only

---

## Scrapers

| Variable | Required | Default | Description |
|---|---|---|---|
| `GITHUB_TOKEN` | Recommended | `""` | GitHub personal access token (increases rate limit from 60 to 5000/hour) |
| `SCRAPER_REQUEST_DELAY_SECONDS` | No | `1.0` | Min delay between requests to same domain |
| `SCRAPER_TIMEOUT_SECONDS` | No | `3600` | Max runtime per scraper run |
| `SCRAPER_USER_AGENT` | No | `APIVault/1.0 ...` | HTTP User-Agent string |
| `RESPECT_ROBOTS_TXT` | No | `true` | Whether to check robots.txt |
| `MAX_CANDIDATES_PER_RUN` | No | `100000` | Max candidates any single scraper can insert per run |

**Per-scraper overrides** (replace `{NAME}` with scraper name uppercased):
```
SCRAPER_{NAME}_ENABLED=false          # Disable a specific scraper
SCRAPER_{NAME}_FREQUENCY_HOURS=48     # Override run frequency
SCRAPER_{NAME}_TIMEOUT_SECONDS=7200   # Override timeout
```

Example: `SCRAPER_CERT_TRANSPARENCY_FREQUENCY_HOURS=168` (weekly)

**Optional API keys for specific scrapers:**
| Variable | Scraper | Description |
|---|---|---|
| `SHODAN_API_KEY` | `deep/shodan.py` | Free key from shodan.io |
| `CENSYS_API_ID` | `deep/censys.py` | From censys.io |
| `CENSYS_API_SECRET` | `deep/censys.py` | From censys.io |
| `RAPIDAPI_KEY` | `directories/rapidapi_free.py` | For authenticated scraping |

---

## Validation

| Variable | Required | Default | Description |
|---|---|---|---|
| `VALIDATION_CONCURRENCY` | No | `50` | Concurrent HTTP probes |
| `VALIDATION_TIMEOUT_CONNECT_SECONDS` | No | `5` | TCP connect timeout |
| `VALIDATION_TIMEOUT_READ_SECONDS` | No | `10` | HTTP read timeout |
| `VALIDATION_DNS_TIMEOUT_SECONDS` | No | `3` | DNS resolution timeout |
| `VALIDATION_RECHECK_INTERVAL_DAYS` | No | `7` | Days between re-validations |
| `VALIDATION_DEAD_RETRY_DAYS` | No | `3` | Days between dead API retries |
| `VALIDATION_DEAD_MAX_RETRIES` | No | `10` | Max retries before stopping |
| `VALIDATION_BATCH_SIZE` | No | `100` | APIs fetched per validation cycle |

---

## Pipeline

| Variable | Required | Default | Description |
|---|---|---|---|
| `PIPELINE_POLL_INTERVAL_SECONDS` | No | `30` | How often worker checks queues |
| `NORMALIZATION_BATCH_SIZE` | No | `500` | Raw candidates per normalization cycle |
| `DEDUP_NAME_SIMILARITY_THRESHOLD` | No | `0.7` | Trigram similarity for name matching |
| `DEDUP_SEMANTIC_SIMILARITY_THRESHOLD` | No | `0.95` | Cosine similarity for semantic dedup |

---

## Scheduler

| Variable | Required | Default | Description |
|---|---|---|---|
| `SCHEDULER_TIMEZONE` | No | `UTC` | Timezone for cron expressions |
| `BOOTSTRAP_ON_EMPTY_DB` | No | `true` | Run bootstrap ingest if DB is empty |

---

## Monitoring

| Variable | Required | Default | Description |
|---|---|---|---|
| `METRICS_ENABLED` | No | `true` | Expose Prometheus metrics at `/metrics` |
| `METRICS_PORT` | No | `9000` | Prometheus metrics port |
| `LOG_LEVEL` | No | `INFO` | Python log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT` | No | `json` | `json` \| `text` |
| `SENTRY_DSN` | No | `""` | Sentry DSN for error tracking (optional) |

---

## `.env.example`

```bash
# ============================================================
# APIVault Configuration
# Copy to .env and fill in values
# ============================================================

# ----- REQUIRED -----
POSTGRES_PASSWORD=changeme_secure_password

# ----- DATABASE -----
DATABASE_URL=postgresql://apivault:${POSTGRES_PASSWORD}@db:5432/apivault

# ----- API -----
ADMIN_KEY=                          # Leave empty to disable admin endpoints
CORS_ORIGINS=*                      # Restrict in production

# ----- LLM (choose one backend) -----
LLM_BACKEND=ollama                  # ollama | claude | openai | none

# If using claude:
# CLAUDE_API_KEY=sk-ant-...

# If using openai:
# OPENAI_API_KEY=sk-...

# ----- SCRAPERS -----
GITHUB_TOKEN=                       # Get from github.com/settings/tokens (public_repo)

# Optional scraper API keys (leave empty to skip those sources)
SHODAN_API_KEY=
CENSYS_API_ID=
CENSYS_API_SECRET=

# ----- MONITORING -----
LOG_LEVEL=INFO
SENTRY_DSN=                         # Optional
```
