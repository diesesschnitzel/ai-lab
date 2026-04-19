"""Tests for the LLM client parsing and prompt building."""

from src.apivault.enrichment.llm_client import (
    build_classification_prompt,
    parse_llm_response,
)
from src.apivault.enrichment.models import EnrichmentContext


class TestParseLLMResponse:
    def test_valid_json(self):
        response = '{"categories": ["Test > Sub"], "tags": ["tag1"], "use_cases": ["Use to test"], "description_llm": "A test API.", "company": "Test Co"}'
        result = parse_llm_response(response)
        assert result is not None
        assert result["categories"] == ["Test > Sub"]
        assert result["tags"] == ["tag1"]

    def test_json_with_markdown_block(self):
        response = '```json\n{"categories": ["Test > Sub"], "tags": [], "use_cases": [], "description_llm": "Test", "company": null}\n```'
        result = parse_llm_response(response)
        assert result is not None
        assert result["categories"] == ["Test > Sub"]

    def test_json_with_text_before(self):
        response = 'Here is the result:\n{"categories": ["Test > Sub"], "tags": [], "use_cases": [], "description_llm": "Test", "company": null}'
        result = parse_llm_response(response)
        assert result is not None

    def test_invalid_json(self):
        result = parse_llm_response("not json at all")
        assert result is None

    def test_empty_response(self):
        result = parse_llm_response("")
        assert result is None

    def test_none_response(self):
        result = parse_llm_response("   ")
        assert result is None


class TestBuildClassificationPrompt:
    def test_prompt_contains_api_name(self):
        ctx = EnrichmentContext(name="Weather API", description="Get weather data")
        prompt = build_classification_prompt(ctx)
        assert "Weather API" in prompt

    def test_prompt_contains_description(self):
        ctx = EnrichmentContext(name="Weather API", description="Get weather data")
        prompt = build_classification_prompt(ctx)
        assert "Get weather data" in prompt

    def test_prompt_handles_missing_description(self):
        ctx = EnrichmentContext(name="Weather API")
        prompt = build_classification_prompt(ctx)
        assert "No description available" in prompt

    def test_prompt_contains_category_list(self):
        ctx = EnrichmentContext(name="Test API")
        prompt = build_classification_prompt(ctx)
        assert "AI & Machine Learning" in prompt
        assert "Weather & Environment" in prompt

    def test_prompt_contains_tag_vocabulary(self):
        ctx = EnrichmentContext(name="Test API")
        prompt = build_classification_prompt(ctx)
        assert "no-auth" in prompt
        assert "rest" in prompt

    def test_prompt_contains_instructions(self):
        ctx = EnrichmentContext(name="Test API")
        prompt = build_classification_prompt(ctx)
        assert "categories:" in prompt.lower() or "categories" in prompt.lower()
        assert "tags:" in prompt.lower() or "tags" in prompt.lower()
        assert "use_cases:" in prompt.lower() or "use cases" in prompt.lower()
