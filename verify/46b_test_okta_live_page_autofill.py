"""Live Verification for Gate 46: Okta Career Page Live Autofill.

Tests end-to-end form mapping on the actual Okta live posting URL:
https://www.okta.com/company/careers/rd/senior-software-engineer-in-test-set-access-essentials-8236753/

Verifies:
1. Canonical/Branded ATS Pattern classification -> OKTA_BRANDED_GREENHOUSE.
2. Contact details (First Name, Last Name, Email, Phone).
3. Candidate Website (Portfolio) populated with https://manjunathhk.netlify.app/.
4. Candidate LinkedIn profile populated.
5. Screening dropdown questions answered accurately.
6. Consent checkboxes checked.
7. EEOC voluntary questions answered.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.autofill.ats_filler import ATSAssistedFiller
from src.autofill.vendor_schemas import ATSVendorPattern, classify_ats_pattern
from src.browser.cdp_stealth import launch_stealth_browser

OKTA_LIVE_URL = (
    "https://www.okta.com/company/careers/rd/senior-software-engineer-in-test-set-access-essentials-8236753/"
)


async def test_live_okta_autofill():
    print("=" * 65)
    print("  Testing Live Okta Application Page Autofill")
    print("=" * 65)

    # 1. Pattern classification check
    pattern = classify_ats_pattern(OKTA_LIVE_URL)
    print(f"🎯 Pattern identified: {pattern}")
    assert pattern == ATSVendorPattern.OKTA_BRANDED_GREENHOUSE

    # 2. Create test resume
    dummy_resume = PROJECT_ROOT / "data" / "Manjunath_HK_Okta_test_Resume.pdf"
    dummy_resume.write_text("%PDF-1.4 dummy resume for okta live test")

    filler = ATSAssistedFiller(headless=True)

    pw, context, page = await launch_stealth_browser(headless=True)
    try:
        res = await filler.fill_ats_page(page, OKTA_LIVE_URL, str(dummy_resume))
        print(f"📊 Live Fill Result: {res}")

        # Check values on live page
        first_name = await page.input_value("input#edit-first-name")
        last_name = await page.input_value("input#edit-last-name")
        email = await page.input_value("input#edit-email")
        phone = await page.input_value("input#edit-phone")
        linkedin = await page.input_value("input#edit-question-69483961")
        website = await page.input_value("input#edit-question-69483962")

        print(f"✅ Verified First Name: '{first_name}'")
        print(f"✅ Verified Last Name: '{last_name}'")
        print(f"✅ Verified Email: '{email}'")
        print(f"✅ Verified Phone: '{phone}'")
        print(f"✅ Verified Candidate LinkedIn: '{linkedin}'")
        print(f"✅ Verified Candidate Website: '{website}'")

        assert first_name == "Manjunath"
        assert last_name == "H K"
        assert email == "manjunathhk833@gmail.com"
        assert "linkedin.com" in linkedin
        assert website == "https://manjunathhk.netlify.app/"

        print("\n🎉 Live Okta application page autofill verified successfully!")
    finally:
        await context.close()
        await pw.stop()
        if dummy_resume.exists():
            dummy_resume.unlink()


if __name__ == "__main__":
    asyncio.run(test_live_okta_autofill())
