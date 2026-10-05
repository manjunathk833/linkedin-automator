"""Verification Gate 56: Workday ATS Vendor Schema & Multi-Stage Autofill Heuristics.

Validates:
1. Pattern Recognition Engine: Accurate classification of ATS URLs across:
   - WORKDAY_STANDARD (JioStar, Nvidia, Adobe, Walmart, etc. on *.myworkdayjobs.com)
   - ORACLE_CLOUD_HCM (Akamai Oracle Cloud HCM)
   - OKTA_BRANDED_GREENHOUSE
   - DATABRICKS_CUSTOM_GREENHOUSE
   - COINBASE_CUSTOM_GREENHOUSE
   - GREENHOUSE_STANDARD
   - LEVER_STANDARD
   - ASHBY_STANDARD
   - LINKEDIN_EASY_APPLY
   - GENERIC_ATS_FALLBACK
2. Vendor Schema Registry & Candidate Master Data:
   - Schema retrieval, DOM fingerprints, and selector coverage (Apply Button, Apply Manually,
     Create Account fields, Password, Checkbox, Sign In, OTP, Name, Address, Phone, Source, Resume)
   - Candidate master data verification (including workday_default_password complexity criteria)
3. Playwright DOM Multi-Stage Autofill on Workday Structure:
   - Cookie consent dismissal
   - Stage 1: 'Apply' -> 'Apply Manually' modal traversal
   - Stage 2: 'Create Account' credentials population & terms agreement
   - Stage 3: 'My Information' section (Name, Address, City, State, Postal Code, Phone, Source)
   - Stage 4: 'My Experience' section (Resume PDF file dropzone attachment & website links)
4. Assertions on zero field contamination and synthetic event firing
5. fill_ats_page direct routing validation for WORKDAY_STANDARD
"""

from __future__ import annotations

import asyncio
import re
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

    # Workday URLs
    jiostar_url = (
        "https://jiostar.wd102.myworkdayjobs.com/JioStar/job/Bengaluru--We-Work/"
        "Senior-Software-Development-Engineer-Test-II_JR10381?source=LinkedIn"
    )
    assert classify_ats_pattern(jiostar_url) == ATSVendorPattern.WORKDAY_STANDARD, (
        f"Expected WORKDAY_STANDARD, got {classify_ats_pattern(jiostar_url)}"
    )

    nvidia_workday = "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/123"
    assert classify_ats_pattern(nvidia_workday) == ATSVendorPattern.WORKDAY_STANDARD

    adobe_workday = "https://adobe.wd5.myworkdayjobs.com/adobejobs/job/Bengaluru/Software-Engineer_123"
    assert classify_ats_pattern(adobe_workday) == ATSVendorPattern.WORKDAY_STANDARD

    walmart_workday = "https://walmart.wd5.myworkdayjobs.com/WalmartExternal/job/Bentonville-AR/Software-Engineer_R-123"
    assert classify_ats_pattern(walmart_workday) == ATSVendorPattern.WORKDAY_STANDARD

    workday_direct = "https://workday.com/en-us/company/careers/job-123"
    assert classify_ats_pattern(workday_direct) == ATSVendorPattern.WORKDAY_STANDARD

    # Other supported vendors
    oracle_url = "https://fa-extu-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/3314"
    assert classify_ats_pattern(oracle_url) == ATSVendorPattern.ORACLE_CLOUD_HCM

    okta_url = "https://www.okta.com/company/careers/rd/senior-software-engineer-in-test-8236753/"
    assert classify_ats_pattern(okta_url) == ATSVendorPattern.OKTA_BRANDED_GREENHOUSE

    databricks_url = "https://www.databricks.com/company/careers/engineering/job-123"
    assert classify_ats_pattern(databricks_url) == ATSVendorPattern.DATABRICKS_CUSTOM_GREENHOUSE

    coinbase_url = "https://www.coinbase.com/careers/positions/8095207"
    assert classify_ats_pattern(coinbase_url) == ATSVendorPattern.COINBASE_CUSTOM_GREENHOUSE

    gh_url = "https://boards.greenhouse.io/coinbase/jobs/8095207"
    assert classify_ats_pattern(gh_url) == ATSVendorPattern.GREENHOUSE_STANDARD

    lever_url = "https://jobs.lever.co/netflix/12345"
    assert classify_ats_pattern(lever_url) == ATSVendorPattern.LEVER_STANDARD

    ashby_url = "https://jobs.ashbyhq.com/zapier/12345"
    assert classify_ats_pattern(ashby_url) == ATSVendorPattern.ASHBY_STANDARD

    linkedin_url = "https://www.linkedin.com/jobs/view/4429248151/"
    assert classify_ats_pattern(linkedin_url) == ATSVendorPattern.LINKEDIN_EASY_APPLY

    generic_url = "https://unknown-startup.io/careers/apply"
    assert classify_ats_pattern(generic_url) == ATSVendorPattern.GENERIC_ATS_FALLBACK

    print("✅ Step 1: All ATS pattern classifications (including Workday tenants) verified.")


def test_workday_vendor_schema_and_master_data():
    print("🧪 Step 2: Testing Workday vendor schema and candidate master data...")

    schema = get_vendor_schema(ATSVendorPattern.WORKDAY_STANDARD)
    assert schema, "Workday vendor schema not found in registry"
    selectors = schema.get("selectors", {})

    required_keys = [
        "apply_button",
        "apply_manually",
        "autofill_with_resume",
        "create_account_email",
        "create_account_password",
        "create_account_verify_password",
        "create_account_checkbox",
        "create_account_submit",
        "create_account_link",
        "sign_in_link",
        "sign_in_submit",
        "otp_input",
        "first_name",
        "last_name",
        "address_line1",
        "city",
        "state",
        "postal_code",
        "phone_device_type",
        "phone_country_code",
        "phone_number",
        "source",
        "resume",
        "save_and_continue",
    ]
    for key in required_keys:
        assert key in selectors, f"Missing required Workday selector mapping: '{key}'"
        assert len(selectors[key]) > 0, f"Selector list for '{key}' is empty"

    # Verify candidate master data and Workday password complexity
    master_data = load_candidate_master_data()
    assert master_data.personal.first_name, "Candidate first name missing"
    assert master_data.personal.last_name, "Candidate last name missing"
    assert master_data.personal.email, "Candidate email missing"
    assert master_data.personal.phone, "Candidate phone missing"

    pwd = master_data.personal.workday_default_password
    assert pwd, "Candidate master data missing workday_default_password"
    assert len(pwd) >= 8, f"Workday password too short: {len(pwd)} chars"
    assert re.search(r"[A-Z]", pwd), "Workday password must contain an uppercase letter"
    assert re.search(r"[a-z]", pwd), "Workday password must contain a lowercase letter"
    assert re.search(r"[0-9]", pwd), "Workday password must contain a numeric digit"
    assert re.search(r"[@#$%^&*!_~+=?]", pwd), "Workday password must contain a special character"

    print("✅ Step 2: Workday vendor schema and candidate master data verified.")


WORKDAY_MOCK_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Senior SDET II (JR10381) - JioStar Workday Mock</title>
  <style>
    .hidden { display: none !important; }
    .stage-card { margin: 20px; padding: 20px; border: 1px solid #ccc; border-radius: 8px; }
    .modal-overlay { background: rgba(0,0,0,0.5); padding: 20px; border: 2px solid #0056b3; }
  </style>
</head>
<body>
  <!-- Cookie Banner -->
  <div id="cookie-banner" style="background:#f4f4f4; padding:10px;">
    <span>Workday uses cookies.</span>
    <button id="onetrust-accept-btn-handler" onclick="document.getElementById('cookie-banner').style.display='none'">Accept All Cookies</button>
  </div>

  <!-- Stage 1: Job Description Page -->
  <div id="stage-1" class="stage-card">
    <h1>Senior Software Development Engineer - Test II (JR10381)</h1>
    <p>JioStar - Bengaluru, Karnataka, India</p>
    <button data-automation-id="applyButton" onclick="openApplyModal()">Apply</button>
  </div>

  <!-- Stage 1 Modal: Start Your Application Options -->
  <div id="apply-modal" class="modal-overlay hidden">
    <h3>Start Your Application</h3>
    <button data-automation-id="autofillWithResume">Autofill with Resume</button>
    <button data-automation-id="applyManually" onclick="goToStage(2)">Apply Manually</button>
    <button data-automation-id="useMyLastApplication">Use My Last Application</button>
  </div>

  <!-- Stage 2: Create Account / Sign In Gate -->
  <div id="stage-2" class="stage-card hidden">
    <h2>Create Account</h2>
    <div>
      <label for="email">Email Address *</label>
      <input type="email" id="email" data-automation-id="email" />
    </div>
    <div>
      <label for="password">Password *</label>
      <input type="password" id="password" data-automation-id="password" />
    </div>
    <div>
      <label for="verifyPassword">Verify New Password *</label>
      <input type="password" id="verifyPassword" data-automation-id="verifyPassword" />
    </div>
    <div>
      <label>
        <input type="checkbox" id="createAccountCheckbox" data-automation-id="createAccountCheckbox" />
        I have read and agree to the Terms of Use and Privacy Policy
      </label>
    </div>
    <button type="button" data-automation-id="createAccountSubmitButton" onclick="goToStage(3)">Create Account</button>
  </div>

  <!-- Stage 3: My Information Form -->
  <div id="stage-3" class="stage-card hidden">
    <h2>My Information</h2>

    <!-- Country Dropdown -->
    <div>
      <label>Country *</label>
      <select data-automation-id="legalNameSection_country">
        <option value="United States of America">United States of America</option>
        <option value="India">India</option>
      </select>
    </div>

    <!-- Name Section -->
    <div>
      <label for="first-name">Legal First Name *</label>
      <input type="text" id="first-name" data-automation-id="legalNameSection_firstName" />
    </div>
    <div>
      <label for="last-name">Legal Last Name *</label>
      <input type="text" id="last-name" data-automation-id="legalNameSection_lastName" />
    </div>

    <!-- Address Section -->
    <div>
      <label for="address-line1">Address Line 1 *</label>
      <input type="text" id="address-line1" data-automation-id="addressSection_addressLine1" />
    </div>
    <div>
      <label for="city">City *</label>
      <input type="text" id="city" data-automation-id="addressSection_city" />
    </div>
    <div>
      <label>State / Province *</label>
      <select data-automation-id="addressSection_countryRegion">
        <option value="Maharashtra">Maharashtra</option>
        <option value="Karnataka">Karnataka</option>
      </select>
    </div>
    <div>
      <label for="postal-code">Postal Code *</label>
      <input type="text" id="postal-code" data-automation-id="addressSection_postalCode" />
    </div>

    <!-- Phone Section -->
    <div>
      <label>Phone Device Type *</label>
      <select data-automation-id="phone-device-type">
        <option value="Landline">Landline</option>
        <option value="Mobile">Mobile</option>
      </select>
    </div>
    <div>
      <label>Country Phone Code *</label>
      <select data-automation-id="countryPhoneCode">
        <option value="United States (+1)">United States (+1)</option>
        <option value="India (+91)">India (+91)</option>
      </select>
    </div>
    <div>
      <label for="phone-number">Phone Number *</label>
      <input type="tel" id="phone-number" data-automation-id="phone-number" />
    </div>

    <!-- Source -->
    <div>
      <label>How Did You Hear About Us? *</label>
      <select data-automation-id="sourcePrompt">
        <option value="Company Website">Company Website</option>
        <option value="LinkedIn">LinkedIn</option>
      </select>
    </div>

    <button type="button" data-automation-id="bottom-navigation-next-button" onclick="goToStage(4)">Save and Continue</button>
  </div>

  <!-- Stage 4: My Experience Form -->
  <div id="stage-4" class="stage-card hidden">
    <h2>My Experience</h2>

    <div data-automation-id="file-upload-dropzone">
      <label>Resume / CV *</label>
      <input type="file" name="resume" accept=".pdf,.doc,.docx" />
    </div>

    <div>
      <label>Websites</label>
      <input type="text" data-automation-id="website" placeholder="https://" />
    </div>
  </div>

  <script>
    function openApplyModal() {
      document.getElementById('apply-modal').classList.remove('hidden');
    }
    function goToStage(stageNum) {
      document.getElementById('stage-1').classList.add('hidden');
      document.getElementById('apply-modal').classList.add('hidden');
      document.getElementById('stage-2').classList.add('hidden');
      document.getElementById('stage-3').classList.add('hidden');
      document.getElementById('stage-4').classList.add('hidden');
      document.getElementById('stage-' + stageNum).classList.remove('hidden');
    }
  </script>
</body>
</html>
"""


async def test_workday_playwright_autofill_simulation():
    print("🧪 Step 3: Testing Workday multi-stage autofill heuristics on Playwright...")

    master_data = load_candidate_master_data()
    filler = ATSAssistedFiller(headless=True, master_data=master_data)

    dummy_pdf = PROJECT_ROOT / "verify" / "resume_test_output.pdf"
    if not dummy_pdf.exists():
        dummy_pdf = PROJECT_ROOT / "verify" / "test_sample_resume.pdf"
        dummy_pdf.write_bytes(b"%PDF-1.4 mock resume content")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Set mock Workday DOM
        await page.set_content(WORKDAY_MOCK_HTML, wait_until="domcontentloaded")

        # Verify Stage 1 is initially visible
        assert await page.locator("#stage-1").is_visible(), "Stage 1 should be initially visible"
        assert not await page.locator("#stage-2").is_visible(), "Stage 2 should be hidden initially"
        assert not await page.locator("#stage-3").is_visible(), "Stage 3 should be hidden initially"

        # Execute Workday multi-stage autofill
        fields_filled, resume_attached = await filler._fill_workday(
            target=page,
            resume_pdf_path=str(dummy_pdf),
        )

        print(f"📊 Workday Autofill Results: fields_filled={fields_filled}, resume_attached={resume_attached}")
        assert fields_filled >= 8, f"Expected at least 8 fields filled, got {fields_filled}"
        assert resume_attached is True, "Resume should have been successfully attached"

        # Assert Stage 4 is now active after multi-stage traversal
        assert await page.locator("#stage-4").is_visible(), "Stage 4 (My Experience) should be visible after completion"

        # Verify Stage 2 credentials populated
        email_val = await page.locator("input[data-automation-id='email']").input_value()
        assert email_val == master_data.personal.email, f"Email mismatch: {email_val} vs {master_data.personal.email}"

        pwd_val = await page.locator("input[data-automation-id='password']").input_value()
        expected_pwd = master_data.personal.workday_default_password
        assert pwd_val == expected_pwd, f"Password mismatch: {pwd_val}"

        verify_pwd_val = await page.locator("input[data-automation-id='verifyPassword']").input_value()
        assert verify_pwd_val == expected_pwd, f"Verify password mismatch: {verify_pwd_val}"

        agree_checked = await page.locator("input[data-automation-id='createAccountCheckbox']").is_checked()
        assert agree_checked is True, "Create account agreement checkbox must be checked"

        # Verify Stage 3 personal and contact details
        first_val = await page.locator("input[data-automation-id='legalNameSection_firstName']").input_value()
        assert first_val == master_data.personal.first_name, f"First name mismatch: {first_val}"

        last_val = await page.locator("input[data-automation-id='legalNameSection_lastName']").input_value()
        assert last_val == master_data.personal.last_name, f"Last name mismatch: {last_val}"

        city_val = await page.locator("input[data-automation-id='addressSection_city']").input_value()
        assert city_val == master_data.personal.city, f"City mismatch: {city_val}"

        postal_val = await page.locator("input[data-automation-id='addressSection_postalCode']").input_value()
        assert postal_val == master_data.personal.postal_code, f"Postal code mismatch: {postal_val}"

        phone_val = await page.locator("input[data-automation-id='phone-number']").input_value()
        expected_digits = master_data.personal.phone.replace("+91", "").strip()
        assert expected_digits in phone_val or phone_val in master_data.personal.phone, (
            f"Phone mismatch: {phone_val} vs {master_data.personal.phone}"
        )

        # Verify dropdown selections
        country_val = await page.locator("select[data-automation-id='legalNameSection_country']").input_value()
        assert "India" in country_val, f"Country should be India, got: {country_val}"

        device_val = await page.locator("select[data-automation-id='phone-device-type']").input_value()
        assert "Mobile" in device_val, f"Phone device type should be Mobile, got: {device_val}"

        code_val = await page.locator("select[data-automation-id='countryPhoneCode']").input_value()
        assert "India (+91)" in code_val or "+91" in code_val, f"Phone code should be +91, got: {code_val}"

        source_val = await page.locator("select[data-automation-id='sourcePrompt']").input_value()
        assert "LinkedIn" in source_val, f"Source should be LinkedIn, got: {source_val}"

        # Verify Stage 4 website link populated
        website_val = await page.locator("input[data-automation-id='website']").input_value()
        expected_web = master_data.profiles.linkedin or master_data.profiles.portfolio
        assert website_val == expected_web, f"Website mismatch: {website_val} vs {expected_web}"

        # Cookie banner should have been dismissed
        cookie_visible = await page.locator("#cookie-banner").is_visible()
        assert not cookie_visible, "Cookie banner should be dismissed"

        await browser.close()

    print("✅ Step 3: Workday multi-stage autofill heuristics verified with zero contamination.")


async def test_full_fill_ats_page_routing_workday():
    print("🧪 Step 4: Testing fill_ats_page direct routing for Workday...")

    master_data = load_candidate_master_data()
    filler = ATSAssistedFiller(headless=True, master_data=master_data)

    dummy_pdf = PROJECT_ROOT / "verify" / "resume_test_output.pdf"

    jiostar_workday_url = (
        "https://jiostar.wd102.myworkdayjobs.com/JioStar/job/Bengaluru--We-Work/"
        "Senior-Software-Development-Engineer-Test-II_JR10381?source=LinkedIn"
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Intercept Workday URL to serve WORKDAY_MOCK_HTML
        await page.route(
            "**/JioStar/**",
            lambda route: route.fulfill(
                status=200,
                body=WORKDAY_MOCK_HTML,
                content_type="text/html",
            ),
        )

        result = await filler.fill_ats_page(
            page=page,
            job_url=jiostar_workday_url,
            resume_pdf_path=str(dummy_pdf) if dummy_pdf.exists() else None,
        )

        assert result["status"] == "ready_for_review", f"Unexpected status: {result['status']}"
        assert result["fields_filled"] >= 8, f"Fields filled too low: {result['fields_filled']}"
        assert result["resume_attached"] is True, "Resume was not attached"

        await browser.close()

    print("✅ Step 4: fill_ats_page direct routing for Workday verified successfully.")


WORKDAY_VERIFY_MOCK_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Workday Sign In - Verification Required</title>
</head>
<body>
  <div id="auth-verify-gate">
    <h2>Sign In</h2>
    <div data-automation-id="errorMessage">An email has been sent to you. Please verify your account.</div>
    <div>
      <label>Email Address</label>
      <input type="email" data-automation-id="email" value="manjunathhk833@gmail.com" />
    </div>
    <div>
      <label>Password</label>
      <input type="password" data-automation-id="password" />
    </div>
    <button type="button" data-automation-id="signInSubmitButton" onclick="simulateVerification()">Sign In</button>
  </div>

  <div id="stage-3" style="display:none;">
    <h2>My Information</h2>
    <input type="text" data-automation-id="legalNameSection_firstName" />
  </div>

  <script>
    function simulateVerification() {
      // Transition from sign-in verification gate to Stage 3 application form
      document.getElementById('auth-verify-gate').style.display = 'none';
      document.getElementById('stage-3').style.display = 'block';
    }
  </script>
</body>
</html>
"""


async def test_workday_email_verification_holding_gate():
    print("🧪 Step 5: Testing Workday email verification holding gate & auto-sign-in...")

    master_data = load_candidate_master_data()
    filler = ATSAssistedFiller(headless=True, master_data=master_data)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.set_content(WORKDAY_VERIFY_MOCK_HTML, wait_until="domcontentloaded")

        # 1. Assert email verification screen is detected
        is_verify_screen = await filler._is_workday_email_verification_screen(page)
        assert is_verify_screen is True, "Failed to detect Workday email verification screen"

        # 2. Execute verification holding loop (max_wait_seconds=15)
        workday_pwd = master_data.personal.workday_default_password
        resumed = await filler._handle_workday_email_verification_loop(
            target=page,
            workday_pwd=workday_pwd,
            max_wait_seconds=15,
        )

        assert resumed is True, "Verification loop did not resume successfully"

        # 3. Assert Stage 3 form is now mounted and visible
        assert await page.locator("#stage-3").is_visible(), "Stage 3 should be visible after verification"
        assert await page.locator("input[data-automation-id='legalNameSection_firstName']").is_visible()

        # 4. Verify password was populated before submission
        pwd_val = await page.locator("input[data-automation-id='password']").input_value()
        assert pwd_val == workday_pwd, f"Password was not populated: {pwd_val}"

        await browser.close()

    print("✅ Step 5: Workday email verification holding gate & auto-sign-in verified successfully.")


WORKDAY_SIGNIN_REDIRECT_MOCK_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Workday Sign In & Redirect Simulation</title>
  <style>.hidden { display: none; }</style>
</head>
<body>
  <!-- Stage 1: Overview -->
  <div id="stage-overview">
    <h2>Senior SDET Job</h2>
    <button data-automation-id="applyButton" onclick="onApplyClick()">Apply</button>
  </div>

  <!-- Modal -->
  <div id="stage-modal" class="hidden">
    <button data-automation-id="applyManually" onclick="goToSignIn()">Apply Manually</button>
  </div>

  <!-- Sign In -->
  <div id="stage-sign-in" class="hidden">
    <h2>Sign In</h2>
    <input type="email" data-automation-id="email" />
    <input type="password" data-automation-id="password" />
    <button type="button" data-automation-id="signInSubmitButton" onclick="simulateLoginRedirect()">Sign In</button>
  </div>

  <!-- Stage 3: My Information -->
  <div id="stage-info" class="hidden">
    <h2>My Information</h2>
    <input type="text" data-automation-id="legalNameSection_firstName" />
    <input type="text" data-automation-id="legalNameSection_lastName" />
    <button type="button" data-automation-id="bottom-navigation-next-button" onclick="goToExperience()">Save and Continue</button>
  </div>

  <!-- Stage 4: My Experience -->
  <div id="stage-exp" class="hidden">
    <h2>My Experience</h2>
    <input type="file" name="resume" />
    <input type="text" data-automation-id="website" />
  </div>

  <script>
    let isLoggedIn = false;
    function onApplyClick() {
      if (!isLoggedIn) {
        document.getElementById('stage-overview').classList.add('hidden');
        document.getElementById('stage-modal').classList.remove('hidden');
      } else {
        document.getElementById('stage-overview').classList.add('hidden');
        document.getElementById('stage-info').classList.remove('hidden');
      }
    }
    function goToSignIn() {
      document.getElementById('stage-modal').classList.add('hidden');
      document.getElementById('stage-sign-in').classList.remove('hidden');
    }
    function simulateLoginRedirect() {
      isLoggedIn = true;
      document.getElementById('stage-sign-in').classList.add('hidden');
      document.getElementById('stage-overview').classList.remove('hidden');
    }
    function goToExperience() {
      document.getElementById('stage-info').classList.add('hidden');
      document.getElementById('stage-exp').classList.remove('hidden');
    }
  </script>
</body>
</html>
"""


async def test_workday_post_auth_redirect_and_sign_in_loop():
    print("🧪 Step 6: Testing Workday post-auth redirection loop & re-entry...")

    master_data = load_candidate_master_data()
    filler = ATSAssistedFiller(headless=True, master_data=master_data)

    dummy_pdf = PROJECT_ROOT / "verify" / "resume_test_output.pdf"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.set_content(WORKDAY_SIGNIN_REDIRECT_MOCK_HTML, wait_until="domcontentloaded")

        fields_filled, resume_attached = await filler._fill_workday(
            target=page,
            resume_pdf_path=str(dummy_pdf) if dummy_pdf.exists() else None,
        )

        print(
            f"📊 Post-Auth Redirection Loop Results: fields_filled={fields_filled}, resume_attached={resume_attached}"
        )
        assert fields_filled >= 3, f"Expected at least 3 fields filled, got {fields_filled}"
        assert resume_attached is True, "Resume should have been attached"

        # Assert Stage 4 is visible after full state machine traversal
        assert await page.locator("#stage-exp").is_visible(), "Stage 4 should be visible after post-auth loop"

        await browser.close()

    print("✅ Step 6: Workday post-auth redirection loop & re-entry verified successfully.")


async def main():
    print("\n🚀 ========================================================")
    print("🚀 Running Verification Gate 56: Workday Standard ATS")
    print("🚀 ========================================================\n")

    test_ats_pattern_classification()
    test_workday_vendor_schema_and_master_data()
    await test_workday_playwright_autofill_simulation()
    await test_full_fill_ats_page_routing_workday()
    await test_workday_email_verification_holding_gate()
    await test_workday_post_auth_redirect_and_sign_in_loop()

    print("\n🎉 ========================================================")
    print("🎉 Verification Gate 56 PASSED: Workday Standard Fully Integrated")
    print("🎉 ========================================================\n")


if __name__ == "__main__":
    asyncio.run(main())
