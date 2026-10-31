"""
Verification Gate 80: Log-Grounded Submission Verification Gate & False-Positive Guardrails.

Validates:
1. SubmissionVerifier audits autofill_events.jsonl and rejects jobs without genuine confirmation events.
2. POST /api/tracking/mark-applied/{job_id} strictly rejects unverified jobs with HTTP 412 Precondition Failed.
3. SubmissionVerifier.record_submission_confirmed logs standardized events and attaches valid screenshots.
4. GET /api/tracking/verify/{job_id} reflects live verification status.
5. POST /api/tracking/mark-applied/{job_id} succeeds (HTTP 200) once verified.
6. force=true query param enables emergency human override on mark-applied.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from starlette.testclient import TestClient

from src.autofill.autofill_logger import SCREENSHOTS_DIR
from src.autofill.autofill_verifier import SubmissionVerifier
from src.storage.database import ApplicationDatabase
from src.ui.app import APPROVED_DIR, app

client = TestClient(app)

TEST_JOB_ID_UNVERIFIED = "gate80_unverified_job_999"
TEST_JOB_ID_VERIFIED = "gate80_verified_job_888"


def setup_test_job(job_id: str, company: str = "Guardrail Corp") -> Path:
    os.makedirs(APPROVED_DIR, exist_ok=True)
    job_file = Path(APPROVED_DIR) / f"{job_id}.json"
    dummy_pdf = Path(APPROVED_DIR) / f"Manjunath_HK_{company}_{job_id}_Resume.pdf"
    dummy_pdf.write_text("Dummy PDF Content")

    payload = {
        "job_id": job_id,
        "source": "linkedin",
        "url": f"https://www.linkedin.com/jobs/view/{job_id}/",
        "application_type": "EASY_APPLY",
        "job_details": {
            "title": "Lead SDET Architect",
            "company": company,
            "location": "Bengaluru, India",
        },
        "generated_pdf_path": str(dummy_pdf.resolve()),
    }
    with open(job_file, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return job_file


def cleanup_test_job(job_id: str):
    for f in Path(APPROVED_DIR).glob(f"*{job_id}*"):
        try:
            os.remove(f)
        except Exception:
            pass

    db = ApplicationDatabase()
    try:
        db.delete_application(job_id)
    except Exception:
        pass


@pytest.mark.asyncio
async def test_unverified_job_fails_precondition_gate():
    print("\n🧪 Step 1: Testing that unverified job fails with HTTP 412...")
    setup_test_job(TEST_JOB_ID_UNVERIFIED, company="Unverified Inc")

    try:
        # Verify verifier returns verified=False
        res_verif = SubmissionVerifier.verify_submission(TEST_JOB_ID_UNVERIFIED)
        assert res_verif["verified"] is False, f"Expected unverified, got: {res_verif}"
        assert "No SUBMISSION_CONFIRMED event found" in res_verif["reason"]

        # Attempt to mark applied via API -> MUST RETURN HTTP 412
        resp = client.post(f"/api/tracking/mark-applied/{TEST_JOB_ID_UNVERIFIED}")
        assert resp.status_code == 412, f"Expected HTTP 412, got: {resp.status_code} - {resp.text}"
        body = resp.json()
        detail = body.get("detail", {})
        assert detail.get("error") == "PRECONDITION_FAILED"
        assert TEST_JOB_ID_UNVERIFIED in detail.get("message", "")
        print("   ✅ Gate successfully blocked unverified application with HTTP 412!")
    finally:
        cleanup_test_job(TEST_JOB_ID_UNVERIFIED)


@pytest.mark.asyncio
async def test_submission_recording_and_verified_tracking():
    print("\n🧪 Step 2: Testing recording confirmation and successful gated tracking...")
    setup_test_job(TEST_JOB_ID_VERIFIED, company="Verified Systems")

    try:
        # Create a dummy screenshot to simulate real visual capture
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        dummy_screenshot = SCREENSHOTS_DIR / f"confirmation_test_{TEST_JOB_ID_VERIFIED}_{int(time.time())}.png"
        dummy_screenshot.write_text("fake screenshot data")

        # Record genuine submission confirmation
        await SubmissionVerifier.record_submission_confirmed(
            job_id=TEST_JOB_ID_VERIFIED,
            company="Verified Systems",
            marker_type="linkedin_modal",
            marker_text="Application sent",
            screenshot_path=str(dummy_screenshot),
        )

        # Audit with verify_submission
        verif = SubmissionVerifier.verify_submission(TEST_JOB_ID_VERIFIED)
        assert verif["verified"] is True, f"Expected verified=True, got: {verif}"
        assert verif["job_id"] == TEST_JOB_ID_VERIFIED
        assert verif["screenshot_exists"] is True
        print("   ✅ SubmissionVerifier successfully audited and approved confirmation event!")

        # Query GET /api/tracking/verify/{job_id}
        get_resp = client.get(f"/api/tracking/verify/{TEST_JOB_ID_VERIFIED}")
        assert get_resp.status_code == 200
        assert get_resp.json().get("verified") is True
        print("   ✅ GET /api/tracking/verify endpoint returned verified=True!")

        # Attempt POST /api/tracking/mark-applied/{job_id} -> MUST SUCCEED with HTTP 200
        post_resp = client.post(f"/api/tracking/mark-applied/{TEST_JOB_ID_VERIFIED}")
        assert post_resp.status_code == 200, f"Expected HTTP 200, got: {post_resp.status_code} - {post_resp.text}"
        post_data = post_resp.json()
        assert post_data.get("status") == "success"
        print("   ✅ Verified application successfully transitioned to 'applied' in SQLite!")

        # Verify database record
        db = ApplicationDatabase()
        app_rec = db.get_application(TEST_JOB_ID_VERIFIED)
        assert app_rec is not None
        assert app_rec.get("status") == "applied"
    finally:
        cleanup_test_job(TEST_JOB_ID_VERIFIED)
        if dummy_screenshot.exists():
            try:
                os.remove(dummy_screenshot)
            except Exception:
                pass


@pytest.mark.asyncio
async def test_human_override_force_param():
    print("\n🧪 Step 3: Testing emergency human override parameter (?force=true)...")
    override_jid = "gate80_override_777"
    setup_test_job(override_jid, company="Override Technologies")

    try:
        # Standard call fails with 412
        resp_blocked = client.post(f"/api/tracking/mark-applied/{override_jid}")
        assert resp_blocked.status_code == 412

        # Override call with ?force=true succeeds
        resp_forced = client.post(f"/api/tracking/mark-applied/{override_jid}?force=true")
        assert resp_forced.status_code == 200, f"Expected 200 with force=true, got {resp_forced.status_code}"
        assert resp_forced.json().get("status") == "success"
        print("   ✅ Human override (?force=true) successfully permitted manual transition!")
    finally:
        cleanup_test_job(override_jid)


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_unverified_job_fails_precondition_gate())
    asyncio.run(test_submission_recording_and_verified_tracking())
    asyncio.run(test_human_override_force_param())
    print("\n🎉 ALL GATE 80 TESTS PASSED WITH 100% SUCCESS!\n")
