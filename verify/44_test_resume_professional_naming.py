"""Verification script for Professional Resume PDF Naming and Delivery.

Tests:
1. Candidate slug extraction correctly standardizes candidate name (e.g., 'Manjunath_HK').
2. Company and job token extractors parse authentic names without scraper prefixes.
3. generate_professional_resume_filename produces recruiter-friendly filenames:
   e.g. 'Manjunath_HK_Coinbase_8095207_Resume.pdf' or 'Manjunath_HK_Zapier_45b2c110_Resume.pdf'.
4. resolve_job_pdf_path provides seamless backward compatibility for existing approved resumes.
5. GET /api/pdf/{job_id} serves PDF with clean Content-Disposition filename (e.g., 'Manjunath_HK_Coinbase_Resume.pdf').
6. DELETE /api/approved/{job_id} cleans up both JSON and the professional PDF.
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
    extract_company_slug,
    extract_job_token,
    generate_professional_resume_filename,
    get_candidate_name_slug,
    resolve_job_pdf_path,
)


def test_naming_helpers():
    print("\n--- 1. Testing Resume Naming Helpers ---")

    # 1. Candidate slug
    cand = get_candidate_name_slug()
    assert cand == "Manjunath_HK", f"Expected 'Manjunath_HK', got '{cand}'"
    print(f"✅ Candidate slug from master profile: {cand}")

    custom_payload = {"tailored_resume": {"personal_details": {"full_name": "Jane Developer"}}}
    assert get_candidate_name_slug(custom_payload) == "Jane_Developer"
    print("✅ Custom payload candidate slug parsed correctly.")

    # 2. Company slug
    comp_coinbase = extract_company_slug("greenhouse_coinbase_8095207", {"job_details": {"company": "Coinbase"}})
    assert comp_coinbase == "Coinbase", f"Expected 'Coinbase', got '{comp_coinbase}'"

    comp_fallback = extract_company_slug("ashby_zapier_45b2c110-f8e0-497a-914c-72fddf447ed0", {})
    assert comp_fallback == "Zapier", f"Expected 'Zapier', got '{comp_fallback}'"
    print(f"✅ Company slug extraction verified: {comp_coinbase}, {comp_fallback}")

    # 3. Job token
    token_num = extract_job_token("greenhouse_coinbase_8095207")
    assert token_num == "8095207", f"Expected '8095207', got '{token_num}'"

    token_uuid = extract_job_token("ashby_zapier_45b2c110-f8e0-497a-914c-72fddf447ed0")
    assert token_uuid == "45b2c110", f"Expected '45b2c110', got '{token_uuid}'"
    print(f"✅ Job token extraction verified: {token_num}, {token_uuid}")

    # 4. Full professional filename
    fn1 = generate_professional_resume_filename(
        "greenhouse_coinbase_8095207",
        {"job_details": {"company": "Coinbase"}},
    )
    assert fn1 == "Manjunath_HK_Coinbase_8095207_Resume.pdf", f"Unexpected filename: {fn1}"
    print(f"✅ Generated Coinbase filename: {fn1}")

    fn2 = generate_professional_resume_filename(
        "ashby_zapier_45b2c110-f8e0-497a-914c-72fddf447ed0",
        {"job_details": {"company": "Zapier"}},
    )
    assert fn2 == "Manjunath_HK_Zapier_45b2c110_Resume.pdf", f"Unexpected filename: {fn2}"
    print(f"✅ Generated Ashby Zapier filename: {fn2}")


def test_api_resolution_and_delivery():
    print("\n--- 2. Testing API Delivery & Backward Compatibility ---")
    client = TestClient(app)
    approved_dir = root_dir / "data" / "approved_queue"
    approved_dir.mkdir(parents=True, exist_ok=True)

    # Test Case A: Professional Naming Job
    test_id = "test_pro_naming_101"
    pro_pdf_name = "Manjunath_HK_AcmeCorp_101_Resume.pdf"
    test_json_path = approved_dir / f"{test_id}.json"
    test_pdf_path = approved_dir / pro_pdf_name

    test_payload = {
        "job_id": test_id,
        "source": "greenhouse",
        "application_type": "ATS_GREENHOUSE",
        "job_details": {
            "title": "Senior SDET",
            "company": "AcmeCorp",
            "location": "Bengaluru",
        },
        "url": "https://boards.greenhouse.io/acmecorp/jobs/101",
        "matched_keywords": ["Python", "Playwright"],
        "generated_pdf_path": str(test_pdf_path),
    }

    with open(test_json_path, "w", encoding="utf-8") as f:
        json.dump(test_payload, f)

    with open(test_pdf_path, "wb") as f:
        f.write(b"%PDF-1.4 Mock Pro PDF content\n%%EOF")

    try:
        # Check resolve_job_pdf_path
        resolved_path, resolved_name = resolve_job_pdf_path(test_id, test_payload)
        assert resolved_path == str(test_pdf_path)
        assert resolved_name == pro_pdf_name
        print(f"✅ Resolved pro path correctly: {resolved_name}")

        # Check GET /api/approved-jobs
        res = client.get("/api/approved-jobs")
        assert res.status_code == 200
        jobs = res.json().get("jobs", [])
        matched = [j for j in jobs if j.get("job_id") == test_id]
        assert len(matched) == 1
        assert matched[0]["pdf_filename"] == pro_pdf_name
        assert matched[0]["has_pdf"] is True
        print("✅ /api/approved-jobs lists professional resume filename correctly.")

        # Check GET /api/pdf/{job_id}
        res_pdf = client.get(f"/api/pdf/{test_id}")
        assert res_pdf.status_code == 200
        assert res_pdf.headers.get("content-type") == "application/pdf"
        cd = res_pdf.headers.get("content-disposition", "")
        assert "Manjunath_HK_AcmeCorp_Resume.pdf" in cd or pro_pdf_name in cd, f"Unexpected header: {cd}"
        print(f"✅ /api/pdf/{test_id} returned 200 with clean download header: {cd}")

    finally:
        # Test DELETE /api/approved/{job_id} cleans up both json and pro pdf
        del_res = client.delete(f"/api/approved/{test_id}")
        assert del_res.status_code == 200
        assert not test_json_path.exists(), "JSON file was not deleted"
        assert not test_pdf_path.exists(), "Professional PDF was not deleted"
        print("✅ DELETE /api/approved/{job_id} successfully deleted JSON and pro PDF.")

    # Test Case B: Legacy Backward Compatibility (f"{job_id}_resume.pdf")
    legacy_id = "test_legacy_job_202"
    legacy_json_path = approved_dir / f"{legacy_id}.json"
    legacy_pdf_path = approved_dir / f"{legacy_id}_resume.pdf"

    legacy_payload = {
        "job_id": legacy_id,
        "source": "lever",
        "job_details": {"company": "OldCorp", "title": "QA Engineer"},
        "url": "https://jobs.lever.co/oldcorp/202",
    }

    with open(legacy_json_path, "w", encoding="utf-8") as f:
        json.dump(legacy_payload, f)

    with open(legacy_pdf_path, "wb") as f:
        f.write(b"%PDF-1.4 Legacy PDF content\n%%EOF")

    try:
        resolved_path, resolved_name = resolve_job_pdf_path(legacy_id, legacy_payload)
        assert resolved_path == str(legacy_pdf_path)
        assert resolved_name == f"{legacy_id}_resume.pdf"
        print(f"✅ Backward compatibility verified: resolved legacy path {resolved_name}")

        res_legacy_pdf = client.get(f"/api/pdf/{legacy_id}")
        assert res_legacy_pdf.status_code == 200
        print("✅ /api/pdf/{legacy_id} serves legacy PDF successfully without 404.")
    finally:
        del_legacy = client.delete(f"/api/approved/{legacy_id}")
        assert del_legacy.status_code == 200
        assert not legacy_json_path.exists()
        assert not legacy_pdf_path.exists()
        print("✅ Legacy test cleanup completed.")


if __name__ == "__main__":
    test_naming_helpers()
    test_api_resolution_and_delivery()
    print("\n🎉 ALL VERIFICATION GATES PASSED: Professional Resume Naming & Backward Compatibility Verified!\n")
