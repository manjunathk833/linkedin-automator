"""
verify/53_test_resume_comparison_and_selection.py — Verification Gate 53:
Validates the Standard vs Tailored Resume PDF Preview & Selection Architecture.

Tests:
1. Standard Base Resume endpoint (/api/pdf/standard).
2. Preview PDF endpoint for pending jobs (/api/pdf/preview/{job_id}?version=tailored and ?version=standard).
3. Approval workflow with resume_choice="standard" vs resume_choice="tailored".
4. Verifies that resolve_job_pdf_path resolves the accurately chosen PDF.
"""

from __future__ import annotations

import glob
import json
import os
import sys

from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ui.app import app, resolve_job_pdf_path


def test_resume_comparison_and_selection():
    print("=" * 60)
    print("  GATE 53: RESUME COMPARISON & SELECTION VERIFICATION")
    print("=" * 60)

    client = TestClient(app)

    # 1. Test /api/pdf/standard
    print("\n🔍 Step 1: Testing /api/pdf/standard endpoint...")
    resp_std = client.get("/api/pdf/standard")
    assert resp_std.status_code == 200, f"Expected 200, got {resp_std.status_code}: {resp_std.text}"
    assert "application/pdf" in resp_std.headers.get("content-type", "")
    assert resp_std.content.startswith(b"%PDF"), "Response is not a valid PDF binary"
    print(f"✅ /api/pdf/standard returned valid PDF ({len(resp_std.content)} bytes)")

    # 2. Pick a job from pending queue to test preview endpoints
    pending_files = glob.glob(os.path.join(PROJECT_ROOT, "data", "pending_queue", "*.json"))
    assert len(pending_files) > 0, "No pending jobs found to test preview"
    sample_file = pending_files[0]
    with open(sample_file, "r", encoding="utf-8") as f:
        job_data = json.load(f)
    job_id = str(job_data["job_id"])

    print(f"\n🔍 Step 2: Testing /api/pdf/preview/{job_id}?version=tailored...")
    resp_prev_tailored = client.get(f"/api/pdf/preview/{job_id}?version=tailored")
    assert resp_prev_tailored.status_code == 200, (
        f"Expected 200, got {resp_prev_tailored.status_code}: {resp_prev_tailored.text}"
    )
    assert resp_prev_tailored.content.startswith(b"%PDF")
    print(f"✅ Preview tailored PDF returned successfully ({len(resp_prev_tailored.content)} bytes)")

    print(f"\n🔍 Step 3: Testing /api/pdf/preview/{job_id}?version=standard...")
    resp_prev_std = client.get(f"/api/pdf/preview/{job_id}?version=standard")
    assert resp_prev_std.status_code == 200
    assert resp_prev_std.content.startswith(b"%PDF")
    print(f"✅ Preview standard PDF returned successfully ({len(resp_prev_std.content)} bytes)")

    # 3. Test Approval with resume_choice="standard" on a synthetic test job
    print("\n🔍 Step 4: Testing approval flow with resume_choice='standard'...")
    synth_std_id = "test_standard_choice_9999"
    synth_payload = dict(job_data)
    synth_payload["job_id"] = synth_std_id
    synth_payload["resume_choice"] = "standard"

    resp_appr_std = client.post(f"/api/approve/{synth_std_id}", json=synth_payload)
    assert resp_appr_std.status_code == 200, f"Approval failed: {resp_appr_std.status_code} - {resp_appr_std.text}"
    appr_data_std = resp_appr_std.json()
    assert appr_data_std.get("chosen_resume_version") == "standard"

    # Check approved file on disk
    approved_file_std = os.path.join(PROJECT_ROOT, "data", "approved_queue", f"{synth_std_id}.json")
    assert os.path.exists(approved_file_std), "Approved JSON file not found"
    with open(approved_file_std, "r") as f:
        saved_std = json.load(f)
    assert saved_std.get("chosen_resume_version") == "standard"
    pdf_path_std, _ = resolve_job_pdf_path(synth_std_id, saved_std)
    assert os.path.exists(pdf_path_std), f"Generated standard PDF does not exist at {pdf_path_std}"
    print(f"✅ Approved with standard resume: {pdf_path_std}")

    # Clean up synthetic job
    client.delete(f"/api/approved/{synth_std_id}")

    # 4. Test Approval with resume_choice="tailored" on a synthetic test job
    print("\n🔍 Step 5: Testing approval flow with resume_choice='tailored'...")
    synth_tailored_id = "test_tailored_choice_8888"
    synth_tailored_payload = dict(job_data)
    synth_tailored_payload["job_id"] = synth_tailored_id
    synth_tailored_payload["resume_choice"] = "tailored"

    resp_appr_tailored = client.post(f"/api/approve/{synth_tailored_id}", json=synth_tailored_payload)
    assert resp_appr_tailored.status_code == 200
    appr_data_tailored = resp_appr_tailored.json()
    assert appr_data_tailored.get("chosen_resume_version") == "tailored"

    approved_file_tailored = os.path.join(PROJECT_ROOT, "data", "approved_queue", f"{synth_tailored_id}.json")
    assert os.path.exists(approved_file_tailored)
    with open(approved_file_tailored, "r") as f:
        saved_tailored = json.load(f)
    assert saved_tailored.get("chosen_resume_version") == "tailored"
    pdf_path_tailored, _ = resolve_job_pdf_path(synth_tailored_id, saved_tailored)
    assert os.path.exists(pdf_path_tailored)
    print(f"✅ Approved with tailored resume: {pdf_path_tailored}")

    # Clean up synthetic job
    client.delete(f"/api/approved/{synth_tailored_id}")

    print("\n" + "=" * 60)
    print("🎉 ALL GATE 53 ASSERTIONS PASSED (100% SUCCESS)!")
    print("=" * 60)


if __name__ == "__main__":
    test_resume_comparison_and_selection()
