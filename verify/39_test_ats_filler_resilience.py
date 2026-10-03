"""Verification script for ATSAssistedFiller resilience, URL resolution, and form detection.

Tests:
1. Canonical ATS URL resolution (Coinbase gh_jid wrapper -> boards.greenhouse.io).
2. Form detection and auto-clicking of 'Apply for this job' trigger on mock career pages.
3. Field mapping, typing, and resume attachment verification with accurate metrics reporting.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from playwright.async_api import async_playwright

from src.autofill.ats_filler import ATSAssistedFiller, resolve_canonical_ats_url


def test_url_resolution():
    print("1. Testing canonical ATS URL resolution...")

    # Case A: Coinbase wrapper URL with gh_jid
    cb_url = "https://www.coinbase.com/careers/positions/8095207?gh_jid=8095207"
    resolved_cb = resolve_canonical_ats_url(cb_url, company="Coinbase")
    assert "job-boards.greenhouse.io/embed/job_app?token=8095207&for=coinbase" in resolved_cb, (
        f"Expected direct greenhouse embed URL, got: {resolved_cb}"
    )
    print(f"   ✅ Coinbase URL resolved to: {resolved_cb}")

    # Case B: Cloudflare already on boards.greenhouse.io
    cf_url = "https://boards.greenhouse.io/cloudflare/jobs/8038898?gh_jid=8038898"
    resolved_cf = resolve_canonical_ats_url(cf_url, company="Cloudflare")
    assert "boards.greenhouse.io/cloudflare/jobs/8038898" in resolved_cf
    print(f"   ✅ Cloudflare URL preserved: {resolved_cf}")

    # Case C: Lever URL
    lever_url = "https://jobs.lever.co/spotify/17a75d93-835d-40ce-b31e-0c381b49f40a"
    resolved_lever = resolve_canonical_ats_url(lever_url, company="Spotify")
    assert "jobs.lever.co/spotify" in resolved_lever
    print(f"   ✅ Lever URL preserved: {resolved_lever}")


async def test_form_fill_with_apply_trigger():
    print("2. Testing form fill resilience on mock career page with 'Apply' button trigger...")

    # Create a temporary mock HTML page simulating a career page where form is hidden until 'Apply' is clicked
    mock_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Senior SDET - Mock Careers</title></head>
    <body style="font-family: sans-serif; padding: 20px;">
        <h1>Senior SDET Lead</h1>
        <p>Job Description details...</p>
        <button id="apply-button" style="padding: 10px 20px; font-size: 16px;">Apply for this job</button>

        <div id="application-form" style="display: none; margin-top: 20px;">
            <h2>Submit Application</h2>
            <form id="job-form">
                <div><label>First Name</label><input id="first_name" type="text" name="first_name"></div>
                <div><label>Last Name</label><input id="last_name" type="text" name="last_name"></div>
                <div><label>Email</label><input id="email" type="email" name="email"></div>
                <div><label>Phone</label><input id="phone" type="tel" name="phone"></div>
                <div><label>LinkedIn</label><input id="linkedin" type="text" name="job_application[answers_attributes][0][text_value]"></div>
                <div><label>Resume</label><input id="resume" type="file" name="resume"></div>
            </form>
        </div>

        <script>
            document.getElementById('apply-button').addEventListener('click', function() {
                document.getElementById('application-form').style.display = 'block';
                this.style.display = 'none';
            });
        </script>
    </body>
    </html>
    """

    mock_file = root_dir / "verify" / "mock_career_page.html"
    with open(mock_file, "w", encoding="utf-8") as f:
        f.write(mock_html)

    # Create a dummy PDF resume for test upload
    dummy_pdf = root_dir / "verify" / "mock_test_resume.pdf"
    with open(dummy_pdf, "wb") as f:
        f.write(b"%PDF-1.4 Mock PDF for verification\n%%EOF")

    mock_url = f"file://{mock_file}"

    filler = ATSAssistedFiller(headless=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            result = await filler.fill_ats_page(page, mock_url, resume_pdf_path=str(dummy_pdf))
            assert result["status"] == "ready_for_review"
            assert result["fields_filled"] >= 4, f"Expected >= 4 fields, got {result['fields_filled']}"
            assert result["resume_attached"] is True, "Resume was not attached"
            print(f"   ✅ Mock application filled successfully! Metrics: {result}")

            # Verify input values in DOM
            val_fn = await page.locator("input#first_name").input_value()
            val_em = await page.locator("input#email").input_value()
            assert "Manjunath" in val_fn
            assert "@" in val_em
            print(f"   ✅ Verified DOM values: Name={val_fn}, Email={val_em}")

        finally:
            await browser.close()
            if mock_file.exists():
                os.remove(mock_file)
            if dummy_pdf.exists():
                os.remove(dummy_pdf)


async def main():
    test_url_resolution()
    await test_form_fill_with_apply_trigger()
    print("\n🎉 ALL ATS RESILIENCE VERIFICATIONS PASSED!")


if __name__ == "__main__":
    asyncio.run(main())
