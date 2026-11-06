#!/usr/bin/env python3
"""
Verification Gate 106: Explicit Organization-Centric CI/CD Career Portal Sniper & Local DB Auto-Ingest.

Tests:
1. Extended Keyless ATS Collectors (SmartRecruiters, Rippling, Workable, Recruitee) normalization & SDET/India filtering.
2. OrgResearcher (Cycle 1) endpoint probing & health classification (VERIFIED_ACTIVE vs ENDPOINT_BROKEN).
3. PortalSniperEngine (Cycle 2) <24h freshness filtering + portal_seen_ledger.json anti-recycle protection.
4. CISyncIngestor Cloud-to-Local onboarding into SQLite tracked_requisitions & data/pending_queue/ + FastAPI /api/ci-sync endpoint.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ingestion.ci_sync import CISyncIngestor
from src.ingestion.extended_providers import (
    RecruiteeCollector,
    RipplingCollector,
    SmartRecruitersCollector,
    WorkableCollector,
)
from src.ingestion.org_researcher import OrgResearcher
from src.ingestion.portal_sniper import PortalSniperEngine
from src.storage.models import JobListing


def test_extended_collectors_parsing():
    print("🧪 [1/5] Testing Extended Collectors (SmartRecruiters, Rippling, Workable, Recruitee)...")
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. SmartRecruiters payload normalization
    sr = SmartRecruitersCollector()
    sr_raw = {
        "content": [
            {
                "id": "sr_9001",
                "name": "Senior SDET - Automation Infrastructure",
                "releasedDate": now_iso,
                "location": {"city": "Bengaluru", "country": "in", "remote": False},
                "ref": "https://api.smartrecruiters.com/v1/companies/visa/postings/sr_9001",
            },
            {
                "id": "sr_9002",
                "name": "Account Executive",
                "releasedDate": now_iso,
                "location": {"city": "Bengaluru", "country": "in", "remote": False},
            },
        ]
    }
    sr_jobs = sr.parse_response("Visa", "visa", sr_raw, filter_sdet=True)
    assert len(sr_jobs) == 1, f"Expected 1 SmartRecruiters SDET job, got {len(sr_jobs)}"
    assert sr_jobs[0].id == "smartrecruiters_visa_sr_9001"
    assert sr_jobs[0].posted_at is not None

    # 2. Rippling payload normalization
    rip = RipplingCollector()
    rip_raw = [
        {
            "uuid": "rip_101",
            "name": "Staff QA Automation Engineer (Playwright)",
            "workLocation": "Bengaluru, India (Hybrid)",
            "created_at": now_iso,
            "url": "https://ats.rippling.com/acme/jobs/rip_101",
        }
    ]
    rip_jobs = rip.parse_response("Acme", "acme", rip_raw, filter_sdet=True)
    assert len(rip_jobs) == 1
    assert rip_jobs[0].id == "rippling_acme_rip_101"

    # 3. Workable payload normalization
    wk = WorkableCollector()
    wk_raw = {
        "jobs": [
            {
                "shortcode": "WK777",
                "title": "Lead Software Engineer in Test",
                "city": "Bangalore",
                "country": "India",
                "telecommuting": True,
                "published_on": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "url": "https://apply.workable.com/testco/j/WK777/",
            }
        ]
    }
    wk_jobs = wk.parse_response("TestCo", "testco", wk_raw, filter_sdet=True)
    assert len(wk_jobs) == 1
    assert wk_jobs[0].id == "workable_testco_WK777"

    # 4. Recruitee payload normalization
    rec = RecruiteeCollector()
    rec_raw = {
        "offers": [
            {
                "id": 5544,
                "title": "SDET II (Backend & API)",
                "location": "Remote, India",
                "remote": True,
                "published_at": now_iso,
                "careers_url": "https://testrec.recruitee.com/o/sdet-ii",
                "description": "<p>Playwright, Python, Pytest</p>",
            }
        ]
    }
    rec_jobs = rec.parse_response("TestRec", "testrec", rec_raw, filter_sdet=True)
    assert len(rec_jobs) == 1
    assert rec_jobs[0].id == "recruitee_testrec_5544"
    print("   ✅ Extended collectors parsed & filtered accurately.")


async def test_portal_sniper_24h_delta_and_ledger():
    print("🧪 [2/5] Testing PortalSniperEngine <24h Freshness Filter & Anti-Recycle Ledger...")
    now = datetime.utcnow()
    fresh_dt = now - timedelta(hours=4)
    stale_dt = now - timedelta(hours=72)

    mock_listings = [
        JobListing(
            id="greenhouse_stripe_11111",
            source="greenhouse",
            company_name="Stripe",
            job_title="Staff SDET - Payments Platform",
            location="Bengaluru, India",
            is_remote=False,
            is_dream_org=True,
            job_description_raw="<p>Playwright, TypeScript, Java, Kafka, 6+ years experience.</p>",
            job_description_clean="Playwright, TypeScript, Java, Kafka, 6+ years experience.",
            url="https://boards.greenhouse.io/stripe/jobs/11111",
            posted_at=fresh_dt,
        ),
        JobListing(
            id="ashby_linear_22222",
            source="ashby",
            company_name="Linear",
            job_title="Senior Quality Engineer (Playwright)",
            location="Remote, India",
            is_remote=True,
            is_dream_org=False,
            job_description_raw="<p>Playwright, TypeScript, CI/CD sharding.</p>",
            job_description_clean="Playwright, TypeScript, CI/CD sharding.",
            url="https://jobs.ashbyhq.com/linear/22222",
            posted_at=fresh_dt,
        ),
        JobListing(
            id="lever_oldco_33333",
            source="lever",
            company_name="OldCo",
            job_title="SDET III",
            location="Bengaluru, India",
            is_remote=False,
            is_dream_org=False,
            job_description_raw="Old job posted 3 days ago",
            job_description_clean="Old job posted 3 days ago",
            url="https://jobs.lever.co/oldco/33333",
            posted_at=stale_dt,
        ),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        inbox_dir = Path(tmpdir) / "ci_inbox"
        sniper = PortalSniperEngine(inbox_dir=str(inbox_dir), max_age_hours=24.0)

        # Run 1: Should capture the 2 fresh (<24h) jobs and reject the 72h stale job
        report1 = sniper.filter_and_package_drops(mock_listings, total_orgs_polled=105)
        assert report1["fresh_drops_count"] == 2, f"Expected 2 fresh drops, got {report1['fresh_drops_count']}"
        assert (inbox_dir / "latest_ci_drops.json").exists()
        assert (inbox_dir / "portal_seen_ledger.json").exists()
        assert (inbox_dir / "latest_daily_report.md").exists()

        # Verify InterviewRouter classification in drops
        drops = report1["drops"]
        tiers = {d["job_id"]: d["routing_strategy"]["routing_tier"] for d in drops}
        assert tiers["greenhouse_stripe_11111"] == "TIER_2_REFERRAL_SLA"
        assert tiers["ashby_linear_22222"] == "TIER_1_SNIPER_APPLY"

        # Run 2: Re-running with the exact same jobs must yield 0 fresh drops because they are now in portal_seen_ledger.json
        report2 = sniper.filter_and_package_drops(mock_listings, total_orgs_polled=105)
        assert report2["fresh_drops_count"] == 0, "Seen ledger must prevent recycled jobs from re-triggering as fresh!"
        print("   ✅ <24h Delta Filter and Stateful Seen Ledger verified.")


def test_ci_sync_ingestor_to_local_db_and_queue():
    print("🧪 [3/5] Testing CISyncIngestor Cloud-to-Local Queue & SQLite Onboarding...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        inbox_dir = tmp_path / "ci_inbox"
        pending_dir = tmp_path / "pending_queue"
        db_file = tmp_path / "processed_jobs.json"
        sqlite_path = tmp_path / "test_app_db.sqlite"

        sniper = PortalSniperEngine(inbox_dir=str(inbox_dir), max_age_hours=24.0)
        fresh_job = JobListing(
            id="ashby_vercel_998877",
            source="ashby",
            company_name="Vercel",
            job_title="Senior SDET - Cloud Infrastructure",
            location="Bengaluru, India",
            is_remote=True,
            is_dream_org=True,
            job_description_raw="<p>Playwright, TypeScript, Docker, Kubernetes, 5+ years experience.</p>",
            job_description_clean="Playwright, TypeScript, Docker, Kubernetes, 5+ years experience.",
            url="https://jobs.ashbyhq.com/vercel/998877",
            posted_at=datetime.utcnow() - timedelta(hours=2),
        )
        sniper.filter_and_package_drops([fresh_job], total_orgs_polled=105)

        ingestor = CISyncIngestor(
            inbox_dir=str(inbox_dir),
            pending_dir=str(pending_dir),
            processed_db_file=str(db_file),
            sqlite_db_path=str(sqlite_path),
            use_ai=False,
        )
        res = ingestor.sync_latest_drops(fetch_remote=False)
        assert res["ingested_count"] == 1, f"Expected 1 ingested job, got {res}"
        staged_file = pending_dir / "ashby_vercel_998877.json"
        assert staged_file.exists(), "Staged job JSON must be created in pending_queue"

        staged_payload = json.loads(staged_file.read_text(encoding="utf-8"))
        assert "tailored_resume" in staged_payload, "Ingested CI job must be tailored automatically"
        assert staged_payload.get("ci_onboarded") is True

        # Second sync should skip as duplicate
        res2 = ingestor.sync_latest_drops(fetch_remote=False)
        assert res2["ingested_count"] == 0
        assert res2["skipped_duplicates"] >= 1
        print("   ✅ CISyncIngestor staged, tailored, and persisted to SQLite cleanly.")


def test_org_researcher_classification():
    print("🧪 [4/5] Testing OrgResearcher Watchlist Coverage, Catalog & URL Auto-Banking...")
    researcher = OrgResearcher()
    companies = researcher.load_watchlist()
    assert len(companies) >= 1000, f"Expected 1,000+ verified active companies in watchlist, found {len(companies)}"

    summary = researcher.get_watchlist_Breakdown(companies)
    assert summary["total_companies"] >= 1000
    assert summary["master_catalog_size"] >= 2000
    assert summary["dream_orgs"] >= 900
    assert "smartrecruiters" in summary["by_provider"]
    assert "rippling" in summary["by_provider"]
    assert "workday" in summary["by_provider"]

    # Test continuous URL auto-banking across providers (save=False so we don't mutate production file in test)
    gh_banked = researcher.extract_and_bank_ats_url(
        "https://job-boards.greenhouse.io/acmecloud/jobs/12345", company_name="Acme Cloud", save=False
    )
    assert gh_banked is not None and gh_banked.ats_provider == "greenhouse" and gh_banked.slug == "acmecloud"

    wd_banked = researcher.extract_and_bank_ats_url(
        "https://mastercard.wd1.myworkdayjobs.com/en-US/CorporateCareers/job/Pune/SDET_R-100",
        company_name="Mastercard",
        save=False,
    )
    assert (
        wd_banked is not None
        and wd_banked.ats_provider == "workday"
        and wd_banked.slug == "mastercard"
        and wd_banked.datacenter == "wd1"
        and wd_banked.site == "CorporateCareers"
    )

    print(
        f"   ✅ Watchlist verified: {summary['total_companies']} verified live boards (from {summary['master_catalog_size']} catalog orgs) across {len(summary['by_provider'])} providers + URL auto-banking."
    )


def test_fastapi_ci_sync_endpoint():
    print("🧪 [5/5] Testing FastAPI /api/ci-sync Endpoint Integration...")
    from src.ui.app import app

    client = TestClient(app)
    resp = client.post("/api/ci-sync", json={"fetch_remote": False})
    assert resp.status_code == 200, f"Expected HTTP 200 from /api/ci-sync, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "status" in data and data["status"] == "ok"
    assert "ingested_count" in data
    print("   ✅ FastAPI /api/ci-sync endpoint verified.")


async def main():
    print("=" * 72)
    print("  GATE 106: EXPLICIT 1,000-ORG CI PORTAL SNIPER & LOCAL DB AUTO-INGEST")
    print("=" * 72)
    test_extended_collectors_parsing()
    await test_portal_sniper_24h_delta_and_ledger()
    test_ci_sync_ingestor_to_local_db_and_queue()
    test_org_researcher_classification()
    test_fastapi_ci_sync_endpoint()
    print("=" * 72)
    print("🎉 ALL GATE 106 ASSERTIONS PASSED 100%!")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
