#!/usr/bin/env python3
"""
Verification Gate 115: Anti-Slop Autofill Grounding, Master-Resume Parity & Learned-Mapping Quarantine.

Enforces zero-fabrication and anti-slop guardrails across the entire ATS autofill pipeline:
1. Static source audit across `src/autofill/` banning hardcoded fake GPA ("8.5"), fake DOB ("1996"),
   and generic 1-line slop role descriptions.
2. `AutofillGroundTruthGuard` unit checks:
   - Blocks `learning_roadmap` (DeepEval, RAGAS, Promptfoo, Garak, TypeScript, WireMock, Pact) and
     `disallowed_hallucinations` (Cypress, Golang, Rust, Terraform, Ansible) in outbound text & learned mappings.
   - Blocks cross-type corruption (non-URL text in LinkedIn/GitHub/Portfolio fields; city names in CTC/salary fields).
   - Blocks ambiguous/placeholder/UUID keys ("yes", "type response", "start typing...", "month", "year",
     "please specify", `cards[...][fieldN]`) from entering `learned_field_mappings.json`.
   - Blocks cross-company resume PDF attachments (`Manjunath_HK_TransUnion_...pdf` on `Vialto Partners`).
3. `master_sync.run_sync()` -> `candidate_master_data.json` parity with `Manjunath_HK_Master_Resume.json`
   (8.02 CGPA, exact YYYY-MM dates, Remote location on ValueLabs, multi-bullet role descriptions).
4. Live audit of `data/logs/learned_field_mappings.json` asserting 0 contaminated entries on disk.
5. Playwright headless DOM test verifying Workday `My Experience` multi-panel grounding, 8.02 CGPA,
   and zero guessing on unset DOB or non-Bengaluru relocation questions.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_static_source_zero_hardcoded_slop() -> None:
    autofill_dir = PROJECT_ROOT / "src" / "autofill"
    forbidden_literals = [
        "Senior Engineer in Quality Engineering specializing in UI, API, and AI/LLM test automation.",
        "(\"input[id*='education'][id*='--gradeAverage']:visible\", \"8.5\")",
        'dob_y.fill("1996")',
        'await dob_y.fill("1996")',
    ]
    violations: list[str] = []
    for py_file in sorted(autofill_dir.glob("*.py")):
        src = py_file.read_text(encoding="utf-8")
        for bad in forbidden_literals:
            if bad in src:
                violations.append(f"{py_file.name}: contains forbidden literal {bad!r}")
    assert not violations, "Hardcoded slop literals detected in src/autofill:\n" + "\n".join(violations)
    print("✅ [1/5] Static source scan passed: 0 hardcoded slop literals in src/autofill/")


def test_ground_truth_guard_rules() -> None:
    from src.autofill.ground_truth_guard import AutofillGroundTruthGuard

    guard = AutofillGroundTruthGuard()

    # A. Roadmap & hallucination tools blocked
    ok_rm, reason_rm = guard.validate_field_value(
        "What AI tools have you used?",
        "Built harnesses with DeepEval, RAGAS, Promptfoo, and Garak.",
        control_type="textarea",
    )
    assert not ok_rm and "roadmap" in reason_rm.lower(), f"Expected roadmap block, got {(ok_rm, reason_rm)}"

    ok_hal, reason_hal = guard.validate_field_value(
        "Automation tools",
        "Built UI tests using Cypress and Terraform.",
        control_type="text",
    )
    assert not ok_hal, f"Expected disallowed tool block, got {(ok_hal, reason_hal)}"

    # Grounded tools allowed
    ok_valid, reason_valid = guard.validate_field_value(
        "What AI tools have you used?",
        "Used GitHub Copilot, Gemini, Claude, and Ollama with Python and REST Assured.",
        control_type="textarea",
    )
    assert ok_valid, f"Expected grounded answer to pass, got {reason_valid}"

    # B. Cross-type corruption blocked
    ok_url, _ = guard.validate_field_value(
        "LinkedIn Profile (Strongly Preferred)",
        "No - I do not consent to receiving text messages",
        control_type="text",
    )
    assert not ok_url, "Expected non-URL value in LinkedIn field to be blocked"

    ok_url_good, _ = guard.validate_field_value(
        "LinkedIn Profile (Strongly Preferred)",
        "https://www.linkedin.com/in/manjunath-h-k/",
        control_type="text",
    )
    assert ok_url_good, "Expected canonical LinkedIn URL to pass"

    ok_ctc, _ = guard.validate_field_value(
        "What is your target base and bonus compensation for the role?",
        "Bengaluru",
        control_type="text",
    )
    assert not ok_ctc, "Expected city name in compensation field to be blocked"

    # C. Ambiguous / placeholder / Lever UUID learned-mapping keys blocked
    for bad_label in [
        "Yes",
        "Month",
        "Year",
        "Type your response",
        "Start typing...",
        "Please specify",
        "Less than 6 months",
        "cards[df48d25e-d077-4e41-85ed-a025a8462c17][field4]",
    ]:
        ok_learn, _ = guard.validate_learned_mapping(bad_label, "Yes", control_type="text")
        assert not ok_learn, f"Expected ambiguous/UUID learned label {bad_label!r} to be rejected"

    # D. Cross-company resume PDF attachment guard
    ok_wrong_pdf, _ = guard.validate_resume_for_company(
        "/tmp/Manjunath_HK_TransUnion_Global_Capability_19042838_Resume.pdf",
        company="Vialto Partners",
    )
    assert not ok_wrong_pdf, "Expected TransUnion PDF to be rejected for Vialto Partners"

    ok_right_pdf, _ = guard.validate_resume_for_company(
        "/tmp/Manjunath_HK_Vialto_Partners_4397785983_Resume.pdf",
        company="Vialto Partners",
    )
    assert ok_right_pdf, "Expected Vialto Partners PDF to pass for Vialto Partners"

    ok_master_pdf, _ = guard.validate_resume_for_company(
        str(PROJECT_ROOT / "data" / "profile" / "Manjunath_HK_Resume.pdf"),
        company="HP Inc India",
    )
    assert ok_master_pdf, "Expected canonical Master Resume PDF to pass for any company"
    print("✅ [2/5] AutofillGroundTruthGuard unit checks passed (roadmap, cross-type, UUID keys, PDF guard)")


def test_master_resume_to_candidate_master_data_parity() -> None:
    master_path = PROJECT_ROOT / "Manjunath_HK_Master_Resume.json"
    cmd_path = PROJECT_ROOT / "data" / "profile" / "candidate_master_data.json"
    if not master_path.exists():
        print("ℹ️  Skipping live Master Resume parity check (synthetic CI environment)")
        return

    cmd_data = json.loads(cmd_path.read_text(encoding="utf-8"))
    edu = cmd_data["education_history"][0]
    assert "8.02" in edu["gpa"], f"Expected 8.02 CGPA in candidate_master_data.json, got {edu['gpa']!r}"
    assert edu.get("gpa_numeric") == "8.02", f"Expected gpa_numeric=='8.02', got {edu.get('gpa_numeric')!r}"

    exp = cmd_data["experience_history"]
    assert len(exp) >= 3, f"Expected >=3 experience entries, got {len(exp)}"
    vl = exp[0]
    assert "value" in vl["company"].lower()
    assert vl["is_current"] is True
    assert vl["location"] == "Remote", f"Expected ValueLabs location 'Remote', got {vl['location']!r}"
    assert vl.get("start_month_num") == "06" and vl.get("start_year") == "2023"
    assert len(vl.get("bullets", [])) >= 5, f"Expected >=5 grounded ValueLabs bullets, got {len(vl.get('bullets', []))}"
    assert "•" in vl["summary"] and len(vl["summary"]) > 300, "Expected multi-bullet summary on ValueLabs"
    print("✅ [3/5] candidate_master_data.json <-> Manjunath_HK_Master_Resume.json parity verified")


def test_learned_field_mappings_on_disk_clean() -> None:
    from src.autofill.ground_truth_guard import AutofillGroundTruthGuard

    guard = AutofillGroundTruthGuard()
    learned_path = PROJECT_ROOT / "data" / "logs" / "learned_field_mappings.json"
    if not learned_path.exists():
        print("✅ [4/5] No learned_field_mappings.json present (clean)")
        return

    payload = json.loads(learned_path.read_text(encoding="utf-8"))
    mappings = payload.get("mappings", {})
    bad_entries: list[str] = []
    for k, entry in mappings.items():
        lbl = entry.get("label") or k
        val = str(entry.get("value") or "")
        ctype = entry.get("control_type") or "text"
        ok, reason = guard.validate_learned_mapping(lbl, val, control_type=ctype)
        if not ok:
            bad_entries.append(f"{k!r} -> {val[:60]!r} ({reason})")

    assert not bad_entries, "Contaminated entries found in learned_field_mappings.json:\n" + "\n".join(bad_entries)
    print(f"✅ [4/5] learned_field_mappings.json audit passed: all {len(mappings)} entries verified clean")


async def _run_workday_dom_grounding_check() -> None:
    from playwright.async_api import async_playwright

    from src.autofill.ats_filler import ATSAssistedFiller

    html = """
    <!DOCTYPE html>
    <html><body>
      <h2>My Experience</h2>
      <div data-automation-id="workExperienceSection">
        <div id="panel-1">
          <input id="workExperience-1--jobTitle" name="jobTitle" value="" />
          <input id="workExperience-1--companyName" name="companyName" value="" />
          <input id="workExperience-1--location" name="location" value="" />
          <input type="checkbox" id="workExperience-1--currentlyWorkHere" name="currentlyWorkHere" />
          <input id="workExperience-1--startDate-dateSectionMonth-input" value="" />
          <input id="workExperience-1--startDate-dateSectionYear-input" value="" />
          <input id="workExperience-1--endDate-dateSectionMonth-input" value="" />
          <input id="workExperience-1--endDate-dateSectionYear-input" value="" />
          <textarea id="workExperience-1--roleDescription"></textarea>
        </div>
        <div id="panel-2">
          <input id="workExperience-2--jobTitle" name="jobTitle" value="" />
          <input id="workExperience-2--companyName" name="companyName" value="" />
          <input id="workExperience-2--location" name="location" value="" />
          <input type="checkbox" id="workExperience-2--currentlyWorkHere" name="currentlyWorkHere" />
          <input id="workExperience-2--startDate-dateSectionMonth-input" value="" />
          <input id="workExperience-2--startDate-dateSectionYear-input" value="" />
          <input id="workExperience-2--endDate-dateSectionMonth-input" value="" />
          <input id="workExperience-2--endDate-dateSectionYear-input" value="" />
          <textarea id="workExperience-2--roleDescription"></textarea>
        </div>
      </div>
      <div data-automation-id="educationSection">
        <input id="education-1--schoolName" name="schoolName" value="" />
        <input id="education-1--fieldOfStudy" value="" />
        <input id="education-1--gradeAverage" name="gradeAverage" value="" />
        <input id="education-1--firstYearAttended-dateSectionYear-input" value="" />
        <input id="education-1--lastYearAttended-dateSectionYear-input" value="" />
      </div>
      <input id="dateOfBirth-dateSectionYear-input" value="" />
    </body></html>
    """
    filler = ATSAssistedFiller(headless=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html)

        await filler._populate_workday_experience_and_education(page, job_id=None)

        co1 = await page.locator("#workExperience-1--companyName").input_value()
        loc1 = await page.locator("#workExperience-1--location").input_value()
        cur1 = await page.locator("#workExperience-1--currentlyWorkHere").is_checked()
        end_y1 = await page.locator("#workExperience-1--endDate-dateSectionYear-input").input_value()
        desc1 = await page.locator("#workExperience-1--roleDescription").input_value()

        co2 = await page.locator("#workExperience-2--companyName").input_value()
        desc2 = await page.locator("#workExperience-2--roleDescription").input_value()
        end_y2 = await page.locator("#workExperience-2--endDate-dateSectionYear-input").input_value()

        gpa = await page.locator("#education-1--gradeAverage").input_value()
        fos = await page.locator("#education-1--fieldOfStudy").input_value()
        dob_y = await page.locator("#dateOfBirth-dateSectionYear-input").input_value()

        await browser.close()

    assert "value" in co1.lower(), f"Expected ValueLabs in panel 1, got {co1!r}"
    assert cur1 is True, "Expected currentlyWorkHere=True on ValueLabs"
    assert end_y1 == "", f"Expected empty endDate on current role ValueLabs, got {end_y1!r}"
    assert "•" in desc1 and len(desc1) > 120, f"Expected multi-bullet grounded description on panel 1, got {desc1!r}"
    assert "Senior Engineer in Quality Engineering specializing in UI" not in desc1

    if len(filler.master_data.experience_history) >= 2:
        assert "dunzo" in co2.lower(), f"Expected Dunzo in panel 2, got {co2!r}"
        assert end_y2 == "2023", f"Expected Dunzo end year 2023, got {end_y2!r}"
        assert len(desc2) > 80, f"Expected grounded Dunzo description, got {desc2!r}"

    if os.path.exists(PROJECT_ROOT / "Manjunath_HK_Master_Resume.json"):
        assert loc1 == "Remote", f"Expected Remote for ValueLabs, got {loc1!r}"
        assert gpa == "8.02", f"Expected 8.02 GPA, got {gpa!r}"
        assert "Computer Science" in fos, f"Expected Computer Science field of study, got {fos!r}"
    assert dob_y == "", f"Expected unset DOB to remain empty, got {dob_y!r}"
    print("✅ [5/5] Playwright Workday My Experience multi-panel grounding & zero-DOB-fabrication check passed")


def main() -> None:
    test_static_source_zero_hardcoded_slop()
    test_ground_truth_guard_rules()
    test_master_resume_to_candidate_master_data_parity()
    test_learned_field_mappings_on_disk_clean()
    asyncio.run(_run_workday_dom_grounding_check())
    print("\n🎉 Gate 115 PASSED: Zero autofill slop, 100% Master-Resume grounding verified.")


if __name__ == "__main__":
    main()
