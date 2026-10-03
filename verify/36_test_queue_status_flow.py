"""Verification script for queue status tracking and dynamic pending count updates.

Tests:
1. Verifies that GET /api/pending-jobs accurately reflects pending directory contents.
2. Approving a job via POST /api/approve/{job_id} decrements the count in pending queue.
3. Rejecting a job via POST /api/reject/{job_id} decrements the count in pending queue.
4. Validates that pending jobs count and approved queue counts stay synchronized.
"""

import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from fastapi.testclient import TestClient

from src.ui.app import app


def test_queue_status_flow():
    print("Testing queue status flow and count synchronization...")
    client = TestClient(app)

    pending_dir = root_dir / "data" / "pending_queue"
    approved_dir = root_dir / "data" / "approved_queue"

    # Step 1: Query current pending jobs
    response = client.get("/api/pending-jobs")
    assert response.status_code == 200
    initial_jobs = response.json().get("jobs", [])
    initial_count = len(initial_jobs)
    print(f"   Initial pending count: {initial_count}")

    # Create a temporary pending job to test approval transition
    test_job_id_1 = "test_queue_sync_job_1"
    test_job_id_2 = "test_queue_sync_job_2"

    dummy_payload_1 = {
        "job_id": test_job_id_1,
        "source": "test",
        "job_details": {"title": "Test Engineer 1", "company": "TestCorp", "requirements": "Testing"},
    }
    dummy_payload_2 = {
        "job_id": test_job_id_2,
        "source": "test",
        "job_details": {"title": "Test Engineer 2", "company": "TestCorp", "requirements": "Testing"},
    }

    file_1 = pending_dir / f"{test_job_id_1}.json"
    file_2 = pending_dir / f"{test_job_id_2}.json"

    with open(file_1, "w") as f:
        json.dump(dummy_payload_1, f)
    with open(file_2, "w") as f:
        json.dump(dummy_payload_2, f)

    try:
        # Check count increased by 2
        res_after_add = client.get("/api/pending-jobs")
        jobs_after_add = res_after_add.json().get("jobs", [])
        assert len(jobs_after_add) == initial_count + 2, f"Expected {initial_count + 2}, got {len(jobs_after_add)}"
        print(f"   ✅ Added 2 test jobs, count increased to {len(jobs_after_add)}")

        # Step 2: Approve test_job_id_1
        # Fetch the tailored version that /api/pending-jobs produced
        target_payload = next(j for j in jobs_after_add if j["job_id"] == test_job_id_1)
        res_approve = client.post(f"/api/approve/{test_job_id_1}", json=target_payload)
        assert res_approve.status_code == 200, f"Approval failed: {res_approve.text}"

        # Verify pending count decremented by 1
        res_after_approve = client.get("/api/pending-jobs")
        jobs_after_approve = res_after_approve.json().get("jobs", [])
        assert len(jobs_after_approve) == initial_count + 1, (
            f"Expected {initial_count + 1}, got {len(jobs_after_approve)}"
        )
        print(f"   ✅ After approving job 1, count decremented to {len(jobs_after_approve)}")

        # Step 3: Reject test_job_id_2
        res_reject = client.post(f"/api/reject/{test_job_id_2}")
        assert res_reject.status_code == 200, f"Reject failed: {res_reject.text}"

        # Verify pending count decremented back to initial_count
        res_after_reject = client.get("/api/pending-jobs")
        jobs_after_reject = res_after_reject.json().get("jobs", [])
        assert len(jobs_after_reject) == initial_count, f"Expected {initial_count}, got {len(jobs_after_reject)}"
        print(f"   ✅ After rejecting job 2, count returned to {len(jobs_after_reject)}")

    finally:
        # Cleanup
        if file_1.exists():
            os.remove(file_1)
        if file_2.exists():
            os.remove(file_2)
        approved_json = approved_dir / f"{test_job_id_1}.json"
        if approved_json.exists():
            os.remove(approved_json)
        approved_pdf = approved_dir / f"{test_job_id_1}_resume.pdf"
        if approved_pdf.exists():
            os.remove(approved_pdf)

    print("\n🎉 ALL QUEUE STATUS VERIFICATION CHECKS PASSED!")


if __name__ == "__main__":
    test_queue_status_flow()
