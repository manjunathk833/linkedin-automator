"""Verification script for ATSAssistedFiller multi-tab and popup window resilience.

Tests:
1. Handling of <a target="_blank"> Apply triggers that open application forms in a new browser tab.
2. Handling of window.open() JS Apply triggers opening application forms in a popup/tab.
3. Verification that active Playwright page reference switches to the new tab, brings it to front, and completes autofill.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from playwright.async_api import async_playwright

from src.autofill.ats_filler import ATSAssistedFiller


async def test_target_blank_new_tab():
    print("1. Testing <a target='_blank'> Apply trigger opening form in a new tab...")

    mock_form_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Application Form - Senior SDET</title></head>
    <body style="font-family: sans-serif; padding: 20px;">
        <h2>Submit Application Form</h2>
        <form id="job-form">
            <div><label>First Name</label><input id="first_name" type="text" name="first_name"></div>
            <div><label>Last Name</label><input id="last_name" type="text" name="last_name"></div>
            <div><label>Email</label><input id="email" type="email" name="email"></div>
            <div><label>Phone</label><input id="phone" type="tel" name="phone"></div>
            <div><label>LinkedIn</label><input id="linkedin" type="text" name="job_application[answers_attributes][0][text_value]"></div>
            <div><label>Resume</label><input id="resume" type="file" name="resume"></div>
        </form>
    </body>
    </html>
    """

    form_file = root_dir / "verify" / "mock_form_page.html"
    with open(form_file, "w", encoding="utf-8") as f:
        f.write(mock_form_html)

    landing_html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Career Portal - Senior SDET</title></head>
    <body style="font-family: sans-serif; padding: 20px;">
        <h1>Senior SDET Lead</h1>
        <p>Career spec details on company portal...</p>
        <a id="apply-button" href="file://{form_file}" target="_blank" style="padding: 10px 20px; font-size: 16px; display: inline-block; background: blue; color: white;">
            Apply Now
        </a>
    </body>
    </html>
    """

    landing_file = root_dir / "verify" / "mock_landing_page.html"
    with open(landing_file, "w", encoding="utf-8") as f:
        f.write(landing_html)

    dummy_pdf = root_dir / "verify" / "mock_tab_resume.pdf"
    with open(dummy_pdf, "wb") as f:
        f.write(b"%PDF-1.4 Mock PDF for tab verification\n%%EOF")

    landing_url = f"file://{landing_file}"

    filler = ATSAssistedFiller(headless=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            result = await filler.fill_ats_page(page, landing_url, resume_pdf_path=str(dummy_pdf))
            print(f"   📊 Fill Result: {result}")
            assert result["status"] == "ready_for_review"
            assert result["fields_filled"] >= 4, f"Expected >= 4 fields, got {result['fields_filled']}"
            assert result["resume_attached"] is True, "Resume was not attached"
            assert "mock_form_page.html" in result["url"], f"URL should point to application tab, got {result['url']}"

            # Verify that the new tab has filled values in DOM
            active_tab = context.pages[-1]
            val_fn = await active_tab.locator("input#first_name").input_value()
            val_em = await active_tab.locator("input#email").input_value()
            assert "Manjunath" in val_fn
            assert "@" in val_em
            print(f"   ✅ Target _blank new tab handled successfully! Candidate: {val_fn}, Email: {val_em}")

        finally:
            await browser.close()
            if form_file.exists():
                os.remove(form_file)
            if landing_file.exists():
                os.remove(landing_file)
            if dummy_pdf.exists():
                os.remove(dummy_pdf)


async def test_window_open_new_tab():
    print("2. Testing window.open() JS Apply trigger opening form in a popup/tab...")

    mock_form_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Application Form - QA Architect</title></head>
    <body style="font-family: sans-serif; padding: 20px;">
        <h2>Submit Application Form</h2>
        <form id="job-form">
            <div><label>First Name</label><input id="first_name" type="text" name="first_name"></div>
            <div><label>Last Name</label><input id="last_name" type="text" name="last_name"></div>
            <div><label>Email</label><input id="email" type="email" name="email"></div>
            <div><label>Phone</label><input id="phone" type="tel" name="phone"></div>
            <div><label>LinkedIn</label><input id="linkedin" type="text" name="linkedin"></div>
        </form>
    </body>
    </html>
    """

    form_file = root_dir / "verify" / "mock_js_form_page.html"
    with open(form_file, "w", encoding="utf-8") as f:
        f.write(mock_form_html)

    landing_html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Career Portal - QA Architect</title></head>
    <body style="font-family: sans-serif; padding: 20px;">
        <h1>QA Architect</h1>
        <p>Career spec details on company portal...</p>
        <button id="apply-button" onclick="window.open('file://{form_file}', '_blank')" style="padding: 10px 20px;">
            Apply for this job
        </button>
    </body>
    </html>
    """

    landing_file = root_dir / "verify" / "mock_js_landing_page.html"
    with open(landing_file, "w", encoding="utf-8") as f:
        f.write(landing_html)

    landing_url = f"file://{landing_file}"

    filler = ATSAssistedFiller(headless=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            result = await filler.fill_ats_page(page, landing_url)
            print(f"   📊 Fill Result: {result}")
            assert result["status"] == "ready_for_review"
            assert result["fields_filled"] >= 4, f"Expected >= 4 fields, got {result['fields_filled']}"
            assert "mock_js_form_page.html" in result["url"]
            print("   ✅ JS window.open() popup handled successfully!")

        finally:
            await browser.close()
            if form_file.exists():
                os.remove(form_file)
            if landing_file.exists():
                os.remove(landing_file)


async def main():
    await test_target_blank_new_tab()
    await test_window_open_new_tab()
    print("\n🎉 ALL NEW-TAB ATS HANDLING VERIFICATIONS PASSED!")


if __name__ == "__main__":
    asyncio.run(main())
