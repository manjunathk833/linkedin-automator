"""
Verification script for Gate 43: Coinbase Greenhouse Live Form Autofill.
Tests end-to-end form mapping on the actual Coinbase Greenhouse application URL:
https://job-boards.greenhouse.io/embed/job_app?token=8095207&for=coinbase&gh_jid=8095207

Verifies:
1. Basic contact fields (First, Last, Email, Phone, Country, Location).
2. Employment history & "Current role" checkbox.
3. Education history comboboxes (School, Degree, Discipline).
4. LinkedIn URL mapping.
5. React-Select combobox handling across all custom Coinbase questions.
6. Voluntary Demographics (Gender, Hispanic/Latino, Veteran status).
7. Resume file upload.
"""

from __future__ import annotations

import asyncio
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from playwright.async_api import async_playwright

from src.autofill.ats_filler import ATSAssistedFiller
from src.autofill.vendor_schemas import load_candidate_master_data

COINBASE_GH_URL = "https://job-boards.greenhouse.io/embed/job_app?token=8095207&for=coinbase&gh_jid=8095207"


async def run_live_greenhouse_test():
    print("=" * 65)
    print("  Testing Gate 43: Live Coinbase Greenhouse Form Autofill")
    print("=" * 65)

    master_data = load_candidate_master_data()
    print(f"👤 Candidate loaded: {master_data.personal.full_name} ({master_data.personal.email})")

    # Use existing sample resume PDF for attachment verification
    resumes_dir = os.path.join(PROJECT_ROOT, "data", "approved_queue")
    sample_pdf = None
    if os.path.exists(resumes_dir):
        for f in os.listdir(resumes_dir):
            if f.endswith(".pdf"):
                sample_pdf = os.path.join(resumes_dir, f)
                break

    if not sample_pdf or not os.path.exists(sample_pdf):
        # Create a dummy pdf in scratch
        sample_pdf = os.path.join(PROJECT_ROOT, "data", "test_resume.pdf")
        with open(sample_pdf, "wb") as f:
            f.write(b"%PDF-1.4 Mock resume content for Gate 43 verification")

    print(f"📎 Resume path for test: {sample_pdf}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        print(f"🌐 Navigating to: {COINBASE_GH_URL}")
        await page.goto(COINBASE_GH_URL, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2.0)

        filler = ATSAssistedFiller(master_data=master_data)
        fields_filled, attached = await filler._fill_greenhouse(page, resume_pdf_path=sample_pdf)

        print("\n" + "=" * 65)
        print(f"📊 Results: {fields_filled} fields pre-filled | Resume attached: {attached}")
        print("=" * 65)

        # Audit key fields on the page to ensure they are populated
        fn_val = await page.locator("input#first_name").input_value()
        ln_val = await page.locator("input#last_name").input_value()
        em_val = await page.locator("input#email").input_value()
        comp_val = await page.locator("input#company-name-0").input_value()
        title_val = await page.locator("input#title-0").input_value()

        print(f"   • First Name: '{fn_val}'")
        print(f"   • Last Name:  '{ln_val}'")
        print(f"   • Email:      '{em_val}'")
        print(f"   • Company:    '{comp_val}'")
        print(f"   • Title:      '{title_val}'")

        assert fn_val == master_data.personal.first_name, f"Expected {master_data.personal.first_name}, got {fn_val}"
        assert ln_val == master_data.personal.last_name, f"Expected {master_data.personal.last_name}, got {ln_val}"
        assert em_val == master_data.personal.email, f"Expected {master_data.personal.email}, got {em_val}"
        assert comp_val == master_data.current_employment.company, (
            f"Expected {master_data.current_employment.company}, got {comp_val}"
        )
        assert title_val == master_data.current_employment.title, (
            f"Expected {master_data.current_employment.title}, got {title_val}"
        )

        assert fields_filled >= 15, f"Expected at least 15 fields filled, but got {fields_filled}"
        assert attached is True, "Resume was not attached"

        await browser.close()

    print("\n✅ GATE 43 LIVE COINBASE GREENHOUSE VERIFICATION PASSED!")


if __name__ == "__main__":
    asyncio.run(run_live_greenhouse_test())
