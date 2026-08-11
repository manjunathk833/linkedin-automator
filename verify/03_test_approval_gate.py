import json
import os
import sys

from fastapi.testclient import TestClient

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ui.app import app

client = TestClient(app)


def test_get_pending_jobs():
    response = client.get("/api/pending-jobs")
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    print("✅ GET /api/pending-jobs passed!")


def test_approve_job_schema_validation():
    # Load real resume to ensure we send a valid ResumeProfile schema
    json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "resume_profile.json"))
    with open(json_path, "r") as f:
        real_resume = json.load(f)

    payload = {
        "job_id": "test_job_999",
        "application_type": "EASY_APPLY",
        "job_details": {"company": "Test Co", "title": "SDET", "requirements": "Tests", "location": "Remote"},
        "tailored_resume": real_resume,
    }

    print("Submitting valid payload to /api/approve/test_job_999...")
    response = client.post("/api/approve/test_job_999", json=payload)

    assert response.status_code == 200, f"Expected 200, got {response.status_code} - {response.text}"
    data = response.json()
    assert data["status"] == "success"

    # Verify it generated the PDF path
    assert "pdf_path" in data
    assert "test_job_999_resume.pdf" in data["pdf_path"]

    print("✅ POST /api/approve passed! (Generated PDF seamlessly)")

    # Cleanup test files
    try:
        os.remove(data["path"])
        os.remove(data["pdf_path"])
    except OSError:
        pass


def test_approve_job_with_frontend_empty_strings():
    json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "resume_profile.json"))
    with open(json_path, "r") as f:
        real_resume = json.load(f)

    # Simulate frontend submitting empty strings for optional int fields
    real_resume["easy_apply_answers"]["salary_expectations_min"] = ""
    real_resume["easy_apply_answers"]["salary_expectations_max"] = ""

    payload = {
        "job_id": "test_job_777",
        "application_type": "EASY_APPLY",
        "job_details": {"company": "Test Co", "title": "SDET", "requirements": "Tests", "location": "Remote"},
        "tailored_resume": real_resume,
    }

    print("Submitting frontend-modified payload with empty strings...")
    response = client.post("/api/approve/test_job_777", json=payload)

    assert response.status_code == 200, f"Expected 200, got {response.status_code} - {response.text}"
    data = response.json()
    assert data["status"] == "success"
    print("✅ Frontend empty string sanitization test passed!")

    try:
        os.remove(data["path"])
        os.remove(data["pdf_path"])
    except OSError:
        pass


def test_reject_job():
    response = client.post("/api/reject/test_job_888")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    print("✅ POST /api/reject passed!")


if __name__ == "__main__":
    test_get_pending_jobs()
    test_approve_job_schema_validation()
    test_approve_job_with_frontend_empty_strings()
    test_reject_job()
    print("\n✅ All UI Approval Gate tests passed!")
