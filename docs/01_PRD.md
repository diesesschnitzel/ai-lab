# Product Requirements Document (PRD)
# APIVault — Comprehensive Free API Database

**Version:** 1.0
**Status:** Approved
**Last Updated:** 2026-04-15

---

## 1. Problem Statement

Developers constantly need external APIs to add functionality to their applications.
The problem is not that APIs don't exist — it's that they are impossible to discover.
Thousands of free, no-auth or low-auth APIs exist across:

- Obscure company developer portals
- Government open data initiatives
- Academic and research institutions
- Open source communities
- Package registry client libraries
- GitHub repositories

A developer building a document processing service may not know that a free PDF
extraction API exists from a company they've never heard of. A developer needing
geographic data may not know 40 free geocoding APIs exist beyond Google Maps.

There is no single, complete, continuously validated, searchable source of truth
for free APIs. Existing directories are:
- Incomplete (cover <5% of what exists)
- Stale (not actively validated)
- Hard to search (keyword only, no semantic understanding)
- Opaque about auth requirements and rate limits

---

## 2. Goal

Build **APIVault**: a self-hosted system that discovers, validates, enriches, and
serves a comprehensive, continuously updated database of free APIs — queryable by
keyword, category, or natural language.

---

## 3. Objectives

| Objective | Metric | Target |
|---|---|---|
| Comprehensiveness | APIs indexed | 90,000+ verified |
| Freshness | Max age of validation | 7 days |
| Accuracy | False positive rate (dead APIs marked alive) | <2% |
| Search quality | Relevant result in top 5 | >90% of queries |
| Query speed | P99 keyword search latency | <100ms |
| Query speed | P99 semantic search latency | <500ms |
| Uptime | API availability | 99.5% |

---

## 4. Non-Goals

- This system does NOT call the external APIs on behalf of users
- This system does NOT manage API keys or credentials for users
- This system does NOT provide paid API discovery (paid-only APIs are excluded)
- This system does NOT guarantee the correctness of indexed API documentation
- This system is NOT a proxy or gateway

---

## 5. Users

### Primary: Developer (Solo / Small Team)
- Building products and needs to add capabilities quickly
- Doesn't know what APIs exist for a given domain
- Wants to filter by: no auth required, free, specific category
- Typical query: "What free APIs exist for currency conversion?"

### Secondary: Technical Architect
- Evaluating options before building a feature in-house
- Needs to know rate limits, reliability, auth overhead
- Typical query: "Show me all PDF processing APIs, no signup required"

### Tertiary: API Researcher / Cataloguer
- Wants to understand the API landscape in a domain
- Browses by category, exports lists
- Uses the database as a reference, not just a one-time search

---

## 6. User Stories

### Discovery
- As a developer, I want to search for APIs by what they do in plain English,
  so I don't need to know the exact terminology
- As a developer, I want to filter APIs by auth requirement (none, API key, OAuth),
  so I can find ones I can use immediately without signing up
- As a developer, I want to see rate limits upfront, so I can assess fit before
  reading full documentation
- As a developer, I want to browse by category, so I can explore what exists in
  a domain I'm unfamiliar with

### Validation
- As a developer, I want to know if an API is currently alive before I invest time
  integrating it, so I don't waste time on dead endpoints
- As a developer, I want to see when an API was last validated, so I can assess
  how trustworthy the status is

### Detail
- As a developer, I want to see example endpoints for an API, so I can quickly
  judge if it does what I need
- As a developer, I want direct links to documentation and OpenAPI specs, so I
  can go deeper without extra searching
- As a developer, I want to see what similar APIs exist, so I can compare options

### API (programmatic use)
- As a developer, I want to query APIVault programmatically, so I can integrate
  discovery into my own tools or agents
- As an AI agent, I want to call the APIVault API to discover what tools are
  available for a given task

---

## 7. Functional Requirements

### FR-01: Discovery
- The system MUST continuously discover APIs from at least 30 distinct source types
- The system MUST process package registries (npm, PyPI, RubyGems, NuGet, crates.io)
- The system MUST crawl GitHub for OpenAPI/Swagger specification files
- The system MUST query certificate transparency logs for API subdomains
- The system MUST index all known public API directories
- The system MUST crawl government open data portals in at least 50 countries
- The system MUST mine community sources (HackerNews, Reddit, dev.to)
- The system MUST process Postman public collections

### FR-02: Validation
- Every indexed API MUST be validated within 7 days of last check
- Validation MUST include: DNS resolution, HTTP reachability, SSL validity
- Validation MUST detect and record auth type (none / API key / OAuth / other)
- Validation MUST record HTTP status codes and response times
- Newly discovered APIs MUST be validated within 24 hours of discovery
- Dead APIs MUST be retried 3 times over 3 days before being marked dead
- Dead APIs MUST be retained in the database with status=dead (not deleted)

### FR-03: Enrichment
- Every API MUST receive LLM-generated tags, categories, and use cases
- Every API MUST have an embedding generated for semantic search
- Every API MUST have a plain-language description generated if one doesn't exist
- Rate limit information MUST be extracted from response headers where available

### FR-04: Deduplication
- The system MUST detect duplicate APIs across different discovery sources
- Duplicates MUST be merged, preserving all source references
- The system MUST not create two records for the same base URL

### FR-05: Search
- The system MUST support keyword (full-text) search
- The system MUST support semantic / natural language search
- The system MUST support filtering by: auth_type, category, status, country,
  rate_limit, format, has_openapi_spec
- The system MUST return results ranked by relevance score
- The system MUST support pagination

### FR-06: API
- The system MUST expose a REST API for all search and browse operations
- The API MUST be self-documenting (OpenAPI spec served at /docs)
- The API MUST include health/status endpoints
- The API MUST support CORS for browser-based use

### FR-07: Operations
- All scraper runs MUST be logged with: source, start time, duration, records found, errors
- The system MUST expose metrics for monitoring
- The system MUST send alerts when validation error rates exceed thresholds
- Configuration MUST be fully environment-variable driven

---

## 8. Non-Functional Requirements

### Performance
- Ingest pipeline: process 10,000 raw candidates per hour minimum
- Validation: probe 5,000 APIs per hour minimum
- Keyword search: P99 < 100ms at 100 concurrent users
- Semantic search: P99 < 500ms at 100 concurrent users
- Database: support 100,000+ API records without degradation

### Reliability
- Scraper failures MUST NOT affect API availability
- Individual scraper crashes MUST be isolated (not crash other scrapers)
- Database writes MUST be idempotent (safe to retry)
- All scheduled jobs MUST have timeout limits

### Security
- The system MUST respect robots.txt on all scraped sites
- The system MUST rate-limit its own outbound requests (max 1 req/sec per domain)
- The system MUST NOT store any credentials scraped from external sources
- The public API MUST be rate-limited to prevent abuse

### Maintainability
- Each scraper module MUST be independently testable
- Adding a new source MUST require changes to only one file
- All configuration MUST be documented in docs/14_CONFIGURATION.md
- All scraper modules MUST emit structured logs

---

## 9. Constraints

- Must run on a single machine with 8GB RAM minimum (self-hosted friendly)
- Must be deployable via Docker Compose without Kubernetes
- All dependencies must be open source
- Must not require paid services to operate at base level
- LLM enrichment: must support local models (Ollama) as an alternative to paid APIs

---

## 10. Success Criteria

At launch (Phase 1 complete):
- 15,000+ verified APIs in the database
- All Tier 1 directory sources indexed
- Keyword search working
- Validation running on schedule

At maturity (Phase 3 complete):
- 90,000+ verified APIs
- Semantic search working
- All 30+ source types active
- Monitoring and alerting live
- Documentation complete
