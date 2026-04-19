"""Tests for the pipeline orchestrator."""

import pytest
from src.apivault.pipeline.models import RawCandidate
from src.apivault.pipeline.orchestrator import PipelineOrchestrator


class TestPipelineOrchestrator:
    @pytest.mark.asyncio
    async def test_run_empty_candidates(self):
        orchestrator = PipelineOrchestrator()
        result = await orchestrator.run([])
        assert len(result.normalized) == 0
        assert len(result.deduplicated) == 0
        assert len(result.new_records) == 0
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_run_single_candidate(self):
        orchestrator = PipelineOrchestrator()
        candidates = [
            RawCandidate(
                name="Test API",
                url="https://api.example.com/v1",
                source="test",
            )
        ]
        result = await orchestrator.run(candidates)
        assert len(result.normalized) == 1
        assert len(result.new_records) == 1
        assert result.duplicates_found == 0

    @pytest.mark.asyncio
    async def test_run_detects_duplicate(self):
        existing = []
        orchestrator = PipelineOrchestrator(existing_records=existing)

        candidates = [
            RawCandidate(
                name="API v1",
                url="https://api.example.com/v1",
                source="test",
            ),
            RawCandidate(
                name="API v1 copy",
                url="https://api.example.com/v1",
                source="test-2",
            ),
        ]
        result = await orchestrator.run(candidates)
        assert result.duplicates_found >= 1

    @pytest.mark.asyncio
    async def test_run_with_existing_records(self):
        from src.apivault.pipeline.models import NormalizedApi

        existing = [
            NormalizedApi(
                name="Existing API",
                base_url="https://api.example.com",
                canonical_domain="api.example.com",
                url_fingerprint="existing-fp",
            )
        ]
        orchestrator = PipelineOrchestrator(existing_records=existing)

        candidates = [
            RawCandidate(
                name="New API",
                url="https://api.new.com/v1",
                source="test",
            )
        ]
        result = await orchestrator.run(candidates)
        assert len(result.new_records) == 1

    @pytest.mark.asyncio
    async def test_run_skips_invalid(self):
        orchestrator = PipelineOrchestrator()
        candidates = [
            RawCandidate(name="Valid", url="https://api.example.com/v1", source="test"),
            RawCandidate(name="Invalid", url="not-a-url", source="test"),
        ]
        result = await orchestrator.run(candidates)
        assert len(result.normalized) == 1
        assert len(result.errors) == 0

    def test_add_existing_records(self):
        from src.apivault.pipeline.models import NormalizedApi

        orchestrator = PipelineOrchestrator()
        new_record = NormalizedApi(
            name="New",
            base_url="https://new.com",
            canonical_domain="new.com",
        )
        orchestrator.add_existing_records([new_record])
        assert len(orchestrator.existing_records) == 1

    def test_get_stats(self):
        orchestrator = PipelineOrchestrator()
        stats = orchestrator.get_stats()
        assert "run_count" in stats
        assert "existing_records" in stats
        assert stats["run_count"] == 0
