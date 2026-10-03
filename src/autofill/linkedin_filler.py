"""
Assisted LinkedIn Easy Apply Autofill Copilot.
Launches headful stealth Chrome, pre-fills candidate details, uploads tailored PDF,
and halts at the final Review step for 1-click manual candidate submission.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from src.autofill.form_mapper import FormFieldMapper
from src.browser.cdp_stealth import launch_stealth_browser
from src.browser.kinematics import human_click, human_type

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class LinkedInAssistedFiller:
    """
    Assisted copilot executing anti-detection form filling for LinkedIn Easy Apply.
    """

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.mapper = FormFieldMapper()

    async def autofill_easy_apply(
        self,
        job_url: str,
        resume_pdf_path: str | None = None,
        max_steps: int = 8,
    ) -> dict[str, Any]:
        """
        Opens the job listing, triggers Easy Apply, fills known fields, attaches PDF,
        and halts at the final submission modal for human review.
        """
        _pw, _context, page = await launch_stealth_browser(
            headless=self.headless,
        )

        try:
            print(f"🌐 Navigating to job: {job_url}")
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2.0)

            # 1. Locate and click Easy Apply button
            apply_btn = page.locator(".jobs-apply-button, button:has-text('Easy Apply')").first
            if not await apply_btn.is_visible(timeout=5000):
                return {"status": "error", "message": "Easy Apply button not found or already applied."}

            await human_click(page, apply_btn)
            await asyncio.sleep(1.5)

            # 2. Step through Easy Apply modal
            for step_num in range(1, max_steps + 1):
                print(f"📋 Traversing modal step {step_num}...")
                await asyncio.sleep(1.0)

                # Check if we have reached the final "Submit" or "Review" step
                submit_btn = page.locator("button:has-text('Submit application')").first
                if await submit_btn.is_visible():
                    print("\n🔔 ========================================================")
                    print("🔔 MODAL READY: Reached final 'Submit application' step!")
                    print("🔔 Browser is paused for candidate inspection and manual click.")
                    print("🔔 ========================================================\n")
                    return {"status": "ready_for_review", "step": step_num}

                # Auto-fill visible text inputs
                text_inputs = page.locator(
                    ".jobs-easy-apply-modal input[type='text'], .jobs-easy-apply-modal input[type='tel']"
                )
                count = await text_inputs.count()
                for i in range(count):
                    inp = text_inputs.nth(i)
                    if await inp.is_visible():
                        val = await inp.input_value()
                        if not val:
                            label_el = page.locator(f"label[for='{await inp.get_attribute('id')}']")
                            label_text = await label_el.text_content() if await label_el.count() else ""
                            resolved = self.mapper.resolve_field_value(label_text or "")
                            if resolved:
                                await human_type(inp, resolved)

                # Handle PDF file upload if file input is present
                if resume_pdf_path and os.path.exists(resume_pdf_path):
                    file_input = page.locator(".jobs-easy-apply-modal input[type='file']").first
                    if await file_input.count() and await file_input.is_visible():
                        print(f"📎 Attaching tailored PDF resume: {resume_pdf_path}")
                        await file_input.set_input_files(resume_pdf_path)
                        await asyncio.sleep(1.0)

                # Check for "Review" or "Next" button to advance step
                review_btn = page.locator("button:has-text('Review')").first
                next_btn = page.locator("button:has-text('Next')").first

                if await review_btn.is_visible():
                    await human_click(page, review_btn)
                    await asyncio.sleep(1.5)
                elif await next_btn.is_visible():
                    await human_click(page, next_btn)
                    await asyncio.sleep(1.5)
                else:
                    break

            return {"status": "ready_for_review", "message": "Autofill paused at final step."}

        except Exception as e:
            print(f"⚠️ Autofill error: {e}")
            return {"status": "error", "error": str(e)}
