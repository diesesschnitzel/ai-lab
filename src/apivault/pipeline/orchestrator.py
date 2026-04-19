"""Pipeline orchestrator: coordinates normalization and deduplication.

Pipeline flow: raw_candidates → normalize → dedup → validate → enrich

The orchestrator manages the flow of API candidates through the pipeline,
handling normalization, deduplication, and preparing records for downstream
validation and enrichment stages.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from .deduplicator import deduplicate
from .models import NormalizedApi, PipelineResult, RawCandidate
from .normalizer import normalize_candidates

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Orchestrates the API discovery pipeline.

    Usage:
        orchestrator = PipelineOrchestrator(existing_records=...)
        result = await orchestrator.run(raw_candidates)
    """

    def __init__(
        self,
        existing_records: list[NormalizedApi] | None = None,
    ) -> None:
        self.existing_records = existing_records or []
        self._run_count = 0

    async def run(self, candidates: list[RawCandidate]) -> PipelineResult:
        """Execute the full pipeline: normalize → dedup.

        Returns a PipelineResult with normalized, deduplicated, new, and merged records.
        """
        self._run_count += 1
        run_id = f"run-{self._run_count}-{datetime.now(UTC).isoformat()}"
        logger.info("Starting pipeline %s with %d candidates", run_id, len(candidates))

        result = PipelineResult()

        # Stage 1: Normalize
        try:
            normalized = self._normalize(candidates)
            result.normalized = normalized
            logger.info("Normalized %d/%d candidates", len(normalized), len(candidates))
        except Exception as e:
            result.errors.append(f"Normalization failed: {e}")
            logger.exception("Normalization stage failed")
            return result

        # Stage 2: Deduplicate
        try:
            deduplicated, new_records, merged_records = self._deduplicate(
                normalized,
                self.existing_records,
            )
            result.deduplicated = deduplicated
            result.new_records = new_records
            result.merged_records = merged_records
            result.duplicates_found = len(normalized) - len(new_records)
            logger.info(
                "Deduplication: %d new, %d merged, %d duplicates",
                len(new_records),
                len(merged_records),
                result.duplicates_found,
            )
        except Exception as e:
            result.errors.append(f"Deduplication failed: {e}")
            logger.exception("Deduplication stage failed")
            return result

        # Stage 3: Validate (placeholder - handled by validation service)
        # Stage 4: Enrich (placeholder - handled by enrichment service)

        logger.info(
            "Pipeline %s complete: %d total, %d new, %d errors",
            run_id,
            len(deduplicated),
            len(new_records),
            len(result.errors),
        )

        return result

    def _normalize(self, candidates: list[RawCandidate]) -> list[NormalizedApi]:
        """Run normalization stage."""
        return normalize_candidates(candidates)

    def _deduplicate(
        self,
        candidates: list[NormalizedApi],
        existing: list[NormalizedApi],
    ) -> tuple[list[NormalizedApi], list[NormalizedApi], list[NormalizedApi]]:
        """Run deduplication stage."""
        return deduplicate(candidates, existing)

    def add_existing_records(self, records: list[NormalizedApi]) -> None:
        """Add records to the existing set for future deduplication."""
        self.existing_records.extend(records)

    def get_stats(self) -> dict[str, Any]:
        """Get pipeline statistics."""
        return {
            "run_count": self._run_count,
            "existing_records": len(self.existing_records),
        }
