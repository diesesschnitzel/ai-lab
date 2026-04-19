"""Tests for the PipelineWorker."""

import pytest
from src.apivault.worker import PipelineWorker


class TestPipelineWorker:
    def test_worker_default_config(self):
        """Worker initializes with default configuration."""
        worker = PipelineWorker()
        assert worker.cycle_interval == 30
        assert worker.normalization_batch_size == 500
        assert worker.validation_concurrency == 50
        assert worker.enrichment_batch_size == 20

    def test_worker_custom_config(self):
        """Worker accepts custom configuration."""
        worker = PipelineWorker(
            cycle_interval=60,
            normalization_batch_size=100,
            validation_concurrency=25,
            enrichment_batch_size=10,
        )
        assert worker.cycle_interval == 60
        assert worker.normalization_batch_size == 100
        assert worker.validation_concurrency == 25
        assert worker.enrichment_batch_size == 10

    def test_worker_initial_stats(self):
        """Worker initializes with zero stats."""
        worker = PipelineWorker()
        stats = worker.get_stats()
        assert stats["cycles_completed"] == 0
        assert stats["candidates_processed"] == 0
        assert stats["apis_validated"] == 0
        assert stats["apis_enriched"] == 0
        assert stats["errors"] == 0
        assert stats["started_at"] is None

    def test_worker_stop(self):
        """Worker can be stopped."""
        worker = PipelineWorker()
        assert worker._running is False
        worker.stop()
        assert worker._running is False
