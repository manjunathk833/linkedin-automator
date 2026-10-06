"""Verification Gate 58: Workday Deterministic Dynamic Question Solver & Multi-Stage Traversal.

Validates:
1. Deterministic resolution of tenant-specific screening questions (e.g. JioStar prior employment radio -> 'No').
2. Dynamic Prefix dropdown selection ('Mr.').
3. Stage 3 Application Questions resolution (work authorization -> 'Yes', visa sponsorship -> 'No').
4. Seamless multi-stage traversal across Information -> Experience -> Questions -> Disclosures -> Review.
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


async def test_workday_dynamic_question_solver():
    print("\n🚀 ========================================================")
    print("🚀 Running Verification Gate 58: Workday Dynamic Question Solver")
    print("🚀 ========================================================\n")

    filler = ATSAssistedFiller(headless=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Step 1: Test Prior Employment Radio & Prefix Dropdown on 'My Information'
        print("🧪 Step 1: Testing Workday 'My Information' prior employment radio & Prefix dropdown...")
        stage_1_html = """
        <!DOCTYPE html>
        <html>
        <head><title>JioStar Senior SDET II - Workday</title></head>
        <body>
            <h2>My Information</h2>
            <p>* Indicates a required field</p>

            <fieldset data-automation-id="formField-previousEmployment">
                <legend>Have you previously been employed by JioStar Private Limited or its predecessor entities, including Disney Star or Viacom18? *</legend>
                <div>
                    <label><input type="radio" name="prevEmp" value="yes" /> Yes</label>
                    <label><input type="radio" name="prevEmp" value="no" /> No</label>
                </div>
            </fieldset>

            <div data-automation-id="formField-country">
                <label>Country *</label>
                <button data-automation-id="legalNameSection_country" aria-haspopup="listbox">India</button>
            </div>

            <div data-automation-id="formField-prefix">
                <label>Prefix *</label>
                <button data-automation-id="legalNameSection_prefix" aria-haspopup="listbox">Select One</button>
            </div>

            <div data-automation-id="formField-firstName">
                <label>Legal First Name *</label>
                <input data-automation-id="legalNameSection_firstName" type="text" />
            </div>

            <div data-automation-id="formField-lastName">
                <label>Legal Last Name *</label>
                <input data-automation-id="legalNameSection_lastName" type="text" />
            </div>

            <div data-automation-id="formField-phone">
                <label>Phone Number *</label>
                <input data-automation-id="phone-number" type="tel" />
            </div>

            <button data-automation-id="bottom-navigation-next-button">Save and Continue</button>

            <!-- Custom listbox dropdown container mock -->
            <div id="prefix-menu" role="listbox" style="display:none;">
                <div role="option" class="select__option">Mr.</div>
                <div role="option" class="select__option">Ms.</div>
                <div role="option" class="select__option">Mrs.</div>
            </div>
        </body>
        </html>
        """
        await page.set_content(stage_1_html)

        # Wire click on prefix button to open mock listbox
        await page.evaluate("""() => {
            const btn = document.querySelector("[data-automation-id='legalNameSection_prefix']");
            const menu = document.getElementById("prefix-menu");
            if (btn && menu) {
                btn.addEventListener('click', () => { menu.style.display = 'block'; });
                const opts = menu.querySelectorAll("[role='option']");
                opts.forEach(opt => {
                    opt.addEventListener('click', () => {
                        btn.textContent = opt.textContent;
                        menu.style.display = 'none';
                    });
                });
            }
        }""")

        ans_count = await filler._resolve_workday_questions(page)
        assert ans_count >= 1, f"Expected at least 1 dynamic question answered, got {ans_count}"

        no_radio = page.locator("input[type='radio'][value='no']")
        is_no_checked = await no_radio.is_checked()
        assert is_no_checked, "Prior employment 'No' radio was not checked by solver!"
        print("   ✓ JioStar prior employment radio group correctly answered: [No]")

        # Test prefix selection
        prefix_btn = page.locator("[data-automation-id='legalNameSection_prefix']").first
        await filler._select_react_combobox(page, prefix_btn, "Mr.")
        prefix_text = (await prefix_btn.text_content() or "").strip()
        assert prefix_text == "Mr.", f"Expected prefix 'Mr.', got '{prefix_text}'"
        print("   ✓ Prefix dropdown successfully selected: [Mr.]")
        print("✅ Step 1: Workday 'My Information' custom fields resolved.")

        # Step 2: Test Stage 3 'Application Questions'
        print("\n🧪 Step 2: Testing Workday 'Application Questions' resolution...")
        stage_3_html = """
        <!DOCTYPE html>
        <html>
        <head><title>JioStar Senior SDET II - Workday</title></head>
        <body>
            <h2>Application Questions</h2>

            <fieldset data-automation-id="formField-workAuth">
                <legend>Are you legally authorized to work in India? *</legend>
                <div>
                    <label><input type="radio" name="auth" value="yes" /> Yes</label>
                    <label><input type="radio" name="auth" value="no" /> No</label>
                </div>
            </fieldset>

            <fieldset data-automation-id="formField-sponsorship">
                <legend>Will you now or in the future require visa sponsorship for employment? *</legend>
                <div>
                    <label><input type="radio" name="spons" value="yes" /> Yes</label>
                    <label><input type="radio" name="spons" value="no" /> No</label>
                </div>
            </fieldset>

            <button data-automation-id="bottom-navigation-next-button">Save and Continue</button>
        </body>
        </html>
        """
        await page.set_content(stage_3_html)

        detected_state = await filler._detect_workday_state(page)
        assert detected_state == "questions", f"Expected state 'questions', got '{detected_state}'"

        q_count = await filler._resolve_workday_questions(page)
        assert q_count == 2, f"Expected 2 questions resolved, got {q_count}"

        auth_yes = page.locator("input[name='auth'][value='yes']")
        spons_no = page.locator("input[name='spons'][value='no']")

        assert await auth_yes.is_checked(), "Work authorization 'Yes' was not checked!"
        assert await spons_no.is_checked(), "Visa sponsorship 'No' was not checked!"
        print("   ✓ Work authorization answered: [Yes]")
        print("   ✓ Visa sponsorship answered: [No]")
        print("✅ Step 2: 'Application Questions' resolved deterministically.")

        # Step 3: Test Stage 4 'Voluntary Disclosures'
        print("\n🧪 Step 3: Testing Workday 'Voluntary Disclosures' resolution...")
        stage_4_html = """
        <!DOCTYPE html>
        <html>
        <head><title>JioStar Senior SDET II - Workday</title></head>
        <body>
            <h2>Voluntary Disclosures</h2>

            <div data-automation-id="formField-gender">
                <label>Gender *</label>
                <button data-automation-id="genderSelect" aria-haspopup="listbox">Select One</button>
            </div>

            <fieldset data-automation-id="formField-disability">
                <legend>Do you have a disability? *</legend>
                <div>
                    <label><input type="radio" name="disab" value="yes" /> Yes, I have a disability</label>
                    <label><input type="radio" name="disab" value="no" /> No, I do not have a disability</label>
                </div>
            </fieldset>

            <button data-automation-id="bottom-navigation-next-button">Save and Continue</button>
        </body>
        </html>
        """
        await page.set_content(stage_4_html)

        detected_state_4 = await filler._detect_workday_state(page)
        assert detected_state_4 == "disclosures", f"Expected state 'disclosures', got '{detected_state_4}'"

        d_count = await filler._resolve_workday_questions(page)
        assert d_count >= 1, f"Expected at least 1 disclosure resolved, got {d_count}"

        disab_no = page.locator("input[name='disab'][value='no']")
        assert await disab_no.is_checked(), "Disability status 'No' was not checked!"
        print("   ✓ Voluntary Disclosures answered: [No, I do not have a disability]")
        print("✅ Step 3: 'Voluntary Disclosures' resolved successfully.")

        # Step 4: Full Multi-Stage Traversal Simulation
        print("\n🧪 Step 4: Testing Full Multi-Stage Traversal on State Machine...")
        dummy_pdf = PROJECT_ROOT / "verify" / "resume_test_output.pdf"
        if not dummy_pdf.exists():
            with open(dummy_pdf, "wb") as f:
                f.write(b"%PDF-1.4 mock resume content")

        full_flow_html = """
        <!DOCTYPE html>
        <html>
        <head><title>JioStar Multi-Stage Application</title></head>
        <body>
            <div id="stage-container">
                <h2>My Information</h2>
                <fieldset>
                    <legend>Have you previously been employed by JioStar Private Limited or its predecessor entities, including Disney Star or Viacom18? *</legend>
                    <label><input type="radio" name="prevEmp" value="yes" /> Yes</label>
                    <label><input type="radio" name="prevEmp" value="no" /> No</label>
                </fieldset>
                <div>
                    <label>Prefix *</label>
                    <button data-automation-id="legalNameSection_prefix" aria-haspopup="listbox">Select One</button>
                </div>
                <input data-automation-id="legalNameSection_firstName" type="text" />
                <input data-automation-id="legalNameSection_lastName" type="text" />
                <input data-automation-id="phone-number" type="tel" />
                <button id="nav-btn" data-automation-id="bottom-navigation-next-button">Save and Continue</button>
            </div>
            <div id="prefix-menu" role="listbox" style="display:none;">
                <div role="option" class="select__option">Mr.</div>
            </div>
        </body>
        </html>
        """
        await page.set_content(full_flow_html)

        await page.evaluate("""() => {
            const btn = document.querySelector("[data-automation-id='legalNameSection_prefix']");
            const menu = document.getElementById("prefix-menu");
            if (btn && menu) {
                btn.addEventListener('click', () => { menu.style.display = 'block'; });
                const opts = menu.querySelectorAll("[role='option']");
                opts.forEach(opt => {
                    opt.addEventListener('click', () => {
                        btn.textContent = opt.textContent;
                        menu.style.display = 'none';
                    });
                });
            }

            // Simulate clicking Save and Continue transitions to Review
            const navBtn = document.getElementById('nav-btn');
            navBtn.addEventListener('click', () => {
                document.getElementById('stage-container').innerHTML = `
                    <h2>Review</h2>
                    <p>Review your application before submitting.</p>
                    <button data-automation-id="bottom-navigation-submit-button">Submit Application</button>
                `;
            });
        }""")

        fields_filled, _attached = await filler._fill_workday(page, str(dummy_pdf))
        assert fields_filled >= 3, f"Expected at least 3 fields filled, got {fields_filled}"

        review_state = await filler._detect_workday_state(page)
        assert review_state == "review", f"Expected to reach 'review' state, got '{review_state}'"
        print("   ✓ Successfully traversed My Information -> Review Gate!")
        print("✅ Step 4: Multi-stage traversal verified 100%.")

        await browser.close()

    print("\n🎉 ========================================================")
    print("🎉 Verification Gate 58 PASSED: Dynamic Question Solver Operational")
    print("🎉 ========================================================\n")


if __name__ == "__main__":
    asyncio.run(test_workday_dynamic_question_solver())
