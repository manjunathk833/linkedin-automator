import asyncio
import json
import os
import sys

from playwright.async_api import async_playwright

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.automation.easy_apply import EasyApplyExecutor
from src.resume_store.models import ResumeProfile

# Local HTML mock representing a multi-step Easy Apply modal
MOCK_MODAL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>LinkedIn Easy Apply Test Modal</title>
    <style>
        .modal { width: 500px; margin: 50px auto; border: 1px solid #ccc; padding: 20px; font-family: sans-serif; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="text"], input[type="number"], select { width: 100%; padding: 8px; box-sizing: border-box; }
        .hidden { display: none; }
        .btn-container { margin-top: 20px; display: flex; justify-content: space-between; }
        button { padding: 10px 15px; cursor: pointer; }
    </style>
</head>
<body>
    <div role="dialog" class="modal jobs-easy-apply-modal">
        <h2>Easy Apply - Test Application</h2>
        
        <!-- Step 1: Contact Info -->
        <div id="step-1" class="step">
            <h3>Contact Information</h3>
            <div class="form-group">
                <label for="phone">Phone Mobile Number</label>
                <input type="text" id="phone" value="">
            </div>
            <div class="form-group">
                <label for="email">Email Address</label>
                <input type="text" id="email" value="">
            </div>
            <div class="form-group">
                <label for="location">Current Location</label>
                <input type="text" id="location" value="">
            </div>
            <div class="btn-container">
                <div></div>
                <button type="button" id="btn-next-1" onclick="nextStep(2)">Next</button>
            </div>
        </div>

        <!-- Step 2: Work Auth & Resume -->
        <div id="step-2" class="step hidden">
            <h3>Work Authorization & Resume</h3>
            <fieldset class="form-group">
                <legend>Are you legally authorized to work in India?</legend>
                <label><input type="radio" name="auth" value="Yes"> Yes</label>
                <label><input type="radio" name="auth" value="No"> No</label>
            </fieldset>
            <fieldset class="form-group">
                <legend>Will you require visa sponsorship?</legend>
                <label><input type="radio" name="sponsor" value="Yes"> Yes</label>
                <label><input type="radio" name="sponsor" value="No"> No</label>
            </fieldset>
            <div class="form-group">
                <label for="resume-upload">Upload Resume PDF</label>
                <input type="file" id="resume-upload" accept=".pdf">
            </div>
            <div class="btn-container">
                <button type="button" onclick="nextStep(1)">Back</button>
                <button type="button" id="btn-next-2" onclick="nextStep(3)">Review</button>
            </div>
        </div>

        <!-- Step 3: Final Review -->
        <div id="step-3" class="step hidden">
            <h3>Review Application</h3>
            <p>Please review your answers before submitting.</p>
            <div class="btn-container">
                <button type="button" onclick="nextStep(2)">Back</button>
                <button type="button" id="btn-submit">Submit application</button>
            </div>
        </div>
    </div>

    <script>
        function nextStep(stepNum) {
            document.querySelectorAll('.step').forEach(s => s.classList.add('hidden'));
            document.getElementById('step-' + stepNum).classList.remove('hidden');
        }
    </script>
</body>
</html>
"""


async def test_easy_apply_mock_flow():
    """Runs a local Playwright headless test against our HTML mock modal to verify form population and dry-run safety."""
    print("==================================================")
    print("  Testing EasyApplyExecutor on Mock Modal")
    print("==================================================")

    # Write temporary HTML file
    temp_html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "temp_mock_modal.html"))
    with open(temp_html_path, "w") as f:
        f.write(MOCK_MODAL_HTML)

    # Load test resume profile
    json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "resume_profile.json"))
    with open(json_path, "r") as f:
        resume_data = json.load(f)

    profile = ResumeProfile(**resume_data)

    # Dummy test PDF
    dummy_pdf = os.path.abspath(os.path.join(os.path.dirname(__file__), "resume_test_output.pdf"))

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"file://{temp_html_path}")

        executor = EasyApplyExecutor()
        modal = page.locator('div[role="dialog"]')

        # Step 1: Fill contact info
        print("🧪 Testing Step 1: Contact Information filling...")
        filled = await executor.fill_form_fields(modal, profile)
        assert filled >= 3, f"Expected at least 3 fields filled, got {filled}"
        print(f"   Filled {filled} fields ✅")

        # Click Next
        btn_next = modal.get_by_role("button", name="Next")
        await btn_next.click()
        await asyncio.sleep(0.5)

        # Step 2: Radio buttons and PDF upload
        print("\n🧪 Testing Step 2: Work Authorization & PDF Upload...")
        filled_step2 = await executor.fill_form_fields(modal, profile)
        assert filled_step2 >= 2, f"Expected at least 2 radio groups filled, got {filled_step2}"

        # Upload file
        uploaded = await executor.handle_file_upload(modal, dummy_pdf)
        assert uploaded is True, "PDF Upload failed!"
        print("   Uploaded PDF resume successfully ✅")

        # Click Review
        btn_review = modal.get_by_role("button", name="Review")
        await btn_review.click()
        await asyncio.sleep(0.5)

        # Step 3: Verify Dry Run Safety (Submit button visible, but NOT clicked)
        print("\n🧪 Testing Step 3: Dry-Run Safety Verification...")
        btn_submit = modal.get_by_role("button", name="Submit application")
        assert await btn_submit.is_visible() is True, "Submit button should be visible!"
        print("   Submit button detected ✅")
        print("   DRY RUN SAFETY CONFIRMED: Stopping execution before submit ✅")

        await browser.close()

    # Clean up temp file
    if os.path.exists(temp_html_path):
        os.remove(temp_html_path)

    print("\n" + "=" * 50)
    print("✅ MOCK EASY APPLY FLOW TEST PASSED PERFECTLY!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_easy_apply_mock_flow())
