#!/usr/bin/env python3
"""
Verification Gate 116: Fortress Top-30 FY-Unlock Prioritization, Strict Domain/Seniority
Pre-Tailoring Filters, Morning Sentinel Resilience, and Gemini GA Fallback Chain.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.filter.job_filter import LinkedInJobFilter
from src.ingestion.filters import is_incompatible_domain_or_seniority, is_sdet_title
from src.notifier.email_reporter import EmailReporter
from src.tailor.llm_provider import GeminiLLMProvider
from src.tailor.referral_generator import InterviewRouter, classify_fortress_company


def test_domain_and_seniority_pre_tailoring_filters() -> None:
    print("1. Testing strict domain & seniority pre-tailoring filters...")
    blocked_titles = [
        "Process Quality Engineer-Chiller",
        "Lead Firmware Test Automation Engineer",
        "Hardware Design/Test Engineer",
        "Linux Kernel Test Engineer - BareMetal and virtualization",
        "Staff/ Senior Staff QA Engineer (C, C++, Python, CXL, PCIE)",
        "Sr Test Engineer - Salesforce CRM",
        "Software Engineer III- ServiceNow QA Analyst",
        "Lead Automation Engineer (C#, Azure)",
        "Senior SDET (.NET / Playwright)",
        "QA Automation Manager",
        "In Business QA Credit Underwriting - Data Analytics - (AVP)",
        "SAP QA Automation Tester",
    ]
    for title in blocked_titles:
        assert not is_sdet_title(title), f"Expected non-core/incompatible title to be rejected: {title}"
        incompat, reason = is_incompatible_domain_or_seniority(title)
        assert incompat and reason, f"Expected pre-tailoring rejection for: {title}"

    # Verify legitimate Senior SDET roles (including at Salesforce/ServiceNow the company!) pass cleanly
    allowed_titles = [
        "Senior SDET - Java & Playwright",
        "Senior Software Development Engineer in Test",
        "Lead QA Automation Engineer",
        "AI Quality Engineer - LLM Evaluation",
        "Member of Technical Staff 3 - SDET Python Automation",
        "Principal Software Engineer in Test",
    ]
    for title in allowed_titles:
        assert is_sdet_title(title), f"Expected legitimate SDET title to pass: {title}"
        incompat, reason = is_incompatible_domain_or_seniority(title)
        assert not incompat, f"Unexpected rejection for '{title}': {reason}"

    # Verify HVAC manufacturing description guard
    jf = LinkedInJobFilter()
    assert jf.max_exp_years == 9, f"Expected max_exp_years=9, got {jf.max_exp_years}"
    ok_chiller, reason_chiller = jf.evaluate_pre_tailoring_eligibility(
        title="Quality Assurance Engineer",
        location="Chennai, India",
        requirements="Bachelor's degree in Mechanical Engineering. 6-8 years in HVAC and chiller manufacturing.",
    )
    assert not ok_chiller and "manufacturing" in (reason_chiller or "").lower(), (
        f"Expected mechanical/HVAC description rejection, got ok={ok_chiller}, reason={reason_chiller}"
    )

    ok_10yoe, reason_10yoe = jf.evaluate_pre_tailoring_eligibility(
        title="Senior SDET",
        location="Bengaluru, India",
        requirements="10+ years of experience in Java and Selenium automation.",
    )
    assert not ok_10yoe and "exceeds max threshold of 9 years" in (reason_10yoe or ""), (
        f"Expected 10+ YOE rejection, got ok={ok_10yoe}, reason={reason_10yoe}"
    )

    ok_fit, _ = jf.evaluate_pre_tailoring_eligibility(
        title="Senior SDET",
        location="Bengaluru, India",
        requirements="5-8 years experience in Java, Python, REST Assured, Playwright, CI/CD.",
    )
    assert ok_fit, "Expected 5-8 YOE Bengaluru Senior SDET role to pass pre-tailoring eligibility"
    print("   ✅ Domain & 9-YOE seniority filters verified.")


def test_fortress_top30_and_fy_unlock_prioritization() -> None:
    print("2. Testing Top-30 Fortress GCC & FY Unlock prioritization...")
    syn = classify_fortress_company("Synopsys")
    assert syn["is_fortress_org"] and syn["fy_unlock_wave"] == "WAVE_1_NOV" and syn["fortress_priority_boost"] == 40

    adobe = classify_fortress_company("Adobe Systems India")
    assert (
        adobe["is_fortress_org"] and adobe["fy_unlock_wave"] == "WAVE_2_DEC" and adobe["fortress_priority_boost"] == 40
    )

    nv = classify_fortress_company("NVIDIA")
    assert nv["is_fortress_org"] and nv["fortress_rank"] == 1 and nv["fy_unlock_wave"] == "WAVE_3_JAN"

    sap = classify_fortress_company("SAP Labs India")
    assert sap["is_fortress_org"] and sap["fortress_rank"] == 7

    # Ensure Publicis Sapient is NOT false-matched as SAP!
    ps = classify_fortress_company("Publicis Sapient")
    assert not ps["is_fortress_org"], f"Publicis Sapient must not match SAP: {ps}"

    # Verify InterviewRouter preserves TIER_2_REFERRAL_SLA while boosting Fortress Top-30 ahead of generic Dream Orgs
    syn_route = InterviewRouter.classify_job_strategy(
        {
            "job_id": "workday_synopsys_12345",
            "source": "workday",
            "is_dream_org": True,
            "job_details": {"company": "Synopsys", "title": "Senior SDET"},
        }
    )
    generic_dream = InterviewRouter.classify_job_strategy(
        {
            "job_id": "workday_generic_99999",
            "source": "workday",
            "is_dream_org": True,
            "job_details": {"company": "Generic Enterprise Corp", "title": "Senior SDET"},
        }
    )
    assert syn_route["routing_tier"] == "TIER_2_REFERRAL_SLA"
    assert syn_route["is_fortress_org"] is True
    assert syn_route["priority_boost"] > generic_dream["priority_boost"], (
        f"Expected Synopsys ({syn_route['priority_boost']}) > generic dream ({generic_dream['priority_boost']})"
    )

    # Verify EmailReporter sorts Fortress Top-30 ahead of standard roles and renders badge
    html = EmailReporter().build_report_html(
        staged_jobs=[
            {
                "job_id": "j1",
                "source": "linkedin",
                "is_dream_org": False,
                "job_details": {"company": "Random Corp", "title": "QA Engineer", "location": "Bengaluru"},
            },
            {
                "job_id": "j2",
                "source": "workday",
                "is_dream_org": True,
                "job_details": {"company": "Adobe", "title": "Senior SDET", "location": "Bengaluru"},
            },
        ],
        hiring_posts=[],
        run_id="gate116_test",
    )
    assert html.index("Adobe") < html.index("Random Corp"), "Expected Fortress Org (Adobe) to sort above Random Corp"
    assert "FORTRESS" in html
    print("   ✅ Top-30 Fortress & FY Unlock Wave prioritization verified.")


def test_gemini_ga_fallback_and_timeout_resilience() -> None:
    print("3. Testing Gemini 2026 Flash-Lite fallback chain, 90s cooldown, and hard wall-clock timeout...")
    prov = GeminiLLMProvider(api_key="", model_name="models/gemini-flash-lite-latest")
    models = prov._build_models_to_try()
    assert models[0] == "models/gemini-flash-lite-latest"
    assert "models/gemini-3.1-flash-lite" in models and "models/gemini-3.5-flash-lite" in models
    assert "models/gemini-2.5-flash" not in models and "gemini-3.8-flash" not in models
    assert prov.TRANSIENT_COOLDOWN_SECONDS == 90.0
    assert prov.CALL_TIMEOUT_SECONDS == 25.0

    # Verify hard timeout aborts hung socket call cleanly
    prov.CALL_TIMEOUT_SECONDS = 0.2
    prov.client = MagicMock()

    def _slow_call(**kwargs):
        time.sleep(1.5)
        return MagicMock()

    prov.client.models.generate_content.side_effect = _slow_call
    t0 = time.time()
    try:
        prov._call_generate_content_with_timeout("models/gemini-flash-lite-latest", "hi", {})
        raise AssertionError("Expected TimeoutError on hung Gemini call")
    except TimeoutError as exc:
        elapsed = time.time() - t0
        assert elapsed < 1.0, f"Expected fast timeout abort (<1.0s), took {elapsed:.2f}s"
        assert "timed out" in str(exc).lower()
    print("   ✅ Gemini Flash-Lite fallback chain & hard timeout guard verified.")


def test_morning_sentinel_and_peak_naukri_schedule() -> None:
    print("4. Testing run_daily_prod.sh morning sentinel and peak Naukri launchd schedule...")
    prod_sh = (Path(PROJECT_ROOT) / "scripts" / "run_daily_prod.sh").read_text(encoding="utf-8")
    assert "MORNING_SENTINEL=" in prod_sh
    assert 'if [[ -f "${MORNING_SENTINEL}" ]]; then' in prod_sh
    assert "main.py daily --skip-tests" in prod_sh
    assert "-ge 10" not in prod_sh, "Legacy wake-after-10AM skip bug (-ge 10) must be removed"

    plist = (Path(PROJECT_ROOT) / "scripts" / "com.linkedin.automator.daily.plist").read_text(encoding="utf-8")
    assert "<integer>9</integer>" in plist and "<integer>15</integer>" in plist, (
        "Expected 09:15 IST weekday peak Naukri Resdex pulse in launchd plist"
    )
    print("   ✅ Morning sentinel & 09:15 IST launchd schedule verified.")


if __name__ == "__main__":
    print("=" * 72)
    print("  GATE 116: FORTRESS PRIORITY, DOMAIN FILTERS & PIPELINE RESILIENCE")
    print("=" * 72)
    test_domain_and_seniority_pre_tailoring_filters()
    test_fortress_top30_and_fy_unlock_prioritization()
    test_gemini_ga_fallback_and_timeout_resilience()
    test_morning_sentinel_and_peak_naukri_schedule()
    print("=" * 72)
    print("🎉 ALL VERIFICATION GATE 116 CHECKS PASSED (100% SUCCESS)!")
    print("=" * 72)
