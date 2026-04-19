# Database Schema
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15
**Database:** PostgreSQL 16 + pgvector extension

---

## Setup

```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- for trigram similarity
```

---

## Table: raw_candidates

```sql
CREATE TABLE raw_candidates (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_name     TEXT NOT NULL,
    source_url      TEXT,
    raw_name        TEXT,
    raw_description TEXT,
    raw_base_url    TEXT,
    raw_docs_url    TEXT,
    raw_auth_type   TEXT,
    raw_json        JSONB,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','processing','done','failed')),
    error           TEXT,
    discovered_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at    TIMESTAMPTZ,
    apis_id         UUID,  -- set after processing; not a FK (api may not exist yet)

    CONSTRAINT raw_candidates_status_check
        CHECK (status IN ('pending','processing','done','failed'))
);

-- Indexes
CREATE INDEX idx_raw_candidates_status ON raw_candidates (status);
CREATE INDEX idx_raw_candidates_source ON raw_candidates (source_name);
CREATE INDEX idx_raw_candidates_discovered ON raw_candidates (discovered_at);
CREATE INDEX idx_raw_candidates_url ON raw_candidates (raw_base_url)
    WHERE raw_base_url IS NOT NULL;
```

---

## Table: scraper_runs

```sql
CREATE TABLE scraper_runs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scraper_name        TEXT NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at         TIMESTAMPTZ,
    status              TEXT NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running','success','failed','timeout')),
    candidates_found    INT DEFAULT 0,
    candidates_new      INT DEFAULT 0,
    candidates_updated  INT DEFAULT 0,
    error               TEXT,
    config_snapshot     JSONB
);

-- Indexes
CREATE INDEX idx_scraper_runs_name ON scraper_runs (scraper_name);
CREATE INDEX idx_scraper_runs_started ON scraper_runs (started_at DESC);
CREATE INDEX idx_scraper_runs_status ON scraper_runs (status);
```

---

## Table: apis (Primary)

```sql
CREATE TABLE apis (
    -- Identity
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug                TEXT UNIQUE,
    name                TEXT NOT NULL,

    -- Description
    description         TEXT,
    description_llm     TEXT,
    version             TEXT,

    -- URLs
    base_url            TEXT,
    docs_url            TEXT,
    spec_url            TEXT,
    postman_url         TEXT,
    signup_url          TEXT,

    -- Auth & Access
    auth_type           TEXT DEFAULT 'unknown'
                        CHECK (auth_type IN (
                            'none','apikey','oauth2','basic','bearer','unknown'
                        )),
    auth_notes          TEXT,
    signup_required     BOOLEAN DEFAULT false,
    login_required      BOOLEAN DEFAULT false,

    -- Pricing
    free_tier           TEXT,
    rate_limit          TEXT,
    rate_limit_header   TEXT,
    pricing_url         TEXT,

    -- Classification
    categories          TEXT[] DEFAULT '{}',
    tags                TEXT[] DEFAULT '{}',
    use_cases           TEXT[] DEFAULT '{}',
    formats             TEXT[] DEFAULT '{}',
    protocols           TEXT[] DEFAULT '{}',
    data_formats        TEXT[] DEFAULT '{}',
    openapi_version     TEXT,

    -- Geographic / Language
    country             TEXT,       -- ISO 3166-1 alpha-2
    language            TEXT,       -- ISO 639-1

    -- Company
    company             TEXT,
    company_url         TEXT,

    -- Source Tracking
    source_names        TEXT[] DEFAULT '{}',
    source_urls         TEXT[] DEFAULT '{}',
    discovered_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Validation
    status              TEXT NOT NULL DEFAULT 'unknown'
                        CHECK (status IN (
                            'unknown','pending_validation','active',
                            'degraded','dead'
                        )),
    health_score        INT CHECK (health_score BETWEEN 0 AND 100),
    last_checked        TIMESTAMPTZ,
    http_status         INT,
    response_time_ms    INT,
    ssl_valid           BOOLEAN,
    ssl_expiry          DATE,
    dns_resolves        BOOLEAN,
    consecutive_failures INT DEFAULT 0,

    -- Enrichment tracking
    enriched_at         TIMESTAMPTZ,
    embedding_model     TEXT,       -- which model generated the embedding

    -- Search
    embedding           vector(1536),
    fts                 tsvector,

    -- Metadata
    raw_json            JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Indexes for apis

```sql
-- Primary lookups
CREATE UNIQUE INDEX idx_apis_slug ON apis (slug) WHERE slug IS NOT NULL;
CREATE INDEX idx_apis_base_url ON apis (base_url) WHERE base_url IS NOT NULL;

-- Status & filtering
CREATE INDEX idx_apis_status ON apis (status);
CREATE INDEX idx_apis_auth_type ON apis (auth_type);
CREATE INDEX idx_apis_health_score ON apis (health_score DESC);
CREATE INDEX idx_apis_last_checked ON apis (last_checked);
CREATE INDEX idx_apis_country ON apis (country) WHERE country IS NOT NULL;

-- Array field indexes (for filtering and containment queries)
CREATE INDEX idx_apis_categories ON apis USING GIN (categories);
CREATE INDEX idx_apis_tags ON apis USING GIN (tags);
CREATE INDEX idx_apis_formats ON apis USING GIN (formats);
CREATE INDEX idx_apis_source_names ON apis USING GIN (source_names);

-- Full-text search
CREATE INDEX idx_apis_fts ON apis USING GIN (fts);

-- Semantic search (IVFFlat index for approximate nearest neighbor)
-- Create AFTER the table has >10k rows for meaningful clustering
CREATE INDEX idx_apis_embedding ON apis
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 200);

-- Compound indexes for common query patterns
CREATE INDEX idx_apis_status_auth ON apis (status, auth_type);
CREATE INDEX idx_apis_status_score ON apis (status, health_score DESC)
    WHERE status = 'active';

-- Discovery queue index
CREATE INDEX idx_apis_pending_validation ON apis (created_at)
    WHERE status = 'pending_validation';

-- Enrichment queue index
CREATE INDEX idx_apis_pending_enrichment ON apis (created_at)
    WHERE enriched_at IS NULL AND status != 'dead';
```

### Full-text search trigger

```sql
-- Auto-update fts column when name, description, tags change
CREATE OR REPLACE FUNCTION apis_fts_update() RETURNS trigger AS $$
BEGIN
    NEW.fts :=
        setweight(to_tsvector('english', coalesce(NEW.name, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.description_llm, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(array_to_string(NEW.tags, ' '), '')), 'C') ||
        setweight(to_tsvector('english', coalesce(array_to_string(NEW.categories, ' '), '')), 'C') ||
        setweight(to_tsvector('english', coalesce(array_to_string(NEW.use_cases, ' '), '')), 'D');
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER apis_fts_trigger
    BEFORE INSERT OR UPDATE ON apis
    FOR EACH ROW EXECUTE FUNCTION apis_fts_update();
```

---

## Table: api_endpoints

```sql
CREATE TABLE api_endpoints (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    api_id          UUID NOT NULL REFERENCES apis(id) ON DELETE CASCADE,
    method          TEXT NOT NULL CHECK (method IN (
                        'GET','POST','PUT','PATCH','DELETE',
                        'HEAD','OPTIONS','TRACE'
                    )),
    path            TEXT NOT NULL,
    summary         TEXT,
    description     TEXT,
    tags            TEXT[] DEFAULT '{}',
    parameters      JSONB,
    request_body    JSONB,
    responses       JSONB,
    auth_required   BOOLEAN DEFAULT false,
    example_request JSONB,
    example_response JSONB,
    deprecated      BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_endpoints_api_id ON api_endpoints (api_id);
CREATE INDEX idx_endpoints_method ON api_endpoints (method);
CREATE INDEX idx_endpoints_deprecated ON api_endpoints (deprecated)
    WHERE deprecated = false;

-- Unique constraint: one method+path per API
CREATE UNIQUE INDEX idx_endpoints_unique
    ON api_endpoints (api_id, method, path);
```

---

## Table: api_health_log

```sql
CREATE TABLE api_health_log (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    api_id              UUID NOT NULL REFERENCES apis(id) ON DELETE CASCADE,
    checked_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    status              TEXT NOT NULL
                        CHECK (status IN ('alive','dead','degraded','error')),
    http_status         INT,
    response_time_ms    INT,
    dns_resolves        BOOLEAN,
    ssl_valid           BOOLEAN,
    auth_type_detected  TEXT,
    rate_limit_detected TEXT,
    error               TEXT,
    checker_version     TEXT
) PARTITION BY RANGE (checked_at);

-- Create partitions by quarter
CREATE TABLE api_health_log_2026_q1
    PARTITION OF api_health_log
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');

CREATE TABLE api_health_log_2026_q2
    PARTITION OF api_health_log
    FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');

CREATE TABLE api_health_log_2026_q3
    PARTITION OF api_health_log
    FOR VALUES FROM ('2026-07-01') TO ('2026-10-01');

CREATE TABLE api_health_log_2026_q4
    PARTITION OF api_health_log
    FOR VALUES FROM ('2026-10-01') TO ('2027-01-01');

-- Indexes (created on each partition automatically)
CREATE INDEX idx_health_log_api_id ON api_health_log (api_id, checked_at DESC);
CREATE INDEX idx_health_log_checked ON api_health_log (checked_at DESC);
CREATE INDEX idx_health_log_status ON api_health_log (status, checked_at DESC);
```

---

## View: v_apis_live

```sql
CREATE OR REPLACE VIEW v_apis_live AS
SELECT
    id, slug, name, description_llm, base_url, docs_url, spec_url,
    auth_type, auth_notes, signup_required,
    free_tier, rate_limit,
    categories, tags, use_cases, formats, data_formats,
    country, language, company,
    health_score, last_checked, http_status, response_time_ms,
    discovered_at
FROM apis
WHERE status = 'active'
  AND health_score >= 50
  AND dns_resolves = true;

COMMENT ON VIEW v_apis_live IS
    'Active, healthy APIs suitable for display in search results';
```

---

## Materialized View: mv_category_counts

```sql
CREATE MATERIALIZED VIEW mv_category_counts AS
SELECT
    unnest(categories) AS category,
    count(*) AS api_count,
    count(*) FILTER (WHERE auth_type = 'none') AS no_auth_count,
    count(*) FILTER (WHERE status = 'active') AS active_count
FROM apis
WHERE status = 'active'
GROUP BY 1
ORDER BY 2 DESC;

CREATE UNIQUE INDEX ON mv_category_counts (category);

-- Refresh on schedule (every 6 hours in the scheduler)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_category_counts;
```

---

## Common Queries

### Keyword search
```sql
SELECT id, name, description_llm, base_url, auth_type, categories, health_score,
       ts_rank(fts, query) AS rank
FROM apis, to_tsquery('english', 'pdf & convert') query
WHERE fts @@ query
  AND status = 'active'
ORDER BY rank DESC
LIMIT 20;
```

### Semantic search
```sql
SELECT id, name, description_llm, base_url, auth_type, categories,
       1 - (embedding <=> $1::vector) AS similarity
FROM apis
WHERE status = 'active'
  AND embedding IS NOT NULL
ORDER BY embedding <=> $1::vector
LIMIT 20;
```

### Filter: no auth, specific category
```sql
SELECT id, name, description_llm, base_url, rate_limit, health_score
FROM apis
WHERE status = 'active'
  AND auth_type = 'none'
  AND categories @> ARRAY['Document Processing']
ORDER BY health_score DESC
LIMIT 50;
```

### APIs due for re-validation
```sql
SELECT id, base_url, last_checked, status
FROM apis
WHERE last_checked < now() - INTERVAL '7 days'
   OR last_checked IS NULL
ORDER BY last_checked ASC NULLS FIRST
LIMIT 100;
```

### APIs needing enrichment
```sql
SELECT id, name, description, base_url
FROM apis
WHERE enriched_at IS NULL
  AND status != 'dead'
  AND (description IS NOT NULL OR docs_url IS NOT NULL)
ORDER BY created_at ASC
LIMIT 50;
```

---

## Maintenance Queries

```sql
-- Archive old health log entries (run monthly)
DELETE FROM api_health_log
WHERE checked_at < now() - INTERVAL '90 days';

-- Find duplicate base URLs (run after each bulk ingest)
SELECT base_url, count(*) FROM apis
GROUP BY base_url
HAVING count(*) > 1;

-- Dead API cleanup report
SELECT count(*) as dead_count,
       count(*) FILTER (WHERE consecutive_failures >= 10) as very_dead
FROM apis WHERE status = 'dead';

-- Source coverage
SELECT unnest(source_names) as source, count(*)
FROM apis GROUP BY 1 ORDER BY 2 DESC;
```
