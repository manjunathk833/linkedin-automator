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

    def __init__(self, headless: bool = False, master_data: CandidateMasterData | None = None):
        self.headless = headless
        self.mapper = FormFieldMapper()
        if master_data is not None:
            self.master_data = master_data
        else:
            try:
                self.master_data = load_candidate_master_data()
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

    async def _fill_text_input(self, locator: Any, value: str) -> bool:
        """Fills text input and triggers React synthetic input, change, and blur events."""
        try:
            if await locator.count() == 0:
                return False
            el = locator.first
            try:
                await el.scroll_into_view_if_needed(timeout=800)
            except Exception:
                pass
            await el.click(timeout=1000)
            await el.fill(value)
            await el.dispatch_event("input")
            await el.dispatch_event("change")
            await el.dispatch_event("blur")
            return True
        except Exception:
            return False

    async def _select_react_combobox(
        self, target: Any, locator: Any, search_text: str, prefer_exact: bool = False
    ) -> bool:
        """Resiliently interacts with React-Select / custom combobox / native select controls."""
        try:
            if await locator.count() == 0:
                return False
            el = locator.first
            try:
                await el.scroll_into_view_if_needed(timeout=800)
            except Exception:
                pass

            # Check if this is a native HTML select
            tag = await el.evaluate("e => e.tagName.toLowerCase()")
            if tag == "select":
                try:
                    await el.select_option(label=search_text)
                    return True
                except Exception:
                    options = await el.locator("option").all()
                    for opt in options:
                        t = await opt.inner_text()
                        if search_text.lower() in t.lower():
                            val = await opt.get_attribute("value")
                            if val:
                                await el.select_option(value=val)
                                return True
                    return False

            # If it's a container element, look for the inner input
            input_el = el
            if tag != "input":
                inner_input = el.locator("input.select__input, input[role='combobox'], input").first
                if await inner_input.count() > 0:
                    input_el = inner_input

            # Focus and clear/type
            await input_el.click(timeout=1200)
            await asyncio.sleep(0.15)
            type_text = "India" if ("+91" in search_text or search_text == "India") else search_text
            await input_el.fill(type_text)
            await input_el.dispatch_event("input")
            await asyncio.sleep(0.5)

            # Check if options menu opened (.select__option, div[role='option'], li[role='option'])
            page = getattr(target, "page", target)
            options = page.locator(".select__option, div[role='option'], li[role='option'], .select__menu-list div")
            try:
                await options.first.wait_for(state="visible", timeout=2500)
            except Exception:
                pass

            opt_count = await options.count()
            if opt_count > 0:
                # Special matching for Country dial code (+91)
                if "+91" in search_text or search_text == "India":
                    for i in range(opt_count):
                        opt = options.nth(i)
                        txt = await opt.inner_text()
                        if "+91" in txt or "India +91" in txt:
                            await opt.click(timeout=1200)
                            await asyncio.sleep(0.2)
                            return True

                # Matching logic
                for i in range(opt_count):
                    opt = options.nth(i)
                    txt = (await opt.inner_text()).strip()
                    if (
                        prefer_exact
                        and search_text.lower() == txt.lower()
                        or not prefer_exact
                        and search_text.lower() in txt.lower()
                    ):
                        await opt.click(timeout=1200)
                        await asyncio.sleep(0.2)
                        return True

                # Fallback to first visible option
                first_opt = options.first
                if await first_opt.is_visible():
                    await first_opt.click(timeout=1200)
                    await asyncio.sleep(0.2)
                    return True

            # If no dropdown option matched, press Enter and dispatch events
            await input_el.press("Enter")
            await input_el.dispatch_event("change")
            await input_el.dispatch_event("blur")
            await asyncio.sleep(0.3)
            return True
        except Exception:
            pass
        return False

    async def _fill_greenhouse(self, target: Any, resume_pdf_path: str | None) -> tuple[int, bool]:
        """Exhaustively fills both classic and modern React-Select Greenhouse application forms."""
        filled = 0
        attached = False
        p = self.master_data.personal

        # 1. First & Last Name
        if await self._fill_text_input(target.locator("input#first_name, input[name='first_name']"), p.first_name):
            filled += 1

        if await self._fill_text_input(target.locator("input#last_name, input[name='last_name']"), p.last_name):
            filled += 1

        # 2. Email & Phone
        if await self._fill_text_input(target.locator("input#email, input[name='email']"), p.email):
            filled += 1

        # Phone Country Combobox (#country -> India +91)
        try:
            country_input = target.locator("input#country, [id*='country']").first
            if await country_input.count() > 0 and await self._select_react_combobox(target, country_input, "+91"):
                filled += 1
        except Exception:
            pass

        try:
            clean_phone = p.phone.replace("+91", "").strip() or p.phone
            if await self._fill_text_input(target.locator("input#phone, input[name='phone']"), clean_phone):
                filled += 1
        except Exception:
            pass

        # 3. Location Combobox (#candidate-location)
        try:
            loc = target.locator("input#candidate-location, [id*='candidate-location']").first
            if await loc.count() > 0 and await self._select_react_combobox(target, loc, "Bengaluru"):
                filled += 1
        except Exception:
            pass

        # 4. Employment History (Value Labs, Dunzo, Tata Elxsi via "Add another")
        try:
            for i, exp in enumerate(self.master_data.experience_history):
                if i > 0:
                    emp_add = target.locator(
                        "#employment--container button.add-another-button, "
                        "#employment--container a.add-another-button, "
                        "#employment--container button:has-text('Add another'), "
                        "button.add-another-button"
                    ).first
                    if await emp_add.count() > 0:
                        try:
                            await emp_add.scroll_into_view_if_needed(timeout=800)
                            await emp_add.click()
                            await asyncio.sleep(0.5)
                        except Exception:
                            pass

                comp_el = target.locator(f"input#company-name-{i}").first
                if await comp_el.count() > 0 and await self._fill_text_input(comp_el, exp.company):
                    filled += 1

                title_el = target.locator(f"input#title-{i}").first
                if await title_el.count() > 0 and await self._fill_text_input(title_el, exp.title):
                    filled += 1

                start_mo = target.locator(f"input#start-date-month-{i}, [id*='start-date-month-{i}']").first
                if await start_mo.count() > 0 and await self._select_react_combobox(
                    target, start_mo, exp.start_month or "June"
                ):
                    filled += 1

                start_yr = target.locator(f"input#start-date-year-{i}, [id*='start-date-year-{i}']").first
                if await start_yr.count() > 0 and await self._fill_text_input(start_yr, exp.start_year or "2023"):
                    filled += 1

                if exp.is_current:
                    curr_chk = target.locator(f"input#current-role-{i}_1, input#current-role-{i}").first
                    if await curr_chk.count() > 0:
                        try:
                            if not await curr_chk.is_checked():
                                await curr_chk.check()
                                filled += 1
                        except Exception:
                            pass
                else:
                    end_mo = target.locator(f"input#end-date-month-{i}, [id*='end-date-month-{i}']").first
                    if await end_mo.count() > 0 and await self._select_react_combobox(
                        target, end_mo, exp.end_month or "January"
                    ):
                        filled += 1

                    end_yr = target.locator(f"input#end-date-year-{i}, [id*='end-date-year-{i}']").first
                    if await end_yr.count() > 0 and await self._fill_text_input(end_yr, exp.end_year or "2023"):
                        filled += 1
        except Exception as e:
            print(f"⚠️ Employment history autofill notice: {e}")

        # 5. Education History
        try:
            for k, edu in enumerate(self.master_data.education_history):
                if k > 0:
                    edu_add = target.locator(
                        "#education--container button.add-another-button, "
                        "#education--container a.add-another-button, "
                        "#education--container button:has-text('Add another')"
                    ).first
                    if await edu_add.count() > 0:
                        try:
                            await edu_add.scroll_into_view_if_needed(timeout=800)
                            await edu_add.click()
                            await asyncio.sleep(0.5)
                        except Exception:
                            pass

                sch = target.locator(f"input#school--{k}, [id*='school--{k}']").first
                if await sch.count() > 0:
                    selected = False
                    for query in ["Visvesvaraya", "Engineering", "Other"]:
                        if await self._select_react_combobox(target, sch, query):
                            selected = True
                            break
                    if not selected:
                        await self._fill_text_input(sch, edu.institution)
                    filled += 1

                deg = target.locator(f"input#degree--{k}, [id*='degree--{k}']").first
                if await deg.count() > 0:
                    if not await self._select_react_combobox(target, deg, "Bachelor"):
                        await self._select_react_combobox(target, deg, edu.degree)
                    filled += 1

                disc = target.locator(f"input#discipline--{k}, [id*='discipline--{k}']").first
                if await disc.count() > 0:
                    if not await self._select_react_combobox(target, disc, "Computer Science"):
                        await self._select_react_combobox(target, disc, edu.discipline)
                    filled += 1
        except Exception as e:
            print(f"⚠️ Education history autofill notice: {e}")

        # 6. LinkedIn Profile URL
        try:
            li = target.locator(
                "input[aria-label*='Linkedin' i], input[id*='linkedin'], input[name*='linkedin'], input[placeholder*='linkedin' i]"
            ).first
            if await li.count() > 0 and await self._fill_text_input(li, self.master_data.profiles.linkedin):
                filled += 1
        except Exception:
            pass

        # 7. Semantic Application Question Traversal
        try:
            question_boxes = target.locator("div.field, fieldset.field, .application-question")
            q_count = await question_boxes.count()
            for i in range(q_count):
                q_box = question_boxes.nth(i)
                try:
                    label_text = (await q_box.inner_text()).lower()
                except Exception as err:
                    print(f"⚠️ Notice reading question label: {err}")
                    continue

                # Check if LinkedIn URL input
                if "linkedin" in label_text:
                    li_box = q_box.locator(
                        "input.input__single-line:not(.select__input), input[type='text'], input[type='url']"
                    ).first
                    if await li_box.count() > 0 and await self._fill_text_input(
                        li_box, self.master_data.profiles.linkedin
                    ):
                        filled += 1
                        continue

                # Look for dropdown / combobox / select
                combobox = q_box.locator("input.select__input, input[role='combobox'], select").first
                if await combobox.count() == 0:
                    continue

                if "18" in label_text or "age" in label_text:
                    if await self._select_react_combobox(target, combobox, "Yes"):
                        filled += 1
                elif "previously" in label_text and "employed" in label_text:
                    if await self._select_react_combobox(target, combobox, "No"):
                        filled += 1
                elif "how did you hear" in label_text or "source" in label_text:
                    source_val = getattr(self.master_data.legal_and_compliance, "how_did_you_hear", "LinkedIn")
                    if await self._select_react_combobox(target, combobox, source_val):
                        filled += 1
                elif "privacy" in label_text or "arbitration" in label_text or "confirm receipt" in label_text:
                    if not await self._select_react_combobox(target, combobox, "I confirm"):
                        if await self._select_react_combobox(target, combobox, "Yes"):
                            filled += 1
                    else:
                        filled += 1
                elif "ai tools to assist" in label_text or "may use ai tools" in label_text:
                    if await self._select_react_combobox(target, combobox, "Yes"):
                        filled += 1
                elif "how you use ai tools today" in label_text or "use ai tools today" in label_text:
                    if not await self._select_react_combobox(target, combobox, "design or automate workflows"):
                        if await self._select_react_combobox(target, combobox, "regularly"):
                            filled += 1
                    else:
                        filled += 1
                elif "authorized" in label_text or "legally authorized" in label_text:
                    if await self._select_react_combobox(target, combobox, "Yes"):
                        filled += 1
                elif "sponsorship" in label_text:
                    if await self._select_react_combobox(target, combobox, "No"):
                        filled += 1
                elif "government official" in label_text:
                    if "relative" in label_text or "close relative" in label_text:
                        if not await self._select_react_combobox(
                            target, combobox, "No, I am not a relative of a government official."
                        ):
                            if await self._select_react_combobox(target, combobox, "No"):
                                filled += 1
                        else:
                            filled += 1
                    else:
                        if not await self._select_react_combobox(
                            target, combobox, "No, I am not a current or former Government Official"
                        ):
                            if await self._select_react_combobox(target, combobox, "No"):
                                filled += 1
                        else:
                            filled += 1
                elif (
                    "conflict" in label_text or "financial interest" in label_text or "referred" in label_text
                ) and await self._select_react_combobox(target, combobox, "No"):
                    filled += 1
        except Exception:
            pass

        # 8. Voluntary Self-ID (EEOC)
        try:
            gen = target.locator("input#gender, [id*='gender']").first
            if await gen.count() > 0 and await self._select_react_combobox(target, gen, "Male"):
                filled += 1

            hisp = target.locator("input#hispanic_ethnicity, [id*='hispanic']").first
            if await hisp.count() > 0 and await self._select_react_combobox(target, hisp, "No"):
                filled += 1

            vet = target.locator("input#veteran_status, [id*='veteran']").first
            if await vet.count() > 0 and await self._select_react_combobox(target, vet, "I am not a protected veteran"):
                filled += 1

            dis = target.locator("input#disability_status, [id*='disability']").first
            if await dis.count() > 0 and await self._select_react_combobox(target, dis, "No"):
                filled += 1
        except Exception:
            pass

        # 9. Attach Resume
        if resume_pdf_path and os.path.exists(resume_pdf_path):
            try:
                res_file = target.locator("input[type='file'][id*='resume'], input[type='file']").first
                if await res_file.count() > 0:
                    print(f"📎 Attaching tailored resume: {resume_pdf_path}")
                    await res_file.set_input_files(resume_pdf_path)
                    await res_file.dispatch_event("change")
                    attached = True
                    await asyncio.sleep(2.0)
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
