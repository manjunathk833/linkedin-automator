#!/usr/bin/env python3
"""
Gate 112: Verification of:
1. EmailReporter .env sanitization (protecting against concatenated KEY=VALUE lines) & LinkedInJobFinder tab recovery.
2. PortalSniperEngine & CISyncIngestor <24h Re-Opened Requisition re-staging (bypassing stale ledger entries when updated <24h).
3. Reposted Applied Jobs (30-day reapply eligibility vs TIER_0_REPOST_FOLLOWUP <300-char Recruiter follow-up note & direct ATS portal bypass).
4. Early-Applicant (<25 applicants) metrics, Pre-Click Foreign Location Gate, and <3h Ultra-Fresh Sniper Wave.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ingestion.ci_sync import CISyncIngestor
from src.ingestion.filters import (
    extract_linkedin_applicant_metrics,
    is_india_or_remote_location,
    is_linkedin_posting_fresh_and_unsaturated,
)
from src.ingestion.portal_sniper import PortalSniperEngine
from src.notifier.email_reporter import EmailReporter, _sanitize_app_password, _sanitize_email_address
from src.scraper.job_finder import LinkedInJobFinder
from src.storage.database import ApplicationDatabase
from src.storage.models import JobListing
from src.tailor.referral_generator import (
    InterviewRouter,
    resolve_direct_ats_portal_url,
)


def test_email_reporter_sanitization_and_tab_recovery() -> None:
    print("🧪 1. Testing EmailReporter .env sanitization & closed-tab recovery...")
    corrupted_recipient = "manjunathhk833@gmail.comWORKDAY_DEFAULT_PASSWORD=SyntheticTestVal123!"
    clean_addr = _sanitize_email_address(corrupted_recipient)
    assert clean_addr == "manjunathhk833@gmail.com", f"Expected clean email, got: {clean_addr}"

    quoted_pw = '"abcd efgh ijkl mnop"'
    clean_pw = _sanitize_app_password(quoted_pw)
    assert clean_pw == "abcd efgh ijkl mnop", f"Expected unquoted password, got: {clean_pw}"

    reporter = EmailReporter(
        sender_email="manjunathhk833@gmail.com",
        app_password=quoted_pw,
        recipient_email=corrupted_recipient,
    )
    assert reporter.recipient == "manjunathhk833@gmail.com"
    assert reporter.sender == "manjunathhk833@gmail.com"

    # Test self-healing closed page recovery
    class DummyPage:
        def __init__(self, closed: bool = False):
            self._closed = closed

        def is_closed(self) -> bool:
            return self._closed

    class DummyContext:
        def __init__(self):
            self.spawned = 0

        async def new_page(self) -> DummyPage:
            self.spawned += 1
            return DummyPage(closed=False)

    finder = LinkedInJobFinder(use_ai=False)
    ctx = DummyContext()
    finder._active_context = ctx
    closed_page = DummyPage(closed=True)
    recovered = asyncio.run(finder._recover_closed_page(closed_page))
    assert not recovered.is_closed(), "Expected closed page to be replaced with a live page"
    assert ctx.spawned == 1
    print("  ✅ EmailReporter sanitization & self-healing tab recovery passed.")


def test_reopened_24h_ci_and_portal_sniper() -> None:
    print("🧪 2. Testing <24h Re-Opened Requisition detection in PortalSniperEngine & CISyncIngestor...")
    now = datetime.utcnow()
    ten_days_ago = now - timedelta(days=10)
    two_hours_ago = now - timedelta(hours=2)

    with tempfile.TemporaryDirectory() as tmpdir:
        inbox_dir = os.path.join(tmpdir, "ci_inbox")
        pending_dir = os.path.join(tmpdir, "pending_queue")
        proc_file = os.path.join(tmpdir, "processed_jobs.json")
        sqlite_db = os.path.join(tmpdir, "test_app.db")

        sniper = PortalSniperEngine(inbox_dir=inbox_dir, max_age_hours=24.0)
        # Seed ledger with two jobs seen 10 days ago
        sniper.save_seen_ledger(
            {
                "greenhouse_stripe_101": {
                    "company": "Stripe",
                    "title": "Senior SDET",
                    "source": "greenhouse",
                    "first_seen_at": ten_days_ago.isoformat() + "Z",
                    "posted_at": ten_days_ago.isoformat(),
                },
                "greenhouse_stripe_102": {
                    "company": "Stripe",
                    "title": "Staff QA Automation Engineer",
                    "source": "greenhouse",
                    "first_seen_at": ten_days_ago.isoformat() + "Z",
                    "posted_at": ten_days_ago.isoformat(),
                },
            }
        )

        # Listing 101: Still has old posted_at (10d ago) -> must be skipped
        stale_listing = JobListing(
            id="greenhouse_stripe_101",
            source="greenhouse",
            company_name="Stripe",
            job_title="Senior SDET",
            location="Bengaluru, India",
            url="https://boards.greenhouse.io/stripe/jobs/101",
            job_description_raw="Senior SDET role requiring Playwright, Java, Python, API testing.",
            job_description_clean="Senior SDET role requiring Playwright, Java, Python, API testing.",
            posted_at=ten_days_ago,
            is_dream_org=True,
        )
        # Listing 102: Recruiter refreshed/re-opened requisition 2 hours ago (<24h) -> must be re-staged!
        reopened_listing = JobListing(
            id="greenhouse_stripe_102",
            source="greenhouse",
            company_name="Stripe",
            job_title="Staff QA Automation Engineer",
            location="Bengaluru, India",
            url="https://boards.greenhouse.io/stripe/jobs/102",
            job_description_raw="Staff QA Automation Engineer requiring Playwright, Java, REST Assured, Kafka.",
            job_description_clean="Staff QA Automation Engineer requiring Playwright, Java, REST Assured, Kafka.",
            posted_at=two_hours_ago,
            is_dream_org=True,
        )

        bundle = sniper.filter_and_package_drops([stale_listing, reopened_listing], total_orgs_polled=1)
        assert bundle["skipped_already_seen"] == 1, f"Expected 1 skipped_seen, got {bundle['skipped_already_seen']}"
        assert bundle["fresh_drops_count"] == 1, f"Expected 1 reopened fresh drop, got {bundle['fresh_drops_count']}"
        assert bundle["reopened_fresh_count"] == 1
        drop = bundle["drops"][0]
        assert drop["job_id"] == "greenhouse_stripe_102"
        assert drop["reopened_fresh"] is True
        assert drop["freshness_badge"] == "🔄 REOPENED (<24h)"

        # Now seed processed_jobs.json with the old 10-day-old entry and verify CISyncIngestor re-stages it
        Path(proc_file).write_text(
            json.dumps(
                {
                    "job_ids": {
                        "greenhouse_stripe_102": {
                            "title": "Staff QA Automation Engineer",
                            "company": "Stripe",
                            "first_seen": ten_days_ago.isoformat() + "Z",
                            "posted_at": ten_days_ago.isoformat() + "Z",
                            "status": "PENDING",
                        }
                    },
                    "composite_hashes": {},
                }
            ),
            encoding="utf-8",
        )

        ingestor = CISyncIngestor(
            inbox_dir=inbox_dir,
            pending_dir=pending_dir,
            processed_db_file=proc_file,
            sqlite_db_path=sqlite_db,
            use_ai=False,
        )
        sync_res = ingestor.sync_latest_drops(fetch_remote=False)
        assert sync_res["ingested_count"] == 1, f"Expected reopened job to be ingested, got: {sync_res}"
        staged_file = Path(pending_dir) / "greenhouse_stripe_102.json"
        assert staged_file.exists(), "Expected reopened job JSON in pending_queue/"
        staged_data = json.loads(staged_file.read_text(encoding="utf-8"))
        assert staged_data["reopened_fresh"] is True
        assert staged_data["freshness_badge"] == "🔄 REOPENED (<24h)"
    print("  ✅ PortalSniperEngine & CISyncIngestor <24h re-opened requisition flow passed.")


def test_reposted_applied_jobs_and_followup_routing() -> None:
    print("🧪 3. Testing Reposted Applied Jobs (30d cool-down vs TIER_0_REPOST_FOLLOWUP)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_repost.db")
        db = ApplicationDatabase(db_path=db_path)

        # Record two applications: one 6 days ago, one 45 days ago
        db.record_application(
            job_id="li_old_1001",
            source="linkedin",
            company_name="Swiggy",
            job_title="Senior SDET",
            job_url="https://www.linkedin.com/jobs/view/1001/",
            status="applied",
        )
        db.record_application(
            job_id="li_old_2002",
            source="linkedin",
            company_name="Postman",
            job_title="Staff QA Engineer",
            job_url="https://www.linkedin.com/jobs/view/2002/",
            status="applied",
        )

        # Backdate applied_at timestamps in SQLite
        six_days_ago = (datetime.utcnow() - timedelta(days=6)).strftime("%Y-%m-%d %H:%M:%S")
        forty_five_days_ago = (datetime.utcnow() - timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(db_path) as conn:
            conn.execute("UPDATE job_applications SET applied_at = ? WHERE id = 'li_old_1001'", (six_days_ago,))
            conn.execute("UPDATE job_applications SET applied_at = ? WHERE id = 'li_old_2002'", (forty_five_days_ago,))
            conn.commit()

        # Case 1: Swiggy applied 6 days ago -> Not reapply eligible (<30d), routes to TIER_0_REPOST_FOLLOWUP
        swiggy_details = db.get_applied_job_details("li_new_1009", "Swiggy", "Senior SDET")
        assert swiggy_details is not None
        assert 5.5 <= swiggy_details["days_since_applied"] <= 6.5
        assert db.is_reapply_eligible("li_new_1009", "Swiggy", "Senior SDET", min_days=30.0) is False

        repost_payload = {
            "job_id": "li_new_1009",
            "company_name": "Swiggy",
            "job_title": "Senior SDET",
            "repost_of_applied": True,
            "days_since_applied": swiggy_details["days_since_applied"],
            "job_url": "https://www.linkedin.com/jobs/view/1009/",
        }
        strategy = InterviewRouter.classify_job_strategy(repost_payload)
        assert strategy["routing_tier"] == "TIER_0_REPOST_FOLLOWUP"
        assert strategy["freshness_badge"] == "🔄 REPOSTED — FOLLOW UP"
        assert len(strategy["repost_followup_note"]) <= 300
        assert "reposted" in strategy["repost_followup_note"].lower()

        # Case 2: Postman applied 45 days ago -> Reposted on new job ID 'li_new_2099' -> Eligible for re-application!
        assert db.is_reapply_eligible("li_new_2099", "Postman", "Staff QA Engineer", min_days=30.0) is True
        # Exact same LinkedIn job ID remains locked forever on LinkedIn
        assert db.is_reapply_eligible("li_old_2002", "Postman", "Staff QA Engineer", min_days=30.0) is False

        portal_url = resolve_direct_ats_portal_url("Postman")
        assert portal_url and "greenhouse.io" in portal_url, f"Expected Greenhouse URL for Postman, got {portal_url}"
    print("  ✅ Reposted applied job cool-down & TIER_0_REPOST_FOLLOWUP routing passed.")


def test_early_applicant_metrics_and_preclick_location_gate() -> None:
    print("🧪 4. Testing Early-Applicant (<25) metrics & Pre-Click Foreign Location Gate...")
    m_first25 = extract_linkedin_applicant_metrics(
        "Bengaluru, Karnataka, India · 42 minutes ago · Be among the first 25 applicants",
        application_type="EASY_APPLY",
    )
    assert m_first25["is_early_applicant"] is True
    assert m_first25["applicant_bucket"] == "<25"
    assert m_first25["priority_boost"] == 25
    assert m_first25["competition_badge"] == "🎯 FIRST 25 APPLICANTS"

    m_exact8 = extract_linkedin_applicant_metrics(
        "Reposted 1 hour ago · 8 people clicked apply",
        application_type="LINKEDIN_EXTERNAL",
    )
    assert m_exact8["is_early_applicant"] is True
    assert m_exact8["applicant_bucket"] == "<10"
    assert m_exact8["priority_boost"] == 30
    assert m_exact8["is_reposted"] is True

    m_ext100 = extract_linkedin_applicant_metrics(
        "Posted 9 hours ago · Over 100 people clicked apply",
        application_type="LINKEDIN_EXTERNAL",
    )
    assert m_ext100["is_saturated"] is True
    assert m_ext100["estimated_completed_applies"] == 25

    # Verify InterviewRouter boosts early-applicant jobs
    routed = InterviewRouter.classify_job_strategy(
        {
            "job_id": "li_999",
            "source": "linkedin",
            "applicant_metrics": m_first25,
            "job_details": {"title": "Senior SDET", "company": "Razorpay"},
        }
    )
    assert routed["priority_boost"] >= 25
    assert routed["freshness_badge"] == "🎯 FIRST 25 APPLICANTS"

    # Verify Pre-Click Location Gate rejects US cards that wasted Sniper slots today
    assert is_india_or_remote_location("Atlanta, GA", allow_unspecified=True) is False
    assert is_india_or_remote_location("Arlington, VA", allow_unspecified=True) is False
    assert is_india_or_remote_location("United States", allow_unspecified=True) is False
    assert is_india_or_remote_location("Bengaluru, Karnataka, India", allow_unspecified=True) is True
    assert is_india_or_remote_location("India (Remote)", allow_unspecified=True) is True

    # Verify SDUI 'Be an early applicant' string is recognized as <25 early-applicant bucket
    m_sdui_early = extract_linkedin_applicant_metrics(
        "India (Remote) · 1 hour ago · Be an early applicant",
        application_type="EASY_APPLY",
    )
    assert m_sdui_early["is_early_applicant"] is True
    assert m_sdui_early["applicant_bucket"] == "<25"
    assert m_sdui_early["competition_badge"] == "🎯 FIRST 25 APPLICANTS"

    # Verify concatenated SDUI spans ('0 applicantsCompany review time', 'Over 100 people clicked applyPromoted')
    m_sdui_zero = extract_linkedin_applicant_metrics(
        "Bengaluru South, Karnataka, India · 42 minutes ago · 0 applicantsCompany review time is typically 1 weekOn-siteFull-timeEasy ApplySave\nBe an early applicant",
        application_type="LINKEDIN_EXTERNAL",
    )
    assert m_sdui_zero["applicant_count"] == 0
    assert m_sdui_zero["applicant_bucket"] == "<10"
    assert m_sdui_zero["priority_boost"] == 30
    assert m_sdui_zero["competition_badge"] == "🎯 EARLY (<10: 0 APPLICANTS)"

    m_sdui_over100_concat = extract_linkedin_applicant_metrics(
        "Bengaluru, Karnataka, India · Reposted 20 hours ago · Over 100 people clicked applyPromoted by hirer · Responses managed off LinkedIn",
        application_type="LINKEDIN_EXTERNAL",
    )
    assert m_sdui_over100_concat["is_saturated"] is True
    assert m_sdui_over100_concat["applicant_bucket"] == "100+"
    assert m_sdui_over100_concat["estimated_completed_applies"] == 25

    # Verify LinkedInJobFinder.build_search_url injects canonical geoId for Bengaluru & India
    # so LinkedIn's /jobs/search-results/ SDUI redirect does not fall back to United States
    finder = LinkedInJobFinder(use_ai=False)
    blr_url = finder.build_search_url(keywords="SDET", location="Bengaluru", time_posted="past_3h")
    assert "geoId=105214831" in blr_url, f"Expected Bengaluru geoId=105214831 in {blr_url}"
    assert "f_TPR=r10800" in blr_url, f"Expected f_TPR=r10800 in {blr_url}"
    ind_url = finder.build_search_url(keywords="QA Automation", location="India", time_posted="past_24h")
    assert "geoId=102713980" in ind_url, f"Expected India geoId=102713980 in {ind_url}"

    # Verify recycled repost + Over 100 saturation is rejected
    valid, reason = is_linkedin_posting_fresh_and_unsaturated(
        "Reposted 3 hours ago · Over 100 people clicked apply",
        max_days=1,
        is_sniper_24h=True,
    )
    assert valid is False and reason == "reposted_and_saturated_over_100_applicants"
    print("  ✅ Early-Applicant (<25) metrics, geoId URL builder & Pre-Click Location Gate passed.")


if __name__ == "__main__":
    print("=" * 72)
    print("🚀 RUNNING GATE 112: REOPENED (<24H), REPOSTED & EARLY-SNIPER VERIFICATION")
    print("=" * 72)
    test_email_reporter_sanitization_and_tab_recovery()
    test_reopened_24h_ci_and_portal_sniper()
    test_reposted_applied_jobs_and_followup_routing()
    test_early_applicant_metrics_and_preclick_location_gate()
    print("=" * 72)
    print("🎉 GATE 112 PASSED (100% ALL ASSERTIONS VERIFIED)")
    print("=" * 72)
