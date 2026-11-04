#!/usr/bin/env python3
"""
Verification Gate 83: Sprint 6 AI QA Filters, USD/EOR Remote Classifier, and Target GCC Registry.

Asserts:
1. is_sdet_title() matches AI QA, LLM Evaluation, and DevSecOps QA roles while rejecting SOC/GRC/Data annotators.
2. evaluate_global_remote_signal() recognizes USD/EUR currency and EOR/B2B signals.
3. has_jurisdiction_restriction() rejects US-only/W-2/clearance locks while allowing India co-listed remote postings.
4. data/config/target_companies.json contains all 19 Tier-1 GCCs and AI orgs with zero duplicate slugs.
5. InterviewRouter routes fresh AI QA and USD/EOR remote roles to TIER_1_SNIPER_APPLY.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ingestion.filters import (
    evaluate_global_remote_signal,
    has_jurisdiction_restriction,
    is_india_or_remote_location,
    is_sdet_title,
)
from src.tailor.referral_generator import InterviewRouter


def test_positive_sdet_titles():
    print("🔍 Step 1: Validating positive title matches for AI QA & DevSecOps...")
    positive_titles = [
        "AI QA Engineer",
        "Senior AI QA Engineer",
        "LLM Evaluation Engineer",
        "Staff GenAI QA Lead",
        "AI Quality Engineer",
        "QA Lead, AI Agents",
        "QA Lead - AI Systems",
        "DevSecOps QA Engineer",
        "Security Automation Engineer",
        "AI Red Team Engineer",
        "Browser Automation Engineer",
        "Senior SDET",
    ]
    for title in positive_titles:
        assert is_sdet_title(title), f"Expected '{title}' to be recognized as SDET/QA role"
    print(f"   ✅ All {len(positive_titles)} positive AI QA / SDET titles matched successfully.")


def test_negative_title_exclusions():
    print("\n🔍 Step 2: Validating negative exclusions for SOC/GRC and manual annotators...")
    negative_titles = [
        "SOC Analyst L2",
        "SOC L1 Analyst",
        "GRC Analyst",
        "Information Security Auditor",
        "IAM Administrator",
        "Penetration Tester",
        "Ethical Hacker",
        "AI Dataset Reviewer",
        "Data Annotator",
        "AI Trainer",
        "Manual Tester",
        "Product Manager",
    ]
    for title in negative_titles:
        assert not is_sdet_title(title), f"Expected '{title}' to be excluded by negative regex"
    print(f"   ✅ All {len(negative_titles)} irrelevant/reset titles successfully rejected.")


def test_global_remote_usd_eor_classification():
    print("\n🔍 Step 3: Validating 3-stage Global Remote USD/EOR classification...")
    # Case A: Global Remote via Deel with USD salary
    job_a = evaluate_global_remote_signal(
        title="Senior AI QA Engineer",
        location="San Francisco, CA (Remote)",
        description="Compensation: $120k - $145k USD. We are async-first and hire globally via Deel or B2B contractor.",
    )
    assert job_a["is_usd_eor_remote"] is True, f"Expected Job A to be USD/EOR remote eligible: {job_a}"
    assert job_a["has_foreign_currency"] is True
    assert job_a["has_eor_signal"] is True
    assert job_a["has_jurisdiction_lock"] is False
    assert job_a["eligible"] is True

    # Case B: Overseas location with NO EOR or global remote signal
    job_b = evaluate_global_remote_signal(
        title="SDET Lead",
        location="Austin, Texas",
        description="Onsite role in Austin. Great benefits and health insurance.",
    )
    assert job_b["is_usd_eor_remote"] is False
    assert job_b["eligible"] is False

    # Case C: Location helper with EOR context override
    assert (
        is_india_or_remote_location(
            "Remote - US",
            text_snippet="We hire global contractors worldwide via Deel or Oyster HR.",
        )
        is True
    )
    print("   ✅ Global remote USD/EOR signals correctly evaluated and parsed.")


def test_jurisdiction_restrictions():
    print("\n🔍 Step 4: Validating jurisdiction and legal restrictions...")
    # Case A: Strict US-only W2
    desc_a = "Role is 100% remote. Must reside in the United States. W-2 only, no C2C."
    assert has_jurisdiction_restriction(desc_a) is True, "Expected US residency W-2 restriction to be detected"

    # Case B: Security clearance & US citizenship
    desc_b = "Active Secret or Top Secret security clearance required. US citizens only."
    assert has_jurisdiction_restriction(desc_b) is True, "Expected clearance/citizenship lock to be detected"

    # Case C: Global role listing both US and India
    desc_c = "We are an async distributed team with engineering hubs in US and Bengaluru, India."
    assert has_jurisdiction_restriction(desc_c) is False, "Expected dual-hub job to be eligible for India"
    print("   ✅ Jurisdiction and legal restriction guards verified.")


def test_target_companies_registry():
    print("\n🔍 Step 5: Validating target_companies.json registry integrity...")
    config_path = os.path.join(PROJECT_ROOT, "data", "config", "target_companies.json")
    with open(config_path, "r", encoding="utf-8") as f:
        comps = json.load(f)

    # 1. Zero duplicate slugs
    slugs = set()
    for c in comps:
        s = c.get("slug")
        assert s, f"Company {c} missing slug"
        assert s not in slugs, f"Duplicate slug found in target_companies.json: '{s}'"
        slugs.add(s)

    # 2. Check all 19 Tier-1 GCCs and AI Orgs
    expected_orgs = [
        "Microsoft IDC",
        "Walmart Global Tech",
        "Goldman Sachs",
        "JPMorgan Chase",
        "Intuit",
        "SAP Labs",
        "Target India",
        "Penguin Solutions",
        "Autodesk",
        "Bosch Global Software",
        "Deel",
        "LangChain",
        "Weights & Biases",
        "Arize AI",
        "PostHog",
        "GitLab",
        "Sprinto HQ",
        "HighLevel",
        "Twilio",
    ]
    for org in expected_orgs:
        match = next((c for c in comps if org.lower() in c.get("name", "").lower()), None)
        assert match is not None, f"Expected target company '{org}' to exist in target_companies.json"
        assert match.get("is_dream_org") is True, f"Expected '{org}' to have is_dream_org: True"

    print(f"   ✅ Registry contains {len(comps)} unique companies with all 19 Tier-1 AI GCCs/Orgs active.")


def test_interview_router_priority_boost():
    print("\n🔍 Step 6: Validating InterviewRouter priority boost for AI QA & USD/EOR roles...")
    now_iso = datetime.now(timezone.utc).isoformat()

    # Case A: Fresh AI Evaluation role (<24h, non-workday) -> TIER_1_SNIPER_APPLY
    payload_ai = {
        "job_id": "test_ai_001",
        "title": "LLM Evaluation Engineer",
        "company_name": "Arize AI",
        "job_url": "https://boards.greenhouse.io/arizeai/jobs/123",
        "posted_at": now_iso,
        "is_dream_org": True,
        "job_details": {
            "title": "LLM Evaluation Engineer",
            "company": "Arize AI",
            "source": "greenhouse",
        },
    }
    strategy_ai = InterviewRouter.classify_job_strategy(payload_ai)
    assert strategy_ai["routing_tier"] == "TIER_1_SNIPER_APPLY", f"Got: {strategy_ai['routing_tier']}"
    assert strategy_ai["allow_immediate_apply"] is True

    # Case B: USD/EOR Remote role (<24h, non-workday) -> TIER_1_SNIPER_APPLY
    payload_usd = {
        "job_id": "test_usd_001",
        "title": "Senior Automation Engineer",
        "company_name": "Deel",
        "job_url": "https://jobs.ashbyhq.com/deel/456",
        "posted_at": now_iso,
        "is_usd_eor_remote": True,
        "is_dream_org": True,
        "job_details": {
            "title": "Senior Automation Engineer",
            "company": "Deel",
            "source": "ashby",
            "is_usd_eor_remote": True,
        },
    }
    strategy_usd = InterviewRouter.classify_job_strategy(payload_usd)
    assert strategy_usd["routing_tier"] == "TIER_1_SNIPER_APPLY", f"Got: {strategy_usd['routing_tier']}"
    assert strategy_usd["allow_immediate_apply"] is True

    # Case C: Workday Dream Org role -> TIER_2_REFERRAL_SLA
    payload_workday = {
        "job_id": "test_wd_001",
        "title": "Senior SDET",
        "company_name": "Target India",
        "job_url": "https://target.wd1.myworkdayjobs.com/targetcareers/job/123",
        "posted_at": now_iso,
        "is_dream_org": True,
        "job_details": {
            "title": "Senior SDET",
            "company": "Target India",
            "source": "workday",
        },
    }
    strategy_wd = InterviewRouter.classify_job_strategy(payload_workday)
    assert strategy_wd["routing_tier"] == "TIER_2_REFERRAL_SLA", f"Got: {strategy_wd['routing_tier']}"
    assert strategy_wd["allow_immediate_apply"] is False
    print("   ✅ InterviewRouter correctly boosts fresh AI QA & USD/EOR roles into TIER_1_SNIPER_APPLY.")


def main():
    print("=" * 70)
    print("  VERIFICATION GATE 83: SPRINT 6 AI QA, USD/EOR & GCC REGISTRY")
    print("=" * 70)

    test_positive_sdet_titles()
    test_negative_title_exclusions()
    test_global_remote_usd_eor_classification()
    test_jurisdiction_restrictions()
    test_target_companies_registry()
    test_interview_router_priority_boost()

    print("\n" + "=" * 70)
    print("  🎉 ALL GATE 83 SPECIFICATIONS VERIFIED: 100% PASS RATE")
    print("=" * 70)


if __name__ == "__main__":
    main()
