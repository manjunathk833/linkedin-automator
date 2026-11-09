#!/usr/bin/env python3
"""
Verification Gate 114: Track 4 Global Remote (USD/GBP/EUR) Sniper, Pre-Click Worldwide Location Gate,
Keyless Global Remote Aggregators (Mercor, Jobicy, Arbeitnow, RemoteOK, Himalayas, WWR, WorkingNomads, Remotive),
InterviewRouter Priority Boost, and Tab 3 Track 4 Funnel Analytics.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_1_sdet_title_and_global_remote_location_heuristics() -> None:
    from src.ingestion.filters import (
        evaluate_global_remote_signal,
        is_india_or_remote_location,
        is_sdet_title,
    )

    # 1. Positive AI Evaluation, Test Systems, and SWE-Bench titles discovered during live recon
    positive_titles = [
        "Senior Software Engineer — AI Evaluation & Benchmarks",
        "Staff Software Engineer, Test Systems & Tooling",
        "SWE-Bench Task Auditor",
        "Code Evaluation Engineer",
        "Applied Engineer, Evaluations Role",
        "Computer Power Users & Automation Builders",
        "Senior SDET (Playwright / Python)",
    ]
    for title in positive_titles:
        assert is_sdet_title(title), f"Expected positive SDET/AI-Eval match for: {title}"

    # 2. Negative exclusions discovered during live recon
    negative_titles = [
        "Audiobook QA Expert — Italian",
        "Audiobook QA Expert — English (US)",
        "Senior Design Quality Engineer",
        "Music Producer & Audio Post Specialist (AI Evaluation)",
        "Electrical Test Automation Engineer",
        "QA Tester Entry Level",
        "Quality Assurance Rater - Spanish speakers in Spain",
    ]
    for title in negative_titles:
        assert not is_sdet_title(title), f"Expected negative exclusion for: {title}"

    # 3. Pre-click location gate (text_snippet=None) must allow explicit Worldwide/Global/APAC even if UK/US prefix exists
    allowed_preclick_locs = [
        "United Kingdom (Remote - Worldwide)",
        "United States (Remote - Global)",
        "Home based - APAC",
        "Home based - Worldwide",
        "Global",
        "Remote - Worldwide",
        "APAC (Remote)",
        "India (Remote)",
    ]
    for loc in allowed_preclick_locs:
        assert is_india_or_remote_location(loc, allow_unspecified=True), (
            f"Expected pre-click location gate to allow '{loc}'"
        )

    # 4. Strict rejection of US-only / UK-only / overseas onsite locations
    rejected_locs = [
        "United States (Remote)",
        "London, United Kingdom",
        "Remote — United States",
        "USA Only",
        "Bay Area, CA",
        "Hong Kong",
    ]
    for loc in rejected_locs:
        assert not is_india_or_remote_location(loc, allow_unspecified=True), (
            f"Expected location gate to reject foreign-only '{loc}'"
        )

    # 5. Global remote signal with USD/GBP/EUR and EOR/B2B contractor signals
    sig_gbp = evaluate_global_remote_signal(
        title="Senior QA Automation Engineer (Playwright)",
        location="United Kingdom (Remote - Worldwide)",
        description="Work from anywhere via Deel B2B contract. Salary: £65,000 - £80,000 GBP.",
    )
    assert sig_gbp["eligible"] is True
    assert sig_gbp["is_usd_eor_remote"] is True
    assert sig_gbp["has_foreign_currency"] is True

    sig_hourly = evaluate_global_remote_signal(
        title="Software Engineering Expert — AI Evaluation",
        location="Remote - Global",
        description="Async-first global remote contract on Mercor paying $70 - $110/hr USD.",
    )
    assert sig_hourly["eligible"] is True
    assert sig_hourly["is_usd_eor_remote"] is True
    print("✅ [1/5] SDET/AI-Eval title & Global Remote pre-click location heuristics verified.")


def test_2_global_remote_aggregator_collectors() -> None:
    from src.ingestion.global_remote_providers import GlobalRemoteAggregatorCollector

    collector = GlobalRemoteAggregatorCollector()

    # 1. Mercor SSR HTML payload with dehydratedState listings
    mercor_html = (
        '<html><script>self.__next_f.push([1,"dehydratedState\\":{\\"queries\\":[{\\"state\\":{\\"data\\":{\\"listings\\":['
        + json.dumps(
            [
                {
                    "listingId": "list_AAABoKOP6g9ZUjU9LdNBCqS7",
                    "title": "Software Engineering Expert — QA & Code Evaluation",
                    "description": "Evaluate Python and Playwright test suites for frontier LLMs. Work from anywhere.",
                    "commitment": "full-time",
                    "status": "active",
                    "rateMin": 70,
                    "rateMax": 120,
                    "payRateFrequency": "hourly",
                    "location": "Remote",
                    "workArrangement": "remote",
                    "listingType": "evergreen",
                    "eligibleLocation": ["USA", "GBR", "IND"],
                    "ineligibleLocation": None,
                    "postedAt": "2025-06-02T20:15:58",
                },
                {
                    "listingId": "list_US_ONLY_1",
                    "title": "SWE-Bench Task Auditor",
                    "description": "Audit tasks.",
                    "status": "active",
                    "rateMin": 70,
                    "rateMax": 90,
                    "location": "Remote — United States",
                    "eligibleLocation": ["USA"],
                    "postedAt": datetime.now(timezone.utc).isoformat(),
                },
                {
                    "listingId": "list_AUDIOBOOK_1",
                    "title": "Audiobook QA Expert — Italian",
                    "description": "Listen to audiobooks.",
                    "status": "active",
                    "rateMin": 15,
                    "rateMax": 20,
                    "location": "Remote",
                    "eligibleLocation": None,
                    "postedAt": datetime.now(timezone.utc).isoformat(),
                },
            ]
        )
        + "]}}]}"
    )
    mercor_jobs = collector.parse_mercor_html(mercor_html)
    assert len(mercor_jobs) == 1, f"Expected 1 eligible Mercor job, got {len(mercor_jobs)}"
    assert mercor_jobs[0].id == "mercor_list_AAABoKOP6g9ZUjU9LdNBCqS7"
    assert "$70-$120/hr USD" in (mercor_jobs[0].salary_range or "")

    # 2. Jobicy JSON parser (only eligible geo + SDET title)
    jobicy_payload = {
        "jobs": [
            {
                "id": 99101,
                "url": "https://jobicy.com/jobs/99101-senior-playwright-sdet",
                "jobTitle": "Senior QA Automation Engineer (Playwright)",
                "companyName": "GlobalScale Labs",
                "jobGeo": "Worldwide",
                "jobDescription": "Build Playwright & Python API automation. Hired via Deel.",
                "pubDate": datetime.now(timezone.utc).isoformat(),
                "salaryMin": 75000,
                "salaryMax": 95000,
                "salaryCurrency": "USD",
            },
            {
                "id": 99102,
                "url": "https://jobicy.com/jobs/99102-us-only-qa",
                "jobTitle": "Senior QA Engineer - US Remote",
                "companyName": "PerfectServe",
                "jobGeo": "USA",
                "jobDescription": "Must reside in the US.",
                "pubDate": datetime.now(timezone.utc).isoformat(),
            },
        ]
    }
    jobicy_jobs = collector.parse_jobicy_payload(jobicy_payload)
    assert len(jobicy_jobs) == 1
    assert jobicy_jobs[0].id == "jobicy_99101"
    assert jobicy_jobs[0].company_name == "GlobalScale Labs"

    # 3. Arbeitnow JSON parser
    arbeitnow_payload = {
        "data": [
            {
                "slug": "software-test-engineer-swisspeak-123",
                "company_name": "SwissPeak Partners GmbH",
                "title": "Software Test Engineer (Playwright / Python)",
                "description": "Global remote B2B contract paying €65,000 EUR. Work from anywhere.",
                "remote": True,
                "url": "https://www.arbeitnow.com/jobs/companies/swisspeak/software-test-engineer-123",
                "tags": ["QA", "Testing", "Python"],
                "location": "Remote job",
                "created_at": int(datetime.now(timezone.utc).timestamp()),
            },
            {
                "slug": "onsite-london-qa",
                "company_name": "Wayve",
                "title": "System Test Automation Engineer",
                "description": "Onsite in London.",
                "remote": False,
                "url": "https://www.arbeitnow.com/jobs/wayve",
                "location": "London, United Kingdom",
                "created_at": int(datetime.now(timezone.utc).timestamp()),
            },
        ]
    }
    arb_jobs = collector.parse_arbeitnow_payload(arbeitnow_payload)
    assert len(arb_jobs) == 1
    assert arb_jobs[0].id == "arbeitnow_software-test-engineer-swisspeak-123"

    # 4. RemoteOK JSON parser (skipping index 0 legal notice)
    remoteok_payload = [
        {"legal": "Terms of service"},
        {
            "id": "109283",
            "epoch": int(datetime.now(timezone.utc).timestamp()),
            "date": datetime.now(timezone.utc).isoformat(),
            "company": "AsyncQA Inc",
            "position": "Senior SDET (Python & Playwright)",
            "tags": ["qa", "testing", "playwright", "python"],
            "description": "Worldwide remote role paying $80k USD via Remote.com.",
            "location": "Worldwide",
            "salary_min": 80000,
            "salary_max": 100000,
            "apply_url": "https://remoteok.com/remote-jobs/109283",
        },
    ]
    rok_jobs = collector.parse_remoteok_payload(remoteok_payload)
    assert len(rok_jobs) == 1
    assert rok_jobs[0].id == "remoteok_109283"

    # 5. Himalayas JSON parser
    himalayas_payload = {
        "jobs": [
            {
                "guid": "him-qa-001",
                "title": "Lead QA Automation Engineer",
                "companyName": "Distributed Systems Co",
                "minSalary": 70000,
                "maxSalary": 95000,
                "currency": "USD",
                "locationRestrictions": [],
                "categories": ["Quality Assurance"],
                "description": "Worldwide remote SDET role.",
                "pubDate": int(datetime.now(timezone.utc).timestamp()),
                "applicationLink": "https://himalayas.app/companies/dist/jobs/lead-qa",
            },
            {
                "guid": "him-qa-korea",
                "title": "Regional Quality Assurance Lead (Korea)",
                "companyName": "Agilent",
                "locationRestrictions": ["South Korea"],
                "description": "Must be based in South Korea.",
                "pubDate": int(datetime.now(timezone.utc).timestamp()),
                "applicationLink": "https://himalayas.app/jobs/korea",
            },
        ]
    }
    him_jobs = collector.parse_himalayas_payload(himalayas_payload)
    assert len(him_jobs) == 1
    assert him_jobs[0].id == "himalayas_him-qa-001"

    # 6. WeWorkRemotely RSS XML parser
    wwr_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel>
      <item>
        <title>TestFleet: Senior QA Automation Engineer</title>
        <region>Anywhere in the World</region>
        <description>Playwright and API testing. $75,000 USD B2B contract.</description>
        <pubDate>Mon, 09 Nov 2026 12:00:00 +0000</pubDate>
        <guid>https://weworkremotely.com/remote-jobs/testfleet-senior-qa</guid>
        <link>https://weworkremotely.com/remote-jobs/testfleet-senior-qa</link>
      </item>
      <item>
        <title>Midi Health: QA Engineer</title>
        <region>USA Only</region>
        <description>US residents only.</description>
        <guid>https://weworkremotely.com/remote-jobs/midi-qa</guid>
        <link>https://weworkremotely.com/remote-jobs/midi-qa</link>
      </item>
    </channel></rss>"""
    wwr_jobs = collector.parse_wwr_rss(wwr_xml)
    assert len(wwr_jobs) == 1
    assert wwr_jobs[0].company_name == "TestFleet"
    print("✅ [2/5] GlobalRemoteAggregatorCollector (Mercor, Jobicy, Arbeitnow, RemoteOK, Himalayas, WWR) verified.")


def test_3_track_4_global_remote_routing_and_queue_tagging() -> None:
    from src.ingestion.ats_discovery import ATSDiscoveryCoordinator
    from src.ingestion.portal_sniper import PortalSniperEngine
    from src.storage.models import JobListing
    from src.tailor.referral_generator import InterviewRouter

    with tempfile.TemporaryDirectory() as tmpdir:
        qdir = os.path.join(tmpdir, "pending_queue")
        db_file = os.path.join(tmpdir, "processed.json")
        inbox_dir = os.path.join(tmpdir, "ci_inbox")

        coord = ATSDiscoveryCoordinator(queue_dir=qdir, db_file=db_file, use_ai=False)
        listing = JobListing(
            id="mercor_list_AAABoKOP6g9ZUjU9LdNBCqS7",
            source="mercor",
            company_name="Mercor AI Lab",
            job_title="Software Engineering Expert — QA & Code Evaluation",
            location="Remote - Worldwide",
            url="https://work.mercor.com/jobs/list_AAABoKOP6g9ZUjU9LdNBCqS7",
            is_remote=True,
            salary_range="$70-$120/hr USD",
            job_description_raw="Global remote AI evaluation & Python/Playwright test automation paying $70-$120/hr USD.",
            job_description_clean="Global remote AI evaluation & Python/Playwright test automation paying $70-$120/hr USD.",
            posted_at=datetime.utcnow(),
        )
        saved = coord.save_listings_to_queue([listing], tailor=False)
        assert len(saved) == 1

        payload = json.loads(Path(saved[0]).read_text(encoding="utf-8"))
        assert payload["discovery_track"] == "TRACK_4_GLOBAL_REMOTE"
        assert payload["is_usd_eor_remote"] is True
        assert payload["routing_strategy"]["routing_tier"] == "TIER_1_SNIPER_APPLY"
        assert payload["routing_strategy"]["priority_boost"] >= 25
        assert "🌍" in payload["freshness_badge"] or "🌍" in payload["routing_strategy"].get("global_remote_badge", "")

        # Verify PortalSniperEngine also tags TRACK_4_GLOBAL_REMOTE
        sniper = PortalSniperEngine(inbox_dir=inbox_dir, max_age_hours=24.0)
        bundle = sniper.filter_and_package_drops([listing], total_orgs_polled=1)
        assert bundle["fresh_drops_count"] == 1
        drop = bundle["drops"][0]
        assert drop["discovery_track"] == "TRACK_4_GLOBAL_REMOTE"
        assert drop["is_usd_eor_remote"] is True

        # Verify InterviewRouter directly on a Greenhouse EOR role
        gh_eor_payload = {
            "job_id": "greenhouse_canonical_999",
            "source": "greenhouse",
            "title": "Software Quality Assurance Engineer",
            "company": "Canonical",
            "is_usd_eor_remote": True,
            "posted_at": datetime.utcnow().isoformat() + "Z",
            "job_details": {
                "title": "Software Quality Assurance Engineer",
                "company": "Canonical",
                "location": "Home based - Worldwide",
                "is_usd_eor_remote": True,
            },
        }
        route = InterviewRouter.classify_job_strategy(gh_eor_payload)
        assert route["routing_tier"] == "TIER_1_SNIPER_APPLY"
        assert route["global_remote_badge"] == "🌍 USD/GBP/EUR REMOTE"
    print("✅ [3/5] TRACK_4_GLOBAL_REMOTE queue tagging, PortalSniper packaging & InterviewRouter verified.")


def test_4_database_track_4_analytics_and_ui_normalization() -> None:
    from src.storage.database import ApplicationDatabase
    from src.ui.app import normalize_job_source_metadata

    # 1. Verify normalize_job_source_metadata handles global remote sources
    for src_name in ("mercor", "jobicy", "arbeitnow", "remoteok", "himalayas", "wwr", "workingnomads", "remotive"):
        norm_src, norm_type = normalize_job_source_metadata(
            {"source": src_name, "job_id": f"{src_name}_123", "url": f"https://{src_name}.com/jobs/123"}
        )
        assert norm_src == src_name
        assert norm_type == f"GLOBAL_{src_name.upper()}"

    # 2. Verify SQLite ApplicationDatabase tracks TRACK_4_GLOBAL_REMOTE in get_funnel_metrics()
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_track4.db")
        db = ApplicationDatabase(db_path=db_path)
        db.record_application(
            job_id="mercor_list_test_1",
            company_name="Mercor AI",
            job_title="Software Engineering Expert — QA Evaluation",
            job_url="https://work.mercor.com/jobs/list_test_1",
            source="mercor",
            discovery_track="TRACK_4_GLOBAL_REMOTE",
            discovery_channel="mercor",
            application_mode="batch_autofill",
            status="applied",
            tailored_data={"is_usd_eor_remote": True, "posted_at": datetime.utcnow().isoformat() + "Z"},
        )
        db.update_funnel_stage(
            "mercor_list_test_1", "RECRUITER_SCREEN", notes="Async AI interview invite on Playwright"
        )
        metrics = db.get_funnel_metrics()
        assert "TRACK_4_GLOBAL_REMOTE" in metrics["tracks"]
        assert metrics["tracks"]["TRACK_4_GLOBAL_REMOTE"] == 1
        t4_turnover = metrics["interview_turnover"]["by_track"]["TRACK_4_GLOBAL_REMOTE"]
        assert t4_turnover["applied"] == 1
        assert t4_turnover["interviewed"] == 1
        assert t4_turnover["turnover_pct"] == 100.0
        pv = metrics["value_and_frequency"]["portfolio_value"]
        assert pv.get("global_remote_count", 0) >= 1
    print("✅ [4/5] SQLite TRACK_4_GLOBAL_REMOTE funnel metrics & UI source normalization verified.")


def test_5_ui_templates_and_target_companies_watchlist() -> None:
    index_html = Path(PROJECT_ROOT, "src", "ui", "templates", "index.html").read_text(encoding="utf-8")
    app_js = Path(PROJECT_ROOT, "src", "ui", "static", "app.js").read_text(encoding="utf-8")
    target_companies = json.loads(
        Path(PROJECT_ROOT, "data", "config", "target_companies.json").read_text(encoding="utf-8")
    )

    assert 'value="TRACK_4_GLOBAL_REMOTE"' in index_html, "Missing TRACK_4_GLOBAL_REMOTE option in index.html"
    assert "TRACK_4_GLOBAL_REMOTE" in app_js or "mercor" in app_js, "Missing global remote badge support in app.js"

    providers = {c.get("ats_provider") for c in target_companies}
    assert "global_remote" in providers, "Expected global_remote provider entries in target_companies.json"

    slugs = {(c.get("ats_provider"), c.get("slug", "").lower()) for c in target_companies}
    for expected in [
        ("global_remote", "mercor"),
        ("global_remote", "jobicy"),
        ("global_remote", "arbeitnow"),
        ("global_remote", "remoteok"),
        ("global_remote", "himalayas"),
        ("global_remote", "wwr"),
        ("ashby", "testgorilla"),
        ("greenhouse", "vercel"),
        ("ashby", "n8n"),
        ("ashby", "temporal"),
        ("ashby", "braintrust"),
    ]:
        assert expected in slugs, f"Missing expected global-remote entry {expected} in target_companies.json"
    print("✅ [5/5] UI templates, app.js badges, and target_companies.json watchlist verified.")


if __name__ == "__main__":
    print("=" * 72)
    print("🧪 RUNNING GATE 114: TRACK 4 GLOBAL USD/GBP/EUR REMOTE SNIPER SUITE")
    print("=" * 72)
    test_1_sdet_title_and_global_remote_location_heuristics()
    test_2_global_remote_aggregator_collectors()
    test_3_track_4_global_remote_routing_and_queue_tagging()
    test_4_database_track_4_analytics_and_ui_normalization()
    test_5_ui_templates_and_target_companies_watchlist()
    print("=" * 72)
    print("🎉 ALL 5 TRACK 4 GLOBAL REMOTE SNIPER GATES PASSED!")
    print("=" * 72)
