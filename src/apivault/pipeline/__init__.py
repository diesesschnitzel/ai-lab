"""API discovery pipeline: normalization and deduplication.

Pipeline flow: raw_candidates → normalize → dedup → validate → enrich
"""

from .deduplicator import deduplicate, find_match
from .fingerprint import (
    canonicalize_domain,
    extract_base_url,
    fingerprint_url,
    normalize_url,
)
from .models import (
    ApiFormat,
    ConfidenceLevel,
    DataSource,
    DedupMatch,
    NormalizedApi,
    PipelineResult,
    RawCandidate,
)
from .normalizer import normalize_candidate, normalize_candidates
from .orchestrator import PipelineOrchestrator

__all__ = [
    "ApiFormat",
    "ConfidenceLevel",
    "DataSource",
    "DedupMatch",
    "NormalizedApi",
    "PipelineResult",
    "RawCandidate",
    "PipelineOrchestrator",
    "normalize_candidate",
    "normalize_candidates",
    "deduplicate",
    "find_match",
    "canonicalize_domain",
    "extract_base_url",
    "fingerprint_url",
    "normalize_url",
]
