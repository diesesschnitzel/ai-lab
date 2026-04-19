"""LLM clients for API classification and enrichment."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from src.apivault.config import settings
from src.apivault.enrichment.models import EnrichmentContext

logger = logging.getLogger(__name__)

CATEGORY_LIST = [
    "AI & Machine Learning",
    "Data & Analytics",
    "Document & File Processing",
    "Communication",
    "Finance & Payments",
    "Geographic & Location",
    "Weather & Environment",
    "Government & Public Data",
    "Science & Research",
    "Health & Medical",
    "E-commerce & Retail",
    "Travel & Transportation",
    "Food & Beverage",
    "Media & Entertainment",
    "Social & Identity",
    "Developer Tools",
    "Security",
    "Search",
    "Utilities",
    "Infrastructure & Networking",
    "Industrial & IoT",
    "Agriculture & Food Supply",
    "Education",
]

TAG_VOCABULARY = [
    "no-auth",
    "apikey-free",
    "oauth-required",
    "instant-signup",
    "no-signup",
    "rate-limited",
    "unlimited",
    "free-tier",
    "rest",
    "graphql",
    "soap",
    "grpc",
    "websocket",
    "sse",
    "json",
    "xml",
    "csv",
    "binary",
    "protobuf",
    "jsonld",
    "openapi",
    "swagger",
    "postman",
    "real-time",
    "historical",
    "batch",
    "streaming",
    "static",
    "geospatial",
    "time-series",
    "text",
    "image",
    "audio",
    "video",
    "structured",
    "unstructured",
    "multilingual",
    "official",
    "community",
    "government",
    "academic",
    "enterprise",
    "well-documented",
    "minimal-docs",
    "stable",
    "beta",
    "deprecated",
    "high-availability",
    "sla-guaranteed",
    "llm",
    "nlp",
    "ocr",
    "computer-vision",
    "speech-to-text",
    "text-to-speech",
    "sentiment",
    "translation",
    "summarization",
    "embeddings",
    "pdf",
    "word",
    "excel",
    "markdown",
    "html",
    "latex",
    "payment",
    "cryptocurrency",
    "stocks",
    "forex",
    "banking",
    "weather",
    "satellite",
    "radar",
    "forecast",
    "climate",
]

CLASSIFICATION_PROMPT = """\
You are building a developer API reference database.
Your task is to classify and describe a single API based on the information provided.

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
   Be specific and practical.
4. description_llm: Write a 2-3 sentence plain-language summary.
   First sentence: what it does.
   Second: who uses it or key differentiator.
   Third (optional): notable limits or free tier detail.
   Do NOT just repeat the source description. Improve it.
5. company: The company or organization that provides this API (if known).

Respond ONLY with valid JSON, no markdown:
{{
  "categories": ["TopLevel > Sub", ...],
  "tags": ["tag1", "tag2", ...],
  "use_cases": ["Use to...", ...],
  "description_llm": "...",
  "company": "..." or null
}}"""


def build_classification_prompt(context: EnrichmentContext) -> str:
    """Build the LLM classification prompt for a single API."""
    return CLASSIFICATION_PROMPT.format(
        name=context.name,
        base_url=context.base_url or "N/A",
        auth_type=context.auth_type,
        description=context.description or "No description available",
        docs_excerpt=context.docs_excerpt or "No docs excerpt available",
        category_list="\n".join(f"- {cat}" for cat in CATEGORY_LIST),
        tag_vocabulary=", ".join(TAG_VOCABULARY),
    )


def parse_llm_response(response_text: str) -> dict[str, Any] | None:
    """Parse LLM JSON response, handling common formatting issues."""
    text = response_text.strip()

    # Strip markdown code blocks if present
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # Find JSON object in text
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None

    json_str = text[start : end + 1]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


class OllamaLLMClient:
    """LLM client using local Ollama instance."""

    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_llm_model
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    async def classify(self, context: EnrichmentContext) -> dict[str, Any] | None:
        """Classify a single API using Ollama."""
        prompt = build_classification_prompt(context)
        client = await self._get_client()

        try:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 1024,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            return parse_llm_response(data.get("response", ""))
        except Exception:
            logger.exception("Ollama classification failed for %s", context.name)
            return None

    async def classify_batch(
        self,
        contexts: list[EnrichmentContext],
    ) -> list[dict[str, Any] | None]:
        """Classify multiple APIs sequentially (Ollama works best one at a time)."""
        results = []
        for context in contexts:
            result = await self.classify(context)
            results.append(result)
        return results

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()


class OpenAILLMClient:
    """LLM client using OpenAI API."""

    def __init__(self) -> None:
        self.api_key = settings.openai_api_key
        self.model = settings.openai_llm_model
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=120.0,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def classify(self, context: EnrichmentContext) -> dict[str, Any] | None:
        """Classify a single API using OpenAI."""
        prompt = build_classification_prompt(context)
        client = await self._get_client()

        try:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an API classification assistant. Respond only with valid JSON.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1024,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return parse_llm_response(content)
        except Exception:
            logger.exception("OpenAI classification failed for %s", context.name)
            return None

    async def classify_batch(
        self,
        contexts: list[EnrichmentContext],
    ) -> list[dict[str, Any] | None]:
        """Classify multiple APIs in parallel using OpenAI."""
        import asyncio

        return await asyncio.gather(*[self.classify(ctx) for ctx in contexts])

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()


def get_llm_client() -> OllamaLLMClient | OpenAILLMClient | None:
    """Get the appropriate LLM client based on configuration."""
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            logger.warning("OpenAI provider selected but no API key configured")
            return None
        return OpenAILLMClient()
    elif settings.llm_provider == "ollama":
        return OllamaLLMClient()
    else:
        return None
