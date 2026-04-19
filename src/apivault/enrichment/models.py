"""Pydantic models for the enrichment pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EnrichmentContext:
    """Context assembled for enriching a single API."""

    name: str
    description: str | None = None
    base_url: str | None = None
    docs_url: str | None = None
    auth_type: str = "unknown"
    existing_categories: list[str] = field(default_factory=list)
    existing_tags: list[str] = field(default_factory=list)
    docs_excerpt: str | None = None
    spec_summary: str | None = None


@dataclass
class EnrichmentResult:
    """Result of LLM enrichment for a single API."""

    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    use_cases: list[str] = field(default_factory=list)
    description_llm: str | None = None
    company: str | None = None
