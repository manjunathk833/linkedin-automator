from __future__ import annotations

import asyncio
import os
import random
import re
from typing import Any

from playwright.async_api import Locator, async_playwright

from src.resume_store.models import ResumeProfile


class EasyApplyExecutor:
    def __init__(self, cdp_url: str = "http://localhost:9222"):
        self.cdp_url = cdp_url

    async def _human_delay(self, min_sec: float = 1.0, max_sec: float = 2.5):
        """Simulate human reading/thinking pause."""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    async def _human_type(self, locator: Locator, text: str):
        """Type text into a field with human-like keystroke delays."""
        await locator.scroll_into_view_if_needed()
        await locator.click()
        await locator.clear()
        for char in text:
            await locator.type(char, delay=random.randint(40, 120))
        await self._human_delay(0.3, 0.8)

    async def fill_form_fields(self, modal: Locator, profile: ResumeProfile) -> int:
        """Finds and populates visible input controls inside the modal."""
        fields_filled = 0
        ea = profile.easy_apply_answers

        # 1. Text Inputs and Textareas
        inputs = await modal.locator('input[type="text"], input[type="number"], textarea').all()
        for field in inputs:
            if not await field.is_visible() or await field.is_disabled():
                continue

            # Check current value
            val = await field.input_value()
            label_text = await self._get_label_text(field)
            label_lower = label_text.lower()

            # Skip if already filled
            if val and len(val) > 0:
                continue

            # Fill rules based on label
            if "phone" in label_lower or "mobile" in label_lower:
                if profile.personal_details.phone:
                    await self._human_type(field, profile.personal_details.phone)
                    fields_filled += 1
            elif "email" in label_lower:
                if profile.personal_details.email:
                    await self._human_type(field, profile.personal_details.email)
                    fields_filled += 1
            elif "city" in label_lower or "location" in label_lower:
                if profile.personal_details.location:
                    await self._human_type(field, profile.personal_details.location)
                    fields_filled += 1
            elif "notice" in label_lower:
                await self._human_type(field, ea.notice_period or "2 weeks")
                fields_filled += 1
            elif "experience" in label_lower or "years" in label_lower:
                # Skill query heuristic
                yoe = profile.get_total_experience_years()
                # Check for specific skill match in label
                for skill_name in profile.skills_matrix:
                    if skill_name.lower() in label_lower:
                        yoe = profile.get_years_of_experience(skill_name)
                        break
                await self._human_type(field, str(int(yoe)))
                fields_filled += 1

        # 2. Radio Buttons (Work Auth & Sponsorship)
        radio_groups = await modal.locator("fieldset").all()
        for group in radio_groups:
            if not await group.is_visible():
                continue
            legend = await group.locator("legend").text_content() or ""
            legend_lower = legend.lower()

            if "authorized" in legend_lower or "work in" in legend_lower or "right to work" in legend_lower:
                target_value = "Yes" if ea.authorization_to_work.get("India", True) else "No"
                await self._select_radio(group, target_value)
                fields_filled += 1
            elif "sponsor" in legend_lower or "visa" in legend_lower:
                target_value = "Yes" if ea.sponsorship_needed else "No"
                await self._select_radio(group, target_value)
                fields_filled += 1

        return fields_filled

    async def _select_radio(self, group: Locator, target_label: str):
        """Click radio option matching Yes/No."""
        radios = await group.locator("label").all()
        for r in radios:
            text = await r.text_content() or ""
            if target_label.lower() in text.lower():
                await r.click()
                break

    async def _get_label_text(self, element: Locator) -> str:
        """Extract label text associated with an input element."""
        try:
            elem_id = await element.get_attribute("id")
            if elem_id:
                # Try finding label[for=id]
                label = element.page.locator(f'label[for="{elem_id}"]')
                if await label.count() > 0:
                    return await label.text_content() or ""
            # Fallback to parent text or aria-label
            aria_label = await element.get_attribute("aria-label")
            if aria_label:
                return aria_label
        except Exception:
            pass
        return ""

    async def handle_file_upload(self, modal: Locator, pdf_path: str) -> bool:
        """Uploads the generated PDF resume file."""
        if not pdf_path or not os.path.exists(pdf_path):
            print(f"⚠️  PDF path invalid or missing: {pdf_path}")
            return False

        file_input = modal.locator('input[type="file"]').first
        if await file_input.count() > 0:
            print(f"📎 Attaching PDF resume: {pdf_path}")
            await file_input.set_input_files(pdf_path)
            await self._human_delay(1.0, 2.0)
            return True
        return False

    async def execute_application(self, job_payload: dict[str, Any], dry_run: bool = True) -> dict[str, Any]:
        """
        Connects over CDP/persistent context, executes the Easy Apply steps for the given job payload.
        Ensures Playwright context cleanup in a finally block and fallback Easy Apply trigger locators.
        """
        job_id = job_payload.get("job_id", "unknown")
        pdf_path = job_payload.get("generated_pdf_path", "")
        profile = ResumeProfile(**job_payload["tailored_resume"])

        async with async_playwright() as p:
            print(f"🔗 Connecting for job {job_id}...")
            from src.browser.cdp_connector import connect_cdp, launch_persistent_browser

            context = None
            try:
                try:
                    context, page = await launch_persistent_browser(p)
                except Exception as e1:
                    print(f"⚠️ Persistent browser failed: {e1}, trying CDP fallback...")
                    try:
                        _browser, page = await connect_cdp(p, self.cdp_url)
                    except Exception as e2:
                        print(f"⚠️ CDP fallback also failed: {e2}")
                        return {"status": "FAILED", "reason": str(e2)}

                # If missing modal, attempt direct job navigation
                modal = page.locator('div[role="dialog"], .jobs-easy-apply-modal')
                if (
                    await modal.count() == 0
                    and job_id
                    and not job_id.startswith("test_")
                    and not job_id.startswith("mock_")
                ):
                    job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"
                    print(f"🌐 Navigating to job page: {job_url}")
                    try:
                        await page.goto(job_url, wait_until="domcontentloaded")
                        await self._human_delay(2.0, 3.5)

                        # Enhanced Easy Apply Trigger Locators with Selector Fallbacks
                        easy_apply_btn = (
                            page.locator(
                                "button.jobs-apply-button, .jobs-apply-button--top-card button, button[data-job-id]"
                            )
                            .or_(page.get_by_role("button", name=re.compile(r"Easy Apply", re.IGNORECASE)))
                            .first
                        )
                        if await easy_apply_btn.count() > 0:
                            print("🖱️  Clicking 'Easy Apply' button...")
                            await easy_apply_btn.click()
                            await self._human_delay(1.5, 3.0)
                    except Exception as e:
                        print(f"⚠️ Navigation / trigger warning: {e}")

                # 1. Locate modal
                modal = page.locator('div[role="dialog"], .jobs-easy-apply-modal')
                if await modal.count() == 0:
                    print("❌ Easy Apply modal not found on page!")
                    return {"status": "FAILED", "reason": "Modal not found"}

                print("✅ Found Easy Apply modal container.")
                await self._human_delay(1.0, 2.0)

                # 2. Upload resume if file input is present on first step
                await self.handle_file_upload(modal, pdf_path)

                # 3. Multi-step form loop
                max_steps = 10
                for step in range(max_steps):
                    print(f"🔄 Traversing Step {step + 1}...")

                    # Fill fields on current step
                    filled_count = await self.fill_form_fields(modal, profile)
                    print(f"   Filled {filled_count} form control(s).")

                    # Check for file upload on subsequent steps
                    await self.handle_file_upload(modal, pdf_path)

                    # Check action buttons
                    btn_next = modal.get_by_role("button", name=re.compile(r"^Next", re.IGNORECASE))
                    btn_review = modal.get_by_role("button", name=re.compile(r"^Review", re.IGNORECASE))
                    btn_submit = modal.get_by_role("button", name=re.compile(r"^Submit", re.IGNORECASE))

                    if await btn_submit.is_visible():
                        print("🎯 Found 'Submit' button!")
                        if dry_run:
                            print("🛡️  DRY RUN MODE ENABLED: Halting before final submission.")
                            return {
                                "status": "DRY_RUN_SUCCESS",
                                "job_id": job_id,
                                "message": "Form filled completely. Stopped before Submit.",
                            }
                        else:
                            print("🚀 Submitting application...")
                            await btn_submit.click()
                            await self._human_delay(2.0, 4.0)
                            return {
                                "status": "SUBMITTED",
                                "job_id": job_id,
                                "message": "Application submitted successfully!",
                            }

                    elif await btn_review.is_visible():
                        print("➡️  Found 'Review' button. Clicking...")
                        await btn_review.click()
                        await self._human_delay(1.5, 3.0)

                    elif await btn_next.is_visible():
                        print("➡️  Found 'Next' button. Clicking...")
                        await btn_next.click()
                        await self._human_delay(1.5, 3.0)
                    else:
                        print("⚠️  No Next/Review/Submit button visible. Execution finished or paused.")
                        break

                return {
                    "status": "PAUSED_NEED_INPUT",
                    "job_id": job_id,
                    "message": "Encountered custom questions requiring manual input.",
                }
            finally:
                if context is not None:
                    try:
                        await context.close()
                        print(f"🔒 Closed Playwright context for job {job_id} safely.")
                    except Exception as e_close:
                        print(f"⚠️ Context close warning: {e_close}")
