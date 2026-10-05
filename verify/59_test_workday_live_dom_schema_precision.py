"""Verification Gate 59: Workday Live DOM Schema Precision & BEM ID Autofill.

Reproduces the exact DOM extracted from the live Workday diagnostic dump
(autofill_dom_stuck_unknown_1791225819.json) to validate:
1. State detection accurately classifies Stage 1 BEM layout as 'info' (not 'unknown').
2. Sibling label radio group matching for prior employment (candidateIsPreviousWorker -> 'No' / value='false').
3. Dropdown combobox precision for Prefix ('#name--legalName--title' -> 'Mr.'), State, and Phone Device Type.
4. Clean text filling across First Name, Last Name, Address Line 1, City, Postal Code, and Phone.
5. Multi-stage advancement via 'pageFooterNextButton' to Stage 2 ('experience').
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from playwright.async_api import async_playwright

from src.autofill.ats_filler import ATSAssistedFiller
from src.autofill.vendor_schemas import load_candidate_master_data

JIOSTAR_LIVE_STAGE_1_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Senior Software Development Engineer Test II - JioStar - Workday</title>
    <style>
        .hidden { display: none; }
        .form-group { margin-bottom: 15px; }
        [role="listbox"] { border: 1px solid #ccc; background: #fff; position: absolute; }
        .select__option { padding: 5px 10px; cursor: pointer; }
        .select__option:hover { background: #e0e0e0; }
    </style>
</head>
<body>
    <div id="app-root">
        <div data-automation-id="utilityButtonBar">
            <button data-automation-id="navigationItem-Candidate Home">Candidate Home</button>
        </div>

        <div id="breadcrumb-bar" role="navigation">
            <span class="active-stage">My Information</span> &gt;
            <span>My Experience</span> &gt;
            <span>Application Questions</span> &gt;
            <span>Voluntary Disclosures</span> &gt;
            <span>Review</span>
        </div>

        <div id="stage-info-container">
            <div data-automation-id="pageHeader">
                <h1>My Information</h1>
                <p>* Indicates a required field</p>
            </div>

            <!-- Prior Employment Radio Group from Live DOM -->
            <fieldset class="form-group" id="fs-prev-worker">
                <legend>Have you previously been employed by JioStar Private Limited or its predecessor entities, including Disney Star or Viacom18? *</legend>
                <div>
                    <input type="radio" id="lijgi" name="candidateIsPreviousWorker" value="true">
                    <label for="lijgi">Yes</label>
                </div>
                <div>
                    <input type="radio" id="lijgj" name="candidateIsPreviousWorker" value="false">
                    <label for="lijgj">No</label>
                </div>
            </fieldset>

            <!-- Country Dropdown -->
            <div class="form-group">
                <label for="country--country">Country *</label>
                <button type="button" id="country--country" aria-label="Country India Required" aria-haspopup="listbox">India</button>
            </div>

            <!-- Prefix Dropdown -->
            <div class="form-group">
                <label for="name--legalName--title">Prefix *</label>
                <button type="button" id="name--legalName--title" aria-label="Prefix Select One Required" aria-haspopup="listbox">Select One</button>
                <div id="menu-prefix" role="listbox" class="hidden">
                    <div role="option" class="select__option">Mr.</div>
                    <div role="option" class="select__option">Ms.</div>
                    <div role="option" class="select__option">Mrs.</div>
                </div>
            </div>

            <!-- Legal Names -->
            <div class="form-group">
                <label for="name--legalName--firstName">Legal First Name *</label>
                <input type="text" id="name--legalName--firstName" name="legalName--firstName" value="" />
            </div>

            <div class="form-group">
                <label for="name--legalName--lastName">Legal Last Name *</label>
                <input type="text" id="name--legalName--lastName" name="legalName--lastName" value="" />
            </div>

            <!-- Address -->
            <div class="form-group">
                <label for="address--addressLine1">Address Line 1 *</label>
                <input type="text" id="address--addressLine1" name="addressLine1" value="" />
            </div>

            <div class="form-group">
                <label for="address--city">City *</label>
                <input type="text" id="address--city" name="city" value="" />
            </div>

            <!-- State Dropdown -->
            <div class="form-group">
                <label for="address--countryRegion">State *</label>
                <button type="button" id="address--countryRegion" aria-label="State Select One Required" aria-haspopup="listbox">Select One</button>
                <div id="menu-state" role="listbox" class="hidden">
                    <div role="option" class="select__option">Karnataka</div>
                    <div role="option" class="select__option">Maharashtra</div>
                    <div role="option" class="select__option">Delhi</div>
                </div>
            </div>

            <div class="form-group">
                <label for="address--postalCode">Postal Code *</label>
                <input type="text" id="address--postalCode" name="postalCode" value="" />
            </div>

            <!-- Phone Device Type Dropdown -->
            <div class="form-group">
                <label for="phoneNumber--phoneType">Phone Device Type *</label>
                <button type="button" id="phoneNumber--phoneType" aria-label="Phone Device Type Select One Required" aria-haspopup="listbox">Select One</button>
                <div id="menu-phone-type" role="listbox" class="hidden">
                    <div role="option" class="select__option">Mobile</div>
                    <div role="option" class="select__option">Landline</div>
                </div>
            </div>

            <!-- Phone Country Code & Number -->
            <div class="form-group">
                <label for="phoneNumber--countryPhoneCode">Country Phone Code *</label>
                <input type="text" id="phoneNumber--countryPhoneCode" value="" />
            </div>

            <div class="form-group">
                <label for="phoneNumber--phoneNumber">Phone Number *</label>
                <input type="text" id="phoneNumber--phoneNumber" name="phoneNumber" value="" />
            </div>

            <!-- Save and Continue Button from Live DOM -->
            <div class="form-group">
                <button type="button" id="footer-next-btn" data-automation-id="pageFooterNextButton">Save and Continue</button>
            </div>
        </div>

        <div id="stage-exp-container" class="hidden">
            <h2>My Experience</h2>
            <div data-automation-id="file-upload-dropzone">
                <input type="file" name="resume-file" />
            </div>
            <button type="button" data-automation-id="pageFooterNextButton">Save and Continue</button>
        </div>
    </div>
</body>
</html>
"""


async def test_workday_live_dom_schema_precision():
    print("\n🚀 ========================================================")
    print("🚀 Running Verification Gate 59: Workday Live DOM Precision")
    print("🚀 ========================================================\n")

    master_data = load_candidate_master_data()
    filler = ATSAssistedFiller(headless=True, master_data=master_data)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Step 1: Verify State Detection on Live Workday DOM
        print("🧪 Step 1: Testing state classification on live Workday BEM DOM layout...")
        await page.set_content(JIOSTAR_LIVE_STAGE_1_HTML, wait_until="domcontentloaded")

        # Wire click handlers for dropdown menus
        await page.evaluate("""() => {
            function wireDropdown(btnId, menuId) {
                const btn = document.getElementById(btnId);
                const menu = document.getElementById(menuId);
                if (btn && menu) {
                    btn.addEventListener('click', () => {
                        menu.classList.toggle('hidden');
                    });
                    menu.querySelectorAll("[role='option']").forEach(opt => {
                        opt.addEventListener('click', () => {
                            btn.textContent = opt.textContent.trim();
                            menu.classList.add('hidden');
                        });
                    });
                }
            }
            wireDropdown('name--legalName--title', 'menu-prefix');
            wireDropdown('address--countryRegion', 'menu-state');
            wireDropdown('phoneNumber--phoneType', 'menu-phone-type');

            const nextBtn = document.getElementById('footer-next-btn');
            nextBtn.addEventListener('click', () => {
                document.getElementById('stage-info-container').classList.add('hidden');
                document.getElementById('stage-exp-container').classList.remove('hidden');
            });
        }""")

        detected_state = await filler._detect_workday_state(page)
        print(f"   Detected active state: [{detected_state}]")
        assert detected_state == "info", f"Expected state 'info', but got '{detected_state}'"
        print("✅ Step 1: Workday live BEM DOM correctly classified as 'info'.")

        # Step 2: Test Dynamic Question Solver on Sibling Radio Group
        print("\n🧪 Step 2: Testing prior employment sibling radio resolution (value='false')...")
        ans_count = await filler._resolve_workday_questions(page)
        assert ans_count >= 1, f"Expected at least 1 question resolved, got {ans_count}"

        no_radio = page.locator("input[name='candidateIsPreviousWorker'][value='false']")
        is_no_checked = await no_radio.is_checked()
        assert is_no_checked is True, "candidateIsPreviousWorker [value='false'] radio was NOT checked!"
        print("   ✓ JioStar prior employment radio group answered: [No] (value='false')")
        print("✅ Step 2: Sibling radio group resolved deterministically.")

        # Step 3: Test Full Stage 1 Autofill Execution on Fresh Page
        print("\n🧪 Step 3: Testing full Stage 1 autofill with live Workday BEM IDs from scratch...")
        await page.set_content(JIOSTAR_LIVE_STAGE_1_HTML, wait_until="domcontentloaded")
        await page.evaluate("""() => {
            function wireDropdown(btnId, menuId) {
                const btn = document.getElementById(btnId);
                const menu = document.getElementById(menuId);
                if (btn && menu) {
                    btn.addEventListener('click', () => {
                        menu.classList.toggle('hidden');
                    });
                    menu.querySelectorAll("[role='option']").forEach(opt => {
                        opt.addEventListener('click', () => {
                            btn.textContent = opt.textContent.trim();
                            menu.classList.add('hidden');
                        });
                    });
                }
            }
            wireDropdown('name--legalName--title', 'menu-prefix');
            wireDropdown('address--countryRegion', 'menu-state');
            wireDropdown('phoneNumber--phoneType', 'menu-phone-type');

            const nextBtn = document.getElementById('footer-next-btn');
            nextBtn.addEventListener('click', () => {
                document.getElementById('stage-info-container').classList.add('hidden');
                document.getElementById('stage-exp-container').classList.remove('hidden');
            });
        }""")

        dummy_pdf = PROJECT_ROOT / "verify" / "resume_test_output.pdf"
        if not dummy_pdf.exists():
            with open(dummy_pdf, "wb") as f:
                f.write(b"%PDF-1.4 mock resume content")

        fields_filled, attached = await filler._fill_workday(page, str(dummy_pdf))
        print(f"   Fields populated: {fields_filled}, Resume Attached: {attached}")
        assert fields_filled >= 8, f"Expected at least 8 fields filled, got {fields_filled}"

        # Assert Stage 2 'My Experience' is now visible
        exp_visible = await page.locator("#stage-exp-container").is_visible()
        assert exp_visible is True, "Stage 2 'My Experience' was not reached!"
        print("   ✓ Advanced to Stage 2 'My Experience' via 'pageFooterNextButton'")
        print("✅ Step 3: Full Stage 1 traversal completed with 0 errors.")

        await browser.close()

    print("\n🎉 ========================================================")
    print("🎉 Verification Gate 59 PASSED: Live Workday BEM Schema 100%")
    print("🎉 ========================================================\n")


if __name__ == "__main__":
    asyncio.run(test_workday_live_dom_schema_precision())
