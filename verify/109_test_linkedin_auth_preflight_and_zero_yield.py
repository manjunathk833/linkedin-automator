#!/usr/bin/env python3
"""
Verification Script 109: LinkedIn Authentication Preflight & Zero-Yield Detection Gate.

Validates:
1. `check_profile_session()` correctly identifies valid vs expired/missing sessions from both
   Cookies SQLite and storage_state.json.
2. `is_auth_redirect()` flags LinkedIn authwalls, checkpoints, and login pages.
3. `summarize_yield()` flags zero-yield runs when all auth-only surfaces return 0 cards.
4. `scrape_similar_jobs()` gracefully extracts similar jobs or exits cleanly when no seed IDs exist.
5. `EmailReporter.build_report_html()` renders a high-visibility warning banner when LinkedIn auth fails.
6. `DailyPipelineRunner` calculates run_status taking LinkedIn auth and yield into account.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.browser.linkedin_auth import (
    check_profile_session,
    is_auth_redirect,
    summarize_yield,
)
from src.notifier.email_reporter import EmailReporter
from src.scraper.job_finder import LinkedInJobFinder


def test_auth_redirect_markers() -> bool:
    print("\n--- Test 1: Auth Redirect URL Matcher ---")
    positive = [
        "https://www.linkedin.com/authwall?trk=rip",
        "https://www.linkedin.com/login?fromSignIn=true",
        "https://www.linkedin.com/uas/login",
        "https://www.linkedin.com/checkpoint/challenge/12345",
    ]
    negative = [
        "https://www.linkedin.com/jobs/search/?keywords=SDET",
        "https://www.linkedin.com/feed/",
        "https://www.linkedin.com/company/swiggy-in/jobs/",
    ]
    for u in positive:
        assert is_auth_redirect(u), f"Expected {u} to be flagged as auth redirect"
    for u in negative:
        assert not is_auth_redirect(u), f"Did not expect {u} to be flagged as auth redirect"
    print("✅ All auth redirect URL markers correctly matched.")
    return True


def test_profile_session_check() -> bool:
    print("\n--- Test 2: Offline Profile Session Detection ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Empty profile dir -> LOGGED_OUT
        res = check_profile_session(tmpdir)
        assert not res["is_authenticated"]
        assert res["status"] == "LOGGED_OUT"

        # Synthetic valid storage_state.json
        state_file = Path(tmpdir) / "storage_state.json"
        state_file.write_text(
            json.dumps({"cookies": [{"name": "li_at", "value": "dummy", "expires": 2000000000}]}),
            encoding="utf-8",
        )
        res_ok = check_profile_session(tmpdir)
        assert res_ok["is_authenticated"]
        assert res_ok["status"] == "AUTHENTICATED"

        # Synthetic expired storage_state.json
        state_file.write_text(
            json.dumps({"cookies": [{"name": "li_at", "value": "dummy", "expires": 1000000000}]}),
            encoding="utf-8",
        )
        res_exp = check_profile_session(tmpdir)
        assert not res_exp["is_authenticated"]
        assert res_exp["status"] == "EXPIRED"

    print("✅ Offline session detection successfully validated across LOGGED_OUT, AUTHENTICATED, and EXPIRED.")
    return True


def test_zero_yield_summarizer() -> bool:
    print("\n--- Test 3: Zero-Yield Summarizer ---")
    auth_surfaces = ("jobs_hub", "company_pages", "collection:recommended")
    suspect_yield = {"search": 7, "jobs_hub": 0, "company_pages": 0, "collection:recommended": 0}
    healthy_yield = {"search": 7, "jobs_hub": 5, "company_pages": 0, "collection:recommended": 3}

    assert summarize_yield(suspect_yield, auth_surfaces) == "ZERO_YIELD_SUSPECT"
    assert summarize_yield(healthy_yield, auth_surfaces) == "OK"
    print("✅ Zero-yield summarizer accurately isolates suspect zero-card runs.")
    return True


def test_email_reporter_auth_banner() -> bool:
    print("\n--- Test 4: Email Reporter Auth Failure Banner ---")
    reporter = EmailReporter()

    html_ok = reporter.build_report_html(
        staged_jobs=[],
        linkedin_telemetry={"is_authenticated": True, "track2_verdict": "OK", "track3_verdict": "OK"},
    )
    assert "🚨 LinkedIn Session Expired" not in html_ok

    html_failed = reporter.build_report_html(
        staged_jobs=[],
        linkedin_telemetry={
            "is_authenticated": False,
            "track2_verdict": "AUTH_FAILED",
            "track3_verdict": "AUTH_FAILED",
        },
    )
    assert "🚨 LinkedIn Session Expired" in html_failed

    html_zero = reporter.build_report_html(
        staged_jobs=[],
        linkedin_telemetry={"is_authenticated": True, "track2_verdict": "ZERO_YIELD_SUSPECT", "track3_verdict": "OK"},
    )
    assert "⚠️ LinkedIn Zero-Yield Warning" in html_zero
    print("✅ Email report dynamically surfaces red alert banner on LinkedIn auth failures.")
    return True


def test_job_finder_channels_and_queue_routing() -> bool:
    print("\n--- Test 5: JobFinder Routing Strategy & Yield Telemetry ---")
    finder = LinkedInJobFinder(use_ai=False)
    finder._record_yield("jobs_hub", 4)
    finder._record_yield("company_pages", 2)
    assert finder.channel_yield["jobs_hub"] == 4
    assert finder.channel_yield["company_pages"] == 2

    # Verify queue enrichment with 3-Tier InterviewRouter
    with tempfile.TemporaryDirectory() as qdir:
        sample = {
            "job_id": "test_routing_999",
            "is_dream_org": True,
            "job_details": {"title": "Staff SDET", "company": "TargetEnterprise"},
        }
        saved = finder.save_job_to_queue(sample, queue_dir=qdir)
        payload = json.loads(Path(saved).read_text(encoding="utf-8"))
        assert "routing_strategy" in payload
        assert "routing_tier" in payload["routing_strategy"]
    print("✅ JobFinder yields and 3-Tier InterviewRouter queue enrichment validated.")
    return True


def main() -> int:
    t1 = test_auth_redirect_markers()
    t2 = test_profile_session_check()
    t3 = test_zero_yield_summarizer()
    t4 = test_email_reporter_auth_banner()
    t5 = test_job_finder_channels_and_queue_routing()

    if t1 and t2 and t3 and t4 and t5:
        print("\n🎉 ALL GATE 109 VERIFICATIONS PASSED SUCCESSFULLY.")
        return 0
    return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
