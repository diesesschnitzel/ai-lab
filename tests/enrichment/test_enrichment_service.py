"""Tests for the enrichment service."""

from src.apivault.enrichment.models import EnrichmentResult
from src.apivault.services.enrichment_service import EnrichmentService, KEYWORD_CATEGORY_MAP


class TestRuleBasedCategorize:
    def setup_method(self):
        self.service = EnrichmentService()

    def test_weather_keyword(self):
        cats = self.service.rule_based_categorize("Weather API", "Get current weather data")
        assert any("Weather" in c for c in cats)

    def test_payment_keyword(self):
        cats = self.service.rule_based_categorize("Payment API", "Process payments")
        assert any("Payment" in c for c in cats)

    def test_unknown_returns_utilities(self):
        cats = self.service.rule_based_categorize("XYZ API", "Some obscure thing")
        assert cats == ["Utilities"]

    def test_multiple_keywords(self):
        cats = self.service.rule_based_categorize("Weather Payment", "Weather and payment data")
        assert len(cats) >= 2

    def test_limits_to_three(self):
        text = "weather forecast payment currency sms email"
        cats = self.service.rule_based_categorize("Multi API", text)
        assert len(cats) <= 3


class TestValidateEnrichment:
    def setup_method(self):
        self.service = EnrichmentService()

    def test_valid_categories(self):
        result = self.service.validate_enrichment(
            {
                "categories": ["AI & Machine Learning > Text Generation & LLMs"],
                "tags": ["llm", "ai"],
                "use_cases": ["Use to generate text"],
                "description_llm": "An AI text generation API.",
                "company": "AI Co",
            }
        )
        assert len(result.categories) == 1
        assert "AI & Machine Learning" in result.categories[0]

    def test_invalid_category_fallback(self):
        result = self.service.validate_enrichment(
            {
                "categories": ["Invalid Category > Something"],
                "tags": [],
                "use_cases": [],
                "description_llm": "Test",
            }
        )
        assert result.categories == ["Utilities"]

    def test_category_without_sublevel(self):
        result = self.service.validate_enrichment(
            {
                "categories": ["AI & Machine Learning"],
                "tags": [],
                "use_cases": [],
                "description_llm": "Test",
            }
        )
        assert len(result.categories) == 1
        assert result.categories[0] == "AI & Machine Learning"

    def test_tags_limited_to_20(self):
        result = self.service.validate_enrichment(
            {
                "categories": ["Utilities"],
                "tags": [f"tag{i}" for i in range(30)],
                "use_cases": [],
                "description_llm": "Test",
            }
        )
        assert len(result.tags) == 20

    def test_use_cases_must_start_with_use_to(self):
        result = self.service.validate_enrichment(
            {
                "categories": ["Utilities"],
                "tags": [],
                "use_cases": [
                    "Use to do something",
                    "This is not valid",
                    "USE TO DO ANOTHER THING",
                ],
                "description_llm": "Test",
            }
        )
        assert len(result.use_cases) == 2
        assert all(uc.lower().startswith("use to") for uc in result.use_cases)

    def test_short_description_becomes_none(self):
        result = self.service.validate_enrichment(
            {
                "categories": ["Utilities"],
                "tags": [],
                "use_cases": [],
                "description_llm": "Too short",
            }
        )
        assert result.description_llm is None

    def test_valid_description_kept(self):
        result = self.service.validate_enrichment(
            {
                "categories": ["Utilities"],
                "tags": [],
                "use_cases": [],
                "description_llm": "This is a proper description that is long enough.",
            }
        )
        assert result.description_llm is not None
        assert len(result.description_llm) >= 20


class TestBuildEmbeddingText:
    def setup_method(self):
        self.service = EnrichmentService()

    def test_builds_from_all_fields(self):
        from unittest.mock import MagicMock

        api = MagicMock()
        api.name = "Test API"
        api.description = "Original description"

        enrichment = EnrichmentResult(
            categories=["Test > Category"],
            tags=["tag1", "tag2"],
            use_cases=["Use to test"],
            description_llm="LLM description",
        )

        text = self.service.build_embedding_text(api, enrichment)
        assert "Test API" in text
        assert "LLM description" in text
        assert "tag1" in text
        assert "tag2" in text
        assert "Use to test" in text
        assert "Test > Category" in text

    def test_limits_to_2000_chars(self):
        from unittest.mock import MagicMock

        api = MagicMock()
        api.name = "Test API"
        api.description = None

        enrichment = EnrichmentResult(
            categories=[],
            tags=["tag"] * 100,
            use_cases=["Use to " + "x" * 500] * 5,
            description_llm="Description",
        )

        text = self.service.build_embedding_text(api, enrichment)
        assert len(text) <= 2000


class TestExtractCompanyFromUrl:
    def setup_method(self):
        self.service = EnrichmentService()

    def test_extracts_domain(self):
        assert self.service._extract_company_from_url("https://stripe.com/api") == "Stripe"

    def test_extracts_from_subdomain(self):
        assert self.service._extract_company_from_url("https://api.openai.com/v1") == "Openai"

    def test_handles_none(self):
        assert self.service._extract_company_from_url(None) is None

    def test_handles_empty(self):
        assert self.service._extract_company_from_url("") is None


class TestRuleBasedEnrichment:
    def setup_method(self):
        self.service = EnrichmentService()

    def test_generates_categories(self):
        from unittest.mock import MagicMock

        api = MagicMock()
        api.name = "Weather API"
        api.description = "Get weather data"
        api.base_url = "https://weather.com"
        api.auth_type = "none"
        api.free_tier = "1000 requests/day"

        result = self.service._rule_based_enrichment(api)
        assert isinstance(result, EnrichmentResult)
        assert len(result.categories) > 0
        assert len(result.tags) > 0
        assert len(result.use_cases) > 0

    def test_no_auth_tag(self):
        from unittest.mock import MagicMock

        api = MagicMock()
        api.name = "Test API"
        api.description = None
        api.base_url = None
        api.auth_type = "none"
        api.free_tier = None

        result = self.service._rule_based_enrichment(api)
        assert "no-auth" in result.tags


class TestKeywordCategoryMap:
    def test_has_expected_categories(self):
        assert any("Weather" in v for v in KEYWORD_CATEGORY_MAP.values())
        assert any("Payment" in v for v in KEYWORD_CATEGORY_MAP.values())
        assert any("Communication" in v for v in KEYWORD_CATEGORY_MAP.values())
        assert any("AI" in v for v in KEYWORD_CATEGORY_MAP.values())
