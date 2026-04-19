"""Tests for the enrichment models."""

from src.apivault.enrichment.models import EnrichmentContext, EnrichmentResult


class TestEnrichmentContext:
    def test_minimal_context(self):
        ctx = EnrichmentContext(name="Test API")
        assert ctx.name == "Test API"
        assert ctx.description is None
        assert ctx.auth_type == "unknown"
        assert ctx.existing_categories == []
        assert ctx.existing_tags == []

    def test_full_context(self):
        ctx = EnrichmentContext(
            name="Weather API",
            description="Get weather data for any location",
            base_url="https://api.weather.com",
            docs_url="https://docs.weather.com",
            auth_type="apikey",
            existing_categories=["Weather & Environment > Current Weather"],
            existing_tags=["weather", "rest"],
            docs_excerpt="Weather API provides real-time weather data",
            spec_summary="Weather endpoints for forecasts",
        )
        assert ctx.name == "Weather API"
        assert ctx.description == "Get weather data for any location"
        assert ctx.auth_type == "apikey"
        assert len(ctx.existing_categories) == 1
        assert len(ctx.existing_tags) == 2


class TestEnrichmentResult:
    def test_empty_result(self):
        result = EnrichmentResult()
        assert result.categories == []
        assert result.tags == []
        assert result.use_cases == []
        assert result.description_llm is None
        assert result.company is None

    def test_full_result(self):
        result = EnrichmentResult(
            categories=["Weather & Environment > Current Weather"],
            tags=["weather", "rest", "no-auth"],
            use_cases=["Use to get current weather for any city"],
            description_llm="A weather API that provides real-time data.",
            company="Weather Inc",
        )
        assert len(result.categories) == 1
        assert len(result.tags) == 3
        assert len(result.use_cases) == 1
        assert "weather" in result.description_llm.lower()
        assert result.company == "Weather Inc"
