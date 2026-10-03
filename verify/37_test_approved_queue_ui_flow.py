"""Verification script for Approved Queue API endpoints and PDF delivery.

Tests:
1. GET /api/approved-jobs returns list of approved jobs with company, title, PDF status, and budget.
2. GET /api/pdf/{job_id} returns 200 OK with content-type application/pdf.
3. DELETE /api/approved/{job_id} properly removes test job payload and PDF.
4. Verifies daily budget information structure from ApplicationGovernor.
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


def test_approved_queue_endpoints():
    print("Testing Approved Queue API endpoints and PDF delivery...")
    client = TestClient(app)

    approved_dir = root_dir / "data" / "approved_queue"
    approved_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Create a mock approved job and dummy PDF for deterministic verification
    test_id = "test_verification_approved_999"
    test_json_path = approved_dir / f"{test_id}.json"
    test_pdf_path = approved_dir / f"{test_id}_resume.pdf"

    test_payload = {
        "job_id": test_id,
        "source": "greenhouse",
        "application_type": "ATS_GREENHOUSE",
        "job_details": {
            "title": "Staff SDET Lead",
            "company": "VerificationCorp",
            "location": "Bengaluru (Remote)",
        },
        "url": "https://boards.greenhouse.io/verificationcorp/jobs/999",
        "matched_keywords": ["Selenium", "Python", "CI/CD"],
        "generated_pdf_path": str(test_pdf_path),
    }

    with open(test_json_path, "w") as f:
        json.dump(test_payload, f)

    # Create dummy PDF bytes
    with open(test_pdf_path, "wb") as f:
        f.write(b"%PDF-1.4 Mock PDF content for verification\n%%EOF")

    try:
        # Step 2: Test GET /api/approved-jobs
        res = client.get("/api/approved-jobs")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "jobs" in data, "Response missing 'jobs' key"
        assert "budget" in data, "Response missing 'budget' key"

        # Verify budget structure
        budget = data["budget"]
        assert "daily_limit" in budget
        assert "used_today" in budget
        assert "remaining" in budget

        # Check our test job is present
        matching_job = next((j for j in data["jobs"] if j["job_id"] == test_id), None)
        assert matching_job is not None, f"Job {test_id} not found in /api/approved-jobs"
        assert matching_job["company"] == "VerificationCorp"
        assert matching_job["has_pdf"] is True
        print(f"   ✅ GET /api/approved-jobs returned {len(data['jobs'])} jobs with valid budget: {budget}")

        # Step 3: Test GET /api/pdf/{job_id}
        pdf_res = client.get(f"/api/pdf/{test_id}")
        assert pdf_res.status_code == 200, f"Expected 200, got {pdf_res.status_code}"
        assert "application/pdf" in pdf_res.headers.get("content-type", "")
        assert b"%PDF-1.4" in pdf_res.content
        print(f"   ✅ GET /api/pdf/{test_id} successfully delivered PDF with application/pdf header")

        # Step 4: Test DELETE /api/approved/{job_id}
        del_res = client.delete(f"/api/approved/{test_id}")
        assert del_res.status_code == 200
        assert not test_json_path.exists(), "JSON file was not deleted"
        assert not test_pdf_path.exists(), "PDF file was not deleted"
        print(f"   ✅ DELETE /api/approved/{test_id} cleanly removed JSON and PDF")

    finally:
        # Cleanup
        if test_json_path.exists():
            os.remove(test_json_path)
        if test_pdf_path.exists():
            os.remove(test_pdf_path)

    print("\n🎉 ALL APPROVED QUEUE FLOW VERIFICATIONS PASSED!")


if __name__ == "__main__":
    test_approved_queue_endpoints()
