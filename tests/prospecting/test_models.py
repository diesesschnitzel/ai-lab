"""Tests for prospecting pipeline data models."""

from datetime import datetime

from src.apivault.prospecting.models import (
    ContentGap,
    DesignQuality,
    MobileAssessment,
    PerformanceMetrics,
    Prospect,
    ProspectSource,
    SEOAssessment,
    WebsiteAnalysis,
)


def test_prospect_basic():
    p = Prospect(
        name="Test Cafe",
        website="https://testcafe.de",
        phone="+49 30 12345678",
        address="Berliner Str. 1, Berlin",
        industry="Restaurant",
        source=ProspectSource.GOOGLE_MAPS,
    )
    assert p.name == "Test Cafe"
    assert p.has_website is True
    assert p.url_with_scheme() == "https://testcafe.de"
    assert p.analysis_status == "pending"


def test_prospect_no_website():
    p = Prospect(
        name="Local Plumber",
        source=ProspectSource.YELLOW_PAGES,
    )
    assert p.has_website is False
    assert p.url_with_scheme() is None


def test_prospect_url_without_scheme():
    p = Prospect(
        name="Example Corp",
        website="example.com",
        source=ProspectSource.GOOGLE_MAPS,
    )
    assert p.url_with_scheme() == "https://example.com"


def test_prospect_gdpr_defaults():
    p = Prospect(
        name="Test",
        source=ProspectSource.GOOGLE_MAPS,
    )
    assert p.gdpr_legal_basis is None
    assert p.gdpr_data_retained_until is None
    assert p.gdpr_deletion_requested is False


def test_seo_assessment_scoring():
    seo = SEOAssessment(
        url="https://example.com",
        has_title_tag=True,
        title_length=45,
        has_meta_description=True,
        description_length=155,
        h1_count=1,
        has_structured_data=True,
        has_canonical_url=True,
        has_robots_txt=True,
        word_count=500,
        image_count=10,
        images_with_alt=8,
        has_sitemap=True,
        internal_link_count=15,
    )
    score = seo.compute_score()
    assert score > 0
    assert seo.seo_score > 80  # Well-optimized site should score high


def test_seo_assessment_poor_site():
    seo = SEOAssessment(
        url="https://example.com",
        has_title_tag=False,
        has_meta_description=False,
        h1_count=0,
        word_count=20,
        image_count=5,
        images_with_alt=0,
        internal_link_count=0,
    )
    score = seo.compute_score()
    assert score < 50  # Poor site should score low


def test_performance_metrics_scoring():
    perf = PerformanceMetrics(
        url="https://example.com",
        first_contentful_paint_ms=1500,
        largest_contentful_paint_ms=2000,
        total_blocking_time_ms=100,
        cumulative_layout_shift=0.05,
    )
    score = perf.compute_score()
    assert score >= 75  # Good performance


def test_performance_metrics_slow_site():
    perf = PerformanceMetrics(
        url="https://example.com",
        first_contentful_paint_ms=5000,
        largest_contentful_paint_ms=8000,
        total_blocking_time_ms=1500,
        cumulative_layout_shift=0.5,
    )
    score = perf.compute_score()
    assert score < 25  # Very slow site


def test_mobile_assessment_responsive():
    mobile = MobileAssessment(
        url="https://example.com",
        has_viewport_meta=True,
        viewport_content="width=device-width, initial-scale=1",
        is_responsive=True,
        uses_media_queries=True,
        uses_flexbox=True,
        no_horizontal_scroll=True,
        font_size_readable=True,
        uses_pwa=True,
        has_apple_touch_icon=True,
    )
    score = mobile.compute_score()
    assert score >= 80  # Good mobile experience


def test_mobile_assessment_non_responsive():
    mobile = MobileAssessment(
        url="https://example.com",
        has_viewport_meta=False,
        is_responsive=False,
        no_horizontal_scroll=False,
    )
    score = mobile.compute_score()
    assert score < 30  # Poor mobile experience


def test_design_quality_good():
    design = DesignQuality(
        url="https://example.com",
        has_hero_section=True,
        has_consistent_colors=True,
        color_palette_size=4,
        has_typography_hierarchy=True,
        uses_custom_fonts=True,
        has_clear_navigation=True,
        has_footer=True,
        has_call_to_action=True,
        whitespace_adequate=True,
        has_images=True,
        has_testimonials=True,
        has_team_section=True,
        has_modern_css=True,
        uses_framework="tailwind",
    )
    score = design.compute_score()
    assert score >= 70


def test_website_analysis_overall_score():
    seo = SEOAssessment(
        url="https://example.com",
        has_title_tag=True,
        title_length=45,
        has_meta_description=True,
        description_length=155,
        h1_count=1,
        word_count=300,
        image_count=5,
        images_with_alt=3,
        has_sitemap=True,
        internal_link_count=10,
    )
    seo.compute_score()
    perf = PerformanceMetrics(
        url="https://example.com",
        first_contentful_paint_ms=1800,
        largest_contentful_paint_ms=2200,
        total_blocking_time_ms=150,
        cumulative_layout_shift=0.08,
    )
    perf.compute_score()
    mobile = MobileAssessment(
        url="https://example.com",
        has_viewport_meta=True,
        is_responsive=True,
        uses_media_queries=True,
        no_horizontal_scroll=True,
    )
    mobile.compute_score()
    design = DesignQuality(
        url="https://example.com",
        has_hero_section=True,
        has_clear_navigation=True,
        has_footer=True,
        has_call_to_action=True,
    )
    design.compute_score()
    analysis = WebsiteAnalysis(
        prospect_id="test-cafe",
        seo=seo,
        performance=perf,
        mobile=mobile,
        design=design,
    )
    score = analysis.compute_overall_score()
    assert score > 0
    assert analysis.overall_score > 0


def test_content_gap_creation():
    gap = ContentGap(
        gap_type="missing_page",
        description="No privacy policy page detected",
        severity="high",
        recommendation="Add a privacy policy page — required by GDPR",
    )
    assert gap.gap_type == "missing_page"
    assert gap.severity == "high"
