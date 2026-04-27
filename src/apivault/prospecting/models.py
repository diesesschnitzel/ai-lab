"""Data models for the prospecting pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ProspectSource(str, Enum):
    """Source from which a prospect was discovered."""
    GOOGLE_MAPS = "google_maps"
    YELP = "yelp"
    YELLOW_PAGES = "yellow_pages"
    THOMSON_LOCAL = "thomson_local"
    EUROPAGES = "europages"
    INDUSTRY_DIRECTORY = "industry_directory"
    CHAMBER_OF_COMMERCE = "chamber_of_commerce"
    MANUAL = "manual"


class Prospect(BaseModel):
    """A single business prospect discovered through scraping."""

    # Business identity
    name: str
    website: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    city: str | None = None
    postal_code: str | None = None
    country: str | None = None

    # Classification
    industry: str | None = None
    category: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)

    # Discovery metadata
    source: ProspectSource
    source_url: str | None = None
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    raw_data: dict[str, Any] = Field(default_factory=dict)

    # GDPR tracking
    gdpr_legal_basis: str | None = None  # "legitimate_interest", "consent"
    gdpr_data_retained_until: datetime | None = None
    gdpr_deletion_requested: bool = False

    # Pipeline state
    analysis_status: str = "pending"  # pending, in_progress, completed, failed
    analysis_completed_at: datetime | None = None

    @property
    def has_website(self) -> bool:
        return bool(self.website and self.website.startswith("http"))

    def url_with_scheme(self) -> str | None:
        """Ensure the website URL has a scheme."""
        if not self.website:
            return None
        if self.website.startswith("http"):
            return self.website
        return f"https://{self.website}"


class SEOAssessment(BaseModel):
    """SEO quality assessment of a prospect's website."""

    url: str
    assessed_at: datetime = Field(default_factory=datetime.utcnow)

    # Meta tags
    has_title_tag: bool = False
    title_length: int | None = None  # Optimal: 50-60 chars
    has_meta_description: bool = False
    description_length: int | None = None  # Optimal: 150-160 chars
    has_robots_meta: bool = False
    has_canonical_url: bool = False

    # Structure
    heading_count: int = 0
    h1_count: int = 0  # Should be exactly 1
    has_structured_data: bool = False  # JSON-LD / schema.org
    has_sitemap: bool = False
    has_robots_txt: bool = False

    # Content
    word_count: int = 0
    image_count: int = 0
    images_with_alt: int = 0
    internal_link_count: int = 0
    external_link_count: int = 0

    # Score
    seo_score: float = 0.0  # 0-100

    def compute_score(self) -> float:
        """Compute an overall SEO score from 0-100."""
        score = 0.0

        # Meta tags (25 points)
        if self.has_title_tag:
            score += 10
            if self.title_length and 30 <= self.title_length <= 70:
                score += 5
        if self.has_meta_description:
            score += 10
            if self.description_length and 120 <= self.description_length <= 170:
                score += 5

        # Structure (30 points)
        if self.h1_count == 1:
            score += 10
        if self.has_structured_data:
            score += 10
        if self.has_canonical_url:
            score += 5
        if self.has_robots_txt:
            score += 5

        # Content (25 points)
        if self.word_count >= 300:
            score += 15
        elif self.word_count >= 100:
            score += 8
        alt_ratio = self.images_with_alt / max(self.image_count, 1)
        score += alt_ratio * 10

        # Technical (20 points)
        if self.has_sitemap:
            score += 10
        if self.has_robots_meta or self.has_canonical_url:
            score += 5
        if self.internal_link_count > 0:
            score += 5

        self.seo_score = min(score, 100.0)
        return self.seo_score


class PerformanceMetrics(BaseModel):
    """Page performance metrics (simplified Lighthouse-style)."""

    url: str
    assessed_at: datetime = Field(default_factory=datetime.utcnow)

    # Core metrics
    load_time_ms: float = 0.0
    first_contentful_paint_ms: float = 0.0
    largest_contentful_paint_ms: float = 0.0
    time_to_interactive_ms: float = 0.0
    total_blocking_time_ms: float = 0.0
    cumulative_layout_shift: float = 0.0

    # Resource analysis
    page_size_kb: float = 0.0
    request_count: int = 0
    image_size_kb: float = 0.0
    js_size_kb: float = 0.0
    css_size_kb: float = 0.0

    # Server
    ttfb_ms: float = 0.0  # Time to first byte
    http_status: int = 0
    has_compression: bool = False
    has_http2: bool = False

    # Score
    performance_score: float = 0.0  # 0-100

    def compute_score(self) -> float:
        """Compute a performance score based on Lighthouse weighting."""
        score = 0.0

        # FCP scoring (0-2s good, 2-4s needs improvement, >4s poor)
        if self.first_contentful_paint_ms <= 2000:
            score += 25
        elif self.first_contentful_paint_ms <= 4000:
            score += 15
        elif self.first_contentful_paint_ms <= 6000:
            score += 5

        # LCP scoring (0-2.5s good, 2.5-4s needs improvement, >4s poor)
        if self.largest_contentful_paint_ms <= 2500:
            score += 25
        elif self.largest_contentful_paint_ms <= 4000:
            score += 15
        elif self.largest_contentful_paint_ms <= 6000:
            score += 5

        # TBT scoring (0-200ms good, 200-600ms needs improvement, >600ms poor)
        if self.total_blocking_time_ms <= 200:
            score += 25
        elif self.total_blocking_time_ms <= 600:
            score += 15
        elif self.total_blocking_time_ms <= 1000:
            score += 5

        # CLS scoring (<0.1 good, 0.1-0.25 needs improvement, >0.25 poor)
        if self.cumulative_layout_shift <= 0.1:
            score += 25
        elif self.cumulative_layout_shift <= 0.25:
            score += 15
        elif self.cumulative_layout_shift <= 0.4:
            score += 5

        self.performance_score = min(score, 100.0)
        return self.performance_score


class MobileAssessment(BaseModel):
    """Mobile responsiveness assessment."""

    url: str
    assessed_at: datetime = Field(default_factory=datetime.utcnow)

    # Viewport
    has_viewport_meta: bool = False
    viewport_content: str | None = None

    # Responsiveness
    is_responsive: bool = False
    uses_media_queries: bool = False
    uses_flexbox: bool = False
    uses_css_grid: bool = False

    # Mobile UX
    tap_targets_sized: bool = False  # Buttons/links are large enough
    font_size_readable: bool = False  # Base font >= 16px
    no_horizontal_scroll: bool = True  # No forced horizontal scroll

    # Technologies
    uses_amp: bool = False
    uses_pwa: bool = False
    has_apple_touch_icon: bool = False

    # Score
    mobile_score: float = 0.0  # 0-100

    def compute_score(self) -> float:
        score = 0.0

        # Viewport (20 points)
        if self.has_viewport_meta:
            score += 20

        # Responsiveness (30 points)
        if self.is_responsive:
            score += 15
        if self.uses_media_queries:
            score += 10
        if self.uses_flexbox or self.uses_css_grid:
            score += 5

        # Mobile UX (30 points)
        if self.no_horizontal_scroll:
            score += 10
        if self.tap_targets_sized:
            score += 10
        if self.font_size_readable:
            score += 10

        # PWA/Modern (20 points)
        if self.uses_pwa:
            score += 10
        if self.has_apple_touch_icon:
            score += 5
        if self.uses_amp:
            score += 5

        self.mobile_score = min(score, 100.0)
        return self.mobile_score


class DesignQuality(BaseModel):
    """Design quality assessment (heuristic-based)."""

    url: str
    assessed_at: datetime = Field(default_factory=datetime.utcnow)

    # Visual
    has_hero_section: bool = False
    has_consistent_colors: bool = False
    color_palette_size: int = 0  # Ideal: 3-5 primary colors
    has_typography_hierarchy: bool = False
    uses_custom_fonts: bool = False

    # Layout
    has_clear_navigation: bool = False
    has_footer: bool = False
    has_call_to_action: bool = False
    whitespace_adequate: bool = False

    # Content quality
    has_images: bool = False
    has_videos: bool = False
    has_testimonials: bool = False
    has_team_section: bool = False

    # Modernity
    has_animations: bool = False
    has_modern_css: bool = False  # CSS variables, grid, etc.
    uses_framework: str | None = None  # Bootstrap, Tailwind, etc.

    # Score
    design_score: float = 0.0  # 0-100

    def compute_score(self) -> float:
        score = 0.0

        # Visual design (30 points)
        if self.has_hero_section:
            score += 8
        if self.has_consistent_colors:
            score += 7
        if 2 <= self.color_palette_size <= 6:
            score += 5
        if self.has_typography_hierarchy:
            score += 5
        if self.uses_custom_fonts:
            score += 5

        # Layout (30 points)
        if self.has_clear_navigation:
            score += 10
        if self.has_footer:
            score += 5
        if self.has_call_to_action:
            score += 10
        if self.whitespace_adequate:
            score += 5

        # Content (20 points)
        if self.has_images:
            score += 5
        if self.has_videos:
            score += 5
        if self.has_testimonials:
            score += 5
        if self.has_team_section:
            score += 5

        # Modernity (20 points)
        if self.has_animations:
            score += 5
        if self.has_modern_css:
            score += 10
        if self.uses_framework:
            score += 5

        self.design_score = min(score, 100.0)
        return self.design_score


class ContentGap(BaseModel):
    """Identified content gap on a prospect's website."""

    gap_type: str  # "missing_page", "thin_content", "no_blog", "no_faq", etc.
    description: str
    severity: str = "medium"  # low, medium, high
    recommendation: str | None = None


class WebsiteAnalysis(BaseModel):
    """Complete website analysis for a prospect."""

    prospect_id: str  # Reference to the prospect
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)

    seo: SEOAssessment | None = None
    performance: PerformanceMetrics | None = None
    mobile: MobileAssessment | None = None
    design: DesignQuality | None = None
    content_gaps: list[ContentGap] = Field(default_factory=list)

    # Overall score
    overall_score: float = 0.0

    def compute_overall_score(self) -> float:
        """Weighted overall score."""
        weights = {
            "seo": 0.30,
            "performance": 0.25,
            "mobile": 0.20,
            "design": 0.25,
        }
        total = 0.0
        weight_sum = 0.0
        for key, weight in weights.items():
            assessment = getattr(self, key)
            if assessment is not None:
                score_attr = f"{key}_score"
                score = getattr(assessment, score_attr, 0)
                total += score * weight
                weight_sum += weight
        if weight_sum > 0:
            self.overall_score = total / weight_sum
        return self.overall_score
