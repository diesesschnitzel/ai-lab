# Scraper Design
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## 1. Design Principles

- **Idempotent**: Re-running a scraper produces the same result; no double-inserts
- **Isolated**: Each scraper is a standalone async function; failure doesn't affect others
- **Respectful**: Obey robots.txt, rate-limit outbound requests per domain
- **Observable**: Every run is logged; structured output throughout
- **Testable**: Each scraper can run against a fixture/mock without network access

---

## 2. Scraper Interface

Every scraper module must implement this interface:

```python
# src/scrapers/base.py

from dataclasses import dataclass, field
from typing import AsyncIterator

@dataclass
class RawCandidate:
    source_name: str
    source_url: str | None
    raw_name: str | None
    raw_description: str | None
    raw_base_url: str | None
    raw_docs_url: str | None
    raw_auth_type: str | None       # 'none' | 'apikey' | 'oauth2' | None
    raw_json: dict = field(default_factory=dict)


@dataclass
class ScraperResult:
    scraper_name: str
    candidates: list[RawCandidate]
    errors: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class BaseScraper:
    name: str = "base"
    frequency_hours: int = 24

    async def run(self) -> AsyncIterator[RawCandidate]:
        """
        Yield RawCandidate records one at a time.
        Must be implemented by each scraper.
        Should handle its own errors and continue (not crash the run).
        """
        raise NotImplementedError
```

---

## 3. Scraper Runner

The runner manages execution, logging, and error isolation:

```python
# src/scrapers/runner.py

async def run_scraper(scraper: BaseScraper, db: Database) -> ScraperResult:
    run_id = await db.start_scraper_run(scraper.name)
    found = 0
    errors = []

    try:
        async with asyncio.timeout(scraper.timeout_seconds):
            async for candidate in scraper.run():
                try:
                    await db.insert_raw_candidate(candidate)
                    found += 1
                except Exception as e:
                    errors.append(str(e))
                    # Continue; don't abort the run

        await db.finish_scraper_run(run_id, 'success', found, errors)

    except asyncio.TimeoutError:
        await db.finish_scraper_run(run_id, 'timeout', found, errors)
    except Exception as e:
        await db.finish_scraper_run(run_id, 'failed', found, [str(e)])

    return ScraperResult(scraper.name, found, errors)
```

---

## 4. HTTP Client Configuration

All scrapers use a shared httpx client with these defaults:

```python
# src/scrapers/http.py

import httpx

DEFAULT_HEADERS = {
    "User-Agent": "APIVault/1.0 (api-discovery-bot; +https://github.com/diesesschnitzel/dummy)",
    "Accept": "application/json, text/html;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
}

DEFAULT_LIMITS = httpx.Limits(
    max_connections=100,
    max_keepalive_connections=20,
    keepalive_expiry=30,
)

def make_client(timeout: float = 15.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers=DEFAULT_HEADERS,
        limits=DEFAULT_LIMITS,
        timeout=httpx.Timeout(timeout),
        follow_redirects=True,
        max_redirects=5,
        http2=True,
    )
```

**Per-domain rate limiting:**
```python
# src/scrapers/ratelimiter.py

from asyncio import Semaphore
from collections import defaultdict

_domain_semaphores: dict[str, Semaphore] = defaultdict(lambda: Semaphore(1))
_domain_last_call: dict[str, float] = {}
MIN_DELAY_SECONDS = 1.0  # max 1 request/second per domain

async def throttled_get(client, url, **kwargs):
    domain = urlparse(url).netloc
    async with _domain_semaphores[domain]:
        now = time.monotonic()
        last = _domain_last_call.get(domain, 0)
        wait = max(0, MIN_DELAY_SECONDS - (now - last))
        if wait:
            await asyncio.sleep(wait)
        _domain_last_call[domain] = time.monotonic()
        return await client.get(url, **kwargs)
```

---

## 5. Key Scraper Implementations

### 5.1 public_apis_github.py

```
Source: github.com/public-apis/public-apis
Method: Download README.md via GitHub API, parse markdown tables
Format: Markdown tables with columns: API | Description | Auth | HTTPS | CORS | Link
Frequency: Every 6 hours
Est. yield: 1,500 APIs
Auth needed: None (GitHub unauthenticated allows 60 req/hour; use token for 5000)
```

Parse strategy:
- Download raw README.md
- Split on `## ` headings → each heading is a category
- For each section, parse markdown table rows
- Extract: Name, Description, Auth (None/apiKey/OAuth), Link

```python
async def run(self) -> AsyncIterator[RawCandidate]:
    url = "https://raw.githubusercontent.com/public-apis/public-apis/master/README.md"
    content = await self.fetch_text(url)
    
    current_category = "Unknown"
    for line in content.splitlines():
        if line.startswith("## "):
            current_category = line[3:].strip()
        elif line.startswith("| ") and not line.startswith("| API ") and "---" not in line:
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 4:
                name, desc, auth, https_flag, *rest = parts
                link = rest[-1] if rest else ""
                # extract URL from markdown link [text](url)
                url_match = re.search(r'\[.*?\]\((.*?)\)', link)
                base_url = url_match.group(1) if url_match else None
                yield RawCandidate(
                    source_name=self.name,
                    source_url="https://github.com/public-apis/public-apis",
                    raw_name=name,
                    raw_description=desc,
                    raw_base_url=base_url,
                    raw_docs_url=base_url,
                    raw_auth_type=None if auth.lower() == "no" else auth.lower(),
                    raw_json={"category": current_category, "https": https_flag}
                )
```

---

### 5.2 apis_guru.py

```
Source: apis.guru (openapi-directory)
Method: GET https://api.apis.guru/v2/list.json → returns all APIs with OpenAPI spec URLs
Format: JSON object keyed by API name
Frequency: Every 6 hours
Est. yield: 2,500 APIs with full OpenAPI specs
Auth needed: None
```

Each entry includes: `title`, `description`, `externalDocs`, `versions`, `preferred version`,
`swaggerUrl`, `openAPIUrl`, `info.x-apisguru-categories`

---

### 5.3 postman_network.py

```
Source: Postman Public API Network
Method: GET https://api.getpostman.com/workspaces?type=public (no auth required for public)
        Also: explore.postman.com scrape
Format: JSON
Frequency: Every 24 hours
Est. yield: 50,000+ collections
Auth needed: None for public browsing
```

Filter: Only import collections that appear to be API references (not just examples).
Scoring: collections with >3 requests, description, and a base URL score higher.

---

### 5.4 npm.py (Registry Miner)

```
Source: npm registry
Method 1: npm search API — GET https://registry.npmjs.org/-/v1/search?text=api-client&size=200
Method 2: CouchDB replication dump — replicate from https://replicate.npmjs.com
Format: JSON
Frequency: Method 1 daily, Method 2 weekly (full dump ~50GB compressed)
Est. yield: 30,000 API wrapper packages
Auth needed: None
```

Search queries to run:
```python
SEARCH_TERMS = [
    "api-client", "api-wrapper", "api-sdk", "rest-client",
    "graphql-client", "openapi-client", "swagger-client",
    # Domain-specific
    "weather-api", "payment-api", "maps-api", "sms-api",
]
```

URL extraction from npm package:
1. Check `package.json` homepage field
2. Search README for URLs matching `https?://(?:api|developer|dev)\.`
3. Check repository field → look at source files for BASE_URL constants
4. Search keywords for "api", "rest", "sdk"

---

### 5.5 cert_transparency.py

```
Source: crt.sh (Certificate Transparency Log aggregator)
Method: Direct PostgreSQL connection to crt.sh public database
Host: crt.sh port 5432
Database: certwatch
User: guest (no password)
Frequency: Weekly
Est. yield: 100,000+ domain candidates (needs heavy filtering)
```

```python
QUERY = """
SELECT DISTINCT lower(name_value) as domain
FROM certificate_transparency
WHERE (
    lower(name_value) SIMILAR TO 'api\.%'
    OR lower(name_value) SIMILAR TO 'developer\.%'
    OR lower(name_value) SIMILAR TO '%.api\.%'
    OR lower(name_value) SIMILAR TO '%\.api'
    OR lower(name_value) SIMILAR TO 'rest\.%'
    OR lower(name_value) SIMILAR TO 'graphql\.%'
)
AND name_value NOT LIKE '%*%'
AND length(name_value) < 100
ORDER BY domain
LIMIT 500000;
"""
```

Post-processing: DNS probe all → HTTP probe survivors → filter to API responses.

---

### 5.6 ckan_crawler.py

```
Source: All known CKAN open data portals worldwide
Method: CKAN Action API: GET /api/3/action/package_list
        Then: GET /api/3/action/package_show?id={name} for each
Format: JSON (standardized CKAN format)
Frequency: Weekly
Est. yield: 50,000+ datasets, filter to those with API/endpoint resources
```

```python
CKAN_INSTANCES = [
    "https://data.gov",
    "https://data.gov.uk",
    "https://open.canada.ca",
    "https://data.europa.eu",
    "https://data.gov.au",
    # ... 190+ more
]

async def crawl_instance(self, base_url: str) -> AsyncIterator[RawCandidate]:
    list_url = f"{base_url}/api/3/action/package_list"
    response = await self.client.get(list_url, timeout=30)
    packages = response.json()["result"]
    
    for package_id in packages:
        package = await self.get_package(base_url, package_id)
        # Look for resources with format=API or URL containing /api/
        for resource in package.get("resources", []):
            if self.is_api_resource(resource):
                yield self.to_candidate(package, resource, base_url)
```

---

## 6. Playwright Scrapers

Some sources require JavaScript rendering. These use Playwright:

```python
# src/scrapers/browser.py

from playwright.async_api import async_playwright

class BrowserScraper(BaseScraper):
    async def fetch_rendered(self, url: str) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            content = await page.content()
            await browser.close()
            return content
```

Used for: rapidapi.com, stoplight.io/explore, some government portals.

---

## 7. Robots.txt Compliance

```python
# src/scrapers/robots.py

from urllib.robotparser import RobotFileParser

_robots_cache: dict[str, RobotFileParser] = {}

async def is_allowed(url: str, user_agent: str = "APIVault") -> bool:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    
    if base not in _robots_cache:
        rp = RobotFileParser()
        rp.set_url(f"{base}/robots.txt")
        try:
            rp.read()
        except Exception:
            return True  # If robots.txt is inaccessible, assume allowed
        _robots_cache[base] = rp
    
    return _robots_cache[base].can_fetch(user_agent, url)
```

---

## 8. Scraper Configuration

Each scraper reads from config:

```python
@dataclass
class ScraperConfig:
    enabled: bool = True
    frequency_hours: int = 24
    timeout_seconds: int = 3600       # 1 hour max per run
    max_candidates_per_run: int = 100_000
    request_delay_seconds: float = 1.0
    max_retries: int = 3
    proxy: str | None = None          # Optional proxy URL
```

Override per-scraper via environment variable:
`SCRAPER_PUBLIC_APIS_FREQUENCY_HOURS=1`

---

## 9. Error Handling Within Scrapers

```python
# Pattern: catch, log, continue — never crash the run

async def run(self) -> AsyncIterator[RawCandidate]:
    for page in range(1, MAX_PAGES + 1):
        try:
            data = await self.fetch_page(page)
            for item in data["results"]:
                try:
                    yield self.parse_item(item)
                except ParseError as e:
                    self.log.warning(f"Parse error on item: {e}", item=item)
                    # Continue to next item
        except httpx.TimeoutException:
            self.log.error(f"Timeout on page {page}, skipping")
            continue
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                await asyncio.sleep(60)  # Rate limited, back off
                continue
            raise  # Other HTTP errors propagate up
```
