"""GDPR compliance helpers for the prospecting pipeline.

Handles legal basis tracking, data retention, and deletion requests
to ensure the prospecting pipeline is GDPR-compliant.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Default retention periods (can be overridden per company)
DEFAULT_RETENTION_DAYS = 365  # 1 year for prospect data


def compute_retention_date(
    discovered_at: datetime,
    retention_days: int = DEFAULT_RETENTION_DAYS,
) -> datetime:
    """Compute the date by which prospect data must be deleted."""
    return discovered_at + timedelta(days=retention_days)


def validate_legal_basis(basis: str | None) -> bool:
    """Validate that a GDPR legal basis is recognized.

    Valid bases under Article 6:
    - consent
    - contract
    - legal_obligation
    - vital_interests
    - public_task
    - legitimate_interest
    """
    valid_bases = {
        "consent",
        "contract",
        "legal_obligation",
        "vital_interests",
        "public_task",
        "legitimate_interest",
    }
    return basis in valid_bases


def determine_legal_basis(
    source: str,
    has_consent: bool = False,
) -> str:
    """Determine the appropriate legal basis for processing prospect data.

    For B2B prospecting, "legitimate_interest" is typically used when:
    - The data is publicly available (business directories, Google Maps)
    - The processing is relevant to the prospect's business
    - The prospect has a reasonable expectation of being contacted
    """
    if has_consent:
        return "consent"

    # Public business data generally qualifies as legitimate interest
    public_sources = {
        "google_maps", "yelp", "yellow_pages", "thomson_local",
        "europages", "industry_directory", "chamber_of_commerce",
    }

    if source in public_sources:
        return "legitimate_interest"

    return "legitimate_interest"  # Default for B2B prospecting


def sanitize_for_gdpr(data: dict[str, Any]) -> dict[str, Any]:
    """Remove or mask fields that should not be stored without consent.

    This ensures we only store data that falls under our legal basis.
    """
    # Fields that are fine to store under legitimate interest (B2B)
    allowed_fields = {
        # Business identity
        "name", "company_name", "website", "phone", "email",
        "address", "city", "postal_code", "country",
        # Classification
        "industry", "category", "description", "tags",
        # Metadata
        "source", "source_url", "discovered_at", "raw_data",
        # Pipeline state
        "analysis_status", "analysis_completed_at",
    }

    # Fields that must be removed or require explicit consent
    sensitive_fields = {
        "personal_notes", "employee_data", "social_security",
        "tax_id", "bank_details", "payment_info",
    }

    sanitized = {}
    for key, value in data.items():
        if key in sensitive_fields:
            logger.debug("Stripping sensitive field: %s", key)
            continue
        if key in allowed_fields:
            sanitized[key] = value

    return sanitized


def is_data_expired(retention_date: datetime | None) -> bool:
    """Check if stored data has passed its retention deadline."""
    if retention_date is None:
        return True
    return datetime.utcnow() > retention_date


def build_deletion_filter(
    issue_ids: list[str] | None = None,
    expired_only: bool = False,
) -> dict[str, Any]:
    """Build a filter for identifying records to delete.

    Used by the storage layer to bulk-delete expired or requested records.
    """
    filter_conditions: dict[str, Any] = {}

    if expired_only:
        filter_conditions["gdpr_data_retained_until__lt"] = datetime.utcnow()

    if issue_ids:
        filter_conditions["id__in"] = issue_ids

    return filter_conditions
