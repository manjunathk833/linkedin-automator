#!/usr/bin/env python3
"""
Verification Gate 71: Referral Reconnaissance URL Parameterization & Direct Job Link Note.
Validates:
1. Search URL Parameterization: Asserts zero occurrences of empty quotes '%22%22' across all 7 approved jobs.
2. Targeted Company & Location: Asserts exact company names and Indian tech hub markers (%20India) in search URLs.
3. Direct Job Link Inclusion: Asserts direct clean job posting URLs are weaved into connection notes and InMail pitches.
4. Strict Character Constraints: Mathematically asserts connection notes <= 300 chars and InMail pitches <= 1000 chars across all approved jobs and stress test payloads.
5. FastAPI Endpoint: Validates /api/referral/generate/{job_id} on live application instance.
"""

import asyncio
import json
import os
import sys
import urllib.parse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import httpx

from src.tailor.referral_generator import (
    CANDIDATE_PORTFOLIO,
    ReferralNoteGenerator,
    clean_job_url,
    extract_company_name,
    extract_job_title,
    extract_job_url,
    extract_location,
    extract_requisition_id,
)
from src.ui.app import app

APPROVED_DIR = os.path.join(PROJECT_ROOT, "data", "approved_queue")


def ensure_approved_fixtures():
    """Ensures at least 7 approved job fixtures exist for CI/isolated runners."""
    os.makedirs(APPROVED_DIR, exist_ok=True)
    existing = [f for f in os.listdir(APPROVED_DIR) if f.endswith(".json")]
    if len(existing) >= 7:
        return

    sample_fixtures = [
        {
            "job_id": "greenhouse_okta_8236753",
            "source": "greenhouse",
            "is_dream_org": True,
            "job_details": {
                "title": "Senior Software Engineer in Test (SET) — Access Essentials",
                "company": "Okta",
                "location": "Bengaluru, India",
            },
            "job_url": "https://www.okta.com/company/careers/opportunity/8236753?gh_jid=8236753",
            "url": "https://www.okta.com/company/careers/opportunity/8236753?gh_jid=8236753",
        },
        {
            "job_id": "greenhouse_okta_8239048",
            "source": "greenhouse",
            "is_dream_org": True,
            "job_details": {
                "title": "Senior Software Engineer in Test (SET) — Identity Governance",
                "company": "Okta",
                "location": "Bengaluru, India",
            },
            "job_url": "https://www.okta.com/company/careers/opportunity/8239048?gh_jid=8239048",
            "url": "https://www.okta.com/company/careers/opportunity/8239048?gh_jid=8239048",
        },
        {
            "job_id": "workday_crowdstrike_r28268",
            "source": "workday",
            "is_dream_org": True,
            "job_details": {
                "title": "Engineer III – Cloud SDET",
                "company": "CrowdStrike",
                "location": "India - Bangalore",
            },
            "job_url": "https://crowdstrike.wd5.myworkdayjobs.com/crowdstrikecareers/job/India---Bangalore/Engineer-III---Cloud-SDET_R28268",
            "url": "https://crowdstrike.wd5.myworkdayjobs.com/crowdstrikecareers/job/India---Bangalore/Engineer-III---Cloud-SDET_R28268",
        },
        {
            "job_id": "4462037180",
            "source": "linkedin",
            "is_dream_org": False,
            "job_details": {
                "title": "Senior SDET",
                "company": "GE HealthCare",
                "location": "Bengaluru, Karnataka, India (On-site)",
            },
            "job_url": "https://www.linkedin.com/jobs/view/4462037180/",
            "url": "https://www.linkedin.com/jobs/view/4462037180/",
        },
        {
            "job_id": "4305570106",
            "source": "linkedin",
            "is_dream_org": False,
            "job_details": {
                "title": "Senior SDET - Hadoop Observability",
                "company": "Acceldata",
                "location": "Bengaluru, Karnataka, India (On-site)",
            },
            "job_url": "https://www.linkedin.com/jobs/view/4305570106/",
            "url": "https://www.linkedin.com/jobs/view/4305570106/",
        },
        {
            "job_id": "4470900213",
            "source": "linkedin",
            "is_dream_org": False,
            "job_details": {
                "title": "Senior Software Development Engineer in Test (SDET)",
                "company": "Akamai Technologies",
                "location": "Bengaluru, Karnataka, India (On-site)",
            },
            "job_url": "https://www.linkedin.com/jobs/view/4470900213/",
            "url": "https://www.linkedin.com/jobs/view/4470900213/",
        },
        {
            "job_id": "4471929554",
            "source": "linkedin",
            "is_dream_org": False,
            "job_details": {
                "title": "Senior Software Engineer I, Quality",
                "company": "SurveyMonkey",
                "location": "Bengaluru, Karnataka, India (On-site)",
            },
            "job_url": "https://www.linkedin.com/jobs/view/4471929554/",
            "url": "https://www.linkedin.com/jobs/view/4471929554/",
        },
    ]

    for fix in sample_fixtures:
        path = os.path.join(APPROVED_DIR, f"{fix['job_id']}.json")
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(fix, f, indent=2)


def test_approved_queue_jobs_referral_pack():
    print("\n--- 1. Testing Referral Packs Across All Approved Queue Jobs ---")
    ensure_approved_fixtures()

    approved_files = [f for f in os.listdir(APPROVED_DIR) if f.endswith(".json")]
    assert len(approved_files) >= 7, f"Expected at least 7 approved jobs, found {len(approved_files)}"

    for filename in sorted(approved_files):
        filepath = os.path.join(APPROVED_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            payload = json.load(f)

        company = extract_company_name(payload)
        title = extract_job_title(payload)
        extract_location(payload)
        job_url = extract_job_url(payload)
        clean_url = clean_job_url(job_url)
        req_id = extract_requisition_id(payload)

        assert company, f"Failed to extract company from {filename}"
        assert title, f"Failed to extract title from {filename}"
        assert req_id and req_id != "open req", f"Failed to extract req ID from {filename}"

        pack = ReferralNoteGenerator.generate_referral_pack(payload, recipient_name="there")

        # 1. Assert Company Name and Job Title
        assert pack["company_name"] == company
        assert pack["job_title"] == title

        # 2. Assert LinkedIn Search URLs Parameterization (Zero Empty Quotes)
        urls = pack["search_urls"]
        for key in ["engineering_managers", "qa_leads", "tech_leads", "alumni"]:
            assert key in urls, f"Missing key {key} in search_urls for {filename}"
            url_str = urls[key]
            assert "%22%22" not in url_str, f"Found empty quotes '%22%22' in {key} search URL for {filename}: {url_str}"
            encoded_company = urllib.parse.quote(company)
            assert encoded_company in url_str or company.replace(" ", "%20") in url_str or company in url_str, (
                f"Company {company} missing from {key} URL: {url_str}"
            )
            # All 7 approved jobs are in India / Bengaluru
            assert "%20India" in url_str, f"Location token %20India missing from {key} URL: {url_str}"

        # 3. Assert Connection Request Note Bounds and Direct Job Link
        conn_note = pack["connection_note"]
        conn_chars = pack["connection_note_chars"]
        assert len(conn_note) <= 300, (
            f"Connection note exceeded 300 chars ({len(conn_note)}) for {filename}: {conn_note}"
        )
        assert conn_chars <= 300, f"Reported connection note chars ({conn_chars}) exceeded 300 for {filename}"
        assert conn_chars == len(conn_note)

        # Assert direct job link is in connection note
        if clean_url:
            assert clean_url in conn_note, (
                f"Clean job URL {clean_url} missing from connection note for {filename}: {conn_note}"
            )
        assert req_id in conn_note, f"Requisition ID {req_id} missing from connection note for {filename}"
        assert company in conn_note, f"Company {company} missing from connection note for {filename}"

        # 4. Assert InMail Pitch Bounds and Job Link
        inmail = pack["inmail_pitch"]
        inmail_chars = pack["inmail_pitch_chars"]
        assert len(inmail) <= 1000, f"InMail pitch exceeded 1000 chars ({len(inmail)}) for {filename}"
        assert inmail_chars <= 1000
        assert req_id in inmail
        assert company in inmail
        if clean_url:
            assert clean_url in inmail
        assert CANDIDATE_PORTFOLIO in inmail

        print(
            f"  ✅ [{filename}] {company} - '{title[:30]}...' (Req: {req_id}): Note={len(conn_note)}/300 chars, InMail={len(inmail)}/1000 chars, Clean Search URLs verified."
        )


def test_stress_test_character_limits():
    print("\n--- 2. Stress Testing Boundary Constraints (Long Names, Long Titles, Long URLs) ---")

    long_payload = {
        "job_id": "workday_extreme_stress_test",
        "company_name": "UltraLongCorporationName Technologies",
        "job_title": "Lead Principal Staff Software Development Engineer in Test and Cloud Distributed Systems Automation Architect",
        "location": "Bengaluru, Karnataka, India",
        "url": "https://ultralongcorporation.wd5.myworkdayjobs.com/careers/job/India---Bangalore---Manyata-Embassy-Business-Park/Lead-Principal-Staff-Software-Development-Engineer-in-Test_R999999999999",
        "requisition_id": "R999999999999",
    }

    # Test with long recipient name
    pack = ReferralNoteGenerator.generate_referral_pack(long_payload, recipient_name="Bartholomew-Alexander")
    conn_note = pack["connection_note"]
    assert len(conn_note) <= 300, (
        f"Stress test failed: connection note exceeded 300 chars ({len(conn_note)}): {conn_note}"
    )
    assert "UltraLongCorporationName" in conn_note
    assert "https://ultralongcorporation.wd5.myworkdayjobs.com" in conn_note
    print(f"  ✅ Stress test passed: Long payload + long name strictly bounded to {len(conn_note)}/300 characters.")


async def test_fastapi_referral_endpoint():
    print("\n--- 3. Testing FastAPI Referral Generate Endpoint on Approved Queue ---")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Test Okta
        res_okta = await client.get("/api/referral/generate/greenhouse_okta_8236753")
        assert res_okta.status_code == 200, f"Failed Okta referral generation: {res_okta.text}"
        data_okta = res_okta.json()
        assert data_okta["status"] == "success"
        pack_okta = data_okta["referral_pack"]
        assert pack_okta["company_name"] == "Okta"
        assert "%22Okta%22" in pack_okta["search_urls"]["engineering_managers"]
        assert "%22%22" not in pack_okta["search_urls"]["engineering_managers"]
        assert len(pack_okta["connection_note"]) <= 300
        assert "https://www.okta.com/company/careers/opportunity/8236753" in pack_okta["connection_note"]

        # Test CrowdStrike (Workday)
        res_cs = await client.get("/api/referral/generate/workday_crowdstrike_r28268")
        assert res_cs.status_code == 200, f"Failed CrowdStrike referral generation: {res_cs.text}"
        data_cs = res_cs.json()
        pack_cs = data_cs["referral_pack"]
        assert pack_cs["company_name"] == "CrowdStrike"
        assert "%22CrowdStrike%22" in pack_cs["search_urls"]["qa_leads"]
        assert len(pack_cs["connection_note"]) <= 300
        assert "https://crowdstrike.wd5.myworkdayjobs.com" in pack_cs["connection_note"]

        print("  ✅ FastAPI endpoints successfully returned valid referral packs for Okta and CrowdStrike.")


def main():
    test_approved_queue_jobs_referral_pack()
    test_stress_test_character_limits()
    asyncio.run(test_fastapi_referral_endpoint())
    print("\n🎉 ALL REFERRAL RECONNAISSANCE VERIFICATION CHECKS PASSED (100% SUCCESS)!\n")


if __name__ == "__main__":
    main()
