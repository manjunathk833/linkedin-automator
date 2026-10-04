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
from src.autofill.vendor_schemas import (
    ATSVendorPattern,
    CandidateMasterData,
    classify_ats_pattern,
    get_vendor_schema,
    load_candidate_master_data,
)
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

    # Databricks custom career portal redirects Greenhouse URLs back to databricks.com
    if "databricks" in url.lower():
        return url

    # Coinbase custom career portal redirects standard Greenhouse boards back to coinbase.com
    # Resolve directly to canonical Greenhouse embed portal to bypass redirects and Cloudflare
    if "coinbase" in url.lower():
        gh_match = re.search(r"gh_jid=(\d+)", url) or re.search(r"positions/(\d+)", url)
        if gh_match:
            job_id = gh_match.group(1)
            canonical = f"https://job-boards.greenhouse.io/embed/job_app?token={job_id}&for=coinbase&gh_jid={job_id}"
            print(f"🎯 Resolved Coinbase wrapper URL to canonical Greenhouse embed portal: {canonical}")
            return canonical

    # Greenhouse wrapper resolution via gh_jid
    gh_match = re.search(r"gh_jid=(\d+)", url)
    if gh_match:
        job_id = gh_match.group(1)
        company_slug = ""
        url_lower = url.lower()

        # Infer company slug from URL domain or parameter
        for known_slug in [
            "cloudflare",
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
        root_input = page.locator("input#first_name, input[name='first_name'], input#name, form#application_form").first
        if await root_input.count() == 0:
            iframe = page.locator(
                "iframe#grnhse_iframe, iframe#grnh_iframe, iframe[src*='greenhouse.io/embed'], iframe[src*='lever.co']"
            ).first
            try:
                if await iframe.count() > 0:
                    print("📦 Detected embedded ATS iframe. Switching target to iframe frame locator...")
                    target = page.frame_locator(
                        "iframe#grnhse_iframe, iframe#grnh_iframe, iframe[src*='greenhouse.io/embed'], iframe[src*='lever.co']"
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
                        # Wait until the new page navigates away from about:blank
                        for _ in range(50):
                            if getattr(new_page, "url", "") and getattr(new_page, "url", "") != "about:blank":
                                break
                            await asyncio.sleep(0.1)
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
                        # Wait until the new page navigates away from about:blank
                        for _ in range(50):
                            if getattr(new_page, "url", "") and getattr(new_page, "url", "") != "about:blank":
                                break
                            await asyncio.sleep(0.1)
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

                    # Re-check for embedded iframe in newly focused tab only if form inputs not already on root
                    try:
                        tab_input = page.locator(
                            "input#first_name, input[name='first_name'], input#name, form#application_form"
                        ).first
                        if await tab_input.count() == 0:
                            tab_iframe = page.locator(
                                "iframe#grnhse_iframe, iframe#grnh_iframe, iframe[src*='greenhouse.io/embed'], iframe[src*='lever.co']"
                            ).first
                            if await tab_iframe.count() > 0:
                                print("📦 Detected embedded ATS iframe in new tab. Switching target...")
                                target = page.frame_locator(
                                    "iframe#grnhse_iframe, iframe#grnh_iframe, iframe[src*='greenhouse.io/embed'], iframe[src*='lever.co']"
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

        # 3. Detect vendor pattern and execute standardized vendor autofill
        active_url = getattr(page, "url", job_url)
        pattern = classify_ats_pattern(active_url)
        print(f"🎯 Pattern Recognition Engine: Identified ATS Pattern [{pattern}] for URL: {active_url}")
        fields_filled = 0
        resume_attached = False

        if pattern == ATSVendorPattern.DATABRICKS_CUSTOM_GREENHOUSE:
            print("🧱 Identified Databricks Custom Greenhouse career portal.")
            fields_filled, resume_attached = await self._fill_databricks(target, resume_pdf_path)
        elif pattern == ATSVendorPattern.OKTA_BRANDED_GREENHOUSE:
            print("🏢 Identified Okta Branded Greenhouse custom career portal.")
            fields_filled, resume_attached = await self._fill_okta(target, resume_pdf_path)
        elif pattern == ATSVendorPattern.COINBASE_CUSTOM_GREENHOUSE:
            print("🪙 Identified Coinbase Custom Greenhouse career portal.")
            fields_filled, resume_attached = await self._fill_greenhouse(target, resume_pdf_path)
        elif pattern == ATSVendorPattern.GREENHOUSE_STANDARD:
            print("🏛️ Identified Greenhouse ATS standard form.")
            fields_filled, resume_attached = await self._fill_greenhouse(target, resume_pdf_path)
        elif pattern == ATSVendorPattern.LEVER_STANDARD:
            print("🏢 Identified Lever ATS standard form.")
            fields_filled, resume_attached = await self._fill_lever(target, resume_pdf_path)
        elif pattern == ATSVendorPattern.ASHBY_STANDARD:
            print("🚀 Identified Ashby ATS standard form.")
            fields_filled, resume_attached = await self._fill_ashby(target, resume_pdf_path)
        elif pattern == ATSVendorPattern.WORKDAY_STANDARD:
            print("🏢 Identified Workday standard portal.")
            fields_filled, resume_attached = await self._fill_workday(target, resume_pdf_path)
        elif pattern == ATSVendorPattern.ORACLE_CLOUD_HCM:
            print("☁️ Identified Oracle Cloud HCM / Fusion Candidate Experience portal.")
            fields_filled, resume_attached = await self._fill_oracle_hcm(page, resume_pdf_path)
        elif pattern == ATSVendorPattern.LINKEDIN_EASY_APPLY:
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
                    await el.select_option(label=search_text, timeout=1500)
                    return True
                except Exception:
                    options = await el.locator("option").all()
                    for opt in options:
                        t = await opt.inner_text()
                        if search_text.lower() in t.lower():
                            val = await opt.get_attribute("value")
                            if val:
                                await el.select_option(value=val, timeout=1500)
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
            container = target if hasattr(target, "locator") else getattr(target, "page", target)
            options = container.locator(
                ".select__option:not(.select__menu-notice), div[role='option']:not(.select__menu-notice), li[role='option']"
            )
            try:
                await options.first.wait_for(state="visible", timeout=3500)
            except Exception:
                pass

            opt_count = await options.count()
            if opt_count > 0:
                # Special matching for Country dial code (+91)
                if "+91" in search_text or search_text == "India":
                    for i in range(opt_count):
                        opt = options.nth(i)
                        txt = await opt.inner_text()
                        if "+91" in txt:
                            await opt.click(timeout=1200)
                            await asyncio.sleep(0.2)
                            return True
                    for i in range(opt_count):
                        opt = options.nth(i)
                        txt = (await opt.inner_text()).strip()
                        if txt == "India" or txt.startswith("India (") or "india (+91)" in txt.lower():
                            await opt.click(timeout=1200)
                            await asyncio.sleep(0.2)
                            return True

                # Matching logic
                for i in range(opt_count):
                    opt = options.nth(i)
                    txt = (await opt.inner_text()).strip()
                    if not txt or "loading" in txt.lower():
                        continue
                    if (
                        prefer_exact
                        and search_text.lower() == txt.lower()
                        or not prefer_exact
                        and search_text.lower() in txt.lower()
                    ):
                        await opt.click(timeout=1200)
                        await asyncio.sleep(0.2)
                        return True

                # Fallback to first visible valid option (ignoring notices)
                first_opt = options.first
                if await first_opt.is_visible():
                    first_txt = (await first_opt.inner_text()).strip()
                    if "loading" not in first_txt.lower():
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

    async def _fill_okta(self, target: Any, resume_pdf_path: str | None) -> tuple[int, bool]:
        """Fills Okta-branded Greenhouse custom application form."""
        filled = 0
        attached = False
        p = self.master_data.personal
        profiles = self.master_data.profiles
        schema = get_vendor_schema(ATSVendorPattern.OKTA_BRANDED_GREENHOUSE).get("selectors", {})

        # 1. First & Last Name
        first_sel = ", ".join(schema.get("first_name", ["input#edit-first-name", "input[name='first_name']"]))
        if await self._fill_text_input(target.locator(first_sel), p.first_name):
            filled += 1

        last_sel = ", ".join(schema.get("last_name", ["input#edit-last-name", "input[name='last_name']"]))
        if await self._fill_text_input(target.locator(last_sel), p.last_name):
            filled += 1

        # 2. Email & Phone
        email_sel = ", ".join(schema.get("email", ["input#edit-email", "input[name='email']"]))
        if await self._fill_text_input(target.locator(email_sel), p.email):
            filled += 1

        phone_sel = ", ".join(schema.get("phone", ["input#edit-phone", "input[name='phone']"]))
        if await self._fill_text_input(target.locator(phone_sel), p.phone):
            filled += 1

        # 3. Resume Upload
        resume_sel = ", ".join(schema.get("resume", ["input#edit-resume", "input[type='file'][name*='resume']"]))
        if resume_pdf_path and os.path.exists(resume_pdf_path):
            try:
                res_el = target.locator(resume_sel).first
                if await res_el.count() > 0:
                    await res_el.set_input_files(os.path.abspath(resume_pdf_path))
                    attached = True
                    filled += 1
                    print(f"📎 Attached resume PDF to Okta form: {os.path.basename(resume_pdf_path)}")
            except Exception as e:
                print(f"⚠️ Okta resume attachment notice: {e}")

        # 4. LinkedIn Profile & Portfolio Website
        # LinkedIn
        linkedin_sel = ", ".join(
            schema.get(
                "linkedin",
                [
                    "input#edit-question-69483961",
                    "div:has(label:has-text('LinkedIn Profile')) input",
                    "input[name*='69483961']",
                    "input[id*='linkedin']",
                ],
            )
        )
        if profiles.linkedin:
            try:
                li_input = target.locator(linkedin_sel).first
                if await li_input.count() > 0 and await self._fill_text_input(li_input, profiles.linkedin):
                    filled += 1
                    print(f"🔗 Populated candidate LinkedIn profile into Okta form: {profiles.linkedin}")
            except Exception:
                pass

        # Website (Candidate Portfolio from data/profile/candidate_master_data.json)
        website_val = profiles.portfolio or "https://manjunathhk.netlify.app/"
        website_sel = ", ".join(
            schema.get(
                "website",
                [
                    "input#edit-question-69483962",
                    "div:has(label:has-text('Website')) input",
                    "input[name*='69483962']",
                    "input[id*='website']",
                ],
            )
        )
        try:
            web_input = target.locator(website_sel).first
            if await web_input.count() > 0 and await self._fill_text_input(web_input, website_val):
                filled += 1
                print(f"🌐 Populated candidate website ({website_val}) into Okta form")
        except Exception:
            pass

        # 5. Screening Questions (Native <select> elements)
        # 5.1 Legally Authorized to Work -> "Yes"
        auth_sel = ", ".join(
            schema.get(
                "work_authorization",
                [
                    "select#edit-question-69483963",
                    "div:has(label:has-text('authorized to work')) select",
                    "select[name*='69483963']",
                ],
            )
        )
        try:
            auth_el = target.locator(auth_sel).first
            if await auth_el.count() > 0 and await self._select_react_combobox(target, auth_el, "Yes"):
                filled += 1
        except Exception:
            pass

        # 5.2 Visa Sponsorship -> "No"
        visa_sel = ", ".join(
            schema.get(
                "visa_sponsorship",
                [
                    "select#edit-question-69483964",
                    "div:has(label:has-text('require Visa Sponsorship')) select",
                    "select[name*='69483964']",
                ],
            )
        )
        try:
            visa_el = target.locator(visa_sel).first
            if await visa_el.count() > 0 and await self._select_react_combobox(target, visa_el, "No"):
                filled += 1
        except Exception:
            pass

        # 5.3 Family / Relative Conflict of Interest -> "No"
        rel_sel = ", ".join(
            schema.get(
                "conflict_relatives",
                [
                    "select#edit-question-69483965",
                    "div:has(label:has-text('family members')) select",
                    "select[name*='69483965']",
                ],
            )
        )
        try:
            rel_el = target.locator(rel_sel).first
            if await rel_el.count() > 0 and await self._select_react_combobox(target, rel_el, "No"):
                filled += 1
        except Exception:
            pass

        # 5.4 Outside Business Activities -> "No"
        out_sel = ", ".join(
            schema.get(
                "outside_activities",
                [
                    "select#edit-question-69483967",
                    "div:has(label:has-text('outside business activity')) select",
                    "select[name*='69483967']",
                ],
            )
        )
        try:
            out_el = target.locator(out_sel).first
            if await out_el.count() > 0 and await self._select_react_combobox(target, out_el, "No"):
                filled += 1
        except Exception:
            pass

        # 5.5 Previous Employment at Okta -> "No"
        prev_sel = ", ".join(
            schema.get(
                "previous_employment",
                [
                    "select#edit-question-69483969",
                    "div:has(label:has-text('employed by Okta')) select",
                    "select[name*='69483969']",
                ],
            )
        )
        try:
            prev_el = target.locator(prev_sel).first
            if await prev_el.count() > 0 and await self._select_react_combobox(target, prev_el, "No"):
                filled += 1
        except Exception:
            pass

        # 6. Consent Checkboxes
        consent_privacy_sel = ", ".join(
            schema.get(
                "consent_privacy",
                [
                    "input[id*='69483970']",
                    "input#edit-question-69483970-753704919",
                    "div:has(label:has-text('I acknowledge')) input[type='checkbox']",
                    "input[type='checkbox'][name*='69483970']",
                ],
            )
        )
        try:
            chk1 = target.locator(consent_privacy_sel).first
            if await chk1.count() > 0:
                if not await chk1.is_checked():
                    try:
                        await chk1.check(timeout=1000)
                    except Exception:
                        await chk1.click(force=True)
                filled += 1
        except Exception:
            pass

        consent_eval_sel = ", ".join(
            schema.get(
                "consent_evaluation",
                [
                    "input[id*='69483971']",
                    "input#edit-question-69483971-753704920",
                    "div:has(label:has-text('consent')) input[type='checkbox']",
                    "input[type='checkbox'][name*='69483971']",
                ],
            )
        )
        try:
            chk2 = target.locator(consent_eval_sel).first
            if await chk2.count() > 0:
                if not await chk2.is_checked():
                    try:
                        await chk2.check(timeout=1000)
                    except Exception:
                        await chk2.click(force=True)
                filled += 1
        except Exception:
            pass

        # 7. Voluntary EEOC Disclosures (<select>)
        # Gender -> "Male"
        gender_sel = ", ".join(
            schema.get("eeoc_gender", ["select#edit-compliance-section-gender-0", "select[name*='gender']"])
        )
        try:
            gender_el = target.locator(gender_sel).first
            if await gender_el.count() > 0 and await self._select_react_combobox(
                target, gender_el, self.master_data.voluntary_eeoc.gender
            ):
                filled += 1
        except Exception:
            pass

        # Race -> "Asian"
        race_sel = ", ".join(schema.get("eeoc_race", ["select#edit-compliance-section-race-0", "select[name*='race']"]))
        try:
            race_el = target.locator(race_sel).first
            if await race_el.count() > 0 and await self._select_react_combobox(
                target, race_el, self.master_data.voluntary_eeoc.race_ethnicity
            ):
                filled += 1
        except Exception:
            pass

        # Veteran Status -> "I am not a protected veteran"
        vet_sel = ", ".join(
            schema.get(
                "eeoc_veteran",
                ["select#edit-compliance-section-veteran-status-0", "select[name*='veteran']"],
            )
        )
        try:
            vet_el = target.locator(vet_sel).first
            if await vet_el.count() > 0 and await self._select_react_combobox(
                target, vet_el, self.master_data.voluntary_eeoc.veteran_status
            ):
                filled += 1
        except Exception:
            pass

        # Disability Status (if present)
        dis_sel = ", ".join(
            schema.get(
                "eeoc_disability",
                ["select#edit-compliance-section-disability-status-0", "select[name*='disability']"],
            )
        )
        try:
            dis_el = target.locator(dis_sel).first
            if await dis_el.count() > 0 and (
                await self._select_react_combobox(target, dis_el, "No")
                or await self._select_react_combobox(target, dis_el, "do not have a disability")
            ):
                filled += 1
        except Exception:
            pass

        return filled, attached

    async def _fill_oracle_hcm(self, page: Any, resume_pdf_path: str | None) -> tuple[int, bool]:
        """Fills Oracle Cloud HCM / Fusion Candidate Experience application form."""
        filled = 0
        attached = False
        p = self.master_data.personal
        profiles = self.master_data.profiles
        schema = get_vendor_schema(ATSVendorPattern.ORACLE_CLOUD_HCM).get("selectors", {})
        target = page

        # 0. Cookie Consent Dismissal
        try:
            cookie_btn = target.locator(
                "button#onetrust-accept-btn-handler, button:has-text('Accept All'), button:has-text('Accept Cookies')"
            ).first
            if await cookie_btn.count() > 0 and await cookie_btn.is_visible():
                print("🍪 Dismissing cookie consent banner...")
                await cookie_btn.click()
                await asyncio.sleep(0.5)
        except Exception as e:
            print(f"⚠️ Cookie banner check notice: {e}")

        # 1. Stage 1: Check if we are on the initial Job Description page and need to click 'Apply Now'
        try:
            email_field = target.locator("input#primary-email-0, input[type='email']").first
            core_name_field = target.locator("input[name*='lastName' i], input#last-name").first
            is_email_visible = await email_field.is_visible() if await email_field.count() > 0 else False
            is_core_visible = await core_name_field.is_visible() if await core_name_field.count() > 0 else False

            if not is_email_visible and not is_core_visible:
                apply_btn = target.locator(
                    "button.apply-now-button.apply-now-button--apply-now, button:has-text('Apply Now'), button:has-text('Apply')"
                ).first
                if await apply_btn.count() > 0 and await apply_btn.is_visible():
                    print("🖱️ Clicking 'Apply Now' button on Oracle HCM job detail page...")
                    await apply_btn.click()
                    await asyncio.sleep(2.0)
        except Exception as e:
            print(f"⚠️ Stage 1 apply trigger notice: {e}")

        # 2. Stage 2: Email & Legal Disclaimer Gate (/job/.../apply/email)
        try:
            email_input = target.locator("input#primary-email-0, input[type='email'], input[name*='email']").first
            if await email_input.count() > 0 and await email_input.is_visible():
                print("📧 Detected Oracle HCM email gate. Populating email and legal disclaimer...")
                if await self._fill_text_input(email_input, p.email):
                    filled += 1

                # Legal disclaimer checkbox
                consent_cb = target.locator(
                    "label.legal-disclaimer-container input[type='checkbox'], input[type='checkbox']#legal-terms, input[type='checkbox']"
                ).first
                if await consent_cb.count() > 0:
                    try:
                        if not await consent_cb.is_checked():
                            await consent_cb.check()
                    except Exception:
                        await consent_cb.click(force=True)
                    print("✅ Checked legal disclaimer consent checkbox.")

                # Click Next button
                next_btn = target.locator("button:has-text('Next'), button.next-button, button[type='submit']").first
                if await next_btn.count() > 0 and await next_btn.is_visible():
                    print("➡️ Submitting email gate with 'Next' button...")
                    await next_btn.click()
                    await asyncio.sleep(3.0)
        except Exception as e:
            print(f"⚠️ Stage 2 email gate notice: {e}")

        # 3. Stage 3: Section 1 - Candidate Profile & Resume (/job/.../apply/section/1)
        # 3.1 Resume Attachment
        resume_sel = ", ".join(schema.get("resume", ["input[type='file'][name*='resume']", "input[type='file']"]))
        if resume_pdf_path and os.path.exists(resume_pdf_path):
            try:
                res_el = target.locator(resume_sel).first
                if await res_el.count() > 0:
                    await res_el.set_input_files(os.path.abspath(resume_pdf_path))
                    attached = True
                    filled += 1
                    print(f"📎 Attached resume PDF to Oracle Cloud HCM form: {os.path.basename(resume_pdf_path)}")
            except Exception as e:
                print(f"⚠️ Oracle HCM resume upload notice: {e}")

        # 3.2 Title Radio Pill (e.g., 'Mr.')
        try:
            title_pill = target.locator(
                "label:has-text('Mr.'), input[type='radio'][value='Mr.'], input[type='radio'][value='MR']"
            ).first
            if await title_pill.count() > 0 and await title_pill.is_visible():
                await title_pill.click()
                filled += 1
                print("🎯 Selected title pill: 'Mr.'")
        except Exception as e:
            print(f"⚠️ Title pill selection notice: {e}")

        # 3.3 First Name
        first_sel = ", ".join(
            schema.get(
                "first_name",
                ["input[name*='firstName' i]", "input#first-name", "input[aria-label*='First Name' i]"],
            )
        )
        if await self._fill_text_input(target.locator(first_sel), p.first_name):
            filled += 1

        # 3.4 Last Name
        last_sel = ", ".join(
            schema.get(
                "last_name",
                ["input[name*='lastName' i]", "input#last-name", "input[aria-label*='Last Name' i]"],
            )
        )
        if await self._fill_text_input(target.locator(last_sel), p.last_name):
            filled += 1

        # 3.5 Middle Name (optional)
        middle_sel = ", ".join(
            schema.get(
                "middle_name",
                ["input[name*='middleName' i]", "input#middle-name", "input[aria-label*='Middle Name' i]"],
            )
        )
        try:
            middle_el = target.locator(middle_sel).first
            if await middle_el.count() > 0 and await middle_el.is_visible():
                pass
        except Exception:
            pass

        # 3.6 Phone Country Dial Code & Phone Number
        try:
            # Country combobox / dropdown if present
            country_combobox = target.locator(
                "div.phone-country-code, select[name*='country' i], div[role='combobox']:has-text('+'), div.select-country"
            ).first
            if await country_combobox.count() > 0 and await country_combobox.is_visible():
                await self._select_react_combobox(target, country_combobox, "India (+91)")

            # Phone number text input
            phone_sel = ", ".join(
                schema.get(
                    "phone",
                    ["input[type='tel']", "input[name*='phone' i]", "input[aria-label*='Phone' i]"],
                )
            )
            phone_digits = p.phone
            if phone_digits.startswith("+91"):
                phone_digits = phone_digits.replace("+91", "").strip()
            if await self._fill_text_input(target.locator(phone_sel), phone_digits):
                filled += 1
        except Exception as e:
            print(f"⚠️ Phone field notice: {e}")

        # 3.7 Links (Portfolio / LinkedIn)
        link_val = profiles.portfolio or profiles.linkedin
        if link_val:
            website_sel = ", ".join(
                schema.get(
                    "website",
                    ["input[name*='link' i]", "input[aria-label*='Link' i]", "input[placeholder*='Link' i]"],
                )
            )
            if await self._fill_text_input(target.locator(website_sel), link_val):
                filled += 1
            elif profiles.linkedin:
                linkedin_sel = ", ".join(
                    schema.get("linkedin", ["input[name*='linkedin' i]", "input[aria-label*='LinkedIn' i]"])
                )
                if await self._fill_text_input(target.locator(linkedin_sel), profiles.linkedin):
                    filled += 1

        return filled, attached

    async def _fill_databricks(self, target: Any, resume_pdf_path: str | None) -> tuple[int, bool]:
        """Fills Databricks custom embedded Greenhouse application form."""
        filled = 0
        attached = False
        p = self.master_data.personal
        profiles = self.master_data.profiles
        current_firm = getattr(self.master_data.current_employment, "company", "Value Labs") or "Value Labs"
        schema = get_vendor_schema(ATSVendorPattern.DATABRICKS_CUSTOM_GREENHOUSE).get("selectors", {})

        # Switch to iframe if target is still the parent page
        if hasattr(target, "goto"):
            iframe = target.locator("iframe#grnhse_iframe, iframe#grnh_iframe, iframe[src*='greenhouse.io']").first
            try:
                if await iframe.count() > 0:
                    target = target.frame_locator(
                        "iframe#grnhse_iframe, iframe#grnh_iframe, iframe[src*='greenhouse.io']"
                    ).first
            except Exception:
                pass

        # 1. First & Last Name
        first_sel = ", ".join(schema.get("first_name", ["input#first_name", "input[name='first_name']"]))
        if await self._fill_text_input(target.locator(first_sel), p.first_name):
            filled += 1

        last_sel = ", ".join(schema.get("last_name", ["input#last_name", "input[name='last_name']"]))
        if await self._fill_text_input(target.locator(last_sel), p.last_name):
            filled += 1

        # 2. Preferred First Name (Required on Databricks!)
        pref_sel = ", ".join(schema.get("preferred_name", ["input#preferred_name", "input[name='preferred_name']"]))
        if await self._fill_text_input(target.locator(pref_sel), p.first_name):
            filled += 1

        # 3. Email
        email_sel = ", ".join(schema.get("email", ["input#email", "input[name='email']"]))
        if await self._fill_text_input(target.locator(email_sel), p.email):
            filled += 1

        # 4. Country Combobox (#country -> India +91)
        try:
            country_sel = ", ".join(
                schema.get(
                    "country",
                    ["input#country"],
                )
            )
            country_input = target.locator(country_sel).first
            if await country_input.count() > 0 and await self._select_react_combobox(target, country_input, "+91"):
                filled += 1
        except Exception:
            pass

        # 5. Phone
        phone_sel = ", ".join(schema.get("phone", ["input#phone", "input[name='phone']"]))
        try:
            clean_phone = p.phone.replace("+91", "").strip() or p.phone
            phone_input = target.locator(phone_sel).first
            if await phone_input.count() > 0 and await self._fill_text_input(phone_input, clean_phone):
                filled += 1
        except Exception:
            pass

        # 6. Candidate Location (Combobox: Bengaluru)
        try:
            loc_sel = ", ".join(
                schema.get(
                    "location",
                    [
                        "input#candidate-location",
                    ],
                )
            )
            loc_input = target.locator(loc_sel).first
            if await loc_input.count() > 0 and await self._select_react_combobox(
                target, loc_input, p.city or "Bengaluru"
            ):
                filled += 1
        except Exception:
            pass

        # 7. Resume Upload
        resume_sel = ", ".join(
            schema.get(
                "resume", ["input#resume[type='file']", "input[type='file'][name*='resume']", "input[type='file']"]
            )
        )
        if resume_pdf_path and os.path.exists(resume_pdf_path):
            try:
                res_el = target.locator(resume_sel).first
                if await res_el.count() > 0:
                    await res_el.set_input_files(os.path.abspath(resume_pdf_path))
                    attached = True
                    filled += 1
                    print(f"📎 Attached resume PDF to Databricks form: {os.path.basename(resume_pdf_path)}")
            except Exception as e:
                print(f"⚠️ Databricks resume attachment notice: {e}")

        # 8. LinkedIn Profile
        linkedin_sel = ", ".join(
            schema.get(
                "linkedin",
                [
                    "input#question_35489440002",
                    "input[aria-label*='LinkedIn' i]",
                ],
            )
        )
        if profiles.linkedin:
            try:
                li_input = target.locator(linkedin_sel).first
                if await li_input.count() > 0 and await self._fill_text_input(li_input, profiles.linkedin):
                    filled += 1
                    print(f"🔗 Populated candidate LinkedIn profile into Databricks form: {profiles.linkedin}")
            except Exception:
                pass

        # 9. Current Firm (Required on Databricks!)
        firm_sel = ", ".join(
            schema.get(
                "current_firm",
                [
                    "input#question_35489441002",
                    "input[aria-label*='Current firm' i]",
                ],
            )
        )
        try:
            firm_input = target.locator(firm_sel).first
            if await firm_input.count() > 0 and await self._fill_text_input(firm_input, current_firm):
                filled += 1
                print(f"🏢 Populated candidate current firm ({current_firm}) into Databricks form")
        except Exception:
            pass

        # 10. Legally Authorized to Work -> "Yes"
        auth_sel = ", ".join(
            schema.get(
                "work_authorization",
                [
                    "input#question_35489442002",
                    ".field-wrapper:has(label:has-text('authorized to work')) input",
                    "input[aria-label*='authorized to work' i]",
                ],
            )
        )
        try:
            auth_el = target.locator(auth_sel).first
            if await auth_el.count() > 0 and await self._select_react_combobox(target, auth_el, "Yes"):
                filled += 1
        except Exception:
            pass

        # 11. Previously Worked for Databricks -> "No"
        prev_sel = ", ".join(
            schema.get(
                "previously_worked",
                [
                    "input#question_35489443002",
                    ".field-wrapper:has(label:has-text('worked for Databricks')) input",
                    "input[aria-label*='worked for Databricks' i]",
                ],
            )
        )
        try:
            prev_el = target.locator(prev_sel).first
            if await prev_el.count() > 0 and await self._select_react_combobox(target, prev_el, "No"):
                filled += 1
        except Exception:
            pass

        return filled, attached

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

    async def autofill_linkedin_external(
        self,
        job_url: str,
        resume_pdf_path: str | None = None,
        company: str = "",
    ) -> dict[str, Any]:
        """Loads a LinkedIn job view, detects Easy Apply vs External Apply, captures opened ATS window,
        and executes matching ATS vendor autofill logic, halting before submission for review."""
        _pw, _context, page = await launch_stealth_browser(headless=self.headless)
        _ACTIVE_SESSIONS.append((_pw, _context, page))

        try:
            try:
                await page.bring_to_front()
            except Exception:
                pass

            print(f"🌐 Navigating to LinkedIn job view: {job_url}")
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2.0)

            # Locate Apply / Easy Apply button on LinkedIn job view
            apply_btn = page.locator(
                ".jobs-apply-button, button.jobs-apply-button--top-card, a.jobs-apply-button, "
                "button[data-control-name*='apply'], button:has-text('Easy Apply'), "
                "button:has-text('Apply'), a:has-text('Apply')"
            ).first

            if await apply_btn.count() == 0 or not await apply_btn.is_visible(timeout=5000):
                # Fallback: Check if already on an ATS page or if redirected
                if "linkedin.com" not in page.url.lower():
                    return await self.fill_ats_page(page, page.url, resume_pdf_path)
                return {
                    "status": "error",
                    "error": "Apply button not found on LinkedIn job view",
                    "url": job_url,
                }

            btn_text = (await apply_btn.text_content() or "").strip().lower()
            aria_label = (await apply_btn.get_attribute("aria-label") or "").strip().lower()
            full_desc = f"{btn_text} {aria_label}"

            if "easy apply" in full_desc:
                print("🔗 Detected LinkedIn Easy Apply. Delegating to LinkedInAssistedFiller...")
                from src.autofill.linkedin_filler import LinkedInAssistedFiller

                li_filler = LinkedInAssistedFiller(headless=self.headless)
                return await li_filler.autofill_easy_apply(job_url, resume_pdf_path)

            print(f"🚀 Detected External Apply button ('{btn_text}'). Capturing external ATS popup...")
            opened_pages: list[Any] = []

            def _on_page(new_p: Any) -> None:
                opened_pages.append(new_p)

            if _context:
                _context.on("page", _on_page)
            try:
                page.on("popup", _on_page)
            except Exception:
                pass

            try:
                await apply_btn.click()
                for _ in range(30):
                    if opened_pages:
                        break
                    await asyncio.sleep(0.1)
            finally:
                if _context:
                    try:
                        _context.remove_listener("page", _on_page)
                    except Exception:
                        pass
                try:
                    page.remove_listener("popup", _on_page)
                except Exception:
                    pass

            # Check if LinkedIn displays an external redirect confirmation modal
            try:
                confirm_btn = page.locator(
                    "button:has-text('Continue'), button:has-text('Apply on company website'), "
                    "a:has-text('Continue'), .artdeco-modal button.artdeco-button--primary"
                ).first
                if await confirm_btn.count() > 0 and await confirm_btn.is_visible(timeout=1500):
                    print("🖱️ Confirming LinkedIn external redirection modal...")
                    await confirm_btn.click()
                    await asyncio.sleep(1.0)
            except Exception:
                pass

            target_page = page
            if opened_pages:
                target_page = opened_pages[0]
            elif _context and len(_context.pages) > 1 and _context.pages[-1] != page:
                target_page = _context.pages[-1]

            # Wait for target page to navigate away from about:blank and linkedin redirect
            print("⏳ Waiting for external ATS portal to load...")
            for _ in range(50):
                cur_url = getattr(target_page, "url", "")
                if cur_url and cur_url != "about:blank" and "linkedin.com/jobs/view/externalApply" not in cur_url:
                    break
                await asyncio.sleep(0.1)

            try:
                await target_page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass

            try:
                await target_page.bring_to_front()
            except Exception:
                pass

            external_ats_url = getattr(target_page, "url", job_url)
            print(f"🎯 Successfully pivoted to External ATS Portal: {external_ats_url}")

            # Execute canonical ATS autofill on the external ATS portal page
            return await self.fill_ats_page(target_page, external_ats_url, resume_pdf_path)

        except Exception as e:
            print(f"⚠️ Error during LinkedIn external ATS pivot: {e}")
            return {"status": "error", "error": str(e), "url": job_url}
