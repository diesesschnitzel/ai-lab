# Testing Strategy
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## 1. Testing Philosophy

- **Scrapers:** Test normalization logic and output parsing in isolation.
  Do not hit real external URLs in unit tests.
- **Pipeline:** Test state transitions; mock database for unit tests.
- **API:** Integration test against a real test database. No mocks.
- **Validation:** Unit test probe logic; mock HTTP client.
- **Coverage target:** 80% for pipeline and API; 60% for scrapers (complex parsing logic)

---

## 2. Test Types

### Unit Tests

Test individual functions in isolation with mocked dependencies.
Located in `tests/unit/`.

```
tests/unit/
├── scrapers/
│   ├── test_public_apis_github.py    # Test markdown parsing
│   ├── test_normalizer.py            # URL canonicalization, auth normalization
│   └── test_deduplicator.py          # Matching logic, merge strategy
├── validators/
│   ├── test_prober.py                # Probe logic with mocked httpx
│   ├── test_health_score.py          # Score calculation
│   └── test_auth_detector.py        # Auth type detection from responses
├── enrichment/
│   ├── test_context_assembly.py
│   └── test_llm_output_validation.py # Validate LLM response parsing
└── api/
    ├── test_search_params.py         # Input validation
    └── test_query_builder.py         # SQL query construction
```

### Integration Tests

Test components against a real (test) PostgreSQL database.
Located in `tests/integration/`.

```
tests/integration/
├── test_pipeline_end_to_end.py       # Raw candidate → active API
├── test_validation_writes.py         # Probe result → health_log + apis update
├── test_search_api.py                # Full HTTP request → database → response
└── test_dedup_database.py           # Dedup against real DB with fixtures
```

### Scraper Smoke Tests

Run scrapers against real external URLs (not in CI; run manually or on schedule).
Located in `tests/smoke/`.

```
tests/smoke/
├── test_public_apis_live.py          # Verify source is still accessible
├── test_apis_guru_live.py
└── test_all_scrapers_reachable.py   # Each source returns >0 results
```

Run smoke tests manually:
```bash
pytest tests/smoke/ -v --smoke -k "not slow"
```

---

## 3. Test Infrastructure

### Fixtures

```python
# tests/conftest.py

import pytest
import asyncpg

@pytest.fixture(scope="session")
async def test_db():
    """Create a fresh test database for the test session."""
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("CREATE DATABASE apivault_test")
    await conn.close()
    
    test_conn = await asyncpg.connect(TEST_DATABASE_URL)
    await run_migrations(test_conn)
    yield test_conn
    
    await test_conn.close()
    # Drop test DB after session


@pytest.fixture
async def clean_db(test_db):
    """Truncate all tables before each test."""
    await test_db.execute("""
        TRUNCATE apis, raw_candidates, api_endpoints,
                 api_health_log, scraper_runs CASCADE
    """)
    yield test_db


@pytest.fixture
def sample_api():
    return {
        "name": "Open-Meteo Weather API",
        "base_url": "https://api.open-meteo.com/v1",
        "docs_url": "https://open-meteo.com/en/docs",
        "auth_type": "none",
        "description": "Free weather API, no key required",
    }


@pytest.fixture
def mock_httpx_client():
    """Mock httpx client for validation tests."""
    with httpx_mock.AsyncMock() as mock:
        yield mock
```

---

## 4. Key Test Cases

### Normalizer Tests

```python
# tests/unit/scrapers/test_normalizer.py

@pytest.mark.parametrize("input,expected", [
    # URL canonicalization
    ("http://api.example.com/", "https://api.example.com"),
    ("HTTPS://API.EXAMPLE.COM/v1/", "https://api.example.com/v1"),
    ("https://www.api.example.com", "https://api.example.com"),
    # Auth normalization
    ("No", "none"),
    ("apiKey", "apikey"),
    ("OAuth", "oauth2"),
    ("", "unknown"),
    (None, "unknown"),
])
def test_normalization(input, expected):
    ...
```

### Deduplication Tests

```python
def test_exact_url_match_finds_duplicate(clean_db, sample_api):
    # Insert an API
    api_id = insert_api(clean_db, sample_api)
    
    # Try to insert the same URL
    result = dedup_check(clean_db, sample_api["base_url"], sample_api["name"])
    
    assert result.is_duplicate == True
    assert result.existing_id == api_id


def test_different_apis_not_merged(clean_db):
    api1 = {"name": "Stripe Payments API", "base_url": "https://api.stripe.com/v1/charges"}
    api2 = {"name": "Stripe Connect API", "base_url": "https://api.stripe.com/v1/accounts"}
    
    # Both from same domain, but different names — should NOT merge
    insert_api(clean_db, api1)
    result = dedup_check(clean_db, api2["base_url"], api2["name"])
    
    assert result.is_duplicate == False
```

### Health Score Tests

```python
@pytest.mark.parametrize("probe,expected_score", [
    (ProbeResult(dns_resolves=False), 0),
    (ProbeResult(dns_resolves=True, http_status=200, ssl_valid=True, response_time_ms=200), 100),
    (ProbeResult(dns_resolves=True, http_status=200, ssl_valid=False, response_time_ms=200), 80),
    (ProbeResult(dns_resolves=True, http_status=500, ssl_valid=True), 30),
    (ProbeResult(dns_resolves=True, http_status=0), 25),
])
def test_health_score(probe, expected_score):
    assert compute_health_score(probe) == expected_score
```

### API Endpoint Tests

```python
# tests/integration/test_search_api.py

async def test_keyword_search_returns_relevant_results(client, seeded_db):
    response = await client.get("/apis?q=weather")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    # Top result should be weather-related
    assert "weather" in data["results"][0]["name"].lower()


async def test_auth_filter_returns_only_matching(client, seeded_db):
    response = await client.get("/apis?auth=none")
    assert response.status_code == 200
    for api in response.json()["results"]:
        assert api["auth_type"] == "none"


async def test_invalid_per_page_returns_422(client):
    response = await client.get("/apis?per_page=999")
    assert response.status_code == 422


async def test_semantic_search_returns_results(client, seeded_db_with_embeddings):
    response = await client.get("/apis/search?ask=extract+text+from+pdf")
    assert response.status_code == 200
    assert len(response.json()["results"]) > 0
```

---

## 5. Running Tests

```bash
# All unit tests (fast, no network)
pytest tests/unit/ -v

# All integration tests (requires test DB)
pytest tests/integration/ -v

# With coverage
pytest tests/unit/ tests/integration/ --cov=src --cov-report=html

# Specific test file
pytest tests/unit/scrapers/test_normalizer.py -v

# Smoke tests (requires network, run manually)
pytest tests/smoke/ -v --run-smoke
```

---

## 6. CI Configuration

```yaml
# .github/workflows/test.yml (or equivalent)
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: apivault_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v2
      - run: uv sync
      - run: uv run pytest tests/unit/ tests/integration/ --cov=src -q
        env:
          TEST_DATABASE_URL: postgresql://postgres:test@localhost:5432/apivault_test
```

---

## 7. Test Data / Fixtures

Seed the test database with representative APIs:

```python
# tests/fixtures/seed_apis.py

SEED_APIS = [
    # No-auth weather API
    {"name": "Open-Meteo", "base_url": "https://api.open-meteo.com/v1",
     "auth_type": "none", "categories": ["Weather & Environment > Forecasting"]},
    
    # API key required
    {"name": "OpenWeatherMap", "base_url": "https://api.openweathermap.org/data/2.5",
     "auth_type": "apikey", "categories": ["Weather & Environment > Current Weather"]},
    
    # OAuth
    {"name": "Spotify API", "base_url": "https://api.spotify.com/v1",
     "auth_type": "oauth2", "categories": ["Media & Entertainment > Music"]},
    
    # Dead API (for testing dead filtering)
    {"name": "Defunct API", "base_url": "https://defunct.example.com/api",
     "status": "dead", "health_score": 0},
    
    # Government API
    {"name": "NASA API", "base_url": "https://api.nasa.gov",
     "auth_type": "apikey", "country": "US",
     "categories": ["Government & Public Data", "Science & Research > Astronomy"]},
]
```
