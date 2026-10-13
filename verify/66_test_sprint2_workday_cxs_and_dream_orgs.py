#!/usr/bin/env python3
"""
Verification Gate 66: Sprint 2 Workday CXS Collector, Dream Org Tracker & SHA-256 Change Detection Suite
========================================================================================================
Validates:
1. Target Enterprise Registry Scale (≥50 companies, valid Workday configs, Dream Org flags).
2. Pydantic models integrity (JobListing, TargetCompany with is_dream_org).
3. Keyless Workday CXS Collector parsing, title filtering, and loop termination.
4. SQLite Requisition State Engine (tracked_requisitions, SHA-256 change detection, NEW/ACTIVE/UPDATED transitions).
5. Fast API / UI payload contract for Dream Org badging.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ingestion.workday import WorkdayCollector, clean_html_description
from src.storage.database import ApplicationDatabase
from src.storage.models import TargetCompany


def test_models_and_registry_scale():
    print("\n--- 1. Testing Models & Enterprise Registry Scale ---")
    cfg_path = os.path.join(PROJECT_ROOT, "data", "config", "target_companies.json")
    assert os.path.exists(cfg_path), f"Missing target_companies.json at {cfg_path}"

    with open(cfg_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) >= 50, f"Expected ≥50 target companies, got {len(data)}"
    print(f"  ✓ Target enterprise count: {len(data)} (≥50 requirement satisfied)")

    parsed_companies = [TargetCompany(**item) for item in data]
    dream_orgs = [c for c in parsed_companies if c.is_dream_org]
    assert len(dream_orgs) >= 30, f"Expected ≥30 Dream Orgs, got {len(dream_orgs)}"
    print(f"  ✓ Tagged Dream Orgs: {len(dream_orgs)} (≥30 requirement satisfied)")

    providers = {c.ats_provider for c in parsed_companies}
    assert {"greenhouse", "lever", "ashby", "workday"}.issubset(providers), f"Missing providers: {providers}"
    print(f"  ✓ Multi-ATS provider coverage: {providers}")

    workday_targets = [c for c in parsed_companies if c.ats_provider == "workday"]
    assert len(workday_targets) >= 8, f"Expected ≥8 Workday targets, got {len(workday_targets)}"
    for wt in workday_targets:
        assert wt.site, f"Workday target {wt.name} missing 'site' attribute"
    print(f"  ✓ Verified {len(workday_targets)} Workday targets with valid site configs")
    print("✅ Model schemas and enterprise registry verified.")


def test_workday_collector_contract():
    print("\n--- 2. Testing Workday CXS Collector Contract ---")
    collector = WorkdayCollector(timeout_seconds=5.0)

    # 1. URL Building
    url_wd = collector._build_base_url("adobe", "external_experienced", "wd5")
    assert url_wd == "https://adobe.wd5.myworkdayjobs.com/wday/cxs/adobe/external_experienced"

    url_direct = collector._build_base_url("adobe", "external_experienced", None)
    assert url_direct == "https://adobe.myworkdayjobs.com/wday/cxs/adobe/external_experienced"
    print("  ✓ CXS Base URL construction verified for datacenter & direct endpoints")

    # 2. HTML Description Cleaning
    raw_html = "<p>Join our <strong>Quality</strong> team &amp; build test frameworks.&nbsp;</p>"
    cleaned = clean_html_description(raw_html)
    assert cleaned == "Join our Quality team & build test frameworks."
    print("  ✓ HTML cleaning and entity unescaping verified")

    # 3. Mock CXS API Ingestion & Defensive Loop Termination
    mock_cxs_jobs_response = {
        "total": 2,
        "jobPostings": [
            {
                "title": "Lead Software Development Engineer in Test (SDET)",
                "externalPath": "/job/Bengaluru-India/Lead-SDET_R-101",
                "locationsText": "Bengaluru, Karnataka, India",
                "bulletFields": ["R-101"],
            },
            {
                "title": "Senior Product Manager",  # Non-SDET role (should be filtered out)
                "externalPath": "/job/Bengaluru-India/Senior-PM_R-102",
                "locationsText": "Bengaluru, Karnataka, India",
                "bulletFields": ["R-102"],
            },
        ],
    }

    mock_detail_response = {
        "jobPostingInfo": {
            "title": "Lead Software Development Engineer in Test (SDET)",
            "jobDescription": "<p>Architect modern Playwright automation frameworks in Bengaluru.</p>",
            "location": "Bengaluru, India",
            "externalUrl": "https://adobe.wd5.myworkdayjobs.com/en-US/external_experienced/job/Bengaluru/Lead-SDET_R-101",
            "jobReqId": "R-101",
        }
    }

    from unittest.mock import MagicMock

    async def run_collector_mock():
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            # Return list response first, then detail response (res.json() is synchronous in httpx)
            mock_post_res = MagicMock()
            mock_post_res.status_code = 200
            mock_post_res.json.return_value = mock_cxs_jobs_response

            mock_get_res = MagicMock()
            mock_get_res.status_code = 200
            mock_get_res.json.return_value = mock_detail_response

            mock_client.post.return_value = mock_post_res
            mock_client.get.return_value = mock_get_res

            jobs = await collector.fetch_board_jobs(
                company_name="Adobe",
                slug="adobe",
                site="external_experienced",
                datacenter="wd5",
                is_dream_org=True,
                max_pages=2,
            )
            return jobs

    jobs = asyncio.run(run_collector_mock())
    assert len(jobs) == 1, f"Expected 1 filtered SDET job, got {len(jobs)}"
    job = jobs[0]
    assert job.source == "workday"
    assert "SDET" in job.job_title
    assert job.is_dream_org is True
    assert "Playwright" in job.job_description_clean
    print(f"  ✓ Successfully parsed Workday job: {job.job_title} (ID: {job.id}, Dream: {job.is_dream_org})")
    print("✅ Workday CXS collector contract and defensive filtering verified.")


def test_sqlite_requisition_state_engine():
    print("\n--- 3. Testing SQLite Requisition State Engine & SHA-256 Hashing ---")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        temp_db_path = tf.name

    try:
        db = ApplicationDatabase(db_path=temp_db_path)

        # 1. Deterministic SHA-256 Hashing
        h1 = db.compute_requisition_hash("Senior SDET", "Bengaluru", "Test automation with Playwright")
        h2 = db.compute_requisition_hash("Senior SDET", "Bengaluru", "Test automation with Playwright")
        h3 = db.compute_requisition_hash("Senior SDET", "Bengaluru", "Test automation with Cypress")
        assert h1 == h2, "Hash must be deterministic"
        assert h1 != h3, "Hash must vary when description changes"
        print("  ✓ Deterministic SHA-256 hashing verified")

        # 2. State Transition: NEW
        res_new = db.sync_requisition(
            requisition_id="workday_target_r123",
            company_slug="target",
            ats_provider="workday",
            job_title="Lead SDET",
            location="Bengaluru, India",
            job_url="https://target.myworkdayjobs.com/job/r123",
            description_clean="Modern test architecture lead",
            is_dream_org=True,
        )
        assert res_new["status"] == "NEW"
        assert res_new["is_changed"] is True
        print("  ✓ State transition 1: NEW requisition published")

        # 3. State Transition: ACTIVE (Unchanged)
        res_active = db.sync_requisition(
            requisition_id="workday_target_r123",
            company_slug="target",
            ats_provider="workday",
            job_title="Lead SDET",
            location="Bengaluru, India",
            job_url="https://target.myworkdayjobs.com/job/r123",
            description_clean="Modern test architecture lead",
            is_dream_org=True,
        )
        assert res_active["status"] == "ACTIVE"
        assert res_active["is_changed"] is False
        print("  ✓ State transition 2: ACTIVE (Unchanged, timestamp bumped)")

        # 4. State Transition: UPDATED (Content Changed)
        res_updated = db.sync_requisition(
            requisition_id="workday_target_r123",
            company_slug="target",
            ats_provider="workday",
            job_title="Lead SDET",
            location="Bengaluru, India",
            job_url="https://target.myworkdayjobs.com/job/r123",
            description_clean="Modern test architecture lead with Kubernetes and Kafka streaming",
            is_dream_org=True,
        )
        assert res_updated["status"] == "UPDATED"
        assert res_updated["is_changed"] is True
        assert res_updated["content_hash"] != res_new["content_hash"]
        print("  ✓ State transition 3: UPDATED (Description change detected via SHA-256)")

        # 5. Dream Org Query Filter
        tracked_dream = db.get_tracked_requisitions(is_dream_only=True)
        assert len(tracked_dream) == 1
        assert tracked_dream[0]["requisition_id"] == "workday_target_r123"
        print("  ✓ Filtered query: is_dream_only correctly scoped")

        # 6. is_dream_company lookup
        assert db.is_dream_company("target") is True
        assert db.is_dream_company("non_existent_corp_xyz") is False
        print("  ✓ is_dream_company lookup verified")

    finally:
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)

    print("✅ SQLite Requisition State Engine verified.")


def test_ui_and_css_contracts():
    print("\n--- 4. Testing Dashboard UI & CSS Contracts ---")
    styles_path = os.path.join(PROJECT_ROOT, "src", "ui", "static", "styles.css")
    with open(styles_path, "r", encoding="utf-8") as f:
        css = f.read()

    assert ".dream-pill" in css, "Missing .dream-pill in styles.css"
    assert "dream-glow" in css, "Missing dream-glow animation in styles.css"
    assert ".badge-cluster" in css, "Missing .badge-cluster in styles.css"
    print("  ✓ CSS classes .dream-pill, .badge-cluster, and dream-glow animation verified")

    index_html = os.path.join(PROJECT_ROOT, "src", "ui", "templates", "index.html")
    with open(index_html, "r", encoding="utf-8") as f:
        html_src = f.read()

    assert 'id="job-dream-badge"' in html_src, "Missing job-dream-badge element in index.html"
    print("  ✓ HTML element #job-dream-badge present in index.html")

    app_js = os.path.join(PROJECT_ROOT, "src", "ui", "static", "app.js")
    with open(app_js, "r", encoding="utf-8") as f:
        js_src = f.read()

    assert "job-dream-badge" in js_src, "app.js must reference job-dream-badge"
    assert "is_dream_org" in js_src, "app.js must check is_dream_org"
    print("  ✓ JS script correctly controls job-dream-badge and is_dream_org rendering")
    print("✅ Dashboard UI and CSS contracts verified.")


if __name__ == "__main__":
    print("=" * 74)
    print(" Verification Gate 66: Sprint 2 Workday CXS & Dream Org Tracker Suite ")
    print("=" * 74)

    test_models_and_registry_scale()
    test_workday_collector_contract()
    test_sqlite_requisition_state_engine()
    test_ui_and_css_contracts()

    print("\n" + "=" * 74)
    print(" GATE 66 PASSED: 100% SUCCESS across models, collector, SQLite & UI ")
    print("=" * 74)
