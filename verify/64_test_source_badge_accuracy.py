#!/usr/bin/env python3
"""
Verification Gate 64: Source Badge Attribution & Metadata Accuracy Test
Validates:
1. normalize_job_source_metadata across all 6 platform variations and legacy edge cases.
2. API endpoints (/api/approved-jobs, /api/tracking/applied) returning authentic sources.
3. CSS styles and front-end helper implementation for all platform badges.
"""

import asyncio
import os
import sys

# Ensure repository root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ui.app import get_applied_tracking, get_approved_jobs, normalize_job_source_metadata


def test_source_normalization_heuristics():
    print("--- 1. Testing normalize_job_source_metadata Heuristics ---")

    test_cases = [
        # (payload, expected_source, expected_app_type)
        (
            {"source": "linkedin", "application_type": "EASY_APPLY", "job_id": "4475109508"},
            "linkedin",
            "EASY_APPLY",
        ),
        (
            {"source": "linkedin", "application_type": "LINKEDIN_EXTERNAL", "job_id": "4475109509"},
            "linkedin",
            "LINKEDIN_EXTERNAL",
        ),
        (
            {"job_id": "p1_job_5", "application_type": "EASY_APPLY"},  # missing source
            "linkedin",
            "EASY_APPLY",
        ),
        (
            {
                "job_id": "4475109508",
                "url": "https://www.linkedin.com/jobs/view/4475109508/",
            },  # missing source & app_type
            "linkedin",
            "EASY_APPLY",
        ),
        (
            {"job_id": "4475109510", "application_type": "LINKEDIN_EXTERNAL"},  # missing source
            "linkedin",
            "LINKEDIN_EXTERNAL",
        ),
        (
            {
                "job_id": "greenhouse_cloudflare_8038898",
                "url": "https://boards.greenhouse.io/embed/job_app?for=cloudflare",
            },
            "greenhouse",
            "ATS_GREENHOUSE",
        ),
        (
            {"source": "greenhouse", "application_type": "ATS_GREENHOUSE"},
            "greenhouse",
            "ATS_GREENHOUSE",
        ),
        (
            {"job_id": "lever_spotify_123", "url": "https://jobs.lever.co/spotify/123"},
            "lever",
            "ATS_LEVER",
        ),
        (
            {"source": "lever", "application_type": "ATS_LEVER"},
            "lever",
            "ATS_LEVER",
        ),
        (
            {"job_id": "ashby_zapier_45b2c110", "url": "https://jobs.ashbyhq.com/zapier/45b2c110"},
            "ashby",
            "ATS_ASHBY",
        ),
        (
            {"source": "ashby", "application_type": "ATS_ASHBY"},
            "ashby",
            "ATS_ASHBY",
        ),
        (
            {"job_id": "workday_jiostar_123", "url": "https://jiostar.wd102.myworkdayjobs.com/JioStar"},
            "workday",
            "ATS_WORKDAY",
        ),
        (
            {"source": "workday", "application_type": "ATS_WORKDAY"},
            "workday",
            "ATS_WORKDAY",
        ),
    ]

    for payload, exp_src, exp_app in test_cases:
        src, app_type = normalize_job_source_metadata(payload)
        assert src == exp_src, f"Expected source '{exp_src}', got '{src}' for payload: {payload}"
        assert app_type == exp_app, f"Expected app_type '{exp_app}', got '{app_type}' for payload: {payload}"
        print(f"  ✓ Validated {exp_src.upper()} ({exp_app}): {payload.get('job_id', 'custom')}")

    print("✅ All source normalization heuristics passed.\n")


def test_api_approved_jobs_attribution():
    print("--- 2. Testing /api/approved-jobs Attribution ---")
    res = asyncio.run(get_approved_jobs())
    jobs = res.get("jobs", [])
    assert len(jobs) > 0, "Approved queue should contain active test jobs"

    sources_found = set()
    for j in jobs:
        src = j.get("source")
        app_type = j.get("application_type")
        jid = j.get("job_id")
        sources_found.add(src)
        assert src in ("linkedin", "greenhouse", "lever", "ashby", "workday"), (
            f"Unrecognized or generic source '{src}' for job {jid}"
        )
        assert app_type in (
            "EASY_APPLY",
            "LINKEDIN_EXTERNAL",
            "ATS_GREENHOUSE",
            "ATS_LEVER",
            "ATS_ASHBY",
            "ATS_WORKDAY",
        ), f"Unrecognized app_type '{app_type}' for job {jid}"
        if jid == "p1_job_5":
            assert src == "linkedin", f"p1_job_5 must be linkedin, got {src}"
            assert app_type == "EASY_APPLY", f"p1_job_5 must be EASY_APPLY, got {app_type}"

    print(f"  ✓ Approved jobs sources verified: {sources_found}")
    print("✅ /api/approved-jobs attribution verified.\n")


def test_api_tracking_applied_attribution():
    print("--- 3. Testing /api/tracking/applied Attribution & SQLite ---")
    res = asyncio.run(get_applied_tracking())
    stats = res.get("stats", {})
    sources = stats.get("sources", {})

    print(f"  Tracked sources breakdown: {sources}")
    assert "manual" not in sources or sources["manual"] == 0, (
        f"Legacy 'manual' source detected in SQLite stats: {sources}"
    )
    assert sources.get("linkedin", 0) > 0, "LinkedIn applications must be explicitly attributed"
    assert sources.get("greenhouse", 0) > 0, "Greenhouse applications must be explicitly attributed"

    for app in res.get("applications", []):
        src = app.get("source")
        assert src != "manual", f"Application {app.get('id')} has unmigrated 'manual' source"

    print("✅ Tracking applied attribution & SQLite migration verified.\n")


def test_css_and_js_badge_contracts():
    print("--- 4. Testing CSS & JS Front-End Contracts ---")
    css_path = os.path.join(os.path.dirname(__file__), "..", "src", "ui", "static", "styles.css")
    js_path = os.path.join(os.path.dirname(__file__), "..", "src", "ui", "static", "app.js")

    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    expected_classes = [
        "badge-linkedin-easy",
        "badge-linkedin-ext",
        "badge-greenhouse",
        "badge-lever",
        "badge-ashby",
        "badge-workday",
        "badge-generic-ats",
    ]
    for cls in expected_classes:
        assert f".{cls}" in css or f".source-pill.{cls}" in css, f"Missing CSS class '{cls}' in styles.css"
        print(f"  ✓ Found CSS class: .{cls}")

    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "function formatSourceBadge(" in js, "Missing formatSourceBadge function in app.js"
    assert "formatSourceBadge(job.source_platform" in js or "formatSourceBadge(job.source" in js, (
        "formatSourceBadge not used in app.js"
    )
    assert "formatSourceBadge(app.source" in js, "formatSourceBadge not used for tracking cards in app.js"
    print("  ✓ formatSourceBadge helper contracts verified in app.js")

    print("✅ CSS and JS front-end contracts passed.\n")


def main():
    print("======================================================================")
    print(" Verification Gate 64: Source Badge Attribution & Metadata Accuracy  ")
    print("======================================================================\n")

    test_source_normalization_heuristics()
    test_api_approved_jobs_attribution()
    test_api_tracking_applied_attribution()
    test_css_and_js_badge_contracts()

    print("======================================================================")
    print(" GATE 64 PASSED: 100% SUCCESS across normalizer, API, DB & UI styles  ")
    print("======================================================================")


if __name__ == "__main__":
    main()
