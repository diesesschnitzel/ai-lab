# Data Model
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## 1. Entity Overview

```
┌─────────────────┐       ┌──────────────────┐
│  raw_candidates │       │   scraper_runs   │
│  (ingest queue) │       │  (audit log)     │
└────────┬────────┘       └──────────────────┘
         │ processed into
         ▼
┌─────────────────┐  1   ┌──────────────────┐
│      apis       │──────│  api_endpoints   │
│  (primary store)│  ∞   │  (endpoint detail│
└────────┬────────┘      └──────────────────┘
         │ 1
         │ ∞
┌────────▼────────┐
│  api_health_log │
│ (time-series)   │
└─────────────────┘
```

**5 tables, 1 view:**
- `raw_candidates` — scraper output, pending processing
- `scraper_runs` — audit log of every scraper execution
- `apis` — one record per unique API (the main table)
- `api_endpoints` — individual endpoint records parsed from specs
- `api_health_log` — validation history (time series)
- `v_apis_live` — view of apis where status = 'active' (convenience)

---

## 2. Entity: `raw_candidates`

The landing zone for all scraper output. Records here have not yet been
deduplicated or validated. Treated as a queue.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `source_name` | TEXT | Which scraper produced this (e.g. `public_apis_github`) |
| `source_url` | TEXT | URL where this was discovered |
| `raw_name` | TEXT | API name as found at source |
| `raw_description` | TEXT | Description as found at source |
| `raw_base_url` | TEXT | Base URL as found (may be dirty) |
| `raw_docs_url` | TEXT | Docs URL as found |
| `raw_auth_type` | TEXT | Auth type as found (may be inconsistent) |
| `raw_json` | JSONB | Full raw payload from scraper |
| `status` | TEXT | `pending` \| `processing` \| `done` \| `failed` |
| `error` | TEXT | Error message if status=failed |
| `discovered_at` | TIMESTAMPTZ | When scraper found this |
| `processed_at` | TIMESTAMPTZ | When normalizer picked this up |
| `apis_id` | UUID | FK to apis record (set after processing) |

---

## 3. Entity: `scraper_runs`

Audit log. One row per scraper execution, regardless of outcome.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `scraper_name` | TEXT | Identifier of the scraper |
| `started_at` | TIMESTAMPTZ | Run start time |
| `finished_at` | TIMESTAMPTZ | Run end time (NULL if still running) |
| `status` | TEXT | `running` \| `success` \| `failed` \| `timeout` |
| `candidates_found` | INT | Raw candidates written to queue |
| `candidates_new` | INT | Of those, how many were truly new |
| `candidates_updated` | INT | How many updated existing records |
| `error` | TEXT | Error/exception if status=failed |
| `config_snapshot` | JSONB | Config used for this run (for reproducibility) |

---

## 4. Entity: `apis` (Primary)

One record per unique API. This is the heart of the system.

### Identity Fields

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `slug` | TEXT | URL-safe unique identifier (e.g. `openweather-api`) |
| `name` | TEXT | Human-readable name |

### Description Fields

| Field | Type | Description |
|---|---|---|
| `description` | TEXT | Original description from source |
| `description_llm` | TEXT | LLM-generated plain-language summary |
| `version` | TEXT | API version (e.g. `v2`, `2.0`) |

### URL Fields

| Field | Type | Description |
|---|---|---|
| `base_url` | TEXT | Canonical base URL (e.g. `https://api.example.com/v2`) |
| `docs_url` | TEXT | Documentation homepage |
| `spec_url` | TEXT | OpenAPI/Swagger/WSDL spec URL |
| `postman_url` | TEXT | Postman collection URL |
| `signup_url` | TEXT | Where to get an API key (if required) |

### Auth & Access Fields

| Field | Type | Description |
|---|---|---|
| `auth_type` | TEXT | `none` \| `apikey` \| `oauth2` \| `basic` \| `bearer` \| `unknown` |
| `auth_notes` | TEXT | Human detail (e.g. "Free key, instant, no credit card") |
| `signup_required` | BOOLEAN | Whether any form of signup is needed |
| `login_required` | BOOLEAN | Whether ongoing login session needed |

### Pricing Fields

| Field | Type | Description |
|---|---|---|
| `free_tier` | TEXT | Description of free tier (e.g. "1000 req/day free") |
| `rate_limit` | TEXT | Best-known rate limit (e.g. `100/minute`) |
| `rate_limit_header` | TEXT | Header name where rate limit was detected |
| `pricing_url` | TEXT | Link to pricing page |

### Classification Fields

| Field | Type | Description |
|---|---|---|
| `categories` | TEXT[] | Taxonomy categories (see docs/05_TAXONOMY.md) |
| `tags` | TEXT[] | Free-form tags |
| `use_cases` | TEXT[] | LLM-generated use cases |
| `formats` | TEXT[] | `REST` \| `GraphQL` \| `SOAP` \| `gRPC` \| `WebSocket` |
| `protocols` | TEXT[] | `HTTP` \| `HTTPS` \| `WSS` |
| `data_formats` | TEXT[] | `JSON` \| `XML` \| `CSV` \| `binary` \| `protobuf` |
| `openapi_version` | TEXT | `2.0` (Swagger) \| `3.0` \| `3.1` if spec is known |

### Geographic / Language Fields

| Field | Type | Description |
|---|---|---|
| `country` | TEXT | ISO 3166-1 alpha-2 (for government APIs) |
| `language` | TEXT | Primary language of responses (ISO 639-1) |

### Company Fields

| Field | Type | Description |
|---|---|---|
| `company` | TEXT | Company or organization name |
| `company_url` | TEXT | Company homepage |

### Source Tracking

| Field | Type | Description |
|---|---|---|
| `source_names` | TEXT[] | All scrapers that found this API |
| `source_urls` | TEXT[] | All source URLs where it was found |
| `discovered_at` | TIMESTAMPTZ | First discovery timestamp |

### Validation Fields

| Field | Type | Description |
|---|---|---|
| `status` | TEXT | `active` \| `dead` \| `degraded` \| `unknown` \| `pending_validation` |
| `health_score` | INT | 0–100 composite health score |
| `last_checked` | TIMESTAMPTZ | Last validation timestamp |
| `http_status` | INT | Last HTTP status code from probe |
| `response_time_ms` | INT | Last probe response time |
| `ssl_valid` | BOOLEAN | SSL certificate currently valid |
| `ssl_expiry` | DATE | SSL certificate expiry date |
| `dns_resolves` | BOOLEAN | DNS resolves successfully |
| `consecutive_failures` | INT | Count of consecutive failed probes |

### Search Fields

| Field | Type | Description |
|---|---|---|
| `embedding` | vector(1536) | Semantic embedding for similarity search |
| `fts` | tsvector | Full-text search vector (auto-maintained by trigger) |

### Metadata

| Field | Type | Description |
|---|---|---|
| `raw_json` | JSONB | Best raw payload available |
| `created_at` | TIMESTAMPTZ | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | Last update timestamp |

---

## 5. Entity: `api_endpoints`

One row per API endpoint, populated when an OpenAPI spec is parsed.
Optional detail layer — not all APIs will have endpoints catalogued.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `api_id` | UUID | FK to apis |
| `method` | TEXT | HTTP method: `GET` `POST` `PUT` `PATCH` `DELETE` |
| `path` | TEXT | Path template (e.g. `/users/{id}`) |
| `summary` | TEXT | Short description |
| `description` | TEXT | Full description |
| `tags` | TEXT[] | Endpoint tags from spec |
| `parameters` | JSONB | Parameter definitions |
| `request_body` | JSONB | Request body schema |
| `responses` | JSONB | Response schemas |
| `auth_required` | BOOLEAN | Whether this endpoint requires auth |
| `example_request` | JSONB | Example request |
| `example_response` | JSONB | Example response |
| `deprecated` | BOOLEAN | Whether marked deprecated in spec |

---

## 6. Entity: `api_health_log`

Time-series history of every validation probe. Used to track API reliability
over time and detect flapping.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `api_id` | UUID | FK to apis |
| `checked_at` | TIMESTAMPTZ | When probe ran |
| `status` | TEXT | `alive` \| `dead` \| `degraded` \| `error` |
| `http_status` | INT | HTTP response code (0 if no response) |
| `response_time_ms` | INT | Time to first byte in ms |
| `dns_resolves` | BOOLEAN | DNS resolution result |
| `ssl_valid` | BOOLEAN | SSL validity |
| `auth_type_detected` | TEXT | Auth type inferred from response |
| `rate_limit_detected` | TEXT | Rate limit from response headers |
| `error` | TEXT | Error details if probe errored |
| `checker_version` | TEXT | Version of validation engine used |

---

## 7. View: `v_apis_live`

Convenience view for the most common query pattern:

```sql
CREATE VIEW v_apis_live AS
SELECT * FROM apis
WHERE status = 'active'
  AND health_score >= 50;
```

---

## 8. Field Value Vocabularies

### status (apis)
- `unknown` — never been validated (initial state)
- `pending_validation` — queued for validation
- `active` — alive and accessible
- `degraded` — responding but with errors or very slow
- `dead` — consistently unreachable

### auth_type
- `none` — no authentication required
- `apikey` — static API key (passed as header or query param)
- `oauth2` — OAuth 2.0 flow
- `basic` — HTTP Basic Auth
- `bearer` — Bearer token (not OAuth)
- `unknown` — could not be determined

### formats
- `REST` — standard HTTP REST
- `GraphQL` — GraphQL endpoint
- `SOAP` — SOAP/WSDL
- `gRPC` — gRPC/protobuf
- `WebSocket` — WebSocket API
- `SSE` — Server-Sent Events

---

## 9. Relationships Summary

```
raw_candidates  →  apis         (N:1, via apis_id)
apis            →  api_endpoints (1:N)
apis            →  api_health_log (1:N)
scraper_runs    →  raw_candidates (1:N, conceptually; no hard FK)
```

All foreign keys use CASCADE DELETE for child tables (endpoints, health_log)
so deleting an API record cleans up all associated data.
