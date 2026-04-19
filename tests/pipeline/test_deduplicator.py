"""Tests for the deduplicator module."""


from src.apivault.pipeline.deduplicator import (
    build_fingerprint_index,
    compute_name_similarity,
    deduplicate,
    find_match,
    match_domain_prefix,
    match_exact_url,
    match_name_similarity,
)
from src.apivault.pipeline.models import DataSource, NormalizedApi


def make_api(name: str, base_url: str, **kwargs) -> NormalizedApi:
    """Helper to create NormalizedApi instances."""
    return NormalizedApi(
        name=name,
        base_url=base_url,
        canonical_domain=base_url.split("://")[1].split("/")[0].split(":")[0],
        url_fingerprint=kwargs.pop("url_fingerprint", None),
        **kwargs,
    )


class TestComputeNameSimilarity:
    def test_exact_match(self):
        assert compute_name_similarity("Stripe API", "Stripe API") == 1.0

    def test_case_insensitive(self):
        assert compute_name_similarity("stripe api", "STRIPE API") == 1.0

    def test_similar_names(self):
        score = compute_name_similarity("Stripe", "Stripe API")
        assert score >= 0.75

    def test_different_names(self):
        score = compute_name_similarity("Stripe", "Twilio")
        assert score < 0.5

    def test_empty_names(self):
        assert compute_name_similarity("", "Stripe") == 0.0

    def test_common_words_ignored(self):
        score = compute_name_similarity("The Free API Hub", "API Hub")
        assert score >= 0.75

    def test_contains_match(self):
        score = compute_name_similarity("GitHub", "GitHub API")
        assert score >= 0.75


class TestMatchExactUrl:
    def test_fingerprint_match(self):
        existing = [make_api("API", "https://api.example.com", url_fingerprint="abc123")]
        candidate = make_api("API", "https://api.example.com", url_fingerprint="abc123")
        result = match_exact_url(candidate, existing)
        assert result is not None
        assert result.name == "API"

    def test_no_match(self):
        existing = [make_api("API", "https://api.example.com", url_fingerprint="abc123")]
        candidate = make_api("API", "https://api.other.com", url_fingerprint="xyz789")
        assert match_exact_url(candidate, existing) is None

    def test_no_fingerprint(self):
        existing = [make_api("API", "https://api.example.com")]
        candidate = make_api("API", "https://api.example.com")
        assert match_exact_url(candidate, existing) is None


class TestMatchDomainPrefix:
    def test_same_domain_same_path(self):
        existing = [make_api("API", "https://api.example.com/v1")]
        candidate = make_api("API", "https://api.example.com/v1")
        result = match_domain_prefix(candidate, existing)
        assert result is not None
        record, score = result
        assert score >= 0.5

    def test_same_domain_different_path(self):
        existing = [make_api("API", "https://api.example.com/v1")]
        candidate = make_api("API", "https://api.example.com/v2")
        result = match_domain_prefix(candidate, existing)
        assert result is not None

    def test_different_domain(self):
        existing = [make_api("API", "https://api.example.com/v1")]
        candidate = make_api("API", "https://api.other.com/v1")
        assert match_domain_prefix(candidate, existing) is None


class TestMatchNameSimilarity:
    def test_similar_names_match(self):
        existing = [make_api("Stripe", "https://api.stripe.com")]
        candidate = make_api("Stripe API", "https://api.stripe.io")
        result = match_name_similarity(candidate, existing)
        assert result is not None

    def test_different_names_no_match(self):
        existing = [make_api("Stripe", "https://api.stripe.com")]
        candidate = make_api("Twilio", "https://api.twilio.com")
        assert match_name_similarity(candidate, existing) is None


class TestFindMatch:
    def test_exact_url_priority(self):
        existing = [
            make_api("Exact", "https://api.example.com", url_fingerprint="fp1"),
            make_api("Similar Name", "https://api.other.com"),
        ]
        candidate = make_api("Different", "https://api.example.com", url_fingerprint="fp1")
        result = find_match(candidate, existing)
        assert result is not None
        _, match_type, _ = result
        assert match_type == "exact_url"

    def test_domain_prefix_fallback(self):
        existing = [make_api("API", "https://api.example.com/v1")]
        candidate = make_api("API v2", "https://api.example.com/v2")
        result = find_match(candidate, existing)
        assert result is not None
        _, match_type, _ = result
        assert match_type == "domain_prefix"

    def test_name_similarity_fallback(self):
        existing = [make_api("Stripe", "https://api.stripe.com")]
        candidate = make_api("Stripe API", "https://api.stripe.io")
        result = find_match(candidate, existing)
        assert result is not None
        _, match_type, _ = result
        assert match_type == "name_similarity"

    def test_no_match(self):
        existing = [make_api("Stripe", "https://api.stripe.com")]
        candidate = make_api("Twilio", "https://api.twilio.com")
        assert find_match(candidate, existing) is None


class TestDeduplicate:
    def test_no_duplicates(self):
        candidates = [
            make_api("API 1", "https://api1.com/v1", url_fingerprint="fp1"),
            make_api("API 2", "https://api2.com/v1", url_fingerprint="fp2"),
        ]
        deduped, new, merged = deduplicate(candidates)
        assert len(new) == 2
        assert len(merged) == 0

    def test_exact_duplicate(self):
        existing = [make_api("Existing", "https://api.example.com", url_fingerprint="fp1")]
        candidate = make_api("Candidate", "https://api.example.com", url_fingerprint="fp1")
        deduped, new, merged = deduplicate([candidate], existing)
        assert len(new) == 0
        assert len(merged) == 1
        assert len(deduped) == 1

    def test_merge_sources(self):
        existing = [
            make_api(
                "Existing",
                "https://api.example.com",
                url_fingerprint="fp1",
                sources=[DataSource(source="source-a")],
            )
        ]
        candidate = make_api(
            "Candidate",
            "https://api.example.com",
            url_fingerprint="fp1",
            sources=[DataSource(source="source-b")],
        )
        deduped, new, merged = deduplicate([candidate], existing)
        assert len(deduped[0].sources) == 2

    def test_with_no_existing(self):
        candidates = [
            make_api("API 1", "https://api1.com/v1", url_fingerprint="fp1"),
        ]
        deduped, new, merged = deduplicate(candidates)
        assert len(new) == 1
        assert len(deduped) == 1

    def test_multiple_duplicates(self):
        existing = [make_api("Existing", "https://api.example.com", url_fingerprint="fp1")]
        candidates = [
            make_api("C1", "https://api.example.com", url_fingerprint="fp1"),
            make_api("C2", "https://api.example.com", url_fingerprint="fp1"),
        ]
        deduped, new, merged = deduplicate(candidates, existing)
        assert len(new) == 0
        assert len(merged) == 2
        assert len(deduped) == 1


class TestBuildFingerprintIndex:
    def test_builds_index(self):
        records = [
            make_api("API 1", "https://api1.com", url_fingerprint="fp1"),
            make_api("API 2", "https://api2.com", url_fingerprint="fp2"),
        ]
        index = build_fingerprint_index(records)
        assert "fp1" in index
        assert "fp2" in index

    def test_fallback_to_base_url(self):
        records = [make_api("API", "https://api.example.com")]
        index = build_fingerprint_index(records)
        assert "https://api.example.com" in index
