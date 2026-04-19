"""Enrichment service for enhancing API metadata and generating embeddings.

This module implements the full enrichment pipeline:
1. Context assembly (name, description, docs fetching)
2. LLM classification (categories, tags, use cases, summary)
3. Embedding generation (vector for semantic search)
4. Database updates

Supports both local Ollama and remote OpenAI providers.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from src.apivault.config import settings
from src.apivault.enrichment.embedding_client import (
    OllamaEmbeddingClient,
    OpenAIEmbeddingClient,
    get_embedding_client,
)
from src.apivault.enrichment.llm_client import (
    CATEGORY_LIST,
    OllamaLLMClient,
    OpenAILLMClient,
    get_llm_client,
)
from src.apivault.enrichment.models import EnrichmentContext, EnrichmentResult
from src.apivault.models.api import Api

logger = logging.getLogger(__name__)

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
    "music": "Media & Entertainment > Music",
    "movie": "Media & Entertainment > Movies & TV",
    "book": "Media & Entertainment > Books & Literature",
    "game": "Media & Entertainment > Games",
    "sport": "Media & Entertainment > Sports",
    "news": "Media & Entertainment > News",
    "podcast": "Media & Entertainment > Podcasts & Radio",
    "recipe": "Food & Beverage > Recipes",
    "restaurant": "Food & Beverage > Restaurant Finder",
    "nutrition": "Food & Beverage > Nutrition Information",
    "flight": "Travel & Transportation > Flights",
    "hotel": "Travel & Transportation > Hotels & Accommodation",
    "car rental": "Travel & Transportation > Car Rental",
    "transit": "Travel & Transportation > Public Transit",
    "dns": "Infrastructure & Networking > DNS",
    "cdn": "Infrastructure & Networking > CDN",
    "ssl": "Infrastructure & Networking > SSL/TLS",
    "whois": "Infrastructure & Networking > WHOIS",
    "vulnerability": "Security > Vulnerability Scanning",
    "threat": "Security > Threat Intelligence",
    "malware": "Security > Malware Detection",
    "password": "Security > Password & Credential Checking",
    "auth": "Developer Tools > Authentication & Authorization",
    "webhook": "Developer Tools > Webhooks & Events",
    "ci/cd": "Developer Tools > CI/CD",
    "testing": "Developer Tools > Testing",
    "uptime": "Developer Tools > Uptime Monitoring",
    "uuid": "Utilities > UUID Generation",
    "qr": "Utilities > QR Code Generation",
    "barcode": "Utilities > Barcode Generation",
    "random": "Utilities > Random Data Generation",
    "url shorten": "Utilities > URL Shortening",
    "color": "Utilities > Color & Design",
    "convert": "Utilities > Unit Conversion",
}


class EnrichmentService:
    """Main enrichment service that orchestrates the full pipeline."""

    def __init__(
        self,
        llm_client: OllamaLLMClient | OpenAILLMClient | None = None,
        embedding_client: OllamaEmbeddingClient | OpenAIEmbeddingClient | None = None,
    ) -> None:
        self.llm_client = llm_client or get_llm_client()
        self.embedding_client = embedding_client or get_embedding_client()
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        return self._http_client

    async def assemble_context(self, api: Api) -> EnrichmentContext:
        """Assemble enrichment context from multiple sources."""
        context = EnrichmentContext(
            name=api.name,
            description=api.description,
            base_url=api.base_url,
            docs_url=api.docs_url,
            auth_type=api.auth_type,
            existing_categories=api.categories or [],
            existing_tags=api.tags or [],
        )

        if api.docs_url:
            try:
                page_text = await self._fetch_docs_text(api.docs_url)
                context.docs_excerpt = self._extract_description(page_text)[:600]
            except Exception:
                logger.debug("Failed to fetch docs for %s", api.name)

        if api.spec_url:
            try:
                spec_summary = await self._fetch_spec_summary(api.spec_url)
                context.spec_summary = spec_summary
            except Exception:
                logger.debug("Failed to fetch spec for %s", api.name)

        return context

    async def _fetch_docs_text(self, url: str) -> str:
        """Fetch and extract text content from a docs page."""
        client = await self._get_http_client()
        response = await client.get(url)
        response.raise_for_status()
        return response.text

    def _extract_description(self, html: str) -> str:
        """Extract meaningful description from HTML content."""
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["nav", "footer", "script", "style", "header"]):
            tag.decompose()

        meta = soup.find("meta", {"name": "description"})
        if meta and meta.get("content"):
            return meta["content"]

        main = soup.find("main") or soup.find("article") or soup.body
        if main:
            first_p = main.find("p")
            if first_p:
                return first_p.get_text(strip=True)

        return soup.get_text(separator=" ", strip=True)[:600]

    async def _fetch_spec_summary(self, url: str) -> str:
        """Fetch and summarize an OpenAPI spec."""
        client = await self._get_http_client()
        response = await client.get(url)
        response.raise_for_status()
        spec = response.json()

        info = spec.get("info", {})
        title = info.get("title", "")
        description = info.get("description", "")

        endpoints = []
        for _path, methods in spec.get("paths", {}).items():
            for method, details in methods.items():
                if method in ("get", "post", "put", "delete", "patch"):
                    summary = details.get("summary", "")
                    if summary:
                        endpoints.append(summary)

        parts = [title, description]
        if endpoints:
            parts.append("Endpoints: " + ", ".join(endpoints[:10]))

        return " ".join(filter(None, parts))[:1000]

    def validate_enrichment(self, result: dict[str, Any]) -> EnrichmentResult:
        """Validate and clean LLM enrichment output."""
        categories = result.get("categories", [])
        valid_cats = [c for c in categories if self._is_valid_category(c)]
        if not valid_cats:
            valid_cats = ["Utilities"]

        tags = result.get("tags", [])[:20]

        use_cases = [u for u in result.get("use_cases", []) if u.lower().startswith("use to")]

        desc = result.get("description_llm", "")
        if len(desc) < 20:
            desc = None

        return EnrichmentResult(
            categories=valid_cats,
            tags=tags,
            use_cases=use_cases,
            description_llm=desc,
            company=result.get("company"),
        )

    def _is_valid_category(self, category: str) -> bool:
        """Check if a category string matches the taxonomy."""
        if ">" not in category:
            return category in CATEGORY_LIST

        top_level = category.split(">")[0].strip()
        return top_level in CATEGORY_LIST

    def rule_based_categorize(self, name: str, description: str | None) -> list[str]:
        """Fallback categorization using keyword matching."""
        text = f"{name} {description or ''}".lower()
        matches = []
        for keyword, category in KEYWORD_CATEGORY_MAP.items():
            if keyword in text:
                matches.append(category)
        return matches[:3] or ["Utilities"]

    def build_embedding_text(self, api: Api, enrichment: EnrichmentResult) -> str:
        """Build the text representation for embedding generation."""
        parts = [
            api.name,
            enrichment.description_llm or api.description or "",
            " ".join(enrichment.tags),
            " ".join(enrichment.use_cases),
            " ".join(enrichment.categories),
        ]
        return " ".join(filter(None, parts))[:2000]

    async def enrich_api(self, api: Api) -> EnrichmentResult | None:
        """Enrich a single API record with LLM classification and embedding."""
        logger.info("Enriching API: %s", api.name)

        context = await self.assemble_context(api)

        if self.llm_client:
            llm_result = await self.llm_client.classify(context)
            if llm_result:
                enrichment = self.validate_enrichment(llm_result)
            else:
                enrichment = self._rule_based_enrichment(api)
        else:
            enrichment = self._rule_based_enrichment(api)

        if self.embedding_client:
            embedding_text = self.build_embedding_text(api, enrichment)
            embedding = await self.embedding_client.embed(embedding_text)
            if embedding:
                from src.apivault.database import async_session_factory
                from src.apivault.enrichment.repository import EnrichmentRepository

                async with async_session_factory() as session:
                    repo = EnrichmentRepository(session)
                    await repo.update_enrichment(
                        api.id,
                        {
                            "categories": enrichment.categories,
                            "tags": enrichment.tags,
                            "use_cases": enrichment.use_cases,
                            "description_llm": enrichment.description_llm,
                            "company": enrichment.company,
                        },
                        embedding=embedding,
                        embedding_model=self._get_embedding_model_name(),
                    )
                    await session.commit()

        return enrichment

    def _rule_based_enrichment(self, api: Api) -> EnrichmentResult:
        """Generate enrichment using rule-based fallback."""
        categories = self.rule_based_categorize(api.name, api.description)
        tags = self._generate_rule_based_tags(api)
        use_cases = self._generate_rule_based_use_cases(api)

        return EnrichmentResult(
            categories=categories,
            tags=tags,
            use_cases=use_cases,
            description_llm=self._generate_rule_based_description(api),
            company=self._extract_company_from_url(api.base_url),
        )

    def _generate_rule_based_tags(self, api: Api) -> list[str]:
        """Generate tags based on available API metadata."""
        tags = []
        text = f"{api.name} {api.description or ''}".lower()

        if api.auth_type == "none":
            tags.append("no-auth")
        elif api.auth_type == "apikey":
            tags.append("api-key")

        if api.free_tier:
            tags.append("free-tier")

        for keyword in ("rest", "graphql", "grpc", "websocket"):
            if keyword in text:
                tags.append(keyword)

        for keyword in ("json", "xml", "csv"):
            if keyword in text:
                tags.append(keyword)

        if not tags:
            tags = ["api"]

        return tags[:15]

    def _generate_rule_based_use_cases(self, api: Api) -> list[str]:
        """Generate generic use cases when LLM is unavailable."""
        name = api.name
        return [
            f"Use to access {name} functionality in your applications",
            f"Use to integrate {name} data into your workflows",
            f"Use to build applications that leverage {name} services",
        ]

    def _generate_rule_based_description(self, api: Api) -> str | None:
        """Generate a basic description when LLM is unavailable."""
        if api.description:
            return api.description[:300]
        return f"API service available at {api.base_url}" if api.base_url else None

    def _extract_company_from_url(self, url: str | None) -> str | None:
        """Extract company/organization name from a URL."""
        if not url:
            return None
        match = re.search(r"https?://(?:www\.)?([^/]+)", url)
        if match:
            domain = match.group(1)
            parts = domain.split(".")
            if len(parts) >= 2:
                return parts[-2].title()
        return None

    def _get_embedding_model_name(self) -> str:
        """Get the name of the current embedding model."""
        if isinstance(self.embedding_client, OllamaEmbeddingClient):
            return settings.ollama_embedding_model
        elif isinstance(self.embedding_client, OpenAIEmbeddingClient):
            return settings.openai_embedding_model
        return "unknown"

    async def enrich_batch(
        self,
        apis: list[Api],
        batch_size: int | None = None,
    ) -> list[tuple[Api, EnrichmentResult | None]]:
        """Enrich multiple APIs in batches for efficiency."""
        if batch_size is None:
            batch_size = settings.enrichment_batch_size

        results: list[tuple[Api, EnrichmentResult | None]] = []

        for i in range(0, len(apis), batch_size):
            batch = apis[i : i + batch_size]
            logger.info("Processing enrichment batch %d-%d", i, i + len(batch))

            contexts = await self._assemble_contexts_batch(batch)

            if self.llm_client:
                llm_results = await self.llm_client.classify_batch(contexts)
                enrichments = [
                    self.validate_enrichment(r) if r else self._rule_based_enrichment(api)
                    for api, r in zip(batch, llm_results, strict=False)
                ]
            else:
                enrichments = [self._rule_based_enrichment(api) for api in batch]

            if self.embedding_client:
                embedding_texts = [
                    self.build_embedding_text(api, enrichment)
                    for api, enrichment in zip(batch, enrichments, strict=False)
                ]
                embeddings = await self.embedding_client.embed_batch(embedding_texts)
            else:
                embeddings = [None] * len(batch)

            for api, enrichment, embedding in zip(batch, enrichments, embeddings, strict=False):
                results.append((api, enrichment))

                if embedding:
                    from src.apivault.database import async_session_factory
                    from src.apivault.enrichment.repository import EnrichmentRepository

                    async with async_session_factory() as session:
                        repo = EnrichmentRepository(session)
                        await repo.update_enrichment(
                            api.id,
                            {
                                "categories": enrichment.categories,
                                "tags": enrichment.tags,
                                "use_cases": enrichment.use_cases,
                                "description_llm": enrichment.description_llm,
                                "company": enrichment.company,
                            },
                            embedding=embedding,
                            embedding_model=self._get_embedding_model_name(),
                        )
                        await session.commit()

        return results

    async def _assemble_contexts_batch(
        self,
        apis: list[Api],
    ) -> list[EnrichmentContext]:
        """Assemble contexts for multiple APIs in parallel."""
        import asyncio

        return await asyncio.gather(*[self.assemble_context(api) for api in apis])

    async def close(self) -> None:
        """Clean up resources."""
        if self.llm_client:
            await self.llm_client.close()
        if self.embedding_client:
            await self.embedding_client.close()
        if self._http_client:
            await self._http_client.aclose()


async def enrich_api(api: Api) -> dict[str, Any]:
    """Convenience function for single API enrichment (backwards compatible)."""
    service = EnrichmentService()
    try:
        result = await service.enrich_api(api)
        if result:
            return {
                "categories": result.categories,
                "tags": result.tags,
                "use_cases": result.use_cases,
                "description_llm": result.description_llm,
                "company": result.company,
            }
        return {}
    finally:
        await service.close()


async def enrich_batch(apis: list[Api], batch_size: int = 20) -> list[dict[str, Any]]:
    """Convenience function for batch enrichment (backwards compatible)."""
    service = EnrichmentService()
    try:
        results = await service.enrich_batch(apis, batch_size)
        return [
            {
                "categories": r.categories if r else [],
                "tags": r.tags if r else [],
                "use_cases": r.use_cases if r else [],
                "description_llm": r.description_llm if r else None,
                "company": r.company if r else None,
            }
            for _, r in results
        ]
    finally:
        await service.close()


async def get_embedding(text: str) -> list[float] | None:
    """Generate embedding for arbitrary text (used by semantic search endpoint)."""
    client = get_embedding_client()
    if not client:
        return None
    try:
        return await client.embed(text)
    finally:
        await client.close()
