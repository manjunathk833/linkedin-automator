"""Assisted Direct ATS Autofill Copilot (Greenhouse, Lever, Ashby, Workday, LinkedIn Easy Apply).

Navigates to public ATS posting application forms, populates candidate fields using
standardized vendor schemas and authentic candidate master data, uploads tailored
resume PDF, and halts before submission for candidate review.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any

from src.autofill.form_mapper import FormFieldMapper
from src.autofill.vendor_schemas import CandidateMasterData, load_candidate_master_data
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
    """Assisted copilot executing anti-detection form filling on Greenhouse, Lever, Ashby, and Workday."""

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.mapper = FormFieldMapper()
        try:
            self.master_data: CandidateMasterData = load_candidate_master_data()
        except Exception:
            # Fallback to defaults if candidate_master_data.json is not yet created
            contact = self.mapper.get_contact_info()
            from src.autofill.vendor_schemas import (
                MasterCurrentEmployment,
                MasterPersonalDetails,
                MasterProfiles,
            )

            self.master_data = CandidateMasterData(
                personal=MasterPersonalDetails(
                    full_name=contact["full_name"],
                    first_name=contact["first_name"],
                    last_name=contact["last_name"],
                    email=contact["email"],
                    phone=contact["phone"],
                ),
                profiles=MasterProfiles(
                    linkedin=contact["linkedin"],
                    github=contact["github"],
                    portfolio=contact["portfolio"],
                ),
                current_employment=MasterCurrentEmployment(
                    company="Value Labs",
                    title="Senior Engineer - QE",
                    start_date="2023-06-01",
                ),
            )

    async def fill_ats_page(
        self,
        page: Any,
        job_url: str,
        resume_pdf_path: str | None = None,
    ) -> dict[str, Any]:
        """Fills out the application form on the given page or frame locator."""
        if getattr(page, "url", None) != job_url:
            print(f"🌐 Navigating to ATS posting: {job_url}")
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2.0)

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
                    "[data-qa='apply-button'], a[href*='/apply'], a:has-text('Apply')"
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

        # 3. Detect vendor and execute standardized vendor autofill
        active_url = getattr(page, "url", job_url).lower()
        fields_filled = 0
        resume_attached = False

        if "greenhouse.io" in active_url:
            print("🏛️ Identified Greenhouse ATS standard form.")
            fields_filled, resume_attached = await self._fill_greenhouse(target, resume_pdf_path)
        elif "lever.co" in active_url:
            print("🏢 Identified Lever ATS standard form.")
            fields_filled, resume_attached = await self._fill_lever(target, resume_pdf_path)
        elif "ashbyhq.com" in active_url:
            print("🚀 Identified Ashby ATS standard form.")
            fields_filled, resume_attached = await self._fill_ashby(target, resume_pdf_path)
        elif "workday" in active_url or "myworkdayjobs.com" in active_url:
            print("🏢 Identified Workday standard portal.")
            fields_filled, resume_attached = await self._fill_workday(target, resume_pdf_path)
        elif "linkedin.com" in active_url:
            print("🔗 Identified LinkedIn Easy Apply modal.")
            fields_filled, resume_attached = await self._fill_linkedin_easy_apply(page, resume_pdf_path)
        else:
            print("🌐 Executing universal resilient ATS autofill heuristics...")
            fields_filled, resume_attached = await self._fill_generic(target, resume_pdf_path)

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

    async def _fill_greenhouse(self, target: Any, resume_pdf_path: str | None) -> tuple[int, bool]:
        """Exhaustively fills a Greenhouse application form."""
        filled = 0
        attached = False
        p = self.master_data.personal

        # First & Last Name
        try:
            fn = target.locator("input#first_name, input[name='first_name']").first
            if await fn.is_visible(timeout=1500) and not (await fn.input_value()):
                await human_type(fn, p.first_name)
                filled += 1
        except Exception:
            pass

        try:
            ln = target.locator("input#last_name, input[name='last_name']").first
            if await ln.is_visible(timeout=1500) and not (await ln.input_value()):
                await human_type(ln, p.last_name)
                filled += 1
        except Exception:
            pass

        # Email & Phone
        try:
            em = target.locator("input#email, input[name='email']").first
            if await em.is_visible(timeout=1500) and not (await em.input_value()):
                await human_type(em, p.email)
                filled += 1
        except Exception:
            pass

        try:
            ph = target.locator("input#phone, input[name='phone']").first
            if await ph.is_visible(timeout=1500) and not (await ph.input_value()):
                await human_type(ph, p.phone)
                filled += 1
        except Exception:
            pass

        # Location Combobox (#candidate-location)
        try:
            loc = target.locator("input#candidate-location, input[name*='location']").first
            if await loc.is_visible(timeout=1500) and not (await loc.input_value()):
                await human_type(loc, p.city)
                await asyncio.sleep(1.0)
                # Try selecting first suggestion if combobox list appears
                first_opt = target.locator("ul[role='listbox'] li, .location-suggestion").first
                if await first_opt.count() > 0 and await first_opt.is_visible():
                    await first_opt.click()
                filled += 1
        except Exception:
            pass

        # Education history (#education--container)
        try:
            if self.master_data.education_history:
                edu = self.master_data.education_history[0]
                sch = target.locator("input[id*='school'], input[name*='school']").first
                if await sch.is_visible(timeout=1000) and not (await sch.input_value()):
                    await human_type(sch, edu.institution)
                    filled += 1

                deg = target.locator("select[id*='degree'], input[id*='degree']").first
                if await deg.is_visible(timeout=1000):
                    try:
                        await deg.select_option(label=edu.degree)
                    except Exception:
                        await human_type(deg, edu.degree)
                    filled += 1
        except Exception:
            pass

        # Employment history (#employment--container)
        try:
            if self.master_data.experience_history:
                exp = self.master_data.experience_history[0]
                comp = target.locator("input[id*='company-name-0'], input[name*='company']").first
                if await comp.is_visible(timeout=1000) and not (await comp.input_value()):
                    await human_type(comp, exp.company)
                    filled += 1

                tit = target.locator("input[id*='title-0'], input[name*='title']").first
                if await tit.is_visible(timeout=1000) and not (await tit.input_value()):
                    await human_type(tit, exp.title)
                    filled += 1
        except Exception:
            pass

        # LinkedIn Profile
        try:
            li = target.locator(
                "input[id*='linkedin'], input[name*='linkedin'], input[id*='question_'][placeholder*='linkedin' i]"
            ).first
            if await li.is_visible(timeout=1000) and not (await li.input_value()):
                await human_type(li, self.master_data.profiles.linkedin)
                filled += 1
        except Exception:
            pass

        # Compliance Dropdowns (18+, Authorized, Sponsorship)
        try:
            selects = target.locator("select[id*='question_']")
            count = await selects.count()
            for i in range(count):
                sel = selects.nth(i)
                label_text = await sel.evaluate("el => el.closest('div.field, fieldset')?.innerText || ''")
                label_lower = label_text.lower()
                if "18" in label_lower or "authorized" in label_lower:
                    try:
                        await sel.select_option(label="Yes")
                        filled += 1
                    except Exception:
                        pass
                elif "sponsorship" in label_lower or "previously employed" in label_lower:
                    try:
                        await sel.select_option(label="No")
                        filled += 1
                    except Exception:
                        pass
        except Exception:
            pass

        # Voluntary Self-ID (EEOC)
        try:
            gender_sel = target.locator("select#gender, select[name*='gender']").first
            if await gender_sel.is_visible(timeout=800):
                await gender_sel.select_option(label=self.master_data.voluntary_eeoc.gender)
                filled += 1
        except Exception:
            pass

        # Attach Resume
        if resume_pdf_path and os.path.exists(resume_pdf_path):
            try:
                res_file = target.locator("input[type='file'][id*='resume'], input[type='file']").first
                if await res_file.count() > 0:
                    print(f"📎 Attaching tailored resume: {resume_pdf_path}")
                    await res_file.set_input_files(resume_pdf_path)
                    attached = True
                    await asyncio.sleep(1.0)
            except Exception as e:
                print(f"⚠️ Resume attachment notice: {e}")

        return filled, attached

    async def _fill_lever(self, target: Any, resume_pdf_path: str | None) -> tuple[int, bool]:
        """Exhaustively fills a Lever application form."""
        filled = 0
        attached = False
        p = self.master_data.personal
        profiles = self.master_data.profiles

        # Name
        try:
            nm = target.locator("input[name='name']").first
            if await nm.is_visible(timeout=1500) and not (await nm.input_value()):
                await human_type(nm, p.full_name)
                filled += 1
        except Exception:
            pass

        # Email & Phone
        try:
            em = target.locator("input[name='email']").first
            if await em.is_visible(timeout=1500) and not (await em.input_value()):
                await human_type(em, p.email)
                filled += 1
        except Exception:
            pass

        try:
            ph = target.locator("input[name='phone']").first
            if await ph.is_visible(timeout=1500) and not (await ph.input_value()):
                await human_type(ph, p.phone)
                filled += 1
        except Exception:
            pass

        # Current Company
        try:
            org = target.locator("input[name='org']").first
            if await org.is_visible(timeout=1500) and not (await org.input_value()):
                await human_type(org, self.master_data.current_employment.company)
                filled += 1
        except Exception:
            pass

        # Profile URLs
        for url_name, val in [
            ("LinkedIn", profiles.linkedin),
            ("GitHub", profiles.github),
            ("Portfolio", profiles.portfolio),
        ]:
            if not val:
                continue
            try:
                u_in = target.locator(f"input[name='urls[{url_name}]']").first
                if await u_in.is_visible(timeout=800) and not (await u_in.input_value()):
                    await human_type(u_in, val)
                    filled += 1
            except Exception:
                pass

        # Demographic / Survey Radios
        try:
            for option_text in [self.master_data.voluntary_eeoc.gender, "Asian", "No"]:
                radio_opt = target.locator(
                    f"input[type='radio'][value='{option_text}'], label:has-text('{option_text}') input[type='radio']"
                ).first
                if await radio_opt.count() > 0 and await radio_opt.is_visible():
                    await radio_opt.check()
                    filled += 1
        except Exception:
            pass

        # Attach Resume
        if resume_pdf_path and os.path.exists(resume_pdf_path):
            try:
                res_file = target.locator("input[type='file'][name='resume'], input[type='file']").first
                if await res_file.count() > 0:
                    print(f"📎 Attaching tailored resume: {resume_pdf_path}")
                    await res_file.set_input_files(resume_pdf_path)
                    attached = True
                    await asyncio.sleep(1.0)
            except Exception as e:
                print(f"⚠️ Resume attachment notice: {e}")

        return filled, attached

    async def _fill_ashby(self, target: Any, resume_pdf_path: str | None) -> tuple[int, bool]:
        """Exhaustively fills an Ashby application form using semantic locators."""
        filled = 0
        attached = False
        p = self.master_data.personal
        profiles = self.master_data.profiles

        # Name fields
        try:
            fn = target.get_by_label("First Name")
            if await fn.is_visible(timeout=1500) and not (await fn.input_value()):
                await human_type(fn, p.first_name)
                filled += 1
        except Exception:
            pass

        try:
            ln = target.get_by_label("Last Name")
            if await ln.is_visible(timeout=1500) and not (await ln.input_value()):
                await human_type(ln, p.last_name)
                filled += 1
        except Exception:
            pass

        try:
            full_n = target.get_by_label("Full Name")
            if await full_n.is_visible(timeout=1000) and not (await full_n.input_value()):
                await human_type(full_n, p.full_name)
                filled += 1
        except Exception:
            pass

        # Email & Phone
        try:
            em = target.get_by_label("Email")
            if await em.is_visible(timeout=1500) and not (await em.input_value()):
                await human_type(em, p.email)
                filled += 1
        except Exception:
            pass

        try:
            ph = target.get_by_label("Phone")
            if await ph.is_visible(timeout=1500) and not (await ph.input_value()):
                await human_type(ph, p.phone)
                filled += 1
        except Exception:
            pass

        # Location Search
        try:
            loc = target.get_by_label("Location")
            if await loc.is_visible(timeout=1500) and not (await loc.input_value()):
                await human_type(loc, p.city)
                await asyncio.sleep(1.0)
                filled += 1
        except Exception:
            pass

        # Links
        for label_name, val in [
            ("LinkedIn", profiles.linkedin),
            ("GitHub", profiles.github),
            ("Portfolio", profiles.portfolio),
        ]:
            if not val:
                continue
            try:
                link_field = target.get_by_label(label_name, exact=False)
                if await link_field.is_visible(timeout=800) and not (await link_field.input_value()):
                    await human_type(link_field, val)
                    filled += 1
            except Exception:
                pass

        # Attach Resume
        if resume_pdf_path and os.path.exists(resume_pdf_path):
            try:
                res_file = target.locator("input[type='file']").first
                if await res_file.count() > 0:
                    print(f"📎 Attaching tailored resume: {resume_pdf_path}")
                    await res_file.set_input_files(resume_pdf_path)
                    attached = True
                    await asyncio.sleep(1.0)
            except Exception as e:
                print(f"⚠️ Resume attachment notice: {e}")

        return filled, attached

    async def _fill_workday(self, target: Any, resume_pdf_path: str | None) -> tuple[int, bool]:
        """Fills standard Workday application fields."""
        filled = 0
        attached = False
        p = self.master_data.personal

        for label_text, val in [
            ("Legal First Name", p.first_name),
            ("Legal Last Name", p.last_name),
            ("Email", p.email),
            ("Phone Number", p.phone),
            ("Address Line 1", p.address_line1 or p.city),
            ("City", p.city),
            ("Postal Code", p.postal_code),
        ]:
            try:
                inp = target.get_by_label(label_text, exact=False)
                if await inp.is_visible(timeout=1000) and not (await inp.input_value()):
                    await human_type(inp, val)
                    filled += 1
            except Exception:
                pass

        # Attach Resume
        if resume_pdf_path and os.path.exists(resume_pdf_path):
            try:
                res_file = target.locator("input[type='file']").first
                if await res_file.count() > 0:
                    print(f"📎 Attaching tailored resume: {resume_pdf_path}")
                    await res_file.set_input_files(resume_pdf_path)
                    attached = True
                    await asyncio.sleep(1.0)
            except Exception as e:
                print(f"⚠️ Resume attachment notice: {e}")

        return filled, attached

    async def _fill_linkedin_easy_apply(self, page: Any, resume_pdf_path: str | None) -> tuple[int, bool]:
        """Navigates LinkedIn Easy Apply modal and populates questions until review screen."""
        filled = 0
        attached = False
        modal = page.locator("div[role='dialog']").first

        try:
            if await modal.is_visible(timeout=3000):
                # Fill phone
                ph = modal.locator("input[id*='phoneNumber']").first
                if await ph.is_visible(timeout=1000) and not (await ph.input_value()):
                    await human_type(ph, self.master_data.personal.phone)
                    filled += 1

                # Check resume file input
                if resume_pdf_path and os.path.exists(resume_pdf_path):
                    file_input = modal.locator("input[type='file']").first
                    if await file_input.count() > 0:
                        await file_input.set_input_files(resume_pdf_path)
                        attached = True

                # Step forward through questions
                for _step in range(6):
                    review_btn = modal.locator("button:has-text('Review')").first
                    if await review_btn.count() > 0 and await review_btn.is_visible():
                        print("🛑 Reached LinkedIn Easy Apply 'Review' step. Halting for user review.")
                        break

                    next_btn = modal.locator("button:has-text('Next')").first
                    if await next_btn.count() > 0 and await next_btn.is_visible():
                        # Fill any numerical experience inputs before advancing
                        num_inputs = modal.locator("input[id*='numeric'], input[type='text']")
                        count = await num_inputs.count()
                        for i in range(count):
                            inp = num_inputs.nth(i)
                            val = await inp.input_value()
                            if not val:
                                lbl = await inp.evaluate("el => el.closest('div')?.innerText || ''")
                                years = str(self.master_data.get_skill_years(lbl, default=5))
                                await human_type(inp, years)
                                filled += 1

                        await next_btn.click()
                        await asyncio.sleep(1.5)
                    else:
                        break
        except Exception as e:
            print(f"⚠️ LinkedIn Easy Apply step notice: {e}")

        return filled, attached

    async def _fill_generic(self, target: Any, resume_pdf_path: str | None) -> tuple[int, bool]:
        """Fallback resilient filling across generic HTML forms."""
        contact = self.mapper.get_contact_info()
        filled = 0
        attached = False

        # First / Last / Full Name
        try:
            fn = target.locator("input#first_name, input[name='first_name'], input[name='firstName']").first
            if await fn.is_visible(timeout=1500) and not (await fn.input_value()):
                await human_type(fn, contact["first_name"])
                filled += 1

            ln = target.locator("input#last_name, input[name='last_name'], input[name='lastName']").first
            if await ln.is_visible(timeout=1500) and not (await ln.input_value()):
                await human_type(ln, contact["last_name"])
                filled += 1

            full_n = target.locator("input[name='name'], input#name").first
            if await full_n.is_visible(timeout=1000) and not (await full_n.input_value()):
                await human_type(full_n, contact["full_name"])
                filled += 1
        except Exception:
            pass

        # Email & Phone
        try:
            em = target.locator("input#email, input[name='email'], input[type='email']").first
            if await em.is_visible(timeout=1500) and not (await em.input_value()):
                await human_type(em, contact["email"])
                filled += 1

            ph = target.locator("input#phone, input[name='phone'], input[type='tel']").first
            if await ph.is_visible(timeout=1500) and not (await ph.input_value()):
                await human_type(ph, contact["phone"])
                filled += 1
        except Exception:
            pass

        # Links
        try:
            li = target.locator("input[name*='linkedin'], input#linkedin, input[placeholder*='linkedin' i]").first
            if await li.is_visible(timeout=1000) and not (await li.input_value()):
                await human_type(li, contact["linkedin"])
                filled += 1

            gh = target.locator("input[name*='github'], input#github, input[placeholder*='github' i]").first
            if await gh.is_visible(timeout=1000) and not (await gh.input_value()):
                await human_type(gh, contact["github"])
                filled += 1
        except Exception:
            pass

        # Resume Attachment
        if resume_pdf_path and os.path.exists(resume_pdf_path):
            try:
                file_input = target.locator("input[type='file']").first
                if await file_input.count() > 0:
                    print(f"📎 Attaching tailored resume: {resume_pdf_path}")
                    await file_input.set_input_files(resume_pdf_path)
                    attached = True
                    await asyncio.sleep(1.0)
            except Exception as e:
                print(f"⚠️ Resume attachment notice: {e}")

        return filled, attached

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
