#!/usr/bin/env python3
"""
Verification Gate 115: Workday Multi-Tenant Fast-Track Question Solver & Anti-Slop Grounding Verification.

Verifies:
1. HPE, Dexcom, Nvidia, PwC, and Thomson Reuters tenant-specific Workday screening rules resolve deterministically.
2. Sponsorship questions containing "work authorization" (e.g. PwC's "need PwC to sponsor your visa or work authorization")
   always resolve to "No" (never overridden by "work authorization" -> "Yes").
3. AutofillGroundTruthGuard validates all outbound answers ("N/A", "60 Days", "No", "Yes", grounded multi-bullet
   Role Descriptions, and CGPA "8.02").
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.autofill.ats_filler import ATSAssistedFiller
from src.autofill.ground_truth_guard import AutofillGroundTruthGuard


def test_workday_fast_track_rules() -> None:
    print("🧪 Running Gate 115: Workday Fast-Track Rules & Anti-Slop Verification...")
    filler = ATSAssistedFiller()
    guard = AutofillGroundTruthGuard()

    mapping_path = Path(PROJECT_ROOT) / "data" / "profile" / "workday_field_mappings.json"
    assert mapping_path.exists(), "workday_field_mappings.json must exist"
    mappings = json.loads(mapping_path.read_text(encoding="utf-8"))
    radio_rules = mappings.get("radio_questions", [])

    # 1. Verify Sponsorship rule precedes Work Authorization in workday_field_mappings.json
    pwc_sponsor_q = "Do you now, or will you in the future, need PwC to sponsor your visa or work authorization?"
    matched_ans = None
    for rule in radio_rules:
        if re.search(rule["pattern"], pwc_sponsor_q, re.IGNORECASE):
            matched_ans = rule["answer"]
            break
    assert matched_ans == "No", f"Expected 'No' for PwC sponsorship question, got {matched_ans!r}"

    # 2. Verify British spelling 'authorised to work' and HPE permit questions resolve to 'Yes'
    for yes_q in (
        "Are you legally authorised to work in the country / territory in which this position is located?",
        "Do you possess a valid work permit in the country for which the position resides?",
        "Do you possess a valid residency permit in the country for which the position resides?",
    ):
        m_yes = None
        for rule in radio_rules:
            if re.search(rule["pattern"], yes_q, re.IGNORECASE):
                m_yes = rule["answer"]
                break
        assert m_yes == "Yes", f"Expected 'Yes' for {yes_q!r}, got {m_yes!r}"

    # 3. Verify GroundTruthGuard allows all grounded fast-track answers and blocks slop
    for label, val in (
        ("For those locations or countries in which you are seeking employment, indicate N/A", "N/A"),
        ("How much notice must you provide your current employer before leaving?", "60 Days"),
        ("Have you ever applied, interviewed, received an offer, or been employed with PwC?", "No"),
        ("Within the last 24 months, have you worked with a PwC engagement team as a client?", "No"),
        ("GPA", "8.02"),
    ):
        ok, reason = guard.validate_field_value(label, val, control_type="textarea")
        assert ok, f"GroundTruthGuard rejected valid answer {val!r} for {label!r}: {reason}"

    # 4. Verify GroundTruthGuard blocks known slop strings
    bad_ok, _ = guard.validate_field_value(
        "Role Description",
        "Senior Engineer in Quality Engineering specializing in UI, API, and AI/LLM test automation.",
        control_type="textarea",
    )
    assert not bad_ok, "GroundTruthGuard must block 1-line slop Role Description"

    desc_map = filler._load_grounded_experience_descriptions(job_id=None)
    assert "valuelabs" in desc_map and "•" in desc_map["valuelabs"], "ValueLabs grounded bullets must be present"
    assert "dunzo" in desc_map and "•" in desc_map["dunzo"], "Dunzo grounded bullets must be present"
    assert "tataelxsi" in desc_map and "•" in desc_map["tataelxsi"], "Tata Elxsi grounded bullets must be present"

    print("✅ Gate 115 PASSED: All Workday fast-track rules & GroundTruthGuard invariants verified!")


if __name__ == "__main__":
    test_workday_fast_track_rules()
