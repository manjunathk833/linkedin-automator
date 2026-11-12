"""Universal 2-Phase 'Extract-Map-BatchExecute' Form Autofill Engine.

Designed to achieve 10-15+ job applications per hour (2-4 minutes per job) with
zero silent country/territory corruption:
- Phase A (Extract & Deterministic Batch Fill in <3s):
  1. Single-call JS DOM extractor tags all visible interactive form controls with
     `data-agy-id` and returns a compact JSON descriptor (label, tag, type, role,
     required, current_value, options).
  2. Deterministically maps 80-90% of fields against `candidate_master_data.json`
     and `workday_field_mappings.json` (including Notice Period = 60 Days,
     Current CTC = 17,00,000 INR, Expected CTC = 27,00,000 INR, Country = India / +91).
  3. Batch-executes all matched fields in one pass using instant `.fill()` +
     synthetic React (`input`, `change`, `blur`) event dispatch and tiered combobox
     selection with hard negative territory exclusion (`British Indian Ocean Territory`, `+246`).
- Phase B (Single-Turn Custom Field Batch Resolution + Read-Back Audit):
  1. Returns compact JSON of only `unmapped_fields` (with option lists) so the agent
     can resolve custom company questions in 1 single turn and apply them via
     `apply_custom_actions(page, actions)`.
  2. Runs `verify_filled_controls(page)` to read back committed DOM values and assert
     zero contaminated territories (`+246` / `British Indian Ocean Territory`) and
     report any remaining empty required fields.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from src.autofill.ats_filler import ATSAssistedFiller
from src.autofill.autofill_logger import AutofillLogger, normalize_field_label_key
from src.autofill.form_mapper import FormFieldMapper
from src.autofill.ground_truth_guard import AutofillGroundTruthGuard
from src.autofill.vendor_schemas import CandidateMasterData, classify_ats_pattern, load_candidate_master_data

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WORKDAY_MAPPINGS_PATH = PROJECT_ROOT / "data" / "profile" / "workday_field_mappings.json"


class UniversalBatchFormFiller:
    """High-speed 2-phase DOM schema extractor, deterministic batch filler, and read-back auditor."""

    def __init__(
        self,
        master_data: CandidateMasterData | None = None,
        mapper: FormFieldMapper | None = None,
    ) -> None:
        self.master_data = master_data or load_candidate_master_data()
        self.mapper = mapper or FormFieldMapper()
        self.ats_helper = ATSAssistedFiller(headless=True)
        self.workday_mappings = self._load_workday_mappings()
        self.logger = AutofillLogger.get_logger()
        self.guard = AutofillGroundTruthGuard()

    def _load_workday_mappings(self) -> dict[str, Any]:
        if WORKDAY_MAPPINGS_PATH.exists():
            try:
                with open(WORKDAY_MAPPINGS_PATH, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    async def extract_form_schema(self, target: Any) -> list[dict[str, Any]]:
        """Extracts all visible interactive fields on the page in a single <100ms JS call.

        Tags each element with `data-agy-id="agy_field_N"` so subsequent batch actions
        can address exact elements without selector collisions.
        """
        js_extractor = """
        () => {
            const results = [];
            let counter = 0;
            for (const existing of document.querySelectorAll('[data-agy-id]')) {
                const m = (existing.getAttribute('data-agy-id') || '').match(/^agy_field_(\\d+)$/);
                if (m) counter = Math.max(counter, parseInt(m[1], 10));
            }

            const isVisible = (el) => {
                if (!el) return false;
                if (el.tagName.toLowerCase() === 'input' && el.type === 'file') return true;
                const visTarget = el.closest('.select__control, .select__container') || el;
                const style = window.getComputedStyle(visTarget);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                    return false;
                }
                const rect = visTarget.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            };

            const cleanText = (txt) => (txt || '').replace(/\\s+/g, ' ').trim();

            const getLabelFor = (el) => {
                // 1. Explicit <label for="id">
                if (el.id) {
                    try {
                        const lbl = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
                        if (lbl && cleanText(lbl.innerText)) return cleanText(lbl.innerText);
                    } catch (e) {}
                }
                // 2. aria-labelledby
                const ariaLblBy = el.getAttribute('aria-labelledby');
                if (ariaLblBy) {
                    const parts = ariaLblBy.split(/\\s+/).map(id => {
                        const node = document.getElementById(id);
                        return node ? cleanText(node.innerText) : '';
                    }).filter(Boolean);
                    if (parts.length > 0) return parts.join(' ');
                }
                // 3. aria-label
                const ariaLbl = el.getAttribute('aria-label');
                if (ariaLbl && cleanText(ariaLbl)) return cleanText(ariaLbl);
                // 4. Enclosing <label>
                const parentLabel = el.closest('label');
                if (parentLabel && cleanText(parentLabel.innerText)) return cleanText(parentLabel.innerText);
                // 5. Fieldset legend (great for radio/checkbox groups)
                const fieldset = el.closest('fieldset');
                if (fieldset) {
                    const legend = fieldset.querySelector('legend');
                    if (legend && cleanText(legend.innerText)) return cleanText(legend.innerText);
                }
                // 6. Nearest field wrapper label (.field, .form-group, .application-question, [data-automation-id], etc.)
                const wrapper = el.closest('.application-question, .field, .form-field, .form-group, [data-qa], [data-automation-id*="formField"], li');
                if (wrapper) {
                    const lblNode = wrapper.querySelector('.application-label, .text, label, .label, [class*="label"]');
                    if (lblNode && cleanText(lblNode.innerText)) return cleanText(lblNode.innerText);
                }
                // 7. Placeholder or name fallback
                return cleanText(el.getAttribute('placeholder') || el.getAttribute('name') || el.id || '');
            };

            const selectors = [
                'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([data-automation-id="beecatcher"])',
                'select',
                'textarea',
                'button[role="combobox"]',
                'div[role="combobox"]'
            ].join(', ');

            const nodes = Array.from(document.querySelectorAll(selectors));
            const seenRadioGroups = new Set();

            for (const el of nodes) {
                if (!isVisible(el)) continue;
                const tag = el.tagName.toLowerCase();
                const type = (el.getAttribute('type') || (tag === 'select' ? 'select' : tag)).toLowerCase();
                const role = (el.getAttribute('role') || '').toLowerCase();

                // Skip inner input if parent div[role="combobox"] is already tracked, or prefer the input itself
                if (tag === 'div' && role === 'combobox' && el.querySelector('input')) {
                    continue;
                }

                // Group radio buttons by name
                if (type === 'radio') {
                    const groupName = el.getAttribute('name') || el.id || '';
                    if (groupName && seenRadioGroups.has(groupName)) continue;
                    if (groupName) seenRadioGroups.add(groupName);
                }

                let agyId = el.getAttribute('data-agy-id');
                if (!agyId) {
                    counter += 1;
                    agyId = `agy_field_${counter}`;
                    el.setAttribute('data-agy-id', agyId);
                }

                let options = [];
                let currentValue = '';
                let isCombobox = (
                    role === 'combobox' ||
                    (el.className && typeof el.className === 'string' && el.className.includes('select__input')) ||
                    el.getAttribute('aria-autocomplete') === 'list' ||
                    el.getAttribute('aria-haspopup') === 'listbox'
                );

                if (tag === 'select') {
                    options = Array.from(el.options || [])
                        .map(o => cleanText(o.text))
                        .filter(t => t && !/^(select|choose|--)/i.test(t));
                    const idx = el.selectedIndex;
                    currentValue = (idx >= 0 && el.options[idx]) ? cleanText(el.options[idx].text) : (el.value || '');
                    if (/^(select|choose|--)/i.test(currentValue)) currentValue = '';
                } else if (type === 'radio' && el.name) {
                    const radios = Array.from(document.querySelectorAll(`input[type="radio"][name="${CSS.escape(el.name)}"]`));
                    options = radios.map((r, rIdx) => {
                        const rId = `${agyId}_opt_${rIdx}`;
                        r.setAttribute('data-agy-radio-id', rId);
                        let rLbl = '';
                        if (r.id) {
                            const l = document.querySelector(`label[for="${CSS.escape(r.id)}"]`);
                            if (l) rLbl = cleanText(l.innerText);
                        }
                        if (!rLbl) {
                            const p = r.closest('label');
                            if (p) rLbl = cleanText(p.innerText);
                        }
                        if (r.checked) currentValue = rLbl || r.value;
                        return rLbl || r.value;
                    }).filter(Boolean);
                } else if (type === 'checkbox') {
                    currentValue = el.checked ? 'true' : '';
                } else if (isCombobox) {
                    const ctrl = el.closest('.select__control, .select__container, .select, .field') || el.parentElement;
                    const singleVal = ctrl ? ctrl.querySelector('.select__single-value, .select__multi-value__label, [class*="singleValue"], [class*="single-value"], [class*="multiValue"], [class*="multi-value"], [data-automation-id*="selectedOption"]') : null;
                    currentValue = singleVal ? cleanText(singleVal.innerText) : (el.value || '');
                } else {
                    currentValue = el.value || '';
                }

                const required = (
                    el.required ||
                    el.getAttribute('aria-required') === 'true' ||
                    getLabelFor(el).includes('*')
                );

                results.push({
                    field_id: agyId,
                    tag: tag,
                    type: isCombobox ? 'combobox' : type,
                    role: role,
                    name: el.getAttribute('name') || '',
                    dom_id: el.id || '',
                    label: getLabelFor(el),
                    required: Boolean(required),
                    current_value: currentValue,
                    options: options.slice(0, 40)
                });
            }
            return results;
        }
        """
        page = getattr(target, "page", target)
        try:
            return await page.evaluate(js_extractor)
        except Exception as e:
            print(f"⚠️ Form schema extraction warning: {e}")
            return []

    def resolve_deterministic_value(self, field: dict[str, Any], resume_pdf_path: str | None = None) -> str | None:
        """Deterministically maps a field descriptor to its grounded candidate value (or None if custom)."""
        ftype = field.get("type", "text")
        label = (field.get("label") or "").strip()
        name = (field.get("name") or "").strip()
        dom_id = (field.get("dom_id") or "").strip()
        options: list[str] = field.get("options") or []
        combined_key = f"{label} {name} {dom_id}".lower()

        if ftype == "file":
            if resume_pdf_path and os.path.exists(resume_pdf_path) and "cover" not in combined_key:
                return os.path.abspath(resume_pdf_path)
            return None

        p = self.master_data.personal
        profiles = self.master_data.profiles
        emp = self.master_data.current_employment
        edu = self.master_data.education_history[0] if self.master_data.education_history else None
        legal = self.master_data.legal_and_compliance
        eeoc = self.master_data.voluntary_eeoc

        # 1. Phone Country / Dial Code vs Country (exclude work-authorization/visa questions that mention 'country')
        if re.search(r"\b(phone\s*country|country\s*code|dial\s*code|calling\s*code)\b", combined_key):
            return p.phone_country_code or "+91"
        if (
            re.search(r"\b(country|country/region|country\s*of\s*residence)\b", combined_key)
            and "phone" not in combined_key
            and not re.search(
                r"\b(right\s*to\s*work|authorized\s*to\s*work|work\s*permit|visa|sponsorship|eligible\s*to\s*work)\b",
                combined_key,
            )
        ):
            return p.country or "India"

        # 2. Personal & Contact
        if re.search(r"\b(first\s*name|given\s*name|legal\s*first)\b", combined_key):
            return p.first_name
        if re.search(r"\b(last\s*name|family\s*name|surname|legal\s*last)\b", combined_key):
            return p.last_name
        if re.search(r"\b(full\s*name|your\s*name|candidate\s*name)\b", combined_key) or dom_id in (
            "name",
            "full_name",
        ):
            return p.full_name
        if re.search(r"\b(email|e-mail)\b", combined_key):
            return p.email
        if re.search(r"\b(phone|mobile|cell|contact\s*number|telephone)\b", combined_key):
            return p.phone
        if re.search(r"\b(city|current\s*city|town)\b", combined_key):
            return p.city
        if re.search(r"\b(state|province|region)\b", combined_key) and "united states" not in combined_key:
            return p.state or "Karnataka"
        if re.search(r"\b(postal|zip|pincode|pin\s*code)\b", combined_key):
            return p.postal_code or "560076"
        if re.search(r"\b(address\s*line\s*1|street\s*address|current\s*location|location)\b", combined_key):
            return p.location if "location" in combined_key else (p.address_line1 or p.city)

        # 3. Profiles / Links
        if "linkedin" in combined_key:
            return profiles.linkedin
        if "github" in combined_key:
            return profiles.github
        if re.search(r"\b(portfolio|website|personal\s*site|blog|url)\b", combined_key):
            return profiles.portfolio

        # 4. Current Employment & Education
        if re.search(
            r"\b(current\s*company|current\s*employer|present\s*employer|company\s*name|organization)\b", combined_key
        ):
            return emp.company
        if re.search(r"\b(current\s*title|job\s*title|designation|current\s*role)\b", combined_key):
            return emp.title
        if edu and re.search(r"\b(school|university|college|institution)\b", combined_key):
            return edu.institution
        if edu and re.search(r"\b(degree|qualification)\b", combined_key):
            return edu.degree
        if edu and re.search(r"\b(discipline|major|field\s*of\s*study|specialization)\b", combined_key):
            return edu.discipline
        if edu and re.search(r"\b(gpa|cgpa|grade|percentage)\b", combined_key):
            return edu.gpa

        # 5. Notice Period (Strictly 60 Days per locked ground truth)
        if re.search(
            r"\b(notice\s*period|days\s*to\s*join|how\s*soon\s*can\s*you\s*join|joining\s*time|availability)\b",
            combined_key,
        ):
            if options:
                for opt in options:
                    if "60" in opt or "2 month" in opt.lower() or "two month" in opt.lower():
                        return opt
            if ftype in ("number", "numeric") or "in days" in combined_key:
                return str(legal.notice_period_days)
            return legal.notice_period_text

        # 6. Compensation (Current = 17 LPA / 17,00,000 INR; Expected = 27 LPA / 27,00,000 INR)
        if re.search(
            r"\b(current\s*ctc|current\s*annual|current\s*salary|present\s*ctc|current\s*compensation)\b", combined_key
        ):
            if "lpa" in combined_key or "lakh" in combined_key:
                return "17" if ftype in ("number", "numeric") else legal.current_ctc_lakhs
            if ftype in ("number", "numeric"):
                return str(legal.current_ctc_numeric)
            return legal.current_ctc
        if re.search(
            r"\b(expected\s*ctc|expected\s*annual|expected\s*salary|desired\s*salary|expected\s*compensation)\b",
            combined_key,
        ):
            if "lpa" in combined_key or "lakh" in combined_key:
                return "27" if ftype in ("number", "numeric") else legal.expected_ctc_lakhs
            if ftype in ("number", "numeric"):
                return str(legal.expected_ctc_numeric)
            return legal.expected_ctc

        # 7. Legal / Authorization / Sponsorship / Previous Employment / Referral
        if re.search(r"\b(at\s*least\s*18|18\s*years\s*of\s*age|legal\s*age)\b", combined_key):
            return "Yes"
        # Check visa/work-permit requirement BEFORE generic 'right to work' to avoid matching 'additional right to work support'
        if re.search(
            r"\b(require\s*sponsorship|visa\s*sponsorship|require\s*visa|work\s*permit|require.*right\s*to\s*work\s*support)\b",
            combined_key,
        ):
            return "No"
        if re.search(
            r"\b(legally\s*authorized|authorized\s*to\s*work|right\s*to\s*work|eligible\s*to\s*work)\b", combined_key
        ):
            return "Yes"
        if re.search(
            r"\b(previously\s*(employed|worked)|currently\s*work\s*for|worked\s*for\s*us\s*before|former\s*employee|ever\s*worked)\b",
            combined_key,
        ):
            return "No"
        if re.search(
            r"\b(government\s*(official|employee)|procurement\s*or\s*contract|conflict\s*of\s*interest|relatives\s*working)\b",
            combined_key,
        ):
            return "No"
        if re.search(r"\b(how\s*did\s*you\s*(hear|learn|find)|source)\b", combined_key) and "other" not in combined_key:
            return legal.how_did_you_hear

        # 8. Voluntary EEOC
        if re.search(r"\b(gender|sex)\b", combined_key):
            return eeoc.gender
        if re.search(r"\b(race|ethnicity)\b", combined_key):
            return eeoc.race_ethnicity
        if re.search(r"\b(hispanic|latino)\b", combined_key):
            return eeoc.hispanic_latino
        if re.search(r"\bveteran\b", combined_key):
            return eeoc.veteran_status
        if re.search(r"\bdisability\b", combined_key):
            return eeoc.disability_status

        # 9. Privacy / Consent Checkboxes
        if ftype == "checkbox" and re.search(
            r"\b(acknowledge|consent|privacy|agree|terms|certify|confirm)\b", combined_key
        ):
            return "true"

        # 10. Delegate to FormFieldMapper for skill experience questions (Java, Selenium, Python, Total YOE)
        mapped = self.mapper.resolve_field_value(label, field_type=ftype)
        if mapped is not None and mapped != "":
            return mapped

        # 11. Closed-Loop Learned Field Mappings (strict exact normalized key match only + ground-truth guard)
        norm_key = normalize_field_label_key(label)
        if norm_key:
            learned = self.logger.get_learned_field_mappings()
            if norm_key in learned:
                cand_val = learned[norm_key].get("value")
                if cand_val is not None:
                    ok_g, _ = self.guard.validate_field_value(label, str(cand_val), control_type=ftype)
                    if ok_g:
                        return str(cand_val)

        return None

    async def execute_field_action(self, target: Any, field: dict[str, Any], value: str) -> bool:
        """Executes a single field action deterministically via its `data-agy-id` attribute."""
        page = getattr(target, "page", target)
        field_id = field["field_id"]
        ftype = field.get("type", "text")
        label = field.get("label") or field.get("name") or ""
        if ftype not in ("file", "checkbox", "radio", "select", "combobox"):
            ok_val, bad_reason = self.guard.validate_field_value(label, str(value), control_type=ftype)
            if not ok_val:
                print(f"🛡️ GroundTruthGuard blocked ungrounded value on '{label[:50]}': {bad_reason}")
                return False
        locator = page.locator(f"[data-agy-id='{field_id}']").first

        try:
            if await locator.count() == 0:
                return False

            if ftype == "file":
                if os.path.exists(value):
                    await locator.set_input_files(value)
                    return True
                return False

            if ftype == "checkbox":
                should_check = str(value).strip().lower() in ("true", "yes", "1", "checked", "check")
                is_chk = await locator.is_checked()
                if should_check != is_chk:
                    try:
                        if should_check:
                            await locator.check(timeout=1000)
                        else:
                            await locator.uncheck(timeout=1000)
                    except Exception:
                        await locator.click(force=True, timeout=1000)
                return True

            if ftype == "radio":
                val_low = str(value).strip().lower()
                name = field.get("name")
                if name:
                    radios = page.locator(f"input[type='radio'][name='{name}']")
                    r_count = await radios.count()
                    for i in range(r_count):
                        r = radios.nth(i)
                        r_lbl = await r.evaluate(
                            """el => {
                                if (el.id) {
                                    const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
                                    if (l) return l.innerText.trim();
                                }
                                const p = el.closest('label');
                                return p ? p.innerText.trim() : (el.value || '');
                            }"""
                        )
                        if r_lbl.lower() == val_low or val_low in r_lbl.lower():
                            try:
                                await r.check(timeout=1000)
                            except Exception:
                                await r.click(force=True, timeout=1000)
                            return True
                return False

            if ftype in ("select", "combobox"):
                return await self.ats_helper._select_react_combobox(
                    page, locator, str(value), prefer_exact=(str(value).lower() in ("no", "yes", "male", "india"))
                )

            # Fast text/number/email/tel/textarea fill with React synthetic event dispatch
            await locator.fill(str(value), timeout=1500)
            await locator.evaluate(
                """el => {
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new Event('blur', { bubbles: true }));
                }"""
            )
            return True
        except Exception as e:
            print(f"⚠️ Batch action warning on {field_id} ({field.get('label')}): {e}")
            return False

    async def verify_filled_controls(
        self, target: Any, expected_actions: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Reads back all live controls on the page to verify zero territory contamination and check required fields."""
        schema = await self.extract_form_schema(target)
        contaminated_fields: list[dict[str, Any]] = []
        empty_required_fields: list[dict[str, Any]] = []

        for f in schema:
            curr = (f.get("current_value") or "").strip()
            lbl = (f.get("label") or "").strip()
            # Check for British Indian Ocean Territory / +246 / Indiana contamination
            if curr and ATSAssistedFiller.is_excluded_territory_option(curr, "India"):
                contaminated_fields.append(
                    {
                        "field_id": f["field_id"],
                        "label": lbl,
                        "contaminated_value": curr,
                    }
                )
            if f.get("required") and not curr and f.get("type") != "file":
                empty_required_fields.append(
                    {
                        "field_id": f["field_id"],
                        "label": lbl,
                        "type": f.get("type"),
                        "options": f.get("options", []),
                    }
                )

        return {
            "verification_passed": len(contaminated_fields) == 0,
            "contaminated_fields": contaminated_fields,
            "empty_required_fields": empty_required_fields,
            "total_visible_fields": len(schema),
        }

    async def inspect_and_autofill_step(
        self,
        target: Any,
        resume_pdf_path: str | None = None,
        overwrite_existing: bool = False,
    ) -> dict[str, Any]:
        """Executes Phase A: extracts schema, batch-fills all known fields, and returns unmapped custom fields + audit."""
        t0 = time.time()
        schema = await self.extract_form_schema(target)
        filled_fields: list[dict[str, Any]] = []
        unmapped_fields: list[dict[str, Any]] = []
        resume_attached = False

        for field in schema:
            curr_val = (field.get("current_value") or "").strip()
            # Auto-repair if existing value is contaminated with British Indian Ocean Territory / +246
            is_contaminated = bool(curr_val and ATSAssistedFiller.is_excluded_territory_option(curr_val, "India"))

            if curr_val and not overwrite_existing and not is_contaminated:
                filled_fields.append(
                    {
                        "field_id": field["field_id"],
                        "label": field.get("label"),
                        "value": curr_val,
                        "status": "already_populated",
                    }
                )
                continue

            resolved = self.resolve_deterministic_value(field, resume_pdf_path=resume_pdf_path)
            if resolved is not None and resolved != "":
                ok = await self.execute_field_action(target, field, resolved)
                if ok:
                    if field.get("type") == "file":
                        resume_attached = True
                    filled_fields.append(
                        {
                            "field_id": field["field_id"],
                            "label": field.get("label"),
                            "value": resolved,
                            "status": "batch_filled",
                        }
                    )
                else:
                    unmapped_fields.append(field)
            else:
                unmapped_fields.append(field)

        audit = await self.verify_filled_controls(target)
        elapsed_ms = round((time.time() - t0) * 1000, 1)

        page = getattr(target, "page", target)
        cur_url = getattr(page, "url", "") or ""
        vendor_name = classify_ats_pattern(cur_url) or "GENERIC"

        self.logger.record_batch_run_metrics(
            url=cur_url,
            vendor=vendor_name,
            total_controls=len(schema),
            auto_filled_count=len(filled_fields),
            unmapped_count=len(unmapped_fields),
            failed_count=len(audit.get("contaminated_fields", [])),
            duration_ms=elapsed_ms,
        )
        if unmapped_fields:
            self.logger.record_unmapped_fields(
                url=cur_url,
                vendor=vendor_name,
                unmapped_fields=unmapped_fields,
            )

        return {
            "elapsed_ms": elapsed_ms,
            "vendor": vendor_name,
            "total_controls": len(schema),
            "coverage_pct": round((len(filled_fields) / max(len(schema), 1)) * 100.0, 1),
            "filled_count": len(filled_fields),
            "resume_attached": resume_attached,
            "filled_fields": filled_fields,
            "unmapped_count": len(unmapped_fields),
            "unmapped_fields": unmapped_fields,
            "verification": audit,
        }

    async def apply_custom_actions(self, target: Any, actions: dict[str, str]) -> dict[str, Any]:
        """Executes Phase B: applies a dictionary of `{field_id_or_label: value}` in a single batch and verifies."""
        t0 = time.time()
        schema = await self.extract_form_schema(target)
        by_id = {f["field_id"]: f for f in schema}
        by_label = {(f.get("label") or "").strip().lower(): f for f in schema if f.get("label")}

        applied: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        learned_count = 0

        for key, val in actions.items():
            field = by_id.get(key) or by_label.get(key.strip().lower())
            if not field:
                # Partial label match fallback
                for lbl_low, f_candidate in by_label.items():
                    if key.strip().lower() in lbl_low:
                        field = f_candidate
                        break
            if not field:
                failed.append({"key": key, "value": val, "reason": "field_not_found"})
                continue

            ok = await self.execute_field_action(target, field, str(val))
            if ok:
                lbl_str = field.get("label") or key
                applied.append({"field_id": field["field_id"], "label": lbl_str, "value": val})
                if lbl_str and field.get("type") != "file":
                    banked = self.logger.record_learned_field_mapping(
                        label=lbl_str,
                        value=str(val),
                        control_type=field.get("type", "text"),
                        source="phase_b_custom",
                    )
                    if banked:
                        learned_count += 1
            else:
                failed.append(
                    {
                        "field_id": field["field_id"],
                        "label": field.get("label"),
                        "value": val,
                        "reason": "action_failed",
                    }
                )

        audit = await self.verify_filled_controls(target)
        return {
            "elapsed_ms": round((time.time() - t0) * 1000, 1),
            "applied_count": len(applied),
            "learned_count": learned_count,
            "applied": applied,
            "failed": failed,
            "verification": audit,
        }
