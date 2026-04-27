"""Prospect data storage layer with GDPR-compliant persistence.

Stores discovered prospects and their website analysis results.
Supports both in-memory (development) and database (production) backends.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from src.apivault.prospecting.gdpr import (
    compute_retention_date,
    determine_legal_basis,
    sanitize_for_gdpr,
    validate_legal_basis,
)
from src.apivault.prospecting.models import (
    Prospect,
    ProspectSource,
    WebsiteAnalysis,
)

logger = logging.getLogger(__name__)


class ProspectStore:
    """In-memory prospect store for development and testing.

    For production, use the SQLAlchemy-based repository.
    """

    def __init__(self):
        self._prospects: dict[str, Prospect] = {}
        self._analyses: dict[str, WebsiteAnalysis] = {}

    def add_prospect(self, prospect: Prospect) -> str:
        """Add a prospect to the store, applying GDPR compliance.

        Returns the prospect ID (derived from website URL or name).
        """
        # Apply GDPR compliance
        prospect.gdpr_legal_basis = determine_legal_basis(
            prospect.source.value if isinstance(prospect.source, ProspectSource)
            else prospect.source
        )
        if not validate_legal_basis(prospect.gdpr_legal_basis):
            logger.warning(
                "Invalid legal basis for prospect %s: %s",
                prospect.name, prospect.gdpr_legal_basis,
            )
            prospect.gdpr_legal_basis = "legitimate_interest"

        prospect.gdpr_data_retained_until = compute_retention_date(
            prospect.discovered_at
        )

        # Sanitize data
        if prospect.raw_data:
            prospect.raw_data = sanitize_for_gdpr(prospect.raw_data)

        # Deduplicate by website URL
        existing = self._find_duplicate(prospect)
        if existing:
            logger.debug(
                "Duplicate prospect found: %s (matches existing %s)",
                prospect.name, existing.name,
            )
            return existing.name

        self._prospects[prospect.name] = prospect
        logger.info("Added prospect: %s", prospect.name)
        return prospect.name

    def add_analysis(
        self,
        prospect_id: str,
        analysis: WebsiteAnalysis,
    ) -> None:
        """Store a website analysis for a prospect."""
        self._analyses[prospect_id] = analysis

    def get_prospect(self, prospect_id: str) -> Prospect | None:
        return self._prospects.get(prospect_id)

    def get_analysis(self, prospect_id: str) -> WebsiteAnalysis | None:
        return self._analyses.get(prospect_id)

    def list_prospects(
        self,
        status: str | None = None,
        source: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Prospect]:
        """List prospects with optional filtering."""
        prospects = list(self._prospects.values())

        if status:
            prospects = [p for p in prospects if p.analysis_status == status]
        if source:
            prospects = [
                p for p in prospects
                if (
                    p.source.value == source
                    if isinstance(p.source, ProspectSource)
                    else p.source == source
                )
            ]

        return prospects[offset:offset + limit]

    def count(self) -> int:
        return len(self._prospects)

    def delete_expired(self) -> int:
        """Delete prospects that have passed their GDPR retention date."""
        now = datetime.utcnow()
        expired = [
            pid for pid, p in self._prospects.items()
            if p.gdpr_data_retained_until
            and now > p.gdpr_data_retained_until
        ]
        for pid in expired:
            del self._prospects[pid]
            self._analyses.pop(pid, None)
        logger.info("Deleted %d expired prospects", len(expired))
        return len(expired)

    def handle_deletion_request(self, prospect_id: str) -> bool:
        """Handle a GDPR deletion request for a specific prospect."""
        if prospect_id not in self._prospects:
            return False

        prospect = self._prospects[prospect_id]
        prospect.gdpr_deletion_requested = True
        del self._prospects[prospect_id]
        self._analyses.pop(prospect_id, None)
        logger.info(
            "Deleted prospect %s per GDPR request", prospect.name
        )
        return True

    def _find_duplicate(self, prospect: Prospect) -> Prospect | None:
        """Find an existing prospect with the same website or name."""
        if prospect.website:
            for p in self._prospects.values():
                if p.website == prospect.website:
                    return p
        return None


# Global store instance
_store: ProspectStore | None = None


def get_store() -> ProspectStore:
    """Get or create the global prospect store."""
    global _store
    if _store is None:
        _store = ProspectStore()
    return _store


def reset_store() -> None:
    """Reset the global store (useful for testing)."""
    global _store
    _store = None
