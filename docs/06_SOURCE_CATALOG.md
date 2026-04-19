# Source Catalog — Complete API Discovery Sources
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## How to Read This Document

Each source entry includes:
- **Method**: How we query it (API / scrape / clone / dump)
- **Auth needed**: Whether we need credentials to access the source
- **Frequency**: How often we run this scraper
- **Est. yield**: Estimated unique APIs per run
- **Priority**: 1 (run first) to 5 (run last)
- **Module**: Python file that implements it

---

## Tier 1: Structured Directories (Highest Quality)

These sources have curated, structured data about APIs. Parse first.

| # | Source | URL | Method | Auth | Frequency | Est. Yield | Priority | Module |
|---|---|---|---|---|---|---|---|---|
| 1 | public-apis GitHub | github.com/public-apis/public-apis | GitHub API + parse MD | None | 6h | 1,500 | 1 | `directories/public_apis_github.py` |
| 2 | apis.guru | apis.guru/openapi-directory | REST API | None | 6h | 2,500 | 1 | `directories/apis_guru.py` |
| 3 | apilist.fun | apilist.fun | JSON endpoint | None | 6h | 600 | 1 | `directories/apilist_fun.py` |
| 4 | any-api.com | any-api.com | HTML scrape | None | 24h | 500 | 1 | `directories/any_api_com.py` |
| 5 | public.apis.zone | public.apis.zone | JSON | None | 24h | 300 | 1 | `directories/public_apis_zone.py` |
| 6 | SwaggerHub (public) | swaggerhub.com/explore | Paginated API | None | 24h | 10,000 | 1 | `directories/swaggerhub.py` |
| 7 | Postman Public Network | api.getpostman.com | REST API | None | 24h | 50,000 | 1 | `directories/postman_network.py` |
| 8 | Stoplight Explore | stoplight.io/explore | Scrape | None | 24h | 1,000 | 2 | `directories/stoplight.py` |
| 9 | RapidAPI Free Tier | rapidapi.com | Scrape + filter | None | 24h | 5,000 | 2 | `directories/rapidapi_free.py` |
| 10 | openapi.directory (GH) | github.com/APIs-guru | Clone + parse | None | 24h | 3,000 | 1 | `directories/openapi_directory.py` |
| 11 | APImatic | apimatic.io | Scrape public | None | 7d | 500 | 3 | `directories/apimatic.py` |
| 12 | API Tracker | apitracker.io | Scrape | None | 7d | 200 | 3 | `directories/api_tracker.py` |

---

## Tier 2: Package Registries (Massive Scale)

Client libraries in package registries each wrap an API.
The strategy: find the library → extract the API URL from README/code.

| # | Source | Method | Auth | Frequency | Est. Yield | Priority | Module |
|---|---|---|---|---|---|---|---|
| 1 | npm | Daily registry dump + search API | None | 24h | 30,000 | 2 | `registries/npm.py` |
| 2 | PyPI | XML-RPC API + bulk download | None | 24h | 15,000 | 2 | `registries/pypi.py` |
| 3 | RubyGems | REST API + bulk download | None | 24h | 5,000 | 2 | `registries/rubygems.py` |
| 4 | NuGet | OData API | None | 24h | 8,000 | 2 | `registries/nuget.py` |
| 5 | crates.io | REST API + dump | None | 24h | 3,000 | 2 | `registries/crates_io.py` |
| 6 | pub.dev (Dart) | REST API | None | 7d | 2,000 | 3 | `registries/pub_dev.py` |
| 7 | Maven Central | REST search API | None | 7d | 10,000 | 3 | `registries/maven.py` |
| 8 | Packagist (PHP) | REST API | None | 7d | 5,000 | 3 | `registries/packagist.py` |
| 9 | Hex.pm (Elixir) | REST API | None | 7d | 500 | 4 | `registries/hex.py` |
| 10 | Hackage (Haskell) | REST API | None | 7d | 300 | 4 | `registries/hackage.py` |
| 11 | OPAM (OCaml) | GitHub clone | None | 7d | 200 | 4 | `registries/opam.py` |

**Search terms per registry:**
```
*-api, *-sdk, *-client, api-*, sdk-*, *-wrapper, *-connector,
api-client, http-client, rest-client, graphql-client
```

**URL extraction strategy from package README:**
1. Search for `https://` URLs in README matching known API patterns
2. Regex: `https?://(?:api|developer|dev)\.[\w.-]+/`
3. Extract from code: look for `BASE_URL`, `API_ENDPOINT`, `base_url =`
4. Check package description for "API for X" phrasing → search for X's API

---

## Tier 3: GitHub Code Search

Search GitHub for OpenAPI specs and API-related files hosted publicly.

| # | Query | Method | Auth | Frequency | Est. Yield | Module |
|---|---|---|---|---|---|---|
| 1 | `filename:openapi.yaml` | GitHub Search API | Token | 24h | 5,000 | `github/search_openapi.py` |
| 2 | `filename:openapi.json` | GitHub Search API | Token | 24h | 5,000 | `github/search_openapi.py` |
| 3 | `filename:swagger.yaml` | GitHub Search API | Token | 24h | 3,000 | `github/search_openapi.py` |
| 4 | `filename:swagger.json` | GitHub Search API | Token | 24h | 3,000 | `github/search_openapi.py` |
| 5 | `"openapi: 3" in:file` | GitHub Search API | Token | 24h | 8,000 | `github/search_openapi.py` |
| 6 | `"swagger: '2.0'" in:file` | GitHub Search API | Token | 24h | 8,000 | `github/search_openapi.py` |
| 7 | `filename:.well-known/openapi` | GitHub Search API | Token | 7d | 500 | `github/search_openapi.py` |
| 8 | awesome-* lists (all) | Clone repos, parse MDs | None | 7d | 10,000 | `github/awesome_lists.py` |
| 9 | README URL extraction | Search + parse READMEs | Token | 7d | 5,000 | `github/readme_extractor.py` |
| 10 | `.env.example` files | Search for API_URL patterns | Token | 7d | 2,000 | `github/env_extractor.py` |

**GitHub token requirements:**
- Use a personal access token with `public_repo` scope only
- Respect rate limits: 30 requests/minute for search API
- Rotate across multiple tokens if available
- Use `X-RateLimit-Remaining` header to throttle

**Awesome lists to crawl (non-exhaustive):**
```
awesome-api, awesome-public-datasets, awesome-free-tier,
awesome-developer-first, awesome-no-login-required,
awesome-self-hosted, awesome-web-scraping,
awesome-python, awesome-node, awesome-go,
awesome-machine-learning, awesome-nlp, awesome-computer-vision,
awesome-finance, awesome-maps, awesome-geo,
awesome-healthcare, awesome-openstreetmap,
awesome-government-datasets, ...
```
(GitHub search: `awesome-` in repo name, sorted by stars, top 1000)

---

## Tier 4: Certificate Transparency Logs

Every TLS certificate is logged publicly. API subdomains are discoverable.

| # | Source | Method | Auth | Frequency | Est. Yield | Module |
|---|---|---|---|---|---|---|
| 1 | crt.sh | PostgreSQL query | None | 7d | 100,000 candidates | `deep/cert_transparency.py` |
| 2 | censys.io | REST API | Free key | 30d | 50,000 candidates | `deep/censys.py` |

**crt.sh Query:**
```sql
SELECT DISTINCT lower(name_value) as domain
FROM certificate_transparency
WHERE lower(name_value) SIMILAR TO
    '(api|developer|developers|dev-api|api-v[0-9]|rest|graphql)\.%'
    OR lower(name_value) LIKE '%.api.%'
    OR lower(name_value) LIKE '%.api'
ORDER BY domain;
```
Connect to: `crt.sh` PostgreSQL on port 5432 (public, no auth)

**Post-processing cert transparency results:**
1. DNS probe each domain (discard if not resolving)
2. HTTP probe surviving domains (discard if no API response)
3. Check for common API indicators: `Content-Type: application/json`,
   swagger-ui headers, X-RateLimit headers, CORS headers
4. Route survivors through normalizer

---

## Tier 5: Common Crawl

Common Crawl indexes ~3 billion web pages. Query the index to find API documentation pages.

| # | Method | Auth | Frequency | Est. Yield | Module |
|---|---|---|---|---|---|
| 1 | Common Crawl Index API | None | 30d | 50,000 candidates | `deep/common_crawl.py` |

**Strategy:**
```python
# Use the CC Index Server (no download needed)
# Query: https://index.commoncrawl.org/CC-MAIN-YYYY-WW-index?url=*&output=json

search_patterns = [
    "*/swagger-ui/*",
    "*/api-docs/*",
    "*/openapi.json",
    "*/swagger.json",
    "*/developer/*/reference",
    "*/api/reference",
]

# For each pattern, query latest crawl index
# Returns list of URLs → probe each → extract API metadata
```

---

## Tier 6: Government & Institutional Portals

Government open data portals worldwide. Most run CKAN (standard API).

### CKAN Instances (Standard API: `/api/3/action/`)
```
data.gov (US)               data.europa.eu (EU)
data.gov.uk (UK)            data.gov.au (Australia)
open.canada.ca (Canada)     dados.gov.br (Brazil)
data.gouv.fr (France)       govdata.de (Germany)
data.gov.in (India)         data.go.jp (Japan)
data.overheid.nl (NL)       datos.gob.es (Spain)
data.gov.ie (Ireland)       data.gv.at (Austria)
data.gov.be (Belgium)       dati.gov.it (Italy)
opendata.swiss (Switzerland) data.gov.lv (Latvia)
opendata.gov.lv (Latvia)    data.gov.ro (Romania)
... (190+ total)
```

Module: `government/ckan_crawler.py`
Strategy: For each CKAN instance, call `/api/3/action/package_list` then
`/api/3/action/package_show?id=` for each. Extract any API endpoints referenced.

### Specialized Government APIs
| Agency | URL | Module |
|---|---|---|
| NASA | api.nasa.gov | `government/nasa.py` |
| NOAA | api.weather.gov | `government/noaa.py` |
| US Census | api.census.gov | `government/census.py` |
| FDA | api.fda.gov | `government/fda.py` |
| USDA | quickstats.nass.usda.gov/api | `government/usda.py` |
| Federal Reserve (FRED) | fred.stlouisfed.org/docs/api | `government/fred.py` |
| Library of Congress | api.loc.gov | `government/loc.py` |
| SEC EDGAR | efts.sec.gov/LATEST | `government/sec.py` |
| Eurostat | ec.europa.eu/eurostat/api | `government/eurostat.py` |
| ECB | data-api.ecb.europa.eu | `government/ecb.py` |
| World Bank | datahelpdesk.worldbank.org | `government/worldbank.py` |
| UN Data | data.un.org/Host.aspx?Content=API | `government/undata.py` |
| WHO | apps.who.int/gho/data/node.api | `government/who.py` |
| OECD | data.oecd.org | `government/oecd.py` |

---

## Tier 7: Academic & Research

| # | Source | URL | Method | Auth | Frequency | Est. Yield | Module |
|---|---|---|---|---|---|---|---|
| 1 | arXiv | arxiv.org/help/api | REST | None | 7d | 1 | `academic/arxiv.py` |
| 2 | PubMed E-utilities | eutils.ncbi.nlm.nih.gov | REST | None | 7d | 1 | `academic/pubmed.py` |
| 3 | Semantic Scholar | api.semanticscholar.org | REST | None | 7d | 1 | `academic/semantic_scholar.py` |
| 4 | CrossRef | api.crossref.org | REST | None | 7d | 1 | `academic/crossref.py` |
| 5 | OpenAlex | api.openalex.org | REST | None | 7d | 1 | `academic/openalex.py` |
| 6 | ORCID | pub.orcid.org | REST | None | 7d | 1 | `academic/orcid.py` |
| 7 | Unpaywall | api.unpaywall.org | REST | None | 7d | 1 | `academic/unpaywall.py` |
| 8 | CORE | core.ac.uk/api-documentation | REST | Key | 7d | 1 | `academic/core.py` |
| 9 | Zenodo | zenodo.org/api | REST | None | 7d | 1 | `academic/zenodo.py` |
| 10 | OpenCitations | opencitations.net/index/api | REST | None | 7d | 1 | `academic/opencitations.py` |
| 11 | Europe PMC | europepmc.org/RestfulWebService | REST | None | 7d | 1 | `academic/europepmc.py` |

---

## Tier 8: Community Intelligence

Mine developer communities for API mentions and discoveries.

| # | Source | Method | Auth | Frequency | Est. Yield | Module |
|---|---|---|---|---|---|---|
| 1 | Hacker News | Algolia HN Search API | None | 7d | 500 | `community/hackernews.py` |
| 2 | Reddit | Pushshift/Pullpush API | None | 7d | 500 | `community/reddit.py` |
| 3 | dev.to | dev.to REST API (tag:api) | None | 7d | 200 | `community/devto.py` |
| 4 | Product Hunt | GraphQL API (filter: developer-tools) | None | 7d | 100 | `community/producthunt.py` |
| 5 | Stack Overflow dump | Quarterly XML dump (api tag) | None | 30d | 1,000 | `community/stackoverflow.py` |
| 6 | GitHub Discussions | Search API | Token | 7d | 200 | `community/github_discussions.py` |

**HN search queries:**
```
"free api", "public api", "open api", "api i built",
"api for", "no auth", "no api key", "show hn api"
```

**Reddit targets:**
```
r/webdev, r/programming, r/learnprogramming, r/sideprojects,
r/datasets, r/MachineLearning, r/datascience, r/compsci,
r/apis (if exists), r/opensource
```

---

## Tier 9: Deep / Novel Discovery

| # | Source | Method | Auth | Frequency | Est. Yield | Module |
|---|---|---|---|---|---|---|
| 1 | Wayback Machine | CDX API for old API directories | None | 30d | 1,000 | `deep/wayback.py` |
| 2 | DNS zone files | .com/.net zone file (Verisign) | Paid | 30d | 10,000 | `deep/dns_zone.py` |
| 3 | Shodan | Search for swagger-ui | Free key | 30d | 2,000 | `deep/shodan.py` |
| 4 | Wikidata SPARQL | Query for companies → find APIs | None | 30d | 500 | `deep/wikidata.py` |
| 5 | AlternativeTo | Scrape API tools category | None | 30d | 200 | `deep/alternativeto.py` |
| 6 | API evangelist blog | Scrape/RSS | None | 7d | 50 | `deep/api_evangelist.py` |
| 7 | ProgrammableWeb Archive | Wayback Machine mirror | None | 30d | 5,000 | `deep/programmableweb.py` |

---

## Source Statistics Tracking

Each scraper records to `scraper_runs` table. Monitor via:

```sql
SELECT
    scraper_name,
    count(*) as total_runs,
    avg(candidates_found) as avg_yield,
    sum(candidates_new) as total_new_apis,
    max(started_at) as last_run
FROM scraper_runs
WHERE status = 'success'
GROUP BY 1
ORDER BY total_new_apis DESC;
```

---

## Adding a New Source

1. Create module in appropriate `src/scrapers/` subdirectory
2. Implement `async def run(db) -> ScraperResult` interface
3. Add entry to this catalog
4. Add to scheduler in `src/scheduler/jobs.py`
5. Write at least one unit test in `tests/scrapers/`
6. Run once manually, verify candidates appear in `raw_candidates`
