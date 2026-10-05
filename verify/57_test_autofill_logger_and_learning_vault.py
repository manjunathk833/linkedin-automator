"""Verification Gate 57: Autofill Structured Diagnostics, Event Logger & Learning Vault.

Validates:
1. AutofillLogger initialization, JSONL event logging, and human-readable diagnostic log writes.
2. Diagnostic failure snapshot capture (full-page screenshot + DOM element dump JSON).
3. Persistent Learning Vault banking (new lessons recorded, retrieved, and audited).
4. Workday Overview vs Navbar Sign In anti-collision heuristic (overview is never misclassified as auth_sign_in).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright

from src.autofill.ats_filler import ATSAssistedFiller
from src.autofill.autofill_logger import (
    DIAGNOSTICS_LOG_FILE,
    EVENTS_JSONL_FILE,
    LEARNING_VAULT_FILE,
    AutofillLogger,
)


async def test_autofill_logger_events_and_vault():
    print("\n🚀 ========================================================")
    print("🚀 Running Verification Gate 57: Autofill Logger & Vault")
    print("🚀 ========================================================\n")

    # Step 1: Logger Initialization & Basic Event Logging
    print("🧪 Step 1: Testing AutofillLogger initialization & JSONL event writing...")
    logger = AutofillLogger.get_logger()
    assert logger is not None, "Failed to get AutofillLogger instance"

    test_event_msg = "Verification Gate 57 probe event"
    logger.log(
        event_type="TEST_PROBE",
        message=test_event_msg,
        vendor="WORKDAY_STANDARD",
        url="https://jiostar.wd102.myworkdayjobs.com/test",
        state="overview",
        details={"probe_id": "gate_57"},
    )

    assert DIAGNOSTICS_LOG_FILE.exists(), f"Diagnostics log not found at {DIAGNOSTICS_LOG_FILE}"
    assert EVENTS_JSONL_FILE.exists(), f"Events JSONL not found at {EVENTS_JSONL_FILE}"

    with open(EVENTS_JSONL_FILE, encoding="utf-8") as f:
        events = [json.loads(line) for line in f if line.strip()]
    assert any(ev.get("message") == test_event_msg for ev in events), (
        "Test probe event was not found in autofill_events.jsonl"
    )
    print("✅ Step 1: AutofillLogger event writing verified successfully.")

    # Step 2: Learning Vault Banking & Audit Summary
    print("🧪 Step 2: Testing Learning Vault lesson banking & audit summary...")
    assert LEARNING_VAULT_FILE.exists(), "Learning Vault file does not exist"
    with open(LEARNING_VAULT_FILE, encoding="utf-8") as f:
        vault = json.load(f)
    assert len(vault.get("lessons", [])) >= 5, "Initial vault lessons missing"

    test_symptom = "Gate 57 simulated selector collision"
    new_lesson = logger.record_learning_incident(
        vendor="WORKDAY_STANDARD",
        symptom=test_symptom,
        root_cause="Simulated collision test",
        fix_rule="Strictly target data-automation-id",
    )
    assert new_lesson["id"].startswith("LESSON-"), f"Unexpected lesson id {new_lesson['id']}"

    summary = logger.get_audit_summary(limit=5)
    assert summary["total_lessons_banked"] >= 6, "Total lessons count mismatch"
    assert any(l["symptom"] == test_symptom for l in summary["lessons"]), "New lesson not found in audit summary"
    print("✅ Step 2: Learning Vault banking and audit summary verified successfully.")

    # Step 3: Diagnostic Snapshot (Screenshot & DOM Element Dump)
    print("🧪 Step 3: Testing full-page diagnostic screenshot & DOM dump capture...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        mock_dom_html = """
        <!DOCTYPE html>
        <html>
        <head><title>JioStar Senior SDET II Mock</title></head>
        <body>
            <header>
                <div class="nav-right">
                    <a role="button" href="/login">Sign In</a>
                </div>
            </header>
            <main>
                <h1>Senior Software Development Engineer Test II</h1>
                <button data-automation-id="applyButton">Apply</button>
                <div role="alert" class="alert-info">Job posted 3 days ago</div>
            </main>
        </body>
        </html>
        """
        await page.set_content(mock_dom_html)

        diag_result = await logger.capture_diagnostic(
            target=page,
            reason="simulated_gate_57_test",
            vendor="WORKDAY_STANDARD",
            state="overview",
        )

        assert os.path.exists(diag_result["screenshot"]), f"Screenshot not created at {diag_result['screenshot']}"
        assert os.path.getsize(diag_result["screenshot"]) > 1000, "Screenshot file is empty"
        assert os.path.exists(diag_result["dom_dump"]), f"DOM dump JSON not created at {diag_result['dom_dump']}"

        with open(diag_result["dom_dump"], encoding="utf-8") as f:
            dom_data = json.load(f)
        assert dom_data["title"] == "JioStar Senior SDET II Mock"
        assert len(dom_data["dom_elements"]["buttons"]) >= 1, "Failed to capture visible buttons in DOM dump"
        assert len(dom_data["dom_elements"]["alerts"]) >= 1, "Failed to capture visible alerts in DOM dump"
        print("✅ Step 3: Diagnostic screenshot and DOM dump verified successfully.")

        # Step 4: Workday Overview vs Navbar Anti-Collision Validation
        print("🧪 Step 4: Testing Workday Overview vs Navbar Sign In anti-collision...")
        filler = ATSAssistedFiller(headless=True)

        # Overview page (has navbar "Sign In" link AND "applyButton", but NO password input)
        state_overview = await filler._detect_workday_state(page)
        assert state_overview == "overview", (
            f"Expected state 'overview', got '{state_overview}'. Navbar Sign In collided!"
        )
        print("   ✓ Page with navbar 'Sign In' correctly identified as 'overview'")

        # Modal state
        modal_html = """
        <div data-automation-id="applicationModal">
            <button data-automation-id="applyManually">Apply Manually</button>
        </div>
        """
        await page.set_content(modal_html)
        state_modal = await filler._detect_workday_state(page)
        assert state_modal == "modal", f"Expected state 'modal', got '{state_modal}'"
        print("   ✓ Application modal correctly identified as 'modal'")

        # Auth Sign In state (requires password field + submit button)
        auth_html = """
        <form data-automation-id="authDialog">
            <input data-automation-id="email" type="email" value="manjunathhk833@gmail.com" />
            <input data-automation-id="password" type="password" value="Candidate@2026Auto!" />
            <button data-automation-id="signInSubmitButton" type="submit">Sign In</button>
        </form>
        """
        await page.set_content(auth_html)
        state_auth = await filler._detect_workday_state(page)
        assert state_auth == "auth_sign_in", f"Expected state 'auth_sign_in', got '{state_auth}'"
        print("   ✓ Credential dialog correctly identified as 'auth_sign_in'")

        await browser.close()

    print("✅ Step 4: Workday Overview vs Navbar Sign In anti-collision validated 100%.")

    print("\n🎉 ========================================================")
    print("🎉 Verification Gate 57 PASSED: Autofill Diagnostics & Vault Operational")
    print("🎉 ========================================================\n")


if __name__ == "__main__":
    asyncio.run(test_autofill_logger_events_and_vault())
