"""Deduplicator: identifies and merges duplicate API candidates.

Matching strategies (in priority order):
1. Exact URL fingerprint match
2. Domain + path prefix match
3. Name similarity match

On match: merge source references, update with higher-confidence data.
On no match: mark as new record for insertion.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from .fingerprint import get_domain_path_prefix
from .models import NormalizedApi

# Minimum similarity threshold for name matching
NAME_SIMILARITY_THRESHOLD = 0.75

# Common words to ignore in name comparison
COMMON_API_WORDS = frozenset(
    {
        "api",
        "the",
        "free",
        "public",
        "open",
        "cloud",
        "web",
        "service",
        "platform",
        "lab",
        "labs",
        "io",
    }
)


def compute_name_similarity(name_a: str, name_b: str) -> float:
    """Compute similarity between two API names.

    Uses a combination of:
    - Normalized string comparison (lowercase, stripped)
    - Token-based comparison (ignoring common words)
    - Sequence matching for partial matches
    """
    if not name_a or not name_b:
        return 0.0

    norm_a = name_a.lower().strip()
    norm_b = name_b.lower().strip()
    if norm_a == norm_b:
        return 1.0

    tokens_a = set(_tokenize_name(norm_a)) - COMMON_API_WORDS
    tokens_b = set(_tokenize_name(norm_b)) - COMMON_API_WORDS

    if tokens_a and tokens_b:
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        jaccard = len(intersection) / len(union) if union else 0.0
    else:
        jaccard = 0.0

    seq_ratio = SequenceMatcher(None, norm_a, norm_b).ratio()
    contains_ratio = 1.0 if (norm_a in norm_b or norm_b in norm_a) else 0.0

    if not tokens_a or not tokens_b:
        return seq_ratio * 0.5

    return max(
        jaccard * 0.4 + seq_ratio * 0.4 + contains_ratio * 0.2,
        seq_ratio,
    )


def _tokenize_name(name: str) -> list[str]:
    """Split a name into tokens for comparison."""
    # Split on spaces, hyphens, underscores, and camelCase boundaries
    tokens = re.split(r"[\s\-_]+", name)
    result = []
    for token in tokens:
        # Split camelCase
        sub_tokens = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)", token)
        for t in sub_tokens:
            lower = t.lower()
            # Skip pure numeric tokens (version numbers, etc.)
            if lower and not lower.isdigit():
                result.append(lower)
    return result


def match_exact_url(
    candidate: NormalizedApi,
    existing: list[NormalizedApi],
) -> NormalizedApi | None:
    """Find an exact URL fingerprint match."""
    if not candidate.url_fingerprint:
        return None

    for record in existing:
        if record.url_fingerprint == candidate.url_fingerprint:
            return record
    return None


def match_domain_prefix(
    candidate: NormalizedApi,
    existing: list[NormalizedApi],
) -> tuple[NormalizedApi, float] | None:
    """Find a domain + path prefix match.

    Returns the matching record and confidence score.
    """
    cand_domain, cand_path = get_domain_path_prefix(candidate.base_url)

    best_match: NormalizedApi | None = None
    best_score = 0.0

    for record in existing:
        rec_domain, rec_path = get_domain_path_prefix(record.base_url)

        if cand_domain != rec_domain:
            continue

        # Calculate path overlap
        if cand_path == rec_path:
            score = 0.9
        elif cand_path.startswith(rec_path) or rec_path.startswith(cand_path):
            score = 0.7
        else:
            score = 0.5

        if score > best_score:
            best_score = score
            best_match = record

    if best_match and best_score >= 0.5:
        return best_match, best_score
    return None


def match_name_similarity(
    candidate: NormalizedApi,
    existing: list[NormalizedApi],
    *,
    threshold: float = NAME_SIMILARITY_THRESHOLD,
) -> tuple[NormalizedApi, float] | None:
    """Find a name similarity match above the threshold."""
    best_match: NormalizedApi | None = None
    best_score = 0.0

    for record in existing:
        score = compute_name_similarity(candidate.name, record.name)
        if score > best_score:
            best_score = score
            best_match = record

    if best_match and best_score >= threshold:
        return best_match, best_score
    return None


def find_match(
    candidate: NormalizedApi,
    existing: list[NormalizedApi],
) -> tuple[NormalizedApi, str, float] | None:
    """Find the best matching existing record for a candidate.

    Returns (existing_record, match_type, confidence) or None.
    Match types: "exact_url", "domain_prefix", "name_similarity"
    """
    # Priority 1: Exact URL match
    exact = match_exact_url(candidate, existing)
    if exact:
        return exact, "exact_url", 1.0

    # Priority 2: Domain + path prefix match
    domain_match = match_domain_prefix(candidate, existing)
    if domain_match:
        record, score = domain_match
        return record, "domain_prefix", score

    # Priority 3: Name similarity match
    name_match = match_name_similarity(candidate, existing)
    if name_match:
        record, score = name_match
        return record, "name_similarity", score

    return None


def deduplicate(
    candidates: list[NormalizedApi],
    existing: list[NormalizedApi] | None = None,
) -> tuple[list[NormalizedApi], list[NormalizedApi], list[NormalizedApi]]:
    """Deduplicate candidates against existing records.

    Returns:
        - deduplicated: Final list of unique API records (merged)
        - new_records: Records that didn't match any existing
        - merged_records: Records that were merged into existing
    """
    if existing is None:
        existing = []

    # Build a working set from existing records
    working_set: dict[str, NormalizedApi] = {record.url_fingerprint or record.base_url: record for record in existing}

    new_records: list[NormalizedApi] = []
    merged_records: list[NormalizedApi] = []
    duplicates_found = 0

    for candidate in candidates:
        match = find_match(candidate, list(working_set.values()))

        if match:
            existing_record, match_type, confidence = match
            duplicates_found += 1

            # Merge candidate into existing
            merged = existing_record.merge_with(candidate)
            merged.metadata["match_type"] = match_type
            merged.metadata["match_confidence"] = confidence

            # Update working set
            key = merged.url_fingerprint or merged.base_url
            working_set[key] = merged
            merged_records.append(merged)
        else:
            # New record - add to working set
            key = candidate.url_fingerprint or candidate.base_url
            working_set[key] = candidate
            new_records.append(candidate)

    deduplicated = list(working_set.values())
    return deduplicated, new_records, merged_records


def build_fingerprint_index(records: list[NormalizedApi]) -> dict[str, NormalizedApi]:
    """Build a fingerprint index for O(1) lookups.

    Returns a dict mapping fingerprints to records.
    """
    index: dict[str, NormalizedApi] = {}
    for record in records:
        if record.url_fingerprint:
            index[record.url_fingerprint] = record
        # Also index by base_url for fallback
        index[record.base_url] = record
    return index
