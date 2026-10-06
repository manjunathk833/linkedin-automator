"""Verification Gate 60: Human-in-the-Loop Manual Takeover Fallback & Submission Confirmation.

Validates the full Manual Takeover architecture:
1. Workday State Machine stuck threshold: when any ATS stage does not advance after
   >= 2 transitions, execution halts immediately and yields control to manual mode.
2. Candidate Quick-Reference Card & DOM Cheat Sheet: terminal card formatted and
   #antigravity-copilot-helper floating widget injected into headful page DOM.
3. Background Submission Confirmation Detector: detects confirmation URL/text markers,
   logs SUBMISSION_CONFIRMED, and updates SQLite ApplicationDatabase with status='applied'.
4. Dedicated FastAPI Endpoint: /api/autofill/manual/{job_id} launches headful Chrome,
   resolves tailored resume PDF, records audit entry, and yields manual control.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright
from starlette.testclient import TestClient

from src.autofill.ats_filler import ATSAssistedFiller
from src.storage.database import ApplicationDatabase
from src.ui.app import app

SAMPLE_STUCK_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>JioStar - My Information - Workday</title>
</head>
<body>
    <div id="app-root">
        <h1>My Information</h1>
        <div data-automation-id="legalNameSection_firstName">
            <input id="name--legalName--firstName" value="Manjunath" />
        </div>
        <div data-automation-id="legalNameSection_lastName">
            <input id="name--legalName--lastName" value="HK" />
        </div>
        <!-- Missing required custom field that prevents page transition -->
        <div id="custom-mandatory-field" style="border: 1px solid red;">
            <label>Custom Mandatory Tenant Field (*)</label>
            <input id="tenant--customField" value="" />
        </div>
        <button data-automation-id="pageFooterNextButton">Save and Continue</button>
    </div>
</body>
</html>
"""

SAMPLE_CONFIRMATION_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Application Submitted - JioStar Workday</title>
</head>
<body>
    <div id="confirmation-box">
        <h1>Thank you for applying!</h1>
        <p>Your application has been received and is being reviewed by our talent acquisition team.</p>
    </div>
</body>
</html>
"""


async def test_workday_stuck_threshold_triggers_manual_takeover(pw) -> None:
    """Step 1: Test that state machine stuck threshold (>= 2) triggers manual takeover."""
    print("\n--- Step 1: Workday State Machine Stuck Threshold Gate ---")
    browser = await pw.chromium.launch(headless=True)
    page = await browser.new_page()
    await page.set_content(SAMPLE_STUCK_PAGE_HTML)

    filler = ATSAssistedFiller(headless=True)

    takeover_called = False
    captured_portal = ""

    async def mock_takeover(*args, **kwargs):
        nonlocal takeover_called, captured_portal
        takeover_called = True
        captured_portal = kwargs.get("portal_name", "")
        return {"status": "manual_takeover_activated"}

    with patch.object(filler, "_enter_manual_takeover_mode", side_effect=mock_takeover):
        # Even though max_transitions is 20, it must halt on transition 2!
        _filled, _attached = await filler._fill_workday(
            target=page,
            resume_pdf_path=None,
            job_id="TEST-JOB-STUCK",
            company="JioStar",
        )

    assert takeover_called, "❌ _enter_manual_takeover_mode was not called on stuck state"
    assert "JioStar" in captured_portal or "Workday" in captured_portal, f"❌ Unexpected portal name: {captured_portal}"
    print(f"✅ Stuck threshold triggered manual takeover cleanly! Target portal: {captured_portal}")
    await browser.close()


async def test_candidate_card_generation_and_dom_injection(pw) -> None:
    """Step 2: Test candidate quick-reference card generation and DOM widget injection."""
    print("\n--- Step 2: Candidate Reference Card & Floating DOM Widget Injection ---")
    browser = await pw.chromium.launch(headless=True)
    page = await browser.new_page()
    await page.set_content(SAMPLE_STUCK_PAGE_HTML)

    filler = ATSAssistedFiller(headless=True)
    dummy_pdf = str(PROJECT_ROOT / "verify" / "resume_test_output.pdf")

    res = await filler._enter_manual_takeover_mode(
        target=page,
        portal_name="JioStar Workday Application",
        resume_pdf_path=dummy_pdf,
        job_id="TEST-60",
        company_name="JioStar",
        job_title="Senior SDET II",
    )

    assert res.get("status") == "manual_takeover_activated", f"❌ Unexpected result: {res}"

    # Verify floating widget was injected into the DOM
    helper_el = page.locator("#antigravity-copilot-helper")
    assert await helper_el.count() > 0, "❌ Floating widget #antigravity-copilot-helper was not injected into DOM"

    widget_text = await helper_el.text_content()
    assert "Candidate Cheat Sheet" in widget_text, "❌ Missing title in widget text"
    assert filler.master_data.personal.first_name in widget_text, "❌ Candidate first name missing from widget"
    assert filler.master_data.personal.email in widget_text, "❌ Candidate email missing from widget"
    assert "resume_test_output.pdf" in widget_text, "❌ Resume PDF name missing from widget"

    print("✅ In-page floating Candidate Cheat Sheet widget successfully injected and verified in DOM!")
    await browser.close()


async def test_submission_confirmation_monitor(pw) -> None:
    """Step 3: Test background submission confirmation detector."""
    print("\n--- Step 3: Background Submission Confirmation Detector ---")
    browser = await pw.chromium.launch(headless=True)
    page = await browser.new_page()
    await page.set_content(SAMPLE_CONFIRMATION_PAGE_HTML)

    filler = ATSAssistedFiller(headless=True)
    db = ApplicationDatabase()

    test_job_id = "TEST-GATE60-CONFIRM"

    # Run monitor for up to 3 seconds
    await filler._monitor_manual_submission(
        page=page,
        job_id=test_job_id,
        company_name="JioStar",
        job_title="Senior SDET II",
        job_url="https://jiostar.wd102.myworkdayjobs.com/JioStar/application-complete",
        resume_path="/dummy/resume.pdf",
        timeout=3.0,
    )

    # Verify SQLite database was updated with status='applied'
    app_record = db.get_application(test_job_id)
    assert app_record is not None, f"❌ Application {test_job_id} not found in database"
    assert app_record["status"] == "applied", f"❌ Expected status 'applied', got '{app_record['status']}'"
    assert app_record["company_name"] == "JioStar"

    print(f"✅ Submission confirmation detected text marker and recorded APPLIED in database for {test_job_id}!")
    await browser.close()


def test_fastapi_manual_apply_endpoint() -> None:
    """Step 4: Test FastAPI endpoint /api/autofill/manual/{job_id}."""
    print("\n--- Step 4: FastAPI Manual Apply Endpoint Gate ---")
    test_job_id = "GATE60_MANUAL_API_TEST"
    pending_dir = PROJECT_ROOT / "data" / "pending_queue"
    pending_dir.mkdir(parents=True, exist_ok=True)
    job_file = pending_dir / f"{test_job_id}.json"

    dummy_job = {
        "job_id": test_job_id,
        "url": "https://jiostar.wd102.myworkdayjobs.com/JioStar/job/123",
        "application_type": "ATS_WORKDAY",
        "job_details": {
            "title": "Senior SDET II",
            "company": "JioStar",
            "location": "Bengaluru, India",
        },
        "tailored_resume": {
            "personal_details": {
                "full_name": "Manjunath HK",
                "email": "manjunathk833@gmail.com",
            }
        },
    }

    with open(job_file, "w", encoding="utf-8") as f:
        json.dump(dummy_job, f)

    try:
        client = TestClient(app)

        async def mock_launch_takeover(*args, **kwargs):
            return {
                "status": "manual_takeover_activated",
                "mode": "manual",
                "url": dummy_job["url"],
            }

        with patch(
            "src.autofill.ats_filler.ATSAssistedFiller.launch_manual_takeover", side_effect=mock_launch_takeover
        ):
            response = client.post(f"/api/autofill/manual/{test_job_id}")

        assert response.status_code == 200, f"❌ Unexpected response code {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "success"
        assert "Manual Apply opened" in data.get("message", "")

        db = ApplicationDatabase()
        rec = db.get_application(test_job_id)
        assert rec is not None, f"❌ Database record not found for {test_job_id}"
        assert rec["status"] == "manual_takeover_opened"
        print("✅ FastAPI /api/autofill/manual/{job_id} endpoint verified successfully!")

    finally:
        if job_file.exists():
            job_file.unlink()


async def main() -> None:
    print("=" * 70)
    print("🚀 RUNNING VERIFICATION GATE 60: MANUAL TAKEOVER & SUBMISSION DETECTOR")
    print("=" * 70)

    async with async_playwright() as pw:
        await test_workday_stuck_threshold_triggers_manual_takeover(pw)
        await test_candidate_card_generation_and_dom_injection(pw)
        await test_submission_confirmation_monitor(pw)

    test_fastapi_manual_apply_endpoint()

    print("\n" + "=" * 70)
    print("🎯 VERIFICATION GATE 60 COMPLETE: 100% PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
