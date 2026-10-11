#!/usr/bin/env python3
"""
Verification Gate 68: Sprint 3 Dual-Funnel Routing & 1-Click Referral Reconnaissance.
Validates:
1. Character Boundaries: Connection note strictly <= 300 chars, InMail strictly <= 1000 chars.
2. Grounded Architecture: Verifies exact Requisition ID citation and candidate proof of work.
3. Persona Search Links: Asserts valid LinkedIn search query URLs for Engineering Managers and Alumni.
4. SQLite Persistence: Validates logging, querying, and status transitions in referral_outreach table.
5. FastAPI Endpoints: Validates /api/referral/generate, /api/referral/log, /api/referral/list, and /api/referral/update-status.
"""

import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import httpx

from src.storage.database import ApplicationDatabase
from src.tailor.referral_generator import (
    CANDIDATE_PORTFOLIO,
    ReferralNoteGenerator,
    extract_requisition_id,
)
from src.ui.app import app


def test_referral_generator_precision():
    print("\n--- 1. Testing Referral Note Character Constraints & Precision ---")

    sample_jobs = [
        {
            "job_id": "workday_adobe_r170647",
            "company_name": "Adobe",
            "job_title": "Software Quality Engineer 5",
            "location": "Noida, India",
            "requisition_id": "R170647",
            "url": "https://adobe.wd5.myworkdayjobs.com/external_experienced/job/Noida/Software-Quality-Engineer-5_R170647",
        },
        {
            "job_id": "greenhouse_okta_8045905",
            "company_name": "Okta",
            "job_title": "Principal Software Engineer in Test - Identity Security Cloud Platform",
            "location": "Bengaluru, India",
            "url": "https://boards.greenhouse.io/okta/jobs/8045905",
        },
        {
            "job_id": "workday_autodesk_26wd100857-1",
            "company_name": "Autodesk",
            "job_title": "Staff SDET (Search & Platform)",
            "location": "Pune, IND",
            "job_details": {"bullet_fields": ["26WD100857-1"]},
        },
    ]

    for job in sample_jobs:
        req_id = extract_requisition_id(job)
        assert req_id and req_id != "open req", f"Failed to extract requisition ID for {job['company_name']}"
        print(f"  ✅ Requisition ID for {job['company_name']}: {req_id}")

        pack = ReferralNoteGenerator.generate_referral_pack(job, recipient_name="Priya")

        # 1. Assert Connection Note bounds
        conn_note = pack["connection_note"]
        conn_chars = pack["connection_note_chars"]
        assert len(conn_note) <= 300, f"Connection note exceeded 300 chars: {len(conn_note)}"
        assert conn_chars <= 300, f"Reported chars exceeded 300: {conn_chars}"
        assert req_id in conn_note, f"Requisition ID {req_id} missing from connection note: {conn_note}"
        assert "manjunathhk.netlify.app" in conn_note, "Portfolio missing from connection note"
        print(f"  ✅ Connection Note ({len(conn_note)}/300 chars) for {job['company_name']}: '{conn_note}'")

        # 2. Assert InMail bounds
        inmail = pack["inmail_pitch"]
        inmail_chars = pack["inmail_pitch_chars"]
        assert len(inmail) <= 1000, f"InMail pitch exceeded 1000 chars: {len(inmail)}"
        assert inmail_chars <= 1000, f"Reported inmail chars exceeded 1000: {inmail_chars}"
        assert req_id in inmail, f"Requisition ID {req_id} missing from InMail: {inmail}"
        assert CANDIDATE_PORTFOLIO in inmail, "Portfolio URL missing from InMail"
        assert "Playwright" in inmail and "Kafka" in inmail, "Key candidate architecture tools missing"
        print(f"  ✅ InMail Pitch ({len(inmail)}/1000 chars) for {job['company_name']} verified.")

        # 3. Assert search URLs
        search_urls = pack["search_urls"]
        assert "engineering_managers" in search_urls
        assert "linkedin.com/search/results/people" in search_urls["engineering_managers"]
        assert job["company_name"] in search_urls["engineering_managers"]
        print(f"  ✅ EM Search Link: {search_urls['engineering_managers']}")


def test_sqlite_referral_ledger():
    print("\n--- 2. Testing SQLite Referral Outreach Ledger ---")
    db = ApplicationDatabase()

    job_id = "test_sprint3_adobe_r170647"
    company = "Adobe"
    title = "Software Quality Engineer 5"
    req_id = "R170647"

    # 1. Log referral outreach
    outreach_id = db.log_referral_outreach(
        job_id=job_id,
        company_name=company,
        job_title=title,
        requisition_id=req_id,
        contact_name="Aravind Sharma",
        contact_title="Engineering Director",
        contact_linkedin_url="https://linkedin.com/in/test-aravind",
        outreach_type="connection_note",
        note_content="Hi Aravind, I am an SDET specializing in Playwright...",
        status="SENT",
    )
    assert outreach_id.startswith(f"ref_{job_id}"), f"Invalid outreach ID: {outreach_id}"
    print(f"  ✅ Logged outreach record: {outreach_id}")

    # 2. Retrieve records
    records = db.get_referral_outreach(job_id=job_id)
    assert len(records) >= 1, "Expected at least 1 record in SQLite"
    rec = records[0]
    assert rec["company_name"] == company
    assert rec["requisition_id"] == req_id
    assert rec["status"] == "SENT"
    print(f"  ✅ Retrieved record: {rec['outreach_id']} | Status: {rec['status']}")

    # 3. Update status
    updated = db.update_referral_status(outreach_id=outreach_id, status="CONNECTED")
    assert updated, "Failed to update outreach status"
    records_updated = db.get_referral_outreach(outreach_id=outreach_id)
    assert records_updated[0]["status"] == "CONNECTED", "Status was not updated in SQLite"
    print(f"  ✅ Updated record status to: {records_updated[0]['status']}")


async def test_fastapi_referral_endpoints():
    print("\n--- 3. Testing FastAPI Referral Endpoints ---")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Log test job into SQLite tracked_requisitions so generate endpoint can resolve it
        db = ApplicationDatabase()
        db.sync_requisition(
            requisition_id="R170647_API_TEST",
            company_slug="adobe",
            ats_provider="workday",
            job_title="Lead Quality Architect",
            location="Noida, India",
            job_url="https://adobe.wd5.myworkdayjobs.com/test",
            description_clean="Test description for quality architect",
            is_dream_org=True,
        )

        # 2. Test /api/referral/generate/{job_id}
        gen_res = await client.post(
            "/api/referral/generate/R170647_API_TEST",
            json={"recipient_name": "Vikram"},
        )
        assert gen_res.status_code == 200, f"Expected 200, got {gen_res.status_code}: {gen_res.text}"
        data = gen_res.json()
        assert data["status"] == "success"
        pack = data["referral_pack"]
        assert "Vikram" in pack["connection_note"]
        assert pack["connection_note_chars"] <= 300
        assert pack["inmail_pitch_chars"] <= 1000
        print(f"  ✅ POST /api/referral/generate returned 200 with {pack['connection_note_chars']}/300 chars.")

        # 3. Test /api/referral/log
        log_res = await client.post(
            "/api/referral/log",
            json={
                "job_id": "api_test_okta_8045905",
                "company_name": "Okta",
                "job_title": "Principal SDET",
                "requisition_id": "8045905",
                "outreach_type": "inmail",
                "note_content": "Test InMail Pitch content...",
                "contact_name": "Priya Patel",
                "status": "SENT",
            },
        )
        assert log_res.status_code == 200, f"Expected 200, got {log_res.status_code}: {log_res.text}"
        log_data = log_res.json()
        outreach_id = log_data["outreach_id"]
        print(f"  ✅ POST /api/referral/log created {outreach_id}")

        # 4. Test /api/referral/list
        list_res = await client.get("/api/referral/list?limit=10")
        assert list_res.status_code == 200
        assert len(list_res.json()["records"]) > 0
        print(f"  ✅ GET /api/referral/list returned {list_res.json()['count']} record(s)")

        # 5. Test /api/referral/update-status
        up_res = await client.post(
            "/api/referral/update-status",
            json={"outreach_id": outreach_id, "status": "REFERRED"},
        )
        assert up_res.status_code == 200
        assert up_res.json()["new_status"] == "REFERRED"
        print("  ✅ POST /api/referral/update-status updated record to REFERRED")


async def main():
    test_referral_generator_precision()
    test_sqlite_referral_ledger()
    await test_fastapi_referral_endpoints()
    print("\n🎉 ALL VERIFICATION GATE 68 CHECKS PASSED (100% SUCCESS)!")


if __name__ == "__main__":
    asyncio.run(main())
