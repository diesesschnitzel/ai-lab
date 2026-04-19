"""Pydantic models for the API discovery pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ApiFormat(str, Enum):
    """Detected API format types."""

    REST = "rest"
    GRAPHQL = "graphql"
    GRPC = "grpc"
    OPENAPI = "openapi"
    SOAP = "soap"
    WEBSOCKET = "websocket"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    """Confidence level for data sources."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DataSource(BaseModel):
    """Represents where an API candidate was discovered."""

    source: str
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    raw_data: dict[str, Any] = Field(default_factory=dict)


class RawCandidate(BaseModel):
    """Raw API candidate from a scraper/source before normalization."""

    name: str | None = None
    url: str | None = None
    description: str | None = None
    source: str = "unknown"
    raw_data: dict[str, Any] = Field(default_factory=dict)


class NormalizedApi(BaseModel):
    """Normalized API record ready for deduplication."""

    id: str | None = None
    name: str
    base_url: str
    docs_url: str | None = None
    canonical_domain: str
    api_format: ApiFormat = ApiFormat.UNKNOWN
    description: str | None = None
    sources: list[DataSource] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    url_fingerprint: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def merge_with(self, other: NormalizedApi) -> NormalizedApi:
        """Merge another normalized API into this one, keeping higher-confidence data."""
        merged_sources = list(self.sources)
        for src in other.sources:
            if src.source not in {s.source for s in merged_sources}:
                merged_sources.append(src)

        other_confidence_order = [ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH]
        self_confidence_idx = other_confidence_order.index(self.confidence)
        other_confidence_idx = other_confidence_order.index(other.confidence)

        if other_confidence_idx > self_confidence_idx:
            new_confidence = other.confidence
        else:
            new_confidence = self.confidence

        return NormalizedApi(
            id=self.id,
            name=self.name if self.name else other.name,
            base_url=self.base_url if self.base_url else other.base_url,
            docs_url=self.docs_url or other.docs_url,
            canonical_domain=self.canonical_domain,
            api_format=self.api_format if self.api_format != ApiFormat.UNKNOWN else other.api_format,
            description=self.description or other.description,
            sources=merged_sources,
            confidence=new_confidence,
            url_fingerprint=self.url_fingerprint,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
            metadata={**self.metadata, **other.metadata},
        )


class DedupMatch(BaseModel):
    """Result of a deduplication match."""

    existing: NormalizedApi
    candidate: NormalizedApi
    match_type: str  # "exact_url", "domain_prefix", "name_similarity"
    confidence: float  # 0.0 to 1.0


class PipelineResult(BaseModel):
    """Result of running the full pipeline."""

    normalized: list[NormalizedApi] = Field(default_factory=list)
    deduplicated: list[NormalizedApi] = Field(default_factory=list)
    new_records: list[NormalizedApi] = Field(default_factory=list)
    merged_records: list[NormalizedApi] = Field(default_factory=list)
    duplicates_found: int = 0
    errors: list[str] = Field(default_factory=list)
