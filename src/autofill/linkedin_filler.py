"""
Assisted LinkedIn Easy Apply Autofill Copilot.
Launches headful stealth Chrome, pre-fills candidate details, uploads tailored PDF,
and halts at the final Review step for 1-click manual candidate submission.
"""

from __future__ import annotations

import asyncio
import os
import time
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
        job_id: str = "",
        company: str = "",
        auto_submit: bool = False,
    ) -> dict[str, Any]:
        """
        Opens the job listing, triggers Easy Apply, fills known fields, attaches PDF,
        and halts at the final submission modal for human review (or auto-submits if requested).
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

                    if auto_submit:
                        await human_click(page, submit_btn)
                        confirmed = await self._monitor_easy_apply_submission(
                            page, job_id=job_id, company=company, timeout=15.0
                        )
                        if confirmed:
                            return {
                                "status": "applied",
                                "step": step_num,
                                "message": "Application submitted and confirmed on LinkedIn.",
                            }

                    # In assisted mode, launch background confirmation listener so candidate click is captured
                    if job_id:
                        asyncio.create_task(self._monitor_easy_apply_submission(page, job_id=job_id, company=company))
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

    async def _monitor_easy_apply_submission(
        self,
        page: Any,
        job_id: str = "",
        company: str = "",
        timeout: float = 300.0,
    ) -> bool:
        """
        Monitors active page for candidate clicking 'Submit application' on LinkedIn,
        detects the genuine post-submission confirmation modal, captures a screenshot,
        and logs a SUBMISSION_CONFIRMED event via SubmissionVerifier.
        """
        start_time = time.time()
        confirmation_selectors = [
            ".artdeco-modal:has-text('Application sent')",
            ".artdeco-modal:has-text('Your application was sent')",
            "div:has-text('Your application was sent to')",
            "h3:has-text('Application sent')",
            "span:has-text('Application submitted')",
            "button[aria-label*='Dismiss']:has-text('Done')",
        ]

        while time.time() - start_time < timeout:
            try:
                if hasattr(page, "is_closed") and page.is_closed():
                    break

                for sel in confirmation_selectors:
                    try:
                        loc = page.locator(sel).first
                        if await loc.count() > 0 and await loc.is_visible():
                            print(f"\n🎉 LINKEDIN EASY APPLY SUBMISSION CONFIRMED: {company} ({job_id})")
                            from src.autofill.autofill_verifier import SubmissionVerifier

                            await SubmissionVerifier.record_submission_confirmed(
                                job_id=job_id,
                                company=company,
                                page=page,
                                marker_type="linkedin_modal",
                                marker_text=sel,
                            )
                            return True
                    except Exception:
                        pass

                await asyncio.sleep(1.0)
            except Exception:
                break
        return False
