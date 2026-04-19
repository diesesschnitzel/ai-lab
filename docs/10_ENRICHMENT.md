# Enrichment Pipeline
# APIVault

**Version:** 1.0
**Last Updated:** 2026-04-15

---

## 1. Purpose

Raw API records often have only: a name, a URL, maybe a one-line description,
and an auth type. That's not enough for useful search.

Enrichment adds:
- **Categories** — where in the taxonomy this API lives
- **Tags** — searchable labels
- **Use cases** — plain-language descriptions of what you'd use it for
- **Summary** — a better description than whatever the source provided
- **Embedding** — a vector representation enabling semantic search

---

## 2. Enrichment Queue

APIs enter the enrichment queue when:
1. Newly inserted (enriched_at IS NULL)
2. Major fields changed (name or description updated)
3. Manually triggered via admin endpoint

Priority order:
1. APIs with `status=active` and `description IS NOT NULL` (best chance of good enrichment)
2. APIs with `status=active` and no description (try with URL + name only)
3. APIs with `status=unknown` (not yet validated)

---

## 3. Context Assembly

Before calling the LLM, assemble context from multiple sources:

```python
async def assemble_context(self, api: API) -> EnrichmentContext:
    context = EnrichmentContext(
        name=api.name,
        description=api.description,
        base_url=api.base_url,
        docs_url=api.docs_url,
        auth_type=api.auth_type,
        existing_categories=api.categories,
        existing_tags=api.tags,
    )
    
    # Attempt to fetch docs page for additional context
    if api.docs_url:
        try:
            page_text = await self.fetch_docs_text(api.docs_url)
            context.docs_excerpt = self.extract_description(page_text)[:600]
        except Exception:
            pass  # Docs fetch is best-effort
    
    # If OpenAPI spec is available, extract summary from it
    if api.spec_url:
        try:
            spec = await self.fetch_spec(api.spec_url)
            context.spec_summary = self.summarize_spec(spec)
        except Exception:
            pass
    
    return context
```

### Docs Page Text Extraction

```python
def extract_description(self, html: str) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    
    # Remove nav, footer, scripts
    for tag in soup(["nav", "footer", "script", "style", "header"]):
        tag.decompose()
    
    # Prefer: meta description, first <p> in main, first <h1>/<h2>
    meta = soup.find("meta", {"name": "description"})
    if meta and meta.get("content"):
        return meta["content"]
    
    main = soup.find("main") or soup.find("article") or soup.body
    if main:
        first_p = main.find("p")
        if first_p:
            return first_p.get_text(strip=True)
    
    return soup.get_text(separator=" ", strip=True)[:600]
```

---

## 4. LLM Classification Prompt

```python
CLASSIFICATION_PROMPT = """
You are building a developer API reference database. Your task is to classify
and describe a single API based on the information provided.

---
API Name: {name}
Base URL: {base_url}
Auth Type: {auth_type}
Source Description: {description}
Docs Excerpt: {docs_excerpt}
---

Available top-level categories (choose from these only):
{category_list}

Instructions:
1. categories: Pick 1-5 categories. Format: "TopLevel > SubCategory".
   Put the most specific/primary category first.

2. tags: Pick 5-15 tags. Use the preferred vocabulary where possible.
   Preferred vocabulary: {tag_vocabulary}
   You may add domain-specific tags not in the vocabulary.

3. use_cases: Write 3-6 use cases. Each must start with "Use to".
   Be specific and practical. Examples:
   - "Use to extract text from PDF documents without server-side processing"
   - "Use to convert any currency to another using live exchange rates"
   - "Use to get real-time weather for any city worldwide, no auth required"

4. description_llm: Write a 2-3 sentence plain-language summary.
   First sentence: what it does. Second: who uses it or key differentiator.
   Third (optional): notable limits or free tier detail.
   Do NOT just repeat the source description. Improve it.

5. company: The company or organization that provides this API (if known).

Respond ONLY with valid JSON, no markdown:
{
  "categories": ["TopLevel > Sub", ...],
  "tags": ["tag1", "tag2", ...],
  "use_cases": ["Use to...", ...],
  "description_llm": "...",
  "company": "..." or null
}
"""
```

---

## 5. Batch Processing

To minimize LLM costs and latency, APIs are classified in batches:

```python
async def enrich_batch(self, apis: list[API]) -> list[EnrichmentResult]:
    # Assemble contexts in parallel
    contexts = await asyncio.gather(
        *[self.assemble_context(api) for api in apis]
    )
    
    # Single LLM call with all contexts
    # (Claude API supports long contexts efficiently)
    results = await self.llm_client.classify_batch(contexts)
    
    # Generate embeddings in parallel
    embeddings = await self.embedding_client.embed_batch([
        f"{api.name} {result.description_llm} {' '.join(result.tags)}"
        for api, result in zip(apis, results)
    ])
    
    # Write all results
    for api, result, embedding in zip(apis, results, embeddings):
        await self.db.update_enrichment(api.id, result, embedding)
    
    return results
```

**Batch size:** 20 APIs per LLM call (balances context length vs. API cost)

---

## 6. Embedding Generation

Embeddings enable semantic search: "find APIs that do X" without exact keyword match.

### Embedding Input Text

```python
def build_embedding_text(self, api: API, enrichment: EnrichmentResult) -> str:
    parts = [
        api.name,
        enrichment.description_llm or api.description or "",
        " ".join(enrichment.tags),
        " ".join(enrichment.use_cases),
        " ".join(enrichment.categories),
    ]
    return " ".join(filter(None, parts))[:2000]
```

### Local Embeddings (Ollama)

```python
class OllamaEmbeddingClient:
    BASE_URL = "http://localhost:11434"
    MODEL = "nomic-embed-text"  # 768 dimensions, fast, good quality
    
    async def embed(self, text: str) -> list[float]:
        response = await self.client.post(
            f"{self.BASE_URL}/api/embeddings",
            json={"model": self.MODEL, "prompt": text}
        )
        return response.json()["embedding"]
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.gather(*[self.embed(t) for t in texts])
```

Note: nomic-embed-text produces 768-dimension vectors. The schema uses 1536
to be compatible with OpenAI/Claude embeddings. When using Ollama, pad to 1536
or adjust the pgvector column dimension in your deployment.

### Remote Embeddings (Claude / OpenAI)

```python
class ClaudeEmbeddingClient:
    # Uses Anthropic's embedding endpoint when available
    # Fallback: openai text-embedding-3-small (1536 dims, cheap)
    pass
```

---

## 7. Enrichment Quality Control

### Validation of LLM Output

```python
def validate_enrichment(self, result: dict) -> EnrichmentResult:
    # Ensure categories are from valid taxonomy
    valid_cats = [c for c in result.get("categories", [])
                  if self.is_valid_category(c)]
    if not valid_cats:
        valid_cats = ["Utilities"]  # Fallback
    
    # Limit tags to 20
    tags = result.get("tags", [])[:20]
    
    # Ensure use_cases start with "Use to"
    use_cases = [u for u in result.get("use_cases", [])
                 if u.lower().startswith("use to")]
    
    # Validate description length
    desc = result.get("description_llm", "")
    if len(desc) < 20:
        desc = None  # Too short to be useful; keep original
    
    return EnrichmentResult(
        categories=valid_cats,
        tags=tags,
        use_cases=use_cases,
        description_llm=desc,
        company=result.get("company"),
    )
```

### Re-enrichment Triggers

An API is re-enriched when:
- Base description changes significantly (>30% different)
- Admin manually triggers it
- Category taxonomy changes and a migration job runs

---

## 8. Enrichment Without LLM

For systems running without any LLM:

**Rule-based fallback categorization:**
```python
KEYWORD_CATEGORY_MAP = {
    "weather": "Weather & Environment > Current Weather",
    "forecast": "Weather & Environment > Forecasting",
    "geocod": "Geographic & Location > Geocoding & Reverse Geocoding",
    "map": "Geographic & Location > Mapping",
    "payment": "Finance & Payments > Payment Processing",
    "currency": "Finance & Payments > Currency & Exchange Rates",
    "translate": "AI & Machine Learning > Translation & Language Detection",
    "ocr": "AI & Machine Learning > Text Extraction & OCR",
    "sms": "Communication > SMS & Messaging",
    "email": "Communication > Email",
    "pdf": "Document & File Processing > PDF Processing",
    "stock": "Finance & Payments > Stock Market & Trading",
    # ... 200+ more mappings
}

def rule_based_categorize(name: str, description: str) -> list[str]:
    text = f"{name} {description}".lower()
    matches = [cat for kw, cat in KEYWORD_CATEGORY_MAP.items() if kw in text]
    return matches[:3] or ["Utilities"]
```

This provides basic categorization with zero external dependencies.

---

## 9. Metrics

```
apivault_enrichment_queue_size
apivault_enrichment_processed_total{model="ollama|claude|openai"}
apivault_enrichment_failed_total{reason="llm_error|parse_error|timeout"}
apivault_enrichment_duration_seconds
apivault_embedding_generated_total
apivault_enrichment_cost_usd_total  (for paid models)
```
