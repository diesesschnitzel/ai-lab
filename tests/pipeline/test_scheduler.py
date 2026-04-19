"""Tests for the APScheduler-based scheduler."""

import pytest
from src.apivault.scheduler import TIMEOUTS, create_scheduler


class TestScheduler:
    def test_timeouts_defined(self):
        """All jobs have timeout limits defined."""
        expected_jobs = [
            "process_raw_candidates",
            "overdue_validation",
            "tier1_scrapers",
            "enrichment_batch",
            "package_registry_scrapers",
            "github_search",
            "dead_api_retry",
            "cert_transparency",
            "government_portals",
            "full_revalidation",
            "common_crawl",
            "wayback_machine",
            "archive_health_logs",
        ]
        for job in expected_jobs:
            assert job in TIMEOUTS, f"Missing timeout for job: {job}"
            assert TIMEOUTS[job] > 0, f"Timeout for {job} must be positive"

    def test_scheduler_creates_all_jobs(self):
        """Scheduler creates all expected jobs."""
        scheduler = create_scheduler()
        jobs = scheduler.get_jobs()

        job_ids = {job.id for job in jobs}
        expected_ids = set(TIMEOUTS.keys())

        assert job_ids == expected_ids, f"Missing jobs: {expected_ids - job_ids}"

    def test_scheduler_job_count(self):
        """Scheduler has exactly 13 jobs."""
        scheduler = create_scheduler()
        assert len(scheduler.get_jobs()) == 13

    def test_scheduler_max_instances(self):
        """All jobs have max_instances=1 to prevent overlap."""
        scheduler = create_scheduler()
        for job in scheduler.get_jobs():
            assert job.max_instances == 1, f"Job {job.id} should have max_instances=1"

    def test_scheduler_job_ids_match_timeouts(self):
        """All timeout keys have corresponding jobs."""
        scheduler = create_scheduler()
        job_ids = {job.id for job in scheduler.get_jobs()}
        assert job_ids == set(TIMEOUTS.keys())
