#!/usr/bin/env python3
"""
Verification Gate 62: User-Driven Applied Trigger & Complete Approved Queue Temp Purge.
Validates:
1. Disentanglement: Launching Copilot or Manual Apply does NOT set status to 'applied' in DB
   and does NOT purge the job from data/approved_queue/.
2. Repeat Click Safety: Multiple browser launches or approvals never prematurely mark a job as applied.
3. Explicit User-Driven Trigger: Only explicit mark-applied updates DB status to 'applied'.
4. Complete Temp Purge: All temporary JSON and PDF files in data/approved_queue/ are purged,
   with the compiled resume archived to data/resumes/ and accessible via /api/pdf/{job_id}.
5. Cleanup Endpoint: POST /api/approved/cleanup sweeps orphaned files leaving queue pristine.
"""

import json
import os
import sys
import time

# Ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from src.storage.database import ApplicationDatabase
from src.ui.app import APPROVED_DIR, RESUMES_DIR, app


def test_copilot_and_manual_apply_do_not_mark_applied():
    print("\n--- [Step 1: Copilot & Manual Apply Isolation from Applied Status] ---")
    db = ApplicationDatabase()
    client = TestClient(app)

    job_id = f"test_user_trigger_{int(time.time())}"
    os.makedirs(APPROVED_DIR, exist_ok=True)
    json_path = os.path.join(APPROVED_DIR, f"{job_id}.json")
    pdf_path = os.path.join(APPROVED_DIR, f"Manjunath_HK_TriggerTest_{job_id}_Resume.pdf")

    # Create dummy approved JSON and dummy PDF
    payload = {
        "job_id": job_id,
        "source": "greenhouse",
        "job_details": {
            "company": "TriggerTest Technologies",
            "title": "Lead SDET Engineer",
            "location": "Bengaluru",
        },
        "url": f"https://boards.greenhouse.io/triggertest/{job_id}",
        "generated_pdf_path": pdf_path,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4 dummy resume content for verification gate 62")

    # Assert job is visible in approved jobs API
    resp = client.get("/api/approved-jobs")
    assert resp.status_code == 200
    approved_list = resp.json().get("jobs", [])
    assert any(j["job_id"] == job_id for j in approved_list), "Job should be visible in approved queue"
    print("✓ Job successfully visible in Approved Queue.")

    # Record a launch audit event (simulating copilot or manual apply launch)
    db.record_application(
        job_id=job_id,
        source="greenhouse",
        company_name="TriggerTest Technologies",
        job_title="Lead SDET Engineer",
        job_url=payload["url"],
        resume_path=pdf_path,
        status="copilot_launched",
    )

    # CRITICAL CHECK: is_job_applied MUST BE FALSE
    assert db.is_job_applied(job_id) is False, (
        "CRITICAL BUG: is_job_applied returned True after copilot launch! Should only be True on explicit 'applied' status."
    )
    assert job_id not in db.get_applied_job_ids(), (
        "CRITICAL BUG: job_id found in get_applied_job_ids() after copilot launch!"
    )
    print("✓ Verified: Launching Copilot DOES NOT mark job as applied in SQLite database.")

    # Second launch audit event (simulating manual apply click)
    db.record_application(
        job_id=job_id,
        source="greenhouse",
        company_name="TriggerTest Technologies",
        job_title="Lead SDET Engineer",
        job_url=payload["url"],
        resume_path=pdf_path,
        status="manual_takeover_opened",
    )

    assert db.is_job_applied(job_id) is False, (
        "CRITICAL BUG: is_job_applied returned True after manual takeover opened!"
    )
    print("✓ Verified: Multiple clicks or manual takeover DOES NOT mark job as applied.")

    # Re-fetch approved jobs API -> Job MUST NOT be purged
    resp2 = client.get("/api/approved-jobs")
    assert resp2.status_code == 200
    approved_list_2 = resp2.json().get("jobs", [])
    assert any(j["job_id"] == job_id for j in approved_list_2), (
        "CRITICAL BUG: Job was purged from approved queue simply because copilot/manual apply was launched!"
    )
    assert os.path.exists(json_path), "JSON file must still exist in approved_queue"
    assert os.path.exists(pdf_path), "PDF file must still exist in approved_queue"
    print("✓ Verified: Job is NOT purged from approved queue upon browser launch.")

    return job_id, json_path, pdf_path


def test_explicit_user_driven_mark_applied_and_temp_purge(job_id: str, json_path: str, pdf_path: str):
    print("\n--- [Step 2: Explicit User-Driven Mark Applied & Complete Temp Purge] ---")
    client = TestClient(app)
    db = ApplicationDatabase()

    pdf_filename = os.path.basename(pdf_path)
    archived_pdf_path = os.path.join(RESUMES_DIR, pdf_filename)

    # Now simulate the explicit user-driven trigger: POST /api/tracking/mark-applied/{job_id}
    mark_resp = client.post(f"/api/tracking/mark-applied/{job_id}")
    assert mark_resp.status_code == 200, f"Expected 200, got: {mark_resp.text}"
    body = mark_resp.json()
    assert body["status"] == "success"
    print(f"✓ Mark applied API returned success: {body['message']}")

    # 1. Assert DB is now marked 'applied'
    assert db.is_job_applied(job_id) is True, "Job MUST be marked applied after explicit user action!"
    assert job_id in db.get_applied_job_ids(), "Job ID MUST be in get_applied_job_ids() after mark-applied!"
    print("✓ SQLite database successfully updated to status = 'applied'.")

    # 2. Assert temp files in data/approved_queue/ are completely purged
    assert not os.path.exists(json_path), f"Temp JSON {json_path} was NOT purged from approved_queue!"
    assert not os.path.exists(pdf_path), f"Temp PDF {pdf_path} was NOT purged from approved_queue!"
    print("✓ Verified: All temporary JSON and PDF files in data/approved_queue/ are 100% purged.")

    # 3. Assert PDF was safely archived into data/resumes/
    assert os.path.exists(archived_pdf_path), f"Archived PDF {archived_pdf_path} was NOT found in resumes directory!"
    print(f"✓ Tailored PDF safely archived to: {archived_pdf_path}")

    # 4. Assert /api/pdf/{job_id} still serves the archived PDF cleanly
    pdf_resp = client.get(f"/api/pdf/{job_id}")
    assert pdf_resp.status_code == 200, f"Expected 200 from /api/pdf/{job_id}, got {pdf_resp.status_code}"
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert b"dummy resume content" in pdf_resp.content
    print("✓ /api/pdf/{job_id} successfully serves the archived PDF without 404.")

    # 5. Clean up archived PDF and database record
    if os.path.exists(archived_pdf_path):
        os.remove(archived_pdf_path)
    db.delete_application(job_id)
    assert db.is_job_applied(job_id) is False
    print("✓ Test cleanup completed.")


def test_approved_queue_cleanup_routine():
    print("\n--- [Step 3: Approved Queue Cleanup Routine & Endpoint] ---")
    client = TestClient(app)

    # Place an orphaned PDF in approved_queue
    orphaned_pdf = os.path.join(APPROVED_DIR, "orphaned_test_file_123.pdf")
    with open(orphaned_pdf, "wb") as f:
        f.write(b"%PDF orphaned test")

    assert os.path.exists(orphaned_pdf)

    # Call cleanup endpoint
    resp = client.post("/api/approved/cleanup")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    # Assert orphaned file is purged
    assert not os.path.exists(orphaned_pdf), "Orphaned PDF was not purged by cleanup routine!"
    print("✓ Approved queue cleanup routine verified: sweeps orphaned temp files.")


def main():
    print("=" * 70)
    print("RUNNING VERIFICATION GATE 62: USER-DRIVEN APPLIED & APPROVED PURGE")
    print("=" * 70)

    job_id, json_path, pdf_path = test_copilot_and_manual_apply_do_not_mark_applied()
    test_explicit_user_driven_mark_applied_and_temp_purge(job_id, json_path, pdf_path)
    test_approved_queue_cleanup_routine()

    print("\n" + "=" * 70)
    print("ALL VERIFICATION GATE 62 TESTS PASSED SUCCESSFULLY! (100%)")
    print("=" * 70)


if __name__ == "__main__":
    main()
