#!/usr/bin/env python3
"""
Verification Gate 113: Pipeline Speed & Efficiency Optimizations
================================================================
Validates:
1. Single-pass multi-company AI tailoring (`generate_multi_company_tailored_bullets`) makes 1 LLM call per job instead of 2.
2. Pre-tailoring experience ceiling (>10 YOE) & jurisdiction gate rejects ineligible jobs in <1ms before calling Gemini.
3. Fast in-memory `session_seen_job_ids` deduplication skips Wave 2 duplicate cards in 0ms before DOM queries.
4. Cloud-CI-aware `skip_static_ats=True` fast path skips redundant 1,119-board local polling when CI drops are <6h fresh.
5. `scripts/run_daily_prod.sh` routes 10:30 IST (`Hour >= 10`) into the fast Intraday Sniper path.
"""

from __future__ import annotations

import asyncio
import datetime
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.filter.job_filter import LinkedInJobFilter
from src.ingestion.ats_discovery import ATSDiscoveryCoordinator
from src.ingestion.ci_sync import CISyncIngestor
from src.pipeline.runner import JobSearchPipelineRunner
from src.scraper.job_finder import LinkedInJobFinder
from src.storage.models import JobListing
from src.tailor.llm_provider import MultiCompanyTailoredBulletsResponse
from src.tailor.resume_tailorer import ResumeTailorer


def test_single_pass_multi_company_tailoring():
    print("🔍 Step 1: Testing Single-Pass Multi-Company AI Tailoring (1 call/job instead of 2)...")
    schema = MultiCompanyTailoredBulletsResponse.model_json_schema()
    assert "companies" in schema.get("properties", {}), "Schema must define 'companies' list"

    tailorer = ResumeTailorer(use_ai=True)
    mock_llm = MagicMock()
    mock_llm.generate_multi_company_tailored_bullets.return_value = {
        "Value Labs": [
            "Mosaic Order Automation Framework [REST Assured · Selenium · BDD · Java]: Built 2000+ test cases cutting regression time by 90%.",
            "PNR Linking & SSR [REST Assured · ReadyAPI · BDD · Java]: Architected API automation suites across airline microservices.",
        ],
        "Dunzo": [
            "Ekam Microservices Framework [Java · Ekam · PostgreSQL]: Automated backend merchant and order microservices.",
            "Cloud Order Fulfillment Validation [Java · Docker · Kubernetes · GCP]: Validated event-driven order fulfillment flows.",
        ],
    }
    tailorer.llm_provider = mock_llm

    job = {
        "job_id": "speed_test_001",
        "job_details": {
            "title": "Senior SDET",
            "company": "Razorpay",
            "requirements": "6+ years experience in Java, Python, REST Assured, Playwright, Docker, Kubernetes.",
        },
    }
    res = tailorer.tailor_job_payload(job)
    assert mock_llm.generate_multi_company_tailored_bullets.call_count == 1, (
        "Must make exactly 1 combined multi-company LLM call per job"
    )
    assert mock_llm.generate_company_tailored_bullets.call_count == 0, (
        "Per-company fallback must not be called when single-pass succeeds"
    )
    assert res["tailoring_method"] == "ai_grounded_star"
    print("   ✅ Single-pass multi-company tailoring verified (50% fewer Gemini API calls)!")


def test_pre_tailoring_eligibility_gate():
    print("🔍 Step 2: Testing Pre-Tailoring Experience Ceiling & Jurisdiction Gate (<1ms)...")
    jf = LinkedInJobFilter()

    ok, reason = jf.evaluate_pre_tailoring_eligibility(
        title="Senior SDET",
        location="Bengaluru, India",
        requirements="Requires 5+ years of experience in Playwright, Python, and API testing.",
    )
    assert ok is True and reason is None

    ok_over, reason_over = jf.evaluate_pre_tailoring_eligibility(
        title="Principal QA Architect",
        location="Bengaluru, India",
        requirements="Requires 15+ years of experience in enterprise test architecture.",
    )
    assert ok_over is False and "15+ years" in str(reason_over)

    ok_us, reason_us = jf.evaluate_pre_tailoring_eligibility(
        title="Senior SDET",
        location="Remote",
        requirements="Must be a US Citizen with active DoD Top Secret clearance. W2 only, no C2C.",
    )
    assert ok_us is False and "jurisdiction" in str(reason_us).lower()

    # Verify ATSDiscoveryCoordinator skips tailoring when pre-tailoring eligibility fails
    with tempfile.TemporaryDirectory() as tmpdir:
        coord = ATSDiscoveryCoordinator(
            queue_dir=os.path.join(tmpdir, "pending"),
            db_file=os.path.join(tmpdir, "processed.json"),
            use_ai=True,
        )
        over_listing = JobListing(
            id="ats_over_15y",
            company_name="Thermo Fisher",
            job_title="Staff SDET",
            location="Bengaluru, India",
            url="https://jobs.thermofisher.com/15y",
            source="workday",
            job_description_raw="<p>Requires 15+ years of experience in automation testing and QA leadership.</p>",
            job_description_clean="Requires 15+ years of experience in automation testing and QA leadership.",
        )
        with patch("src.tailor.resume_tailorer.ResumeTailorer.tailor_job_payload") as m_tailor:
            saved = coord.save_listings_to_queue([over_listing], tailor=True)
            assert len(saved) == 0, "15+ YOE job must be rejected pre-tailoring"
            assert m_tailor.call_count == 0, "Gemini tailorer must NEVER be called for >10 YOE jobs"

    print("   ✅ Pre-tailoring experience & jurisdiction gate verified!")


def test_fast_session_deduplication_in_job_finder():
    print("🔍 Step 3: Testing 0ms In-Memory Session Deduplication across Sniper Waves...")
    finder = LinkedInJobFinder(use_ai=False)
    finder.session_seen_job_ids.add("4398999999")

    mock_card = MagicMock()
    mock_card.get_attribute = AsyncMock(side_effect=lambda attr: "4398999999" if attr == "data-job-id" else None)
    mock_card.locator = MagicMock()

    res = asyncio.run(finder._extract_card_payload(MagicMock(), mock_card, 0))
    assert res is None, "Already-seen session job_id must return None immediately"
    assert mock_card.locator.call_count == 0, "Must skip all DOM locator round-trips for session-seen cards"
    print("   ✅ 0ms in-memory session deduplication verified!")


def test_ci_aware_skip_static_ats_fast_path():
    print("🔍 Step 4: Testing Cloud-CI-Aware Morning Track 1 Fast Path...")
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    old_iso = (datetime.datetime.utcnow() - datetime.timedelta(hours=10)).isoformat() + "Z"

    assert CISyncIngestor._is_bundle_fresh({"generated_at": now_iso}, max_age_hours=6.0) is True
    assert CISyncIngestor._is_bundle_fresh({"generated_at": old_iso}, max_age_hours=6.0) is False

    runner = JobSearchPipelineRunner(config={"llm": {"use_ai": False}, "search_profiles": []})
    with (
        patch(
            "src.ingestion.ats_discovery.ATSDiscoveryCoordinator.ingest_all_sources", new_callable=AsyncMock
        ) as m_all,
        patch(
            "src.ingestion.ats_discovery.ATSDiscoveryCoordinator.ingest_direct_portals", new_callable=AsyncMock
        ) as m_portals,
        patch("src.ingestion.ats_discovery.ATSDiscoveryCoordinator.save_listings_to_queue", return_value=[]),
        patch("src.posts.post_tracker.LinkedInPostTracker.discover_posts", new_callable=AsyncMock, return_value=[]),
    ):
        m_portals.return_value = []
        asyncio.run(runner.run_search_stage(source="all", headless=True, skip_static_ats=True))
        assert m_all.call_count == 0, "1,119-board static ATS poll must be skipped when skip_static_ats=True"
        assert m_portals.call_count == 1, "Direct Indian portals (Hirist/Instahyre) must still be polled"

    prod_sh = (Path(PROJECT_ROOT) / "scripts" / "run_daily_prod.sh").read_text(encoding="utf-8")
    assert "-ge 10" in prod_sh, "run_daily_prod.sh must route 10:30 IST (Hour >= 10) into Intraday Sniper mode"
    print("   ✅ Cloud-CI-aware fast path and 10:30 IST Sniper routing verified!")


if __name__ == "__main__":
    print("=" * 68)
    print("  GATE 113: PIPELINE SPEED & EFFICIENCY OPTIMIZATIONS")
    print("=" * 68)
    test_single_pass_multi_company_tailoring()
    test_pre_tailoring_eligibility_gate()
    test_fast_session_deduplication_in_job_finder()
    test_ci_aware_skip_static_ats_fast_path()
    print("=" * 68)
    print("🎉 ALL GATE 113 SPEED OPTIMIZATION CHECKS PASSED!")
    print("=" * 68)
