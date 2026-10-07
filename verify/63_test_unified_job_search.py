"""
Verification Gate 63: Unified Job Search & Cross-Source Applied Reseed Defense.
Tests:
1. SQLite cross-source company+role deduplication and composite hashes.
2. ATSDiscoveryCoordinator pre-ingestion duplicate and applied reseed guard.
3. Cross-platform duplicate prevention between Greenhouse/Lever/Ashby and LinkedIn.
4. LinkedInJobFilter retention of external and ATS jobs when easy_apply_only is false.
5. JobSearchPipelineRunner unified discovery orchestration across sources.
6. FastAPI POST /api/discovery/run endpoint response structure.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient

from src.filter.job_filter import LinkedInJobFilter
from src.ingestion.ats_discovery import ATSDiscoveryCoordinator
from src.pipeline.runner import JobSearchPipelineRunner
from src.scraper.job_finder import LinkedInJobFinder
from src.storage.database import ApplicationDatabase
from src.storage.models import JobListing
from src.ui.app import app


def test_sqlite_cross_source_checks():
    print("\n--- STEP 1: SQLite Cross-Source Company+Role Defense ---")
    db = ApplicationDatabase()
    test_id = f"greenhouse_stripe_test_{int(time.time())}"
    test_company = "Stripe"
    test_title = "Senior SDET Architect"

    try:
        # Before recording
        assert not db.is_job_applied(test_id)
        assert not db.is_company_role_applied(test_company, test_title)

        # Record application
        db.record_application(
            job_id=test_id,
            source="greenhouse",
            company_name=test_company,
            job_title=test_title,
            job_url="https://boards.greenhouse.io/stripe/jobs/123",
            status="applied",
        )

        # Exact ID check
        assert db.is_job_applied(test_id) is True, "Exact job_id check failed"

        # Case-insensitive and whitespace-trimmed check
        assert db.is_company_role_applied("Stripe", "Senior SDET Architect") is True
        assert db.is_company_role_applied(" stripe ", " senior sdet architect ") is True
        assert db.is_company_role_applied("STRIPE", "SENIOR SDET ARCHITECT") is True

        # Negative check
        assert db.is_company_role_applied("Stripe", "Staff Backend Engineer") is False
        assert db.is_company_role_applied("Google", "Senior SDET Architect") is False

        # Composite hash set
        hashes = db.get_applied_composite_hashes()
        db.get_applied_composite_hashes()
        assert len(hashes) > 0, "Composite hashes set should not be empty"

        print("✓ SQLite cross-source normalized checks and composite hashes verified.")
    finally:
        db.delete_application(test_id)


def test_ats_coordinator_deduplication_and_reseed_guard():
    print("\n--- STEP 2: ATS Pre-Ingestion Deduplication & Reseed Guard ---")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_queue = os.path.join(tmp_dir, "pending_queue")
        tmp_db = os.path.join(tmp_dir, "processed_jobs.json")

        coordinator = ATSDiscoveryCoordinator(
            queue_dir=tmp_queue,
            db_file=tmp_db,
            use_ai=False,
        )

        listing1 = JobListing(
            id="greenhouse_figma_101",
            source="greenhouse",
            company_name="Figma",
            job_title="Senior QA Engineer",
            location="Remote",
            job_description_raw="<p>Python Playwright automation</p>",
            job_description_clean="Python Playwright automation",
            url="https://boards.greenhouse.io/figma/jobs/101",
        )
        listing2 = JobListing(
            id="lever_datadog_202",
            source="lever",
            company_name="Datadog",
            job_title="Lead SDET",
            location="Bengaluru",
            job_description_raw="<p>API test frameworks and performance</p>",
            job_description_clean="API test frameworks and performance",
            url="https://jobs.lever.co/datadog/202",
        )

        # 1. Initial save of 2 fresh jobs
        saved = coordinator.save_listings_to_queue([listing1, listing2], tailor=False)
        assert len(saved) == 2, f"Expected 2 saved jobs, got {len(saved)}"
        assert os.path.exists(os.path.join(tmp_queue, "greenhouse_figma_101.json"))
        assert os.path.exists(os.path.join(tmp_queue, "lever_datadog_202.json"))

        # 2. Saving the exact same listings again should be detected as duplicates
        saved_again = coordinator.save_listings_to_queue([listing1, listing2], tailor=False)
        assert len(saved_again) == 0, "Duplicate ATS jobs should not be re-saved!"

        # 3. Simulate DB applied status for a third job
        db = ApplicationDatabase()
        applied_ats_id = f"ashby_notion_303_{int(time.time())}"
        db.record_application(
            job_id=applied_ats_id,
            source="ashby",
            company_name="Notion",
            job_title="Senior SDET",
            job_url="https://jobs.ashbyhq.com/notion/303",
            status="applied",
        )

        try:
            listing3 = JobListing(
                id=applied_ats_id,
                source="ashby",
                company_name="Notion",
                job_title="Senior SDET",
                location="Bengaluru",
                job_description_raw="<p>Test infra</p>",
                job_description_clean="Test infra",
                url="https://jobs.ashbyhq.com/notion/303",
            )
            saved_applied = coordinator.save_listings_to_queue([listing3], tailor=False)
            assert len(saved_applied) == 0, "Already applied ATS job must NOT be queued!"
            print("✓ ATS pre-ingestion deduplication and applied reseed guard verified.")
        finally:
            db.delete_application(applied_ats_id)


def test_cross_platform_deduplication():
    print("\n--- STEP 3: Cross-Platform Deduplication (ATS <-> LinkedIn) ---")
    db = ApplicationDatabase()
    cross_id = f"ats_coinbase_404_{int(time.time())}"
    company = "Coinbase"
    title = "Senior SDET Automation"

    # Record application under ATS ID
    db.record_application(
        job_id=cross_id,
        source="greenhouse",
        company_name=company,
        job_title=title,
        job_url="https://boards.greenhouse.io/coinbase/jobs/404",
        status="applied",
    )

    try:
        finder = LinkedInJobFinder()
        # LinkedIn finds the same role, but with an entirely different LinkedIn numeric ID
        linkedin_job_id = "9988776655"

        # Assert LinkedIn recognizes it is duplicate via is_company_role_applied
        is_dup = finder.is_duplicate(job_id=linkedin_job_id, company=company, title=title)
        assert is_dup is True, "LinkedInJobFinder should detect cross-platform duplicate by company+title!"
        print("✓ Cross-platform deduplication between Greenhouse and LinkedIn verified.")
    finally:
        db.delete_application(cross_id)


def test_job_filter_external_and_ats_retention():
    print("\n--- STEP 4: JobFilter Multi-Source Retention Engine ---")
    with tempfile.TemporaryDirectory() as tmp_queue:
        # Create 5 diverse multi-source jobs
        sources_payloads = [
            ("easy_apply_1", "EASY_APPLY", "Senior SDET", "Acme Corp"),
            ("linkedin_ext_2", "LINKEDIN_EXTERNAL", "Senior QA Automation Engineer", "Beta Tech"),
            ("ats_gh_3", "ATS_GREENHOUSE", "Test Automation Lead", "Gamma Soft"),
            ("ats_lev_4", "ATS_LEVER", "Senior Software Engineer in Test", "Delta AI"),
            ("ats_ash_5", "ATS_ASHBY", "Staff SDET", "Epsilon Systems"),
        ]

        for jid, app_type, title, company in sources_payloads:
            payload = {
                "job_id": jid,
                "application_type": app_type,
                "job_details": {
                    "title": title,
                    "company": company,
                    "requirements": "Looking for 5+ years experience in automation testing.",
                },
            }
            with open(os.path.join(tmp_queue, f"{jid}.json"), "w", encoding="utf-8") as f:
                json.dump(payload, f)

        # Test with easy_apply_only = False (Unified default)
        filter_unified = LinkedInJobFilter(queue_dir=tmp_queue, easy_apply_only=False)
        res_unified = filter_unified.filter_pending_queue()
        assert res_unified["retained"] == 5, f"Expected 5 retained jobs, got {res_unified['retained']}"
        assert res_unified["filtered"] == 0, f"Expected 0 filtered jobs, got {res_unified['filtered']}"

        # Test with easy_apply_only = True
        filter_easy_only = LinkedInJobFilter(queue_dir=tmp_queue, easy_apply_only=True)
        res_easy_only = filter_easy_only.filter_pending_queue()
        assert res_easy_only["retained"] == 1, "Only EASY_APPLY job should be retained when easy_apply_only=True"
        assert res_easy_only["filtered"] == 4, "Non-easy apply jobs should be filtered out"
        print("✓ LinkedInJobFilter retains external and ATS sources when easy_apply_only=False.")


def test_unified_runner_orchestration():
    print("\n--- STEP 5: Unified Runner Orchestration ---")
    config = {
        "search_profiles": [{"keywords": "Senior SDET", "location": "Bengaluru", "max_jobs": 5}],
        "discovery": {"easy_apply_only": False},
        "llm": {"use_ai": False},
    }
    runner = JobSearchPipelineRunner(config)

    with (
        patch.object(ATSDiscoveryCoordinator, "ingest_all_sources", new_callable=AsyncMock) as mock_ats_ingest,
        patch.object(
            ATSDiscoveryCoordinator, "save_listings_to_queue", return_value=["path1", "path2"]
        ) as mock_ats_save,
        patch.object(
            LinkedInJobFinder, "search_all_channels", new_callable=AsyncMock, return_value=[{"job_id": "li_1"}]
        ) as mock_li_search,
    ):
        import asyncio

        # Case A: source = "all"
        asyncio.run(runner.run_search_stage(source="all"))
        assert mock_ats_ingest.called, "Track 1 (ATS) must be called for source='all'"
        assert mock_ats_save.called, "Track 1 save must be called for source='all'"
        assert mock_li_search.called, "Track 2 (LinkedIn) must be called for source='all'"

        # Reset mocks
        mock_ats_ingest.reset_mock()
        mock_li_search.reset_mock()

        # Case B: source = "ats"
        asyncio.run(runner.run_search_stage(source="ats"))
        assert mock_ats_ingest.called, "Track 1 (ATS) must be called for source='ats'"
        assert not mock_li_search.called, "Track 2 (LinkedIn) must NOT be called for source='ats'"

        # Reset mocks
        mock_ats_ingest.reset_mock()
        mock_li_search.reset_mock()

        # Case C: source = "linkedin"
        asyncio.run(runner.run_search_stage(source="linkedin"))
        assert not mock_ats_ingest.called, "Track 1 (ATS) must NOT be called for source='linkedin'"
        assert mock_li_search.called, "Track 2 (LinkedIn) must be called for source='linkedin'"

        print("✓ JobSearchPipelineRunner successfully routes all/ats/linkedin source targets.")


def test_api_discovery_endpoint():
    print("\n--- STEP 6: FastAPI POST /api/discovery/run Endpoint ---")
    client = TestClient(app)

    with (
        patch.object(JobSearchPipelineRunner, "run_search_stage", new_callable=AsyncMock),
        patch.object(JobSearchPipelineRunner, "run_filter_stage"),
    ):
        response = client.post("/api/discovery/run?source=all")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["started", "success"]
        assert data["source"] == "all"
        print("✓ POST /api/discovery/run endpoint response verified.")


def main():
    print("=" * 65)
    print("RUNNING VERIFICATION GATE 63: UNIFIED JOB SEARCH & RESEED DEFENSE")
    print("=" * 65)

    test_sqlite_cross_source_checks()
    test_ats_coordinator_deduplication_and_reseed_guard()
    test_cross_platform_deduplication()
    test_job_filter_external_and_ats_retention()
    test_unified_runner_orchestration()
    test_api_discovery_endpoint()

    print("\n" + "=" * 65)
    print("🎉 ALL VERIFICATION GATE 63 CHECKS PASSED (100% SUCCESS)")
    print("=" * 65)


if __name__ == "__main__":
    main()
