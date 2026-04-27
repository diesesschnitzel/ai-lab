"""Website analysis pipeline: SEO, performance, mobile, and design assessment."""

from __future__ import annotations

import logging
from typing import Any

from src.apivault.prospecting.models import (
    ContentGap,
    DesignQuality,
    MobileAssessment,
    PerformanceMetrics,
    SEOAssessment,
    WebsiteAnalysis,
)

logger = logging.getLogger(__name__)


def _get_bs4():
    """Lazy import of BeautifulSoup to avoid hard dependency at module load."""
    from bs4 import BeautifulSoup
    return BeautifulSoup


async def analyze_website(url: str, html: bytes, **kwargs: Any) -> WebsiteAnalysis:
    """Run a complete website analysis on the given HTML content.

    Args:
        url: The URL being analyzed
        html: Raw HTML content of the page
        **kwargs: Optional pre-fetched data (e.g., "requests" from Playwright)

    Returns:
        Complete WebsiteAnalysis with SEO, performance, mobile, and design scores.
    """
    BeautifulSoup = _get_bs4()
    soup = BeautifulSoup(html, "html.parser")

    analysis = WebsiteAnalysis(
        prospect_id=kwargs.get("prospect_id", ""),
        seo=analyze_seo(soup, url),
        performance=analyze_performance(soup, kwargs.get("performance_data")),
        mobile=analyze_mobile(soup),
        design=analyze_design(soup),
        content_gaps=identify_content_gaps(soup, url),
    )

    analysis.compute_overall_score()
    return analysis


def analyze_seo(soup: BeautifulSoup, url: str) -> SEOAssessment:
    """Analyze SEO quality of a webpage."""
    assessment = SEOAssessment(url=url)

    # Title tag
    title = soup.find("title")
    if title:
        assessment.has_title_tag = True
        assessment.title_length = len(title.get_text(strip=True))

    # Meta description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        assessment.has_meta_description = True
        assessment.description_length = len(meta_desc["content"].strip())

    # Robots meta
    meta_robots = soup.find("meta", attrs={"name": "robots"})
    assessment.has_robots_meta = meta_robots is not None

    # Canonical URL
    canonical = soup.find("link", attrs={"rel": "canonical"})
    assessment.has_canonical_url = canonical is not None

    # Headings
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    assessment.heading_count = len(headings)
    assessment.h1_count = len(soup.find_all("h1"))

    # Structured data (JSON-LD)
    json_ld = soup.find("script", attrs={"type": "application/ld+json"})
    assessment.has_structured_data = json_ld is not None

    # Content analysis
    text_content = soup.get_text(separator=" ", strip=True)
    assessment.word_count = len(text_content.split())

    # Images
    images = soup.find_all("img")
    assessment.image_count = len(images)
    assessment.images_with_alt = sum(
        1 for img in images if img.get("alt", "").strip()
    )

    # Links
    links = soup.find_all("a", href=True)
    base_domain = url.split("/")[2] if "/" in url else ""
    internal = 0
    external = 0
    for link in links:
        href = link["href"]
        if href.startswith("http"):
            if base_domain in href:
                internal += 1
            else:
                external += 1
        elif not href.startswith("#") and not href.startswith("javascript:"):
            internal += 1
    assessment.internal_link_count = internal
    assessment.external_link_count = external

    assessment.compute_score()
    return assessment


def analyze_performance(
    soup: BeautifulSoup,
    performance_data: dict[str, Any] | None = None,
) -> PerformanceMetrics:
    """Analyze page performance metrics.

    If Playwright/Lighthouse data is provided, uses that.
    Otherwise performs static analysis of the page structure.
    """
    metrics = PerformanceMetrics(url="")

    if performance_data:
        # Use real performance data from Playwright/Lighthouse
        metrics.first_contentful_paint_ms = performance_data.get(
            "firstContentfulPaint", 0
        )
        metrics.largest_contentful_paint_ms = performance_data.get(
            "largestContentfulPaint", 0
        )
        metrics.time_to_interactive_ms = performance_data.get(
            "timeToInteractive", 0
        )
        metrics.total_blocking_time_ms = performance_data.get(
            "totalBlockingTime", 0
        )
        metrics.cumulative_layout_shift = performance_data.get(
            "cumulativeLayoutShift", 0
        )
        metrics.load_time_ms = performance_data.get("loadTime", 0)
        metrics.page_size_kb = performance_data.get("pageSizeKb", 0)
        metrics.request_count = performance_data.get("requestCount", 0)
        metrics.compute_score()
        return metrics

    # Static analysis fallback (no real performance data available)
    # Estimate based on page complexity
    images = soup.find_all("img")
    scripts = soup.find_all("script", src=True)
    stylesheets = soup.find_all("link", attrs={"rel": "stylesheet"})

    # Rough estimates based on resource count
    metrics.request_count = len(images) + len(scripts) + len(stylesheets)

    # Estimate page size (very rough heuristic)
    metrics.image_size_kb = len(images) * 150  # ~150KB per image average
    metrics.js_size_kb = len(scripts) * 50  # ~50KB per script average
    metrics.css_size_kb = len(stylesheets) * 30  # ~30KB per stylesheet average
    metrics.page_size_kb = (
        metrics.image_size_kb + metrics.js_size_kb + metrics.css_size_kb
    )

    # Simple score based on resource count
    # Fewer resources generally = faster page
    if metrics.request_count <= 20:
        metrics.performance_score = 75
    elif metrics.request_count <= 40:
        metrics.performance_score = 50
    else:
        metrics.performance_score = 25

    return metrics


def analyze_mobile(soup: BeautifulSoup) -> MobileAssessment:
    """Analyze mobile responsiveness of a webpage."""
    assessment = MobileAssessment(url="")

    # Viewport meta
    viewport = soup.find("meta", attrs={"name": "viewport"})
    if viewport:
        assessment.has_viewport_meta = True
        assessment.viewport_content = viewport.get("content", "")

    # CSS analysis
    styles = soup.find_all("style")
    stylesheets = soup.find_all("link", attrs={"rel": "stylesheet"})
    all_css = " ".join(
        s.get_text() for s in styles
    )

    # Check for responsive CSS patterns
    assessment.uses_media_queries = "@media" in all_css
    assessment.uses_flexbox = "display: flex" in all_css or "display:flex" in all_css
    assessment.uses_css_grid = "display: grid" in all_css or "display:grid" in all_css

    # Font size check
    font_sizes = ["16px", "1em", "1rem", "100%"]
    assessment.font_size_readable = any(
        f"font-size: {size}" in all_css for size in font_sizes
    )

    # Check for PWA indicators
    manifest = soup.find("link", attrs={"rel": "manifest"})
    assessment.uses_pwa = manifest is not None

    apple_touch = soup.find("link", attrs={"rel": "apple-touch-icon"})
    assessment.has_apple_touch_icon = apple_touch is not None

    # Check for AMP
    html_tag = soup.find("html")
    if html_tag:
        html_attrs = " ".join(html_tag.attrs) if html_tag.attrs else ""
        assessment.uses_amp = "amp" in html_attrs or "⚡" in html_attrs

    # Responsiveness: if it has viewport + media queries, likely responsive
    assessment.is_responsive = (
        assessment.has_viewport_meta and assessment.uses_media_queries
    )

    assessment.compute_score()
    return assessment


def analyze_design(soup: BeautifulSoup) -> DesignQuality:
    """Analyze design quality using heuristic analysis."""
    assessment = DesignQuality(url="")

    # Check for hero section
    hero_selectors = [".hero", ".hero-section", "#hero", ".banner", ".jumbotron"]
    assessment.has_hero_section = any(
        soup.select_one(s) for s in hero_selectors
    )

    # Navigation
    nav = soup.find("nav")
    if not nav:
        nav = soup.find(id=lambda x: x and "nav" in str(x).lower())
    assessment.has_clear_navigation = nav is not None

    # Footer
    footer = soup.find("footer")
    if not footer:
        footer = soup.find(id=lambda x: x and "footer" in str(x).lower())
    assessment.has_footer = footer is not None

    # Call to action
    cta_selectors = [".cta", ".btn-primary", ".button-primary", "button.cta"]
    cta_elements = [soup.select_one(s) for s in cta_selectors]
    assessment.has_call_to_action = any(
        el for el in cta_elements if el is not None
    )

    # Images
    images = soup.find_all("img")
    assessment.has_images = len(images) > 0

    # Videos
    videos = soup.find_all(["video", "iframe"])
    assessment.has_videos = len(videos) > 0

    # Testimonials
    testimonial_keywords = ["testimonial", "review", "feedback", "what our clients"]
    body_text = soup.get_text().lower()
    assessment.has_testimonials = any(
        keyword in body_text for keyword in testimonial_keywords
    )

    # Team section
    team_keywords = ["our team", "meet the team", "about us", "leadership"]
    assessment.has_team_section = any(
        keyword in body_text for keyword in team_keywords
    )

    # CSS analysis
    styles = soup.find_all("style")
    stylesheets = soup.find_all("link", attrs={"rel": "stylesheet"})
    all_css = " ".join(s.get_text() for s in styles)

    # CSS variables (modern CSS indicator)
    assessment.has_modern_css = "--" in all_css

    # Detect framework
    css_text = all_css.lower()
    if "tailwind" in css_text or any(
        f"class=\"{p}" in soup.decode().lower()
        for p in ["container mx-auto", "flex justify-", "grid grid-cols-"]
    ):
        assessment.uses_framework = "tailwind"
    elif "bootstrap" in css_text or any(
        "bootstrap" in (s.get("href") or "") for s in stylesheets
    ):
        assessment.uses_framework = "bootstrap"
    elif "bulma" in css_text or any(
        "bulma" in (s.get("href") or "") for s in stylesheets
    ):
        assessment.uses_framework = "bulma"

    # Typography hierarchy
    heading_tags = soup.find_all(["h1", "h2", "h3"])
    assessment.has_typography_hierarchy = len(heading_tags) >= 2

    # Color palette estimation (count unique color values in CSS)
    import re
    color_pattern = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    colors = set(color_pattern.findall(all_css))
    assessment.color_palette_size = len(colors)
    assessment.has_consistent_colors = len(colors) <= 15  # Reasonable palette

    assessment.compute_score()
    return assessment


def identify_content_gaps(soup: BeautifulSoup, url: str) -> list[ContentGap]:
    """Identify content gaps on a prospect's website."""
    gaps: list[ContentGap] = []
    body_text = soup.get_text().lower()

    # Check for common missing pages
    common_pages = {
        "privacy policy": ("missing_page", "No privacy policy page detected"),
        "terms of service": ("missing_page", "No terms of service page detected"),
        "about us": ("missing_page", "No about us page detected"),
        "contact": ("missing_page", "No contact page detected"),
        "faq": ("no_faq", "No FAQ section found"),
        "blog": ("no_blog", "No blog or news section found"),
    }

    for keyword, (gap_type, description) in common_pages.items():
        if keyword not in body_text:
            severity = "high" if keyword in ["privacy policy", "contact"] else "medium"
            recommendation = _get_recommendation(keyword)
            gaps.append(ContentGap(
                gap_type=gap_type,
                description=description,
                severity=severity,
                recommendation=recommendation,
            ))

    # Thin content check
    word_count = len(soup.get_text().split())
    if word_count < 200:
        gaps.append(ContentGap(
            gap_type="thin_content",
            description=f"Very thin page content ({word_count} words)",
            severity="high",
            recommendation="Add more substantive content to improve SEO and user trust",
        ))

    return gaps


def _get_recommendation(missing_page: str) -> str:
    """Get a recommendation for a missing content type."""
    recommendations = {
        "privacy policy": "Add a privacy policy page — required by GDPR and builds user trust",
        "terms of service": "Add terms of service to clarify legal obligations",
        "about us": "Create an about us page to build credibility and trust",
        "contact": "Add a clear contact page with multiple contact methods",
        "faq": "Add an FAQ section to address common customer questions",
        "blog": "Start a blog to improve SEO and establish thought leadership",
    }
    return recommendations.get(missing_page, "")
