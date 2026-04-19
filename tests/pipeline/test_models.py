"""Tests for pipeline models."""


from src.apivault.pipeline.models import (
    ApiFormat,
    ConfidenceLevel,
    DataSource,
    NormalizedApi,
    RawCandidate,
)


class TestNormalizedApiMerge:
    def test_merge_combines_sources(self):
        a = NormalizedApi(
            name="API A",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
            sources=[DataSource(source="scraper-1")],
        )
        b = NormalizedApi(
            name="API B",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
            sources=[DataSource(source="scraper-2")],
        )
        merged = a.merge_with(b)
        assert len(merged.sources) == 2
        assert {s.source for s in merged.sources} == {"scraper-1", "scraper-2"}

    def test_merge_keeps_higher_confidence(self):
        a = NormalizedApi(
            name="API A",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
            confidence=ConfidenceLevel.LOW,
        )
        b = NormalizedApi(
            name="API B",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
            confidence=ConfidenceLevel.HIGH,
        )
        merged = a.merge_with(b)
        assert merged.confidence == ConfidenceLevel.HIGH

    def test_merge_keeps_existing_name_when_present(self):
        a = NormalizedApi(
            name="Existing API",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
        )
        b = NormalizedApi(
            name="New API",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
        )
        merged = a.merge_with(b)
        assert merged.name == "Existing API"

    def test_merge_uses_other_name_when_self_empty(self):
        a = NormalizedApi(
            name="",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
        )
        b = NormalizedApi(
            name="New API",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
        )
        merged = a.merge_with(b)
        assert merged.name == "New API"

    def test_merge_prefers_existing_docs_url(self):
        a = NormalizedApi(
            name="API",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
            docs_url="https://api.example.com/docs",
        )
        b = NormalizedApi(
            name="API",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
            docs_url=None,
        )
        merged = a.merge_with(b)
        assert merged.docs_url == "https://api.example.com/docs"

    def test_merge_uses_other_docs_url_when_self_none(self):
        a = NormalizedApi(
            name="API",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
            docs_url=None,
        )
        b = NormalizedApi(
            name="API",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
            docs_url="https://api.example.com/docs",
        )
        merged = a.merge_with(b)
        assert merged.docs_url == "https://api.example.com/docs"

    def test_merge_updates_timestamp(self):
        a = NormalizedApi(
            name="API",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
        )
        b = NormalizedApi(
            name="API",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
        )
        merged = a.merge_with(b)
        assert merged.updated_at > a.updated_at

    def test_merge_combines_metadata(self):
        a = NormalizedApi(
            name="API",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
            metadata={"key_a": "value_a"},
        )
        b = NormalizedApi(
            name="API",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
            metadata={"key_b": "value_b"},
        )
        merged = a.merge_with(b)
        assert merged.metadata == {"key_a": "value_a", "key_b": "value_b"}

    def test_merge_keeps_unknown_format_when_self_has_format(self):
        a = NormalizedApi(
            name="API",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
            api_format=ApiFormat.REST,
        )
        b = NormalizedApi(
            name="API",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
            api_format=ApiFormat.UNKNOWN,
        )
        merged = a.merge_with(b)
        assert merged.api_format == ApiFormat.REST

    def test_merge_uses_other_format_when_self_unknown(self):
        a = NormalizedApi(
            name="API",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
            api_format=ApiFormat.UNKNOWN,
        )
        b = NormalizedApi(
            name="API",
            base_url="https://api.example.com",
            canonical_domain="api.example.com",
            api_format=ApiFormat.GRAPHQL,
        )
        merged = a.merge_with(b)
        assert merged.api_format == ApiFormat.GRAPHQL


class TestRawCandidate:
    def test_raw_candidate_defaults(self):
        candidate = RawCandidate()
        assert candidate.source == "unknown"
        assert candidate.raw_data == {}
        assert candidate.name is None
        assert candidate.url is None

    def test_raw_candidate_with_data(self):
        candidate = RawCandidate(
            name="Test API",
            url="https://api.test.com",
            description="A test API",
            source="github",
            raw_data={"stars": 100},
        )
        assert candidate.name == "Test API"
        assert candidate.url == "https://api.test.com"
        assert candidate.description == "A test API"
        assert candidate.source == "github"
        assert candidate.raw_data == {"stars": 100}
