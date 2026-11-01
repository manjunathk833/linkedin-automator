#!/usr/bin/env python3
"""
Verification Gate 107: Test Mark Applied Error Formatting & Force Override Handling.
Validates that:
1. When mark-applied is called without verification evidence, HTTP 412 is returned with structured detail.
2. When ?force=true is supplied, the job is cleanly transitioned to applied in SQLite database and queues are updated.
"""

import json
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from src.storage.database import ApplicationDatabase
from src.ui.app import app


def test_mark_applied_verification_and_override():
    print("🧪 Running Gate 107: Mark Applied Verification & Manual Force Override...")
    client = TestClient(app)
    db = ApplicationDatabase()

    test_job_id = "test_manual_override_gate107"
    approved_dir = PROJECT_ROOT / "data" / "approved_queue"
    approved_dir.mkdir(parents=True, exist_ok=True)
    job_file = approved_dir / f"{test_job_id}.json"

    # Seed mock job in approved_queue
    payload = {
        "job_id": test_job_id,
        "company": "Swiggy Test",
        "title": "Staff SDET",
        "job_details": {
            "company": "Swiggy Test",
            "title": "Staff SDET",
            "location": "Bangalore, India",
        },
        "url": f"https://www.linkedin.com/jobs/view/{test_job_id}/",
    }
    job_file.write_text(json.dumps(payload, indent=2))

    try:
        # Step 1: Attempt mark-applied without verification -> must return HTTP 412
        res1 = client.post(f"/api/tracking/mark-applied/{test_job_id}")
        assert res1.status_code == 412, f"Expected 412, got {res1.status_code}"
        detail = res1.json().get("detail", {})
        assert isinstance(detail, dict), "Detail must be a structured dict"
        assert detail.get("error") == "PRECONDITION_FAILED", f"Unexpected error detail: {detail}"
        assert "SUBMISSION_CONFIRMED" in detail.get("message", ""), "Expected message explaining missing event"
        print("  ✓ Step 1 Passed: Unverified submission correctly blocked with HTTP 412 structured detail.")

        # Step 2: Attempt mark-applied with ?force=true -> must return HTTP 200 and persist
        res2 = client.post(f"/api/tracking/mark-applied/{test_job_id}?force=true")
        assert res2.status_code == 200, f"Expected 200 with force=true, got {res2.status_code}"
        body = res2.json()
        assert body.get("status") == "success"
        assert body.get("job_id") == test_job_id
        print("  ✓ Step 2 Passed: Manual human override ?force=true accepted with HTTP 200.")

        # Step 3: Verify recorded in SQLite database
        app_entry = db.get_application(test_job_id)
        assert app_entry is not None, "Expected job to be recorded in SQLite applications table"
        assert app_entry.get("company_name") == "Swiggy Test"
        print("  ✓ Step 3 Passed: Job verified recorded in SQLite application tracking.")

    finally:
        # Cleanup
        if job_file.exists():
            job_file.unlink()
        db.delete_application(test_job_id)

    print("✅ Gate 107 PASSED: Mark Applied Verification & Manual Override verified.")


if __name__ == "__main__":
    test_mark_applied_verification_and_override()
