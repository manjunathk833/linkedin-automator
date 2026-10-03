"""Assisted Direct ATS Autofill Copilot (Greenhouse, Lever, Ashby).

Navigates to public ATS posting application forms, populates candidate fields,
uploads tailored resume PDF, and halts before submission for candidate review.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any

from src.autofill.form_mapper import FormFieldMapper
from src.browser.cdp_stealth import launch_stealth_browser
from src.browser.kinematics import human_type

# Global registry holding active browser sessions to prevent Python garbage collection from closing the window
_ACTIVE_SESSIONS: list[tuple[Any, Any, Any]] = []


def resolve_canonical_ats_url(url: str, company: str = "") -> str:
    """Resolves wrapper company career URLs into canonical ATS portal endpoints.

    For example, converts 'https://www.coinbase.com/careers/positions/8095207?gh_jid=8095207'
    into 'https://boards.greenhouse.io/coinbase/jobs/8095207' where form fields are immediately exposed.
    """
    if not url:
        return url

    # Greenhouse wrapper resolution via gh_jid
    gh_match = re.search(r"gh_jid=(\d+)", url)
    if gh_match:
        job_id = gh_match.group(1)
        company_slug = ""
        url_lower = url.lower()

        # Infer company slug from URL domain or parameter
        for known_slug in [
            "coinbase",
            "cloudflare",
            "databricks",
            "instacart",
            "thoughtworks",
            "gitlab",
            "stripe",
            "figma",
            "docker",
            "linear",
        ]:
            if known_slug in url_lower:
                company_slug = known_slug
                break

        if not company_slug and company:
            company_slug = re.sub(r"[^a-zA-Z0-9]", "", company).lower()

        if company_slug and "boards.greenhouse.io" not in url:
            canonical = f"https://boards.greenhouse.io/{company_slug}/jobs/{job_id}"
            print(f"🎯 Resolved wrapper URL to canonical Greenhouse board: {canonical}")
            return canonical

    return url


class ATSAssistedFiller:
    """Assisted copilot executing anti-detection form filling on Greenhouse and Lever application pages."""

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.mapper = FormFieldMapper()

    async def fill_ats_page(
        self,
        page: Any,
        job_url: str,
        resume_pdf_path: str | None = None,
    ) -> dict[str, Any]:
        """Fills out the application form on the given page or frame locator."""
        if page.url != job_url:
            print(f"🌐 Navigating to ATS posting: {job_url}")
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2.0)

        contact = self.mapper.get_contact_info()
        fields_filled = 0
        resume_attached = False

        # 1. Check if the page has an embedded Greenhouse or Lever iframe
        target: Any = page
        iframe = page.locator("iframe#grnh_iframe, iframe[src*='greenhouse.io'], iframe[src*='lever.co']").first
        try:
            if await iframe.count() > 0 and await iframe.is_visible():
                print("📦 Detected embedded ATS iframe. Switching target to iframe frame locator...")
                target = page.frame_locator(
                    "iframe#grnh_iframe, iframe[src*='greenhouse.io'], iframe[src*='lever.co']"
                ).first
        except Exception as e:
            print(f"⚠️ Iframe detection notice: {e}")

        # 2. Check if form fields are visible; if not, look for an 'Apply' trigger button
        first_input = target.locator(
            "input#first_name, input[name='first_name'], input[name='firstName'], input[name='name'], input#name"
        ).first
        try:
            if not await first_input.is_visible(timeout=2500):
                apply_btn = target.locator(
                    "button#apply-button, a.postings-btn, button:has-text('Apply for this job'), "
                    "button:has-text('Apply Now'), a:has-text('Apply for this job'), a:has-text('Apply Now'), "
                    "[data-qa='apply-button'], a[href*='/apply']"
                ).first
                if await apply_btn.count() > 0 and await apply_btn.is_visible():
                    print("🖱️ Clicking 'Apply' trigger button to expose application form...")

                    # Setup context page listener to capture new tabs/windows
                    context = getattr(page, "context", None)
                    opened_pages: list[Any] = []

                    def _on_page(new_p: Any) -> None:
                        opened_pages.append(new_p)

                    if context:
                        try:
                            context.on("page", _on_page)
                        except Exception:
                            pass

                    try:
                        await apply_btn.click()
                        # Poll briefly for new tab event
                        for _ in range(20):
                            if opened_pages:
                                break
                            await asyncio.sleep(0.1)
                    finally:
                        if context:
                            try:
                                context.remove_listener("page", _on_page)
                            except Exception:
                                pass

                    # Determine if a new page/tab was opened
                    if opened_pages:
                        new_page = opened_pages[0]
                        print(f"📑 Detected new application tab ({getattr(new_page, 'url', '')}). Switching focus...")
                        try:
                            await new_page.wait_for_load_state("domcontentloaded", timeout=15000)
                        except Exception:
                            pass
                        try:
                            await new_page.bring_to_front()
                        except Exception:
                            pass
                        page = new_page
                        target = page
                        await asyncio.sleep(1.5)
                    elif context and len(context.pages) > 1 and context.pages[-1] != page:
                        new_page = context.pages[-1]
                        print(f"📑 Detected new background tab ({getattr(new_page, 'url', '')}). Switching focus...")
                        try:
                            await new_page.wait_for_load_state("domcontentloaded", timeout=15000)
                            await new_page.bring_to_front()
                        except Exception:
                            pass
                        page = new_page
                        target = page
                        await asyncio.sleep(1.5)
                    else:
                        await asyncio.sleep(2.0)

                    # Re-check for embedded iframe in newly focused tab
                    try:
                        tab_iframe = page.locator(
                            "iframe#grnh_iframe, iframe[src*='greenhouse.io'], iframe[src*='lever.co']"
                        ).first
                        if await tab_iframe.count() > 0 and await tab_iframe.is_visible():
                            print("📦 Detected embedded ATS iframe in new tab. Switching target...")
                            target = page.frame_locator(
                                "iframe#grnh_iframe, iframe[src*='greenhouse.io'], iframe[src*='lever.co']"
                            ).first
                    except Exception as e:
                        print(f"⚠️ Application tab iframe notice: {e}")

                    # Check if the new page requires clicking a secondary 'Apply' button
                    try:
                        sub_first_input = target.locator(
                            "input#first_name, input[name='first_name'], input[name='firstName'], input[name='name'], input#name"
                        ).first
                        if not await sub_first_input.is_visible(timeout=1500):
                            sub_apply = target.locator(
                                "button#apply-button, a.postings-btn, button:has-text('Apply for this job'), "
                                "button:has-text('Apply Now'), a:has-text('Apply for this job'), a:has-text('Apply Now'), "
                                "[data-qa='apply-button'], a[href*='/apply']"
                            ).first
                            if await sub_apply.count() > 0 and await sub_apply.is_visible():
                                print("🖱️ Clicking secondary 'Apply' button on application page...")
                                await sub_apply.click()
                                await asyncio.sleep(2.0)
                    except Exception as e:
                        print(f"⚠️ Secondary apply button notice: {e}")
        except Exception as e:
            print(f"⚠️ Apply trigger check notice: {e}")

        # 3. Fill First & Last Name
        try:
            first_name_input = target.locator(
                "input#first_name, input[name='first_name'], input[name='firstName']"
            ).first
            if await first_name_input.is_visible(timeout=2500):
                curr = await first_name_input.input_value()
                if not curr:
                    await human_type(first_name_input, contact["first_name"])
                    fields_filled += 1

            last_name_input = target.locator("input#last_name, input[name='last_name'], input[name='lastName']").first
            if await last_name_input.is_visible(timeout=1500):
                curr = await last_name_input.input_value()
                if not curr:
                    await human_type(last_name_input, contact["last_name"])
                    fields_filled += 1
        except Exception:
            pass

        # Full Name fallback (e.g. Lever)
        try:
            full_name_input = target.locator("input[name='name'], input#name").first
            if await full_name_input.is_visible(timeout=1500):
                curr = await full_name_input.input_value()
                if not curr:
                    await human_type(full_name_input, contact["full_name"])
                    fields_filled += 1
        except Exception:
            pass

        # 4. Fill Email
        try:
            email_input = target.locator("input#email, input[name='email'], input[type='email']").first
            if await email_input.is_visible(timeout=1500):
                curr = await email_input.input_value()
                if not curr:
                    await human_type(email_input, contact["email"])
                    fields_filled += 1
        except Exception:
            pass

        # 5. Fill Phone
        try:
            phone_input = target.locator("input#phone, input[name='phone'], input[type='tel']").first
            if await phone_input.is_visible(timeout=1500):
                curr = await phone_input.input_value()
                if not curr:
                    await human_type(phone_input, contact["phone"])
                    fields_filled += 1
        except Exception:
            pass

        # 6. Fill Links (LinkedIn, GitHub, Portfolio)
        try:
            linkedin_input = target.locator(
                "input[name*='linkedin'], input#linkedin, input[placeholder*='linkedin' i]"
            ).first
            if await linkedin_input.is_visible(timeout=1500):
                curr = await linkedin_input.input_value()
                if not curr:
                    await human_type(linkedin_input, contact["linkedin"])
                    fields_filled += 1
        except Exception:
            pass

        try:
            github_input = target.locator("input[name*='github'], input#github, input[placeholder*='github' i]").first
            if await github_input.is_visible(timeout=1000):
                curr = await github_input.input_value()
                if not curr:
                    await human_type(github_input, contact["github"])
                    fields_filled += 1
        except Exception:
            pass

        # 7. Attach Tailored PDF Resume
        if resume_pdf_path and os.path.exists(resume_pdf_path):
            try:
                file_input = target.locator("input[type='file']").first
                if await file_input.count() > 0:
                    print(f"📎 Attaching tailored resume: {resume_pdf_path}")
                    await file_input.set_input_files(resume_pdf_path)
                    resume_attached = True
                    await asyncio.sleep(1.0)
            except Exception as e:
                print(f"⚠️ Resume attachment notice: {e}")

        status = "ready_for_review" if (fields_filled > 0 or resume_attached) else "needs_manual_navigation"

        print("\n🔔 ========================================================")
        print(f"🔔 ATS AUTOFILL COMPLETE: {fields_filled} fields typed, Resume Attached={resume_attached}")
        print("🔔 Status: Pausing session for candidate manual review and submission.")
        print("🔔 ========================================================\n")

        return {
            "status": status,
            "fields_filled": fields_filled,
            "resume_attached": resume_attached,
            "url": getattr(page, "url", job_url),
        }

    async def autofill_ats_application(
        self,
        job_url: str,
        resume_pdf_path: str | None = None,
        company: str = "",
    ) -> dict[str, Any]:
        """Loads the public ATS job page, pre-fills candidate inputs, attaches resume, and yields control."""
        canonical_url = resolve_canonical_ats_url(job_url, company=company)

        _pw, _context, page = await launch_stealth_browser(headless=self.headless)
        # Retain reference in active sessions so browser does not close when function returns
        _ACTIVE_SESSIONS.append((_pw, _context, page))

        try:
            # Ensure window is visible and focused on macOS
            try:
                await page.bring_to_front()
            except Exception:
                pass

            result = await self.fill_ats_page(page, canonical_url, resume_pdf_path)
            return result

        except Exception as e:
            print(f"⚠️ ATS Autofill error: {e}")
            return {"status": "error", "error": str(e), "url": canonical_url}
