"""Verification Gate 46: Okta Custom ATS Branded Vendor Schema & Autofill Heuristics.

Validates:
1. Pattern Recognition Engine: Accurate classification of ATS URLs across:
   - OKTA_BRANDED_GREENHOUSE
   - GREENHOUSE_STANDARD
   - LEVER_STANDARD
   - ASHBY_STANDARD
   - WORKDAY_STANDARD
   - LINKEDIN_EASY_APPLY
   - GENERIC_ATS_FALLBACK
2. Vendor Schema Registry: Schema retrieval, selector coverage, and website/portfolio mapping.
3. Candidate Master Data: Inclusion and integrity of candidate portfolio URL (https://manjunathhk.netlify.app/).
4. Playwright DOM Autofill on Okta Branded Structure:
   - First Name & Last Name
   - Email & Phone
   - Resume attachment
   - LinkedIn Profile
   - Website (Portfolio)
   - Screening questions (Work auth, Visa sponsorship, Conflicts, Outside activities, Prior employment)
   - Legal consent checkboxes
   - Voluntary EEOC disclosures (Gender, Race, Veteran status)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright

from src.autofill.ats_filler import ATSAssistedFiller
from src.autofill.vendor_schemas import (
    ATSVendorPattern,
    classify_ats_pattern,
    get_vendor_schema,
    load_candidate_master_data,
)


def test_ats_pattern_classification():
    print("🧪 Step 1: Testing ATS pattern classification...")

    okta_url = "https://www.okta.com/company/careers/rd/senior-software-engineer-in-test-set-access-essentials-8236753/"
    assert classify_ats_pattern(okta_url) == ATSVendorPattern.OKTA_BRANDED_GREENHOUSE, (
        f"Expected OKTA_BRANDED_GREENHOUSE, got {classify_ats_pattern(okta_url)}"
    )

    gh_url = "https://boards.greenhouse.io/coinbase/jobs/8095207"
    assert classify_ats_pattern(gh_url) == ATSVendorPattern.GREENHOUSE_STANDARD

    lever_url = "https://jobs.lever.co/netflix/12345"
    assert classify_ats_pattern(lever_url) == ATSVendorPattern.LEVER_STANDARD

    ashby_url = "https://jobs.ashbyhq.com/zapier/12345"
    assert classify_ats_pattern(ashby_url) == ATSVendorPattern.ASHBY_STANDARD

    workday_url = "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/123"
    assert classify_ats_pattern(workday_url) == ATSVendorPattern.WORKDAY_STANDARD

    linkedin_url = "https://www.linkedin.com/jobs/view/12345"
    assert classify_ats_pattern(linkedin_url) == ATSVendorPattern.LINKEDIN_EASY_APPLY

    generic_url = "https://unknown-startup.io/careers/apply"
    assert classify_ats_pattern(generic_url) == ATSVendorPattern.GENERIC_ATS_FALLBACK

    print("✅ Step 1: All 7 ATS pattern classifications verified.")


def test_okta_vendor_schema_and_master_data():
    print("🧪 Step 2: Testing Okta vendor schema and candidate master data...")

    schema = get_vendor_schema(ATSVendorPattern.OKTA_BRANDED_GREENHOUSE)
    assert schema, "Okta vendor schema not found in registry"
    selectors = schema.get("selectors", {})

    required_keys = [
        "first_name",
        "last_name",
        "email",
        "phone",
        "resume",
        "linkedin",
        "website",
        "work_authorization",
        "visa_sponsorship",
        "conflict_relatives",
        "outside_activities",
        "previous_employment",
        "consent_privacy",
        "consent_evaluation",
        "eeoc_gender",
        "eeoc_race",
        "eeoc_veteran",
    ]
    for key in required_keys:
        assert key in selectors, f"Missing selector key in Okta schema: {key}"

    master_data = load_candidate_master_data()
    assert master_data.profiles.portfolio == "https://manjunathhk.netlify.app/", (
        f"Candidate portfolio does not match expected URL: {master_data.profiles.portfolio}"
    )
    assert master_data.personal.first_name == "Manjunath"
    assert master_data.personal.last_name == "H K"
    assert master_data.personal.email == "manjunathhk833@gmail.com"

    print("✅ Step 2: Okta vendor schema and candidate portfolio verified.")


OKTA_MOCK_HTML = """
<!DOCTYPE html>
<html>
<head><title>Okta Careers Application</title></head>
<body>
    <form id="okta-job-application">
        <input type="text" id="edit-first-name" name="first_name" />
        <input type="text" id="edit-last-name" name="last_name" />
        <input type="email" id="edit-email" name="email" />
        <input type="tel" id="edit-phone" name="phone" />
        <input type="file" id="edit-resume-upload" name="files[resume]" />
        
        <div class="form-item">
            <label for="edit-question-69483961">LinkedIn Profile</label>
            <input type="text" id="edit-question-69483961" name="question_69483961" />
        </div>
        
        <div class="form-item">
            <label for="edit-question-69483962">Website</label>
            <input type="text" id="edit-question-69483962" name="question_69483962" />
        </div>
        
        <div class="form-item">
            <label for="edit-question-69483963">Are you legally authorized to work in the country you reside?</label>
            <select id="edit-question-69483963" name="question_69483963">
                <option value="">Choose</option>
                <option value="1">Yes</option>
                <option value="0">No</option>
            </select>
        </div>
        
        <div class="form-item">
            <label for="edit-question-69483964">Will you now or in the future require Visa Sponsorship?</label>
            <select id="edit-question-69483964" name="question_69483964">
                <option value="">Choose</option>
                <option value="1">Yes</option>
                <option value="0">No</option>
            </select>
        </div>

        <div class="form-item">
            <label for="edit-question-69483965">Family members / relatives conflict</label>
            <select id="edit-question-69483965" name="question_69483965">
                <option value="">Choose</option>
                <option value="1">Yes</option>
                <option value="0">No</option>
            </select>
        </div>

        <div class="form-item">
            <label for="edit-question-69483967">Outside business activities</label>
            <select id="edit-question-69483967" name="question_69483967">
                <option value="">Choose</option>
                <option value="1">Yes</option>
                <option value="0">No</option>
            </select>
        </div>

        <div class="form-item">
            <label for="edit-question-69483969">Employed by Okta in the past?</label>
            <select id="edit-question-69483969" name="question_69483969">
                <option value="">Choose</option>
                <option value="1">Yes</option>
                <option value="0">No</option>
            </select>
        </div>
        
        <div class="form-item">
            <label><input type="checkbox" id="edit-question-69483970-753704919" name="question_69483970[753704919]" /> I acknowledge</label>
        </div>
        <div class="form-item">
            <label><input type="checkbox" id="edit-question-69483971-753704920" name="question_69483971[753704920]" /> Yes</label>
        </div>
        
        <select id="edit-compliance-section-gender-0" name="gender">
            <option value="">Choose</option>
            <option value="1">Male</option>
            <option value="2">Female</option>
        </select>
        
        <select id="edit-compliance-section-race-0" name="race">
            <option value="">Choose</option>
            <option value="2">Asian</option>
            <option value="5">White</option>
        </select>

        <select id="edit-compliance-section-veteran-status-0" name="veteran">
            <option value="">Choose</option>
            <option value="1">I am not a protected veteran</option>
            <option value="2">I identify as protected veteran</option>
        </select>
    </form>
</body>
</html>
"""


async def test_okta_form_autofill():
    print("🧪 Step 3: Testing Okta autofill heuristics on Okta DOM structure...")

    dummy_resume = Path("/tmp/test_okta_resume.pdf")
    dummy_resume.write_text("%PDF-1.4 dummy resume for okta test")

    filler = ATSAssistedFiller(headless=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        # Load Okta HTML fixture
        await page.set_content(OKTA_MOCK_HTML)

        # Directly invoke _fill_okta
        filled, attached = await filler._fill_okta(page, str(dummy_resume))

        print(f"📊 Okta Autofill Result: {filled} fields populated, Resume Attached={attached}")

        # Assertions
        assert await page.input_value("input#edit-first-name") == "Manjunath"
        assert await page.input_value("input#edit-last-name") == "H K"
        assert await page.input_value("input#edit-email") == "manjunathhk833@gmail.com"
        assert await page.input_value("input#edit-phone") == "+917337813770"
        assert attached is True

        # Assert LinkedIn was populated
        linkedin_val = await page.input_value("input#edit-question-69483961")
        assert "linkedin.com" in linkedin_val

        # Assert candidate website was populated
        website_val = await page.input_value("input#edit-question-69483962")
        assert website_val == "https://manjunathhk.netlify.app/", f"Website value mismatch: {website_val}"

        # Assert Screening Dropdowns
        auth_val = await page.input_value("select#edit-question-69483963")
        assert auth_val == "1"  # "Yes" option value

        visa_val = await page.input_value("select#edit-question-69483964")
        assert visa_val == "0"  # "No" option value

        rel_val = await page.input_value("select#edit-question-69483965")
        assert rel_val == "0"  # "No" option value

        out_val = await page.input_value("select#edit-question-69483967")
        assert out_val == "0"  # "No" option value

        prev_val = await page.input_value("select#edit-question-69483969")
        assert prev_val == "0"  # "No" option value

        # Assert Checkboxes
        assert await page.is_checked("input#edit-question-69483970-753704919") is True
        assert await page.is_checked("input#edit-question-69483971-753704920") is True

        # Assert EEOC
        assert await page.input_value("select#edit-compliance-section-gender-0") == "1"
        assert await page.input_value("select#edit-compliance-section-race-0") == "2"
        assert await page.input_value("select#edit-compliance-section-veteran-status-0") == "1"

        await browser.close()

    if dummy_resume.exists():
        dummy_resume.unlink()

    print("✅ Step 3: Okta DOM autofill heuristics completely verified.")


async def main():
    print("=" * 65)
    print("  Gate 46: Okta Custom ATS Branded Vendor Schema & Autofill")
    print("=" * 65)

    test_ats_pattern_classification()
    test_okta_vendor_schema_and_master_data()
    await test_okta_form_autofill()

    print("\n🎉 ALL GATE 46 VERIFICATION TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(main())
