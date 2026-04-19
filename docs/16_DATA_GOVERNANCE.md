# Data Governance
# APIVault — Legal, Attribution & Ethics

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## 1. What We Collect

APIVault collects:
- **API metadata**: Name, base URL, documentation URL, description, auth type
- **Health data**: HTTP response codes, DNS resolution results, SSL validity
- **Classification**: LLM-generated tags, categories, use cases

We do NOT collect:
- API keys or credentials
- User data from external APIs
- Content returned by external APIs (only metadata about them)
- Personally identifiable information of any kind

---

## 2. Sources and Terms of Service

### Public Information

All data collected by APIVault is:
1. **Publicly available** — discoverable by any internet user without authentication
2. **Factual metadata** — not creative content subject to copyright
3. **Minimal** — we record pointers (URLs, names) not content

API names, URLs, and descriptions are factual information that is not generally
copyrightable, analogous to a business listing or a library catalog entry.

### GitHub Data

We query GitHub's API under its terms of service. Specifically:
- We use only the public search API
- We access only public repositories
- We do not clone or cache full repository contents
- We extract only metadata (API spec URLs, base URLs, names)
- We respect GitHub's rate limits

GitHub's ToS permits programmatic access to public data via their API.

### Package Registries

npm, PyPI, RubyGems, NuGet, crates.io, and similar registries:
- All publish bulk data download options specifically for this type of use
- npm's CouchDB replication is explicitly intended for mirrors and tools
- PyPI's XMLRPC and JSON APIs are documented for programmatic use
- Package metadata (name, description, homepage URL) is factual and minimal

### Public API Directories

Sites like public-apis GitHub, apis.guru, apilist.fun:
- These are published with the explicit intent of being used and referenced
- We credit sources in our `source_names` field
- We link back to original source URLs

### Government Data

Government open data portals operate under open data licenses:
- US Government data: Public domain (17 U.S.C. § 105)
- EU data: CC BY 4.0 or similar open licenses
- Most national portals: explicitly open data licenses

### Certificate Transparency Logs

CT logs are operated under RFC 6962 and are specifically designed as public
infrastructure. Querying them is explicitly permitted and encouraged for
security research and tooling.

### Web Scraping

For sites where we scrape HTML rather than use an API:
- We respect `robots.txt` in all cases
- We do not scrape behind login walls
- We cache results to minimize server load
- We identify ourselves in User-Agent
- We limit request rate to 1/second per domain

---

## 3. Attribution

APIVault maintains full source provenance for every API record:
- `source_names` — all scrapers that contributed data for this API
- `source_urls` — the original URLs where information was found
- `docs_url` — direct link to the original API documentation

Users of the APIVault query API should:
- Link back to the original API's documentation (`docs_url`)
- Not republish APIVault's database wholesale without attribution

---

## 4. Data Accuracy Disclaimer

APIVault makes no guarantees about the accuracy or completeness of indexed data:
- API descriptions may be outdated
- Auth requirements may have changed since last validation
- Rate limits may differ from what is recorded
- Some APIs may have been discontinued

The `last_checked` timestamp and `health_score` indicate data freshness.
Users should always verify information against the official API documentation.

---

## 5. Robots.txt Policy

APIVault respects `robots.txt` on all scraped domains. This is non-negotiable:
- Scrapers check robots.txt before any URL fetch
- Disallowed paths are never fetched, even if they would contain valuable data
- Robots.txt is cached and re-checked periodically (not just once)
- If a domain explicitly disallows our user-agent, we stop scraping it entirely

To request removal from APIVault: add to robots.txt:
```
User-agent: APIVault
Disallow: /
```

Or contact us via the GitHub repository.

---

## 6. GDPR / Privacy

APIVault does not collect or process personal data:
- We do not track users of the APIVault query API
- No user accounts, sessions, or cookies
- IP addresses are used only for rate limiting (not logged to disk)
- No analytics or tracking scripts

The system is designed to be GDPR-compliant by default.

---

## 7. Removal Requests

If you are an API provider and want your API removed from APIVault:

1. Open an issue at the GitHub repository
2. Include the API name and base URL
3. We will remove the record within 48 hours

Alternatively, block our user-agent in your robots.txt and the record will
be marked dead on next validation.

---

## 8. Data Retention

| Data | Retention |
|---|---|
| Active API records | Indefinitely (updated continuously) |
| Dead API records | 2 years after last confirmation of death |
| Health log entries | 90 days |
| Raw candidates | 30 days |
| Scraper run logs | 90 days |

Dead APIs are retained because:
- They may return (maintenance, domain changes)
- Historical reference value
- Merge target if rediscovered under different URL

---

## 9. License

The APIVault **software** (code, configuration, documentation) is licensed
under the MIT License.

The **data** in the APIVault database (API metadata) is published under
Creative Commons CC0 1.0 Universal (public domain dedication).

This means: use the data for any purpose, no attribution required, though
appreciated.

---

## 10. Responsible Use

APIVault is intended for legitimate developer use:
- Finding APIs for software development
- Research into the API ecosystem
- Building developer tools

Prohibited uses:
- Scraping contact information for spam
- Building competitive intelligence products
- Any automated mass-exploitation of indexed APIs
- Circumventing rate limits of external APIs

If you discover APIVault is being used to harm API providers, report it
via the GitHub repository.
