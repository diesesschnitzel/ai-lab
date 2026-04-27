"""Prospecting pipeline: web scraping and website analysis for customer discovery.

Pipeline flow: discovery (Google Maps, directories) → analysis (SEO, performance,
mobile, design) → storage (prospect database with GDPR compliance)
"""

from .analysis import analyze_website
from .gdpr import (
    compute_retention_date,
    determine_legal_basis,
    sanitize_for_gdpr,
    validate_legal_basis,
)
from .models import (
    ContentGap,
    DesignQuality,
    MobileAssessment,
    PerformanceMetrics,
    Prospect,
    ProspectSource,
    SEOAssessment,
    WebsiteAnalysis,
)
from .scrapers.base import BaseScraper, ScraperResult
from .scrapers.directories import BusinessDirectoryScraper
from .scrapers.google_maps import GoogleMapsScraper
from .scrapers.playwright_scraper import PlaywrightScraper
from .storage import ProspectStore, get_store, reset_store

__all__ = [
    "Prospect",
    "ProspectSource",
    "WebsiteAnalysis",
    "SEOAssessment",
    "PerformanceMetrics",
    "MobileAssessment",
    "DesignQuality",
    "ContentGap",
    "BaseScraper",
    "ScraperResult",
    "GoogleMapsScraper",
    "BusinessDirectoryScraper",
    "PlaywrightScraper",
    "ProspectStore",
    "get_store",
    "reset_store",
    "analyze_website",
    "compute_retention_date",
    "determine_legal_basis",
    "sanitize_for_gdpr",
    "validate_legal_basis",
]
