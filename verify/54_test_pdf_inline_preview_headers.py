"""
verify/54_test_pdf_inline_preview_headers.py — Verification Gate 54:
Validates that PDF endpoints return Content-Disposition: inline to prevent unintended file downloads
and ensure smooth in-browser/iframe rendering.
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

from src.ui.app import app


def test_pdf_inline_headers():
    print("=" * 60)
    print("  GATE 54: PDF INLINE PREVIEW HEADERS VERIFICATION")
    print("=" * 60)

    client = TestClient(app)

    # 1. Test /api/pdf/standard
    print("\n🔍 Step 1: Testing /api/pdf/standard Content-Disposition...")
    resp_std = client.get("/api/pdf/standard")
    assert resp_std.status_code == 200, f"Expected 200, got {resp_std.status_code}"
    cd_std = resp_std.headers.get("content-disposition", "")
    print(f"   /api/pdf/standard Content-Disposition: '{cd_std}'")
    assert cd_std.startswith("inline;"), f"Expected inline disposition, got '{cd_std}'"
    assert "attachment" not in cd_std, f"Found unintended attachment in '{cd_std}'"
    assert "no-cache" in resp_std.headers.get("cache-control", ""), "Expected no-cache header"
    print("✅ /api/pdf/standard has valid inline disposition!")

    # 2. Test /api/pdf/preview/{job_id}?version=tailored
    pending_files = glob.glob(os.path.join(PROJECT_ROOT, "data", "pending_queue", "*.json"))
    assert len(pending_files) > 0, "No pending jobs found to test preview"
    with open(pending_files[0], "r", encoding="utf-8") as f:
        job_data = json.load(f)
    job_id = str(job_data["job_id"])

    print(f"\n🔍 Step 2: Testing /api/pdf/preview/{job_id}?version=tailored Content-Disposition...")
    resp_prev = client.get(f"/api/pdf/preview/{job_id}?version=tailored")
    assert resp_prev.status_code == 200, f"Expected 200, got {resp_prev.status_code}"
    cd_prev = resp_prev.headers.get("content-disposition", "")
    print(f"   /api/pdf/preview/{job_id} Content-Disposition: '{cd_prev}'")
    assert cd_prev.startswith("inline;"), f"Expected inline disposition, got '{cd_prev}'"
    assert "attachment" not in cd_prev, f"Found unintended attachment in '{cd_prev}'"
    assert "no-cache" in resp_prev.headers.get("cache-control", ""), "Expected no-cache header"
    print("✅ /api/pdf/preview has valid inline disposition!")

    # 3. Test /api/pdf/preview/{job_id}?version=standard
    print(f"\n🔍 Step 3: Testing /api/pdf/preview/{job_id}?version=standard Content-Disposition...")
    resp_prev_std = client.get(f"/api/pdf/preview/{job_id}?version=standard")
    assert resp_prev_std.status_code == 200
    cd_prev_std = resp_prev_std.headers.get("content-disposition", "")
    print(f"   /api/pdf/preview standard version Content-Disposition: '{cd_prev_std}'")
    assert cd_prev_std.startswith("inline;")
    assert "attachment" not in cd_prev_std
    print("✅ /api/pdf/preview?version=standard has valid inline disposition!")

    print("\n" + "=" * 60)
    print("🎉 ALL GATE 54 ASSERTIONS PASSED (100% SUCCESS)!")
    print("=" * 60)


if __name__ == "__main__":
    test_pdf_inline_headers()
