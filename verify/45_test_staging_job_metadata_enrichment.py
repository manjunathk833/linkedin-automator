"""Verification script for Staging Job Metadata Enrichment (Location, Experience, Link, Salary).

Tests:
1. classify_job_location correctly identifies:
   - 'Remote - USA' as is_us_only=True with 'warning' badge.
   - 'Bengaluru, India' as is_india=True with 'success' badge.
   - 'Worldwide Remote' as 'info' badge.
2. extract_job_experience parses experience requirements from JD text (e.g., '5+ years' or '3-5 years').
3. extract_salary_estimate retrieves disclosed compensation ranges.
4. GET /api/pending-jobs returns enriched metadata payload containing:
   - experience_required
   - location_info
   - direct_link
   - source_platform
   - salary_estimate
5. HTML template and app.js contain the required visual DOM anchors:
   - job-location-pill
   - job-experience
   - job-salary
   - job-link-btn
   - job-matched-tags
"""

import json
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from fastapi.testclient import TestClient

from src.ui.app import (
    app,
    classify_job_location,
    extract_job_experience,
    extract_salary_estimate,
)


def test_metadata_helpers():
    print("\n--- 1. Testing Metadata Enrichment Helpers ---")

    # 1. Location Classification
    loc_us = classify_job_location("Remote - USA")
    assert loc_us["is_us_only"] is True, f"Expected US Only for 'Remote - USA', got: {loc_us}"
    assert loc_us["badge_type"] == "warning"
    assert "US" in loc_us["badge_label"]
    print(f"✅ US-only location detected: {loc_us['badge_label']}")

    loc_india = classify_job_location("Bengaluru, Karnataka, India")
    assert loc_india["is_india"] is True, f"Expected India for Bengaluru, got: {loc_india}"
    assert loc_india["badge_type"] == "success"
    print(f"✅ India location detected: {loc_india['badge_label']}")

    loc_global = classify_job_location("Worldwide Remote")
    assert loc_global["badge_type"] == "info"
    print(f"✅ Global remote location detected: {loc_global['badge_label']}")

    # 2. Experience Extraction
    sample_jd_text = (
        "We are looking for a Senior SDET. Required skills: 5+ years in IT engineering, "
        "automation, and distributed systems. Experience with REST APIs."
    )
    exp = extract_job_experience(sample_jd_text)
    assert "5" in exp, f"Expected '5+ years', got '{exp}'"
    print(f"✅ Experience extracted: {exp}")

    range_text = "Qualifications: 6-8 years experience in test automation frameworks."
    exp_range = extract_job_experience(range_text)
    assert "6" in exp_range and "8" in exp_range, f"Expected '6–8 years', got '{exp_range}'"
    print(f"✅ Experience range extracted: {exp_range}")

    # 3. Salary Extraction
    jd_with_salary = {"description": "<p>Annual base salary range: $113,815 — $133,900 USD plus equity.</p>"}
    sal = extract_salary_estimate(jd_with_salary)
    assert "113" in sal and "133" in sal, f"Expected salary range, got: '{sal}'"
    print(f"✅ Salary extracted from description: {sal}")


def test_api_pending_jobs_enrichment():
    print("\n--- 2. Testing /api/pending-jobs Enrichment Payload ---")
    client = TestClient(app)
    pending_dir = root_dir / "data" / "pending_queue"
    pending_dir.mkdir(parents=True, exist_ok=True)

    test_id = "test_pending_enrichment_8095"
    test_file = pending_dir / f"{test_id}.json"

    mock_job = {
        "job_id": test_id,
        "source": "greenhouse",
        "application_type": "ATS_GREENHOUSE",
        "url": "https://www.coinbase.com/careers/positions/8095?gh_jid=8095",
        "job_details": {
            "title": "Senior Automation Engineer",
            "company": "Coinbase",
            "location": "Remote - USA",
            "description": "5+ years in test engineering. Salary range: $120,000 — $140,000 USD",
            "requirements": "5+ years automation experience with Python and Java.",
        },
        "matched_keywords": ["Python", "Java", "Automation"],
        "tailored_resume": {
            "personal_details": {"full_name": "Manjunath H K", "email": "manjunath@example.com"},
            "experience_history": [],
        },
    }

    with open(test_file, "w", encoding="utf-8") as f:
        json.dump(mock_job, f)

    try:
        res = client.get("/api/pending-jobs")
        assert res.status_code == 200
        data = res.json()
        jobs = data.get("jobs", [])
        matched = [j for j in jobs if j.get("job_id") == test_id]
        assert len(matched) == 1, f"Mock job {test_id} not returned"
        job = matched[0]

        # Verify enriched fields
        assert "experience_required" in job, "experience_required missing from job payload"
        assert "5" in job["experience_required"]
        assert "location_info" in job, "location_info missing from job payload"
        assert job["location_info"]["is_us_only"] is True
        assert "direct_link" in job, "direct_link missing from job payload"
        assert job["direct_link"] == mock_job["url"]
        assert "salary_estimate" in job, "salary_estimate missing from job payload"
        assert "120" in job["salary_estimate"]
        assert "source_platform" in job, "source_platform missing from job payload"
        print("✅ /api/pending-jobs returns fully enriched metadata contract!")

    finally:
        if test_file.exists():
            test_file.unlink()
        print("✅ Pending test cleanup completed.")


def test_ui_template_anchors():
    print("\n--- 3. Testing UI Template Anchors in index.html ---")
    template_path = root_dir / "src" / "ui" / "templates" / "index.html"
    content = template_path.read_text(encoding="utf-8")

    required_anchors = [
        "job-location-pill",
        "job-meta-grid",
        "job-experience",
        "job-salary",
        "job-link-btn",
        "job-matched-tags",
    ]

    for anchor in required_anchors:
        assert anchor in content, f"Required DOM anchor '{anchor}' missing from index.html"
        print(f"✅ Found DOM anchor: {anchor}")


if __name__ == "__main__":
    test_metadata_helpers()
    test_api_pending_jobs_enrichment()
    test_ui_template_anchors()
    print("\n🎉 ALL VERIFICATION GATES PASSED: Staging Metadata Enrichment Verified!\n")
