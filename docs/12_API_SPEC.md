# Public Query API Specification
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15
**Base URL:** `http://localhost:8000` (self-hosted default)

---

## Overview

The APIVault query API is a read-only REST API for searching and browsing
the API database. It serves as the interface for developers, tools, and AI agents
to discover APIs programmatically.

Self-documenting: Swagger UI available at `/docs`, OpenAPI JSON at `/openapi.json`.

---

## Authentication

The query API is unauthenticated by default for self-hosted deployments.
Rate limiting is applied per IP: 100 requests/minute (configurable).

---

## Common Response Format

All list endpoints return:
```json
{
  "total": 1234,
  "page": 1,
  "per_page": 20,
  "results": [ ... ]
}
```

All error responses return:
```json
{
  "error": "short_error_code",
  "message": "Human-readable description",
  "details": {}
}
```

---

## Endpoints

---

### GET /apis

Search and browse APIs with filters.

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `q` | string | — | Keyword search (full-text) |
| `ask` | string | — | Semantic / natural language search |
| `category` | string | — | Filter by category (exact or prefix) |
| `tag` | string | — | Filter by tag |
| `auth` | string | — | Filter by auth_type: `none`, `apikey`, `oauth2`, `basic`, `bearer` |
| `status` | string | `active` | Filter by status: `active`, `dead`, `all` |
| `format` | string | — | Filter by format: `REST`, `GraphQL`, `SOAP`, `gRPC` |
| `country` | string | — | Filter by country code (ISO 3166-1 alpha-2) |
| `has_spec` | boolean | — | Filter to APIs with known OpenAPI spec |
| `min_health` | integer | 50 | Minimum health score (0–100) |
| `sort` | string | `relevance` | Sort: `relevance`, `health_score`, `discovered_at`, `name` |
| `order` | string | `desc` | Sort order: `asc`, `desc` |
| `page` | integer | 1 | Page number |
| `per_page` | integer | 20 | Results per page (max 100) |

**Examples:**

```http
# Keyword search
GET /apis?q=pdf+convert&auth=none

# All weather APIs
GET /apis?category=Weather+%26+Environment

# No-auth APIs sorted by health
GET /apis?auth=none&sort=health_score&order=desc

# Natural language
GET /apis?ask=extract+text+from+images+without+signing+up

# Government APIs from the US
GET /apis?category=Government+%26+Public+Data&country=US
```

**Response:**
```json
{
  "total": 42,
  "page": 1,
  "per_page": 20,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "slug": "open-meteo",
      "name": "Open-Meteo",
      "description_llm": "Open-Meteo provides free weather forecast APIs with no API key required. It offers hourly and daily forecasts for any coordinate on Earth using global weather models. Completely free, no signup, suitable for commercial use.",
      "base_url": "https://api.open-meteo.com/v1",
      "docs_url": "https://open-meteo.com/en/docs",
      "auth_type": "none",
      "signup_required": false,
      "categories": ["Weather & Environment > Forecasting", "Weather & Environment > Current Weather"],
      "tags": ["weather", "forecast", "no-auth", "free", "rest", "json", "real-time"],
      "use_cases": [
        "Use to get hourly weather forecasts for any location without an API key",
        "Use to build weather widgets without rate limit concerns",
        "Use to access historical weather data for analysis"
      ],
      "free_tier": "Unlimited, completely free",
      "rate_limit": null,
      "formats": ["REST"],
      "health_score": 97,
      "status": "active",
      "last_checked": "2026-04-14T08:00:00Z",
      "discovered_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

---

### GET /apis/{id}

Get full details for a single API by ID or slug.

**Path Parameters:**
- `id` — UUID or slug string

**Query Parameters:**
- `include_endpoints` — boolean, default false: include api_endpoints
- `include_health_history` — boolean, default false: include last 30 health_log entries

**Response:**
```json
{
  "id": "...",
  "slug": "open-meteo",
  "name": "Open-Meteo",
  "description": "...",
  "description_llm": "...",
  "version": "v1",
  "base_url": "https://api.open-meteo.com/v1",
  "docs_url": "https://open-meteo.com/en/docs",
  "spec_url": null,
  "postman_url": null,
  "signup_url": null,
  "auth_type": "none",
  "auth_notes": null,
  "signup_required": false,
  "login_required": false,
  "free_tier": "Unlimited, completely free",
  "rate_limit": null,
  "categories": ["Weather & Environment > Forecasting"],
  "tags": ["weather", "forecast", "no-auth", "free"],
  "use_cases": ["Use to..."],
  "formats": ["REST"],
  "protocols": ["HTTPS"],
  "data_formats": ["JSON"],
  "company": "Open-Meteo",
  "company_url": "https://open-meteo.com",
  "country": null,
  "language": "en",
  "status": "active",
  "health_score": 97,
  "last_checked": "2026-04-14T08:00:00Z",
  "http_status": 200,
  "response_time_ms": 145,
  "ssl_valid": true,
  "ssl_expiry": "2026-12-01",
  "source_names": ["public_apis_github", "apis_guru"],
  "discovered_at": "2026-01-01T00:00:00Z",
  "endpoints": null,
  "health_history": null
}
```

---

### GET /apis/search

Semantic / natural language search. Finds APIs by meaning, not keywords.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `ask` | string | **Required.** Natural language query |
| `auth` | string | Optional filter: `none`, `apikey`, etc. |
| `limit` | integer | Max results (default 10, max 50) |
| `min_similarity` | float | Min cosine similarity 0-1 (default 0.5) |

**Example:**
```http
GET /apis/search?ask=I+need+to+convert+a+Word+document+to+PDF+server+side&auth=none
```

**Response:**
```json
{
  "query": "I need to convert a Word document to PDF server side",
  "results": [
    {
      "id": "...",
      "name": "...",
      "description_llm": "...",
      "similarity": 0.89,
      "auth_type": "none",
      "base_url": "...",
      "categories": [...]
    }
  ]
}
```

**Implementation Note:** The query text is embedded using the same model used
for API embeddings, then a nearest-neighbor search runs against the `embedding`
column using pgvector's `<=>` (cosine distance) operator.

---

### GET /categories

List all categories with API counts.

**Query Parameters:**
- `auth` — filter counts to only APIs with this auth type
- `min_count` — minimum API count to include (default 1)

**Response:**
```json
{
  "categories": [
    {
      "category": "Weather & Environment > Current Weather",
      "api_count": 45,
      "no_auth_count": 12,
      "active_count": 38
    }
  ]
}
```

---

### GET /tags

List all tags with frequencies.

**Query Parameters:**
- `search` — filter tags by prefix
- `limit` — max tags returned (default 100)

---

### GET /stats

Database-wide statistics.

**Response:**
```json
{
  "total_apis": 87432,
  "active_apis": 72100,
  "dead_apis": 12100,
  "unknown_apis": 3232,
  "no_auth_apis": 18500,
  "apis_with_spec": 22000,
  "categories_count": 89,
  "sources_count": 34,
  "last_scraped": "2026-04-15T06:00:00Z",
  "last_validated": "2026-04-15T08:00:00Z",
  "db_size_mb": 4200,
  "scraper_stats": [
    {
      "scraper": "public_apis_github",
      "last_run": "2026-04-15T06:00:00Z",
      "apis_contributed": 1487,
      "status": "success"
    }
  ]
}
```

---

### GET /health

System health check for monitoring/load balancers.

**Response (200 OK):**
```json
{
  "status": "ok",
  "database": "ok",
  "pipeline": "ok",
  "version": "1.0.0",
  "uptime_seconds": 86400
}
```

**Response (503 Service Unavailable):**
```json
{
  "status": "degraded",
  "database": "ok",
  "pipeline": "error",
  "error": "Pipeline worker not responding"
}
```

---

### GET /apis/{id}/similar

Find APIs similar to a given one using semantic similarity.

**Path Parameters:**
- `id` — UUID or slug

**Query Parameters:**
- `limit` — max results (default 5, max 20)
- `auth` — filter by auth type

---

### POST /admin/validate/{id}

Trigger immediate re-validation of a specific API.
(Admin endpoint — protected by `ADMIN_KEY` env var if configured)

---

### POST /admin/enrich/{id}

Trigger immediate re-enrichment of a specific API.
(Admin endpoint)

---

## Error Codes

| Code | HTTP Status | Meaning |
|---|---|---|
| `not_found` | 404 | API ID or slug doesn't exist |
| `invalid_parameter` | 400 | Invalid query parameter value |
| `missing_parameter` | 400 | Required parameter absent |
| `rate_limited` | 429 | Too many requests |
| `search_unavailable` | 503 | Semantic search not available (no embeddings yet) |
| `internal_error` | 500 | Unexpected server error |

---

## Rate Limiting

Default limits (configurable via env vars):
- 100 requests/minute per IP (general)
- 20 requests/minute for `/apis/search` (semantic search is expensive)
- No limit on `/health` and `/stats`

Rate limit headers returned:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1713168000
```

---

## CORS

CORS is enabled for all origins by default (self-hosted). Configure via:
```
CORS_ORIGINS=https://yourdomain.com,https://anotherdomain.com
```
