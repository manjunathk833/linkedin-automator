#!/usr/bin/env python3
"""
Verification Gate 77: Comprehensive Daily Pipeline All-Capability Wiring Test
============================================================================
Verifies:
1. Full capability orchestration in DailyPipelineRunner (Health Check -> Knowledge Sync ->
   Track 1 ATS + Track 2 LinkedIn + Track 3 Social Posts -> Filter -> Naukri Refresh -> Email -> Dashboard).
2. Upfront Dream Org resolution in LinkedInJobFinder card extraction.
3. Track 3 Social Hiring Posts integration into JobSearchPipelineRunner.run_search_stage.
4. Non-blocking fault tolerance: Naukri refresh failure or auth prompt does not crash daily pipeline.
5. EmailReporter HTML structure generates Social Leads section, Naukri status badge, and KPI metrics.
6. Naukri pinger headless mode fails fast on unauthenticated session without blocking.
"""

from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.notifier.email_reporter import EmailReporter
from src.pipeline.daily_runner import DailyPipelineRunner
from src.pipeline.runner import JobSearchPipelineRunner
from src.scraper.job_finder import LinkedInJobFinder


def test_daily_runner_wiring_architecture():
    """Step 1: Asserts that DailyPipelineRunner contains all required lifecycle methods."""
    print("Testing DailyPipelineRunner architecture and method wiring...")
    runner = DailyPipelineRunner(config={"llm": {"use_ai": False}})

    assert hasattr(runner, "run_health_checks"), "Must have run_health_checks"
    assert hasattr(runner, "run_naukri_refresh"), "Must have run_naukri_refresh"
    assert hasattr(runner, "ensure_dashboard_running"), "Must have ensure_dashboard_running"
    assert hasattr(runner, "execute_daily_run"), "Must have execute_daily_run"
    assert hasattr(runner.pipeline_runner, "run_sync_stage"), "Pipeline runner must have run_sync_stage"
    assert hasattr(runner.pipeline_runner, "run_search_stage"), "Pipeline runner must have run_search_stage"
    print("  ✓ DailyPipelineRunner method architecture verified")


def test_track3_wired_in_pipeline_runner():
    """Step 2: Asserts that JobSearchPipelineRunner wires Track 3 Posts discovery."""
    print("Testing Track 3 Posts discovery wiring in JobSearchPipelineRunner...")
    pipeline = JobSearchPipelineRunner(config={"llm": {"use_ai": False}, "search_profiles": []})
    assert hasattr(pipeline, "last_posts_discovered"), "Pipeline runner must maintain last_posts_discovered attribute"

    # Mock ATS and LinkedIn discovery, mock Track 3 posts tracker
    mock_posts = [
        {
            "post_id": "post_mock_1",
            "author_name": "Satya Nadella",
            "company_name": "Microsoft",
            "is_dream_org": True,
            "quality_score": 90,
            "outreach_status": "NEW",
            "extracted_emails": ["recruiter@microsoft.com"],
            "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:123456789/",
        }
    ]

    with (
        patch(
            "src.ingestion.ats_discovery.ATSDiscoveryCoordinator.ingest_all_sources", new_callable=AsyncMock
        ) as m_ats,
        patch("src.ingestion.ats_discovery.ATSDiscoveryCoordinator.save_listings_to_queue", return_value=["p1.json"]),
        patch("src.posts.post_tracker.LinkedInPostTracker.discover_posts", new_callable=AsyncMock) as m_posts,
    ):
        m_ats.return_value = []
        m_posts.return_value = mock_posts

        asyncio.run(pipeline.run_search_stage(source="all", headless=True))

        assert m_posts.called, "LinkedInPostTracker.discover_posts must be called when source='all'"
        assert len(pipeline.last_posts_discovered) == 1, "last_posts_discovered must capture Track 3 leads"
        assert pipeline.last_posts_discovered[0]["company_name"] == "Microsoft"

    print("  ✓ Track 3 Social Posts discovery wiring verified")


def test_linkedin_upfront_dream_org_resolution():
    """Step 3: Asserts that LinkedIn card extraction resolves is_dream_org upfront."""
    print("Testing upfront is_dream_org resolution in LinkedInJobFinder...")
    finder = LinkedInJobFinder(use_ai=False)

    with patch("src.storage.database.ApplicationDatabase.is_dream_company") as m_dream:

        def mock_is_dream(*args, **kwargs):
            comp = args[-1] if args else kwargs.get("company_name_or_slug", "")
            return str(comp).lower() in ("snowflake", "databricks", "postman")

        m_dream.side_effect = mock_is_dream

        # Mock page and card
        mock_card = MagicMock()
        mock_card.get_attribute = AsyncMock(side_effect=lambda attr: "123456" if attr == "data-job-id" else None)
        mock_card.is_visible = AsyncMock(return_value=False)

        # Mock title
        m_title = MagicMock()
        m_title.count = AsyncMock(return_value=1)
        m_title.text_content = AsyncMock(return_value="Senior SDET")
        m_title.first = m_title

        # Mock company
        m_comp = MagicMock()
        m_comp.count = AsyncMock(return_value=1)
        m_comp.text_content = AsyncMock(return_value="Snowflake")
        m_comp.first = m_comp

        # Mock loc
        m_loc = MagicMock()
        m_loc.count = AsyncMock(return_value=1)
        m_loc.text_content = AsyncMock(return_value="Bengaluru, India")
        m_loc.first = m_loc

        def locator_router(selector):
            if "company" in selector or "primary-description" in selector:
                return m_comp
            elif "title" in selector and "subtitle" not in selector:
                return m_title
            elif "metadata" in selector or "caption" in selector:
                return m_loc
            mock_gen = MagicMock()
            mock_gen.count = AsyncMock(return_value=0)
            mock_gen.first = mock_gen
            return mock_gen

        mock_card.locator = MagicMock(side_effect=locator_router)

        with (
            patch.object(finder, "is_duplicate", return_value=False),
            patch.object(finder, "save_job_to_queue", return_value="dummy.json"),
            patch.object(finder, "mark_job_processed"),
        ):
            mock_page = MagicMock()
            mock_page.locator = MagicMock(side_effect=locator_router)
            res = asyncio.run(finder._extract_card_payload(mock_page, mock_card, 0))

            assert res is not None, "Extracted payload must not be None"
            assert res.get("is_dream_org") is True, "Snowflake must be classified as Dream Org upfront"
            assert res.get("job_details", {}).get("is_dream_org") is True, "job_details must include is_dream_org"

    print("  ✓ Upfront is_dream_org resolution in LinkedIn card extraction verified")


def test_email_reporter_all_capabilities_rendering():
    """Step 4: Asserts that EmailReporter renders Staged Jobs, Social Leads, and Naukri status."""
    print("Testing EmailReporter HTML generation across all tracks...")
    reporter = EmailReporter(sender_email="test@gmail.com", app_password="dummy", recipient_email="test@gmail.com")

    staged_jobs = [
        {
            "job_id": "job_101",
            "source": "greenhouse",
            "is_dream_org": True,
            "job_details": {
                "title": "Lead SDET",
                "company": "Databricks",
                "location": "Bengaluru",
                "job_url": "https://databricks.com/jobs/101",
            },
        }
    ]

    hiring_posts = [
        {
            "post_id": "post_201",
            "author_name": "Priya Sharma",
            "author_role_category": "LEAD",
            "company_name": "Razorpay",
            "is_dream_org": True,
            "quality_score": 88,
            "extracted_emails": ["priya@razorpay.com"],
            "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:999/",
        }
    ]

    naukri_status = {"status": "SUCCESS", "message": "Profile touched"}

    html = reporter.build_report_html(
        staged_jobs=staged_jobs,
        regression_passed=True,
        regression_summary="55/55 Passed (100%)",
        execution_duration_sec=15.2,
        hiring_posts=hiring_posts,
        naukri_status=naukri_status,
    )

    assert "Naukri Resdex: Refreshed ✅" in html, "Report must include Naukri refresh success badge"
    assert "Databricks" in html, "Report must render staged ATS jobs"
    assert "Inbound Social Hiring Posts & Leads (Track 3)" in html, "Report must contain Track 3 section"
    assert "Priya Sharma" in html, "Report must render social post author"
    assert "mailto:priya@razorpay.com" in html, "Report must provide 1-click email mailto link"
    assert "Social Leads" in html, "Report must render Social Leads KPI box"

    print("  ✓ EmailReporter comprehensive rendering verified")


def test_naukri_headless_fail_fast():
    """Step 5: Asserts that Naukri pinger in headless mode does not stall on unauthenticated session."""
    print("Testing Naukri pinger headless fail-fast auth handling...")
    from scripts.naukri_pinger import run_naukri_pinger

    # Mock Playwright to simulate unauthenticated page
    with patch("scripts.naukri_pinger.async_playwright") as m_pw:
        mock_ctx = AsyncMock()
        mock_page = AsyncMock()
        mock_page.url = "https://www.naukri.com/nlogin/login"
        mock_ctx.pages = [mock_page]
        mock_ctx.close = AsyncMock()

        m_p_inst = MagicMock()
        m_p_inst.chromium.launch_persistent_context = AsyncMock(return_value=mock_ctx)
        m_pw.return_value.__aenter__.return_value = m_p_inst

        with patch("scripts.naukri_pinger.check_naukri_login", new_callable=AsyncMock) as m_chk:
            m_chk.return_value = False

            res = asyncio.run(run_naukri_pinger(headless=True, dry_run=False))
            assert res.get("status") == "AUTH_REQUIRED", "Headless unauthenticated run must return AUTH_REQUIRED"
            assert mock_ctx.close.called, "Browser context must be closed cleanly"

    print("  ✓ Naukri pinger headless fail-fast behavior verified")


def test_daily_runner_fault_isolation():
    """Step 6: Asserts that Naukri failure or warnings do not crash daily execution."""
    print("Testing DailyPipelineRunner non-blocking fault isolation...")
    runner = DailyPipelineRunner(config={"llm": {"use_ai": False}})

    with (
        patch.object(runner, "run_health_checks", return_value=(True, "55/55 Passed")),
        patch.object(runner.pipeline_runner, "run_sync_stage", return_value={"added": 1}),
        patch.object(runner.pipeline_runner, "run_search_stage", new_callable=AsyncMock),
        patch.object(runner.pipeline_runner, "run_filter_stage"),
        patch.object(runner, "get_staged_jobs", return_value=[]),
        patch.object(runner, "run_naukri_refresh", new_callable=AsyncMock) as m_naukri,
        patch.object(runner.reporter, "send_report", return_value=True),
        patch.object(runner, "ensure_dashboard_running", return_value=True),
    ):
        # Simulate Naukri requiring authentication
        m_naukri.return_value = {"status": "AUTH_REQUIRED", "message": "Login required"}
        runner.pipeline_runner.last_posts_discovered = []

        res = asyncio.run(
            runner.execute_daily_run(
                headless=True,
                send_email=True,
                skip_tests=False,
                launch_dashboard=True,
            )
        )

        assert res.get("status") == "SUCCESS", "Daily run must report SUCCESS even if Naukri requires auth"
        assert res.get("naukri_status") == "AUTH_REQUIRED", "Naukri status must be accurately tracked"

    print("  ✓ DailyPipelineRunner fault isolation verified")


if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("  RUNNING VERIFICATION GATE 77: DAILY RUN COMPREHENSIVE WIRING")
    print("=" * 65 + "\n")

    test_daily_runner_wiring_architecture()
    test_track3_wired_in_pipeline_runner()
    test_linkedin_upfront_dream_org_resolution()
    test_email_reporter_all_capabilities_rendering()
    test_naukri_headless_fail_fast()
    test_daily_runner_fault_isolation()

    print("\n" + "=" * 65)
    print("🎉 VERIFICATION GATE 77 PASSED (6/6 TESTS SUCCESSFUL)!")
    print("=" * 65 + "\n")
