"""Verification script for Approval Gate type coercion and payload handling.

Tests:
1. Notice period given as integer 60 -> coerced to string "60"
2. Empty strings for notice_period and current_location -> preserved as "" instead of null
3. Numeric strings for salary_expectations_min/max -> coerced to int or None
4. Boolean coercion for authorization flags and sponsorship
5. WorkPreference string handling
6. End-to-end FastAPI endpoint POST /api/approve/{job_id} with integer notice_period: 60
"""

import copy
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from fastapi.testclient import TestClient

from src.resume_store.models import EasyApplyAnswers, WorkPreference
from src.ui.app import app, coerce_easy_apply_answers


def test_unit_coercion():
    print("1. Testing unit coercion logic...")

    raw_ea = {
        "authorization_to_work": {"IN": True},
        "sponsorship_needed": False,
        "salary_expectations_min": "1800000",
        "salary_expectations_max": 2500000,
        "salary_currency": "INR",
        "notice_period": 60,  # Integer 60
        "start_date_available": "Immediate",
        "current_location": "Bengaluru, India",
        "willing_to_relocate": "true",
        "work_preference": "remote",
    }

    coerced = coerce_easy_apply_answers(raw_ea)
    assert coerced["notice_period"] == "60", f"Expected '60', got {coerced['notice_period']}"
    assert coerced["salary_expectations_min"] == 1800000
    assert coerced["salary_expectations_max"] == 2500000
    assert coerced["willing_to_relocate"] is True
    assert coerced["work_preference"] == WorkPreference.REMOTE

    validated = EasyApplyAnswers(**coerced)
    assert validated.notice_period == "60"
    print("   ✅ Unit coercion passed!")

    # Test empty / None handling
    empty_ea = {
        "notice_period": None,
        "current_location": None,
        "salary_expectations_min": "",
        "work_preference": "INVALID",
    }
    coerced_empty = coerce_easy_apply_answers(empty_ea)
    validated_empty = EasyApplyAnswers(**coerced_empty)
    assert validated_empty.notice_period == ""
    assert validated_empty.current_location == ""
    assert validated_empty.salary_expectations_min is None
    assert validated_empty.work_preference == WorkPreference.FLEXIBLE
    print("   ✅ Empty / null field coercion passed!")


def test_api_approve_endpoint_with_int_notice_period():
    print("2. Testing POST /api/approve/{job_id} with integer notice_period (reproducing user scenario)...")
    client = TestClient(app)

    # Find a pending job
    pending_dir = root_dir / "data" / "pending_queue"
    pending_files = list(pending_dir.glob("*.json"))
    if not pending_files:
        print("   ⚠️ No pending files found to test approval endpoint. Skipping API simulation.")
        return

    sample_file = pending_files[0]
    with open(sample_file, "r") as f:
        job_data = json.load(f)

    # Ensure tailored_resume exists
    if "tailored_resume" not in job_data:
        from src.tailor.resume_tailorer import ResumeTailorer

        tailorer = ResumeTailorer(use_ai=False)
        job_data = tailorer.tailor_job_payload(job_data)

    test_payload = copy.deepcopy(job_data)
    test_job_id = "test_coercion_job_9999"
    test_payload["job_id"] = test_job_id

    # Create dummy pending file for this test
    test_pending_path = pending_dir / f"{test_job_id}.json"
    with open(test_pending_path, "w") as f:
        json.dump(test_payload, f)

    # Inject integer notice_period = 60
    test_payload["tailored_resume"]["easy_apply_answers"]["notice_period"] = 60

    try:
        response = client.post(f"/api/approve/{test_job_id}", json=test_payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        res_json = response.json()
        assert res_json["status"] == "success"
        print(f"   ✅ API Approval succeeded! Message: {res_json['message']}")

        # Verify approved file exists and notice_period is "60"
        approved_dir = root_dir / "data" / "approved_queue"
        approved_file = approved_dir / f"{test_job_id}.json"
        assert approved_file.exists(), "Approved JSON file was not saved"

        with open(approved_file, "r") as f:
            saved_approved = json.load(f)
        assert saved_approved["tailored_resume"]["easy_apply_answers"]["notice_period"] == "60"
        print("   ✅ Approved JSON verified with coerced notice_period='60'")

        # Verify PDF was generated
        pdf_path = Path(saved_approved["generated_pdf_path"])
        assert pdf_path.exists(), f"PDF was not generated at {pdf_path}"
        print(f"   ✅ PDF successfully generated at {pdf_path}")

        # Verify pending file was cleanly removed
        assert not test_pending_path.exists(), "Pending file should have been cleaned up after approval"
        print("   ✅ Pending file was cleanly removed after approval")

    finally:
        # Cleanup test artifacts
        if test_pending_path.exists():
            os.remove(test_pending_path)
        approved_file = root_dir / "data" / "approved_queue" / f"{test_job_id}.json"
        if approved_file.exists():
            os.remove(approved_file)
        test_pdf = root_dir / "data" / "approved_queue" / f"{test_job_id}_resume.pdf"
        if test_pdf.exists():
            os.remove(test_pdf)


if __name__ == "__main__":
    test_unit_coercion()
    test_api_approve_endpoint_with_int_notice_period()
    print("\n🎉 ALL VERIFICATION TESTS PASSED SUCCESSFULLY!")
