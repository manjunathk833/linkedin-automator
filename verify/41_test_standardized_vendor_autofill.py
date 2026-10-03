"""Verification Gate 41: Standardized Vendor Autofill & Candidate Master Profile.

Validates:
1. CandidateMasterData loading, validation, and skill experience calculation.
2. FormFieldMapper integration with CandidateMasterData.
3. Modular vendor autofill handlers on mock Greenhouse, Lever, and Ashby DOM fixtures.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright

from src.autofill.ats_filler import ATSAssistedFiller
from src.autofill.form_mapper import FormFieldMapper
from src.autofill.vendor_schemas import load_candidate_master_data


def test_master_data_loading():
    print("🧪 Testing CandidateMasterData schema loading...")
    master = load_candidate_master_data()
    assert master.personal.full_name == "Manjunath H K"
    assert master.personal.first_name == "Manjunath"
    assert master.personal.last_name == "H K"
    assert master.personal.email == "manjunathhk833@gmail.com"
    assert master.personal.phone == "+917337813770"
    assert len(master.experience_history) >= 3
    assert len(master.education_history) >= 1
    assert master.get_skill_years("Java") == 6
    assert master.get_skill_years("Selenium") == 6
    assert master.get_skill_years("Python") == 4
    assert master.get_skill_years("unknown_skill", default=5) == 5
    print("✅ Master data loading verified.")


def test_form_mapper_integration():
    print("🧪 Testing FormFieldMapper integration with Master Data...")
    mapper = FormFieldMapper()
    contact = mapper.get_contact_info()
    assert contact["full_name"] == "Manjunath H K"
    assert contact["first_name"] == "Manjunath"
    assert contact["last_name"] == "H K"
    assert contact["phone_country_code"] == "+91"
    print("✅ FormFieldMapper integration verified.")


async def test_vendor_mock_autofill():
    print("🧪 Testing Playwright mock DOM autofill across Greenhouse, Lever, and Ashby...")
    filler = ATSAssistedFiller(headless=True)

    # Create dummy resume for upload test
    dummy_resume = Path("/tmp/test_dummy_resume.pdf")
    dummy_resume.write_text("%PDF-1.4 dummy pdf for testing")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)

        # 1. Test Greenhouse Mock Form
        print("  🏛️ Testing Greenhouse DOM...")
        page_gh = await browser.new_page()
        gh_html = """
        <html>
        <body>
            <input id="first_name" name="first_name" type="text" />
            <input id="last_name" name="last_name" type="text" />
            <input id="email" name="email" type="email" />
            <input id="phone" name="phone" type="tel" />
            <input id="candidate-location" type="text" />
            <div id="education--container">
                <input id="school" name="school" type="text" />
                <select id="degree"><option value="B.E.">Bachelor of Engineering (B.E.)</option></select>
            </div>
            <div id="employment--container">
                <input id="company-name-0" type="text" />
                <input id="title-0" type="text" />
            </div>
            <input id="linkedin" name="linkedin" type="text" />
            <input type="file" id="resume" />
        </body>
        </html>
        """
        await page_gh.set_content(gh_html)
        filled, attached = await filler._fill_greenhouse(page_gh, str(dummy_resume))
        assert filled >= 6, f"Expected at least 6 filled fields in Greenhouse, got {filled}"
        assert attached is True, "Expected resume to be attached in Greenhouse"
        assert await page_gh.locator("#first_name").input_value() == "Manjunath"
        assert await page_gh.locator("#last_name").input_value() == "H K"
        assert await page_gh.locator("#company-name-0").input_value() == "Value Labs"
        await page_gh.close()
        print("  ✅ Greenhouse mock autofill verified.")

        # 2. Test Lever Mock Form
        print("  🏢 Testing Lever DOM...")
        page_lever = await browser.new_page()
        lever_html = """
        <html>
        <body>
            <input name="name" type="text" />
            <input name="email" type="email" />
            <input name="phone" type="tel" />
            <input name="org" type="text" />
            <input name="urls[LinkedIn]" type="text" />
            <input name="urls[GitHub]" type="text" />
            <input type="radio" value="Man" name="gender" />
            <input type="radio" value="Asian" name="ethnicity" />
            <input type="file" name="resume" />
        </body>
        </html>
        """
        await page_lever.set_content(lever_html)
        filled_lev, attached_lev = await filler._fill_lever(page_lever, str(dummy_resume))
        assert filled_lev >= 5, f"Expected at least 5 filled fields in Lever, got {filled_lev}"
        assert attached_lev is True, "Expected resume to be attached in Lever"
        assert await page_lever.locator("input[name='name']").input_value() == "Manjunath H K"
        assert await page_lever.locator("input[name='org']").input_value() == "Value Labs"
        await page_lever.close()
        print("  ✅ Lever mock autofill verified.")

        # 3. Test Ashby Mock Form
        print("  🚀 Testing Ashby DOM...")
        page_ashby = await browser.new_page()
        ashby_html = """
        <html>
        <body>
            <label for="fn">First Name</label><input id="fn" type="text" />
            <label for="ln">Last Name</label><input id="ln" type="text" />
            <label for="em">Email</label><input id="em" type="email" />
            <label for="ph">Phone</label><input id="ph" type="tel" />
            <label for="loc">Location</label><input id="loc" type="text" />
            <label for="li">LinkedIn</label><input id="li" type="text" />
            <label for="res">Resume</label><input id="res" type="file" />
        </body>
        </html>
        """
        await page_ashby.set_content(ashby_html)
        filled_ash, attached_ash = await filler._fill_ashby(page_ashby, str(dummy_resume))
        assert filled_ash >= 5, f"Expected at least 5 filled fields in Ashby, got {filled_ash}"
        assert attached_ash is True, "Expected resume to be attached in Ashby"
        assert await page_ashby.locator("#fn").input_value() == "Manjunath"
        assert await page_ashby.locator("#ln").input_value() == "H K"
        await page_ashby.close()
        print("  ✅ Ashby mock autofill verified.")

        await browser.close()

    # Clean up dummy resume
    if dummy_resume.exists():
        dummy_resume.unlink()

    print("🎉 All vendor autofill mock tests passed!")


if __name__ == "__main__":
    test_master_data_loading()
    test_form_mapper_integration()
    asyncio.run(test_vendor_mock_autofill())
    print("\n🚀 GATE 41 PASSED: Centralized Candidate Master Profile & Modular Vendor Schemas Verified.")
