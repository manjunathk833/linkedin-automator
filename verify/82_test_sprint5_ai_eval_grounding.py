#!/usr/bin/env python3
"""
Verification Gate 82: Sprint 5 AI Evaluation & Red-Teaming Knowledge Grounding.

Asserts:
1. allowed_tools_whitelist.json contains deepeval, ragas, promptfoo, owasp llm, garak, and cdp.
2. FabricationDetector permits a Technical Projects bullet containing
   "DeepEval, RAGAS, and Promptfoo for OWASP LLM red-teaming".
3. FabricationDetector rejects/strips "DeepEval" and "Promptfoo" when passed inside
   a Tata Elxsi, Dunzo, or Value Labs employer bullet.
4. master_knowledge_bank.json contains newly grounded STAR achievements with zero
   cross-employer contamination.
"""

from __future__ import annotations

import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.resume_store.models import ResumeProfile
from src.tailor.fabrication_detector import FabricationDetector


def test_allowed_tools_whitelist():
    print("🔍 Step 1: Validating allowed_tools_whitelist.json...")
    whitelist_path = os.path.join(PROJECT_ROOT, "data", "profile", "allowed_tools_whitelist.json")
    assert os.path.exists(whitelist_path), f"Whitelist not found: {whitelist_path}"

    with open(whitelist_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    allowed = {t.lower() for t in data.get("allowed_tools", [])}
    required_tools = ["deepeval", "ragas", "promptfoo", "owasp llm", "garak", "cdp", "langsmith", "fastapi"]
    for t in required_tools:
        assert t in allowed, f"Required tool '{t}' missing from allowed_tools_whitelist.json"
    print("   ✅ All required AI Evaluation & CDP tools present in whitelist.")


def test_fabrication_detector_project_scope():
    print("\n🔍 Step 2: Testing FabricationDetector with Technical Projects bullets...")
    profile_path = os.path.join(PROJECT_ROOT, "data", "resume_profile.json")
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
    profile = ResumeProfile(**profile_data)

    bank_path = os.path.join(PROJECT_ROOT, "data", "master_knowledge_bank.json")
    bank_data = {}
    if os.path.exists(bank_path):
        with open(bank_path, "r", encoding="utf-8") as f:
            bank_data = json.load(f)

    detector = FabricationDetector(profile=profile, master_knowledge_bank=bank_data)

    project_bullet = (
        "AI Evaluation Pipeline [DeepEval · RAGAS · Promptfoo · OWASP LLM]: Architected automated "
        "LLM-as-a-Judge test harness measuring Faithfulness and Context Recall."
    )
    # 2A. Bullet check should be valid (not flagged as hallucinated tool)
    check_res = detector.check_bullet(project_bullet)
    assert check_res["is_valid"], f"Expected project bullet to be valid, got: {check_res['fabricated_tools']}"

    # 2B. Company contamination check under Technical Projects should be clean
    contam_proj = detector.check_company_contamination("Technical Projects", project_bullet)
    assert contam_proj["is_clean"], (
        f"Expected Technical Projects bullet to be clean, got violations: {contam_proj['violating_companies']}"
    )
    print("   ✅ Technical Projects bullet with DeepEval & RAGAS successfully permitted.")


def test_fabrication_detector_employer_isolation():
    print("\n🔍 Step 3: Testing employer boundary isolation (rejecting AI eval tools in past employment)...")
    profile_path = os.path.join(PROJECT_ROOT, "data", "resume_profile.json")
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
    profile = ResumeProfile(**profile_data)
    detector = FabricationDetector(profile=profile)

    fake_dunzo_bullet = (
        "Merchant Automation [Dunzo · DeepEval · Promptfoo]: Built automated LLM evaluation for merchant onboarding."
    )
    res_dunzo = detector.check_company_contamination("Dunzo", fake_dunzo_bullet)
    assert not res_dunzo["is_clean"], "Expected Dunzo bullet with DeepEval/Promptfoo to be flagged as contamination"
    print(f"   ✅ Dunzo contamination correctly caught: {res_dunzo['violating_companies']}")

    fake_elxsi_bullet = (
        "OTT Quality [Tata Elxsi · RAGAS · OWASP LLM]: Conducted adversarial red-teaming on media chatbot."
    )
    res_elxsi = detector.check_company_contamination("Tata Elxsi", fake_elxsi_bullet)
    assert not res_elxsi["is_clean"], "Expected Tata Elxsi bullet with RAGAS/OWASP LLM to be flagged as contamination"
    print(f"   ✅ Tata Elxsi contamination correctly caught: {res_elxsi['violating_companies']}")

    fake_vl_bullet = "Mosaic Core [Value Labs · DeepEval · Garak]: Integrated LLM red-teaming into airline framework."
    res_vl = detector.check_company_contamination("Value Labs", fake_vl_bullet)
    assert not res_vl["is_clean"], "Expected Value Labs bullet with DeepEval/Garak to be flagged as contamination"
    print(f"   ✅ Value Labs contamination correctly caught: {res_vl['violating_companies']}")


def test_master_knowledge_bank_integrity():
    print("\n🔍 Step 4: Testing master_knowledge_bank.json schema and zero cross-employer contamination...")
    bank_path = os.path.join(PROJECT_ROOT, "data", "master_knowledge_bank.json")
    assert os.path.exists(bank_path), f"Knowledge bank missing: {bank_path}"

    with open(bank_path, "r", encoding="utf-8") as f:
        bank_data = json.load(f)

    vault = bank_data.get("master_achievements_vault", [])
    assert len(vault) > 0, "Vault is empty"

    # Verify new AI eval achievements exist
    eval_achievements = [
        item
        for item in vault
        if any(tool.lower() in ["deepeval", "ragas", "promptfoo", "garak", "cdp"] for tool in item.get("tools", []))
        or "deepeval" in item.get("star_achievement", "").lower()
        or "promptfoo" in item.get("star_achievement", "").lower()
    ]
    assert len(eval_achievements) > 0, "No AI evaluation achievements found in master_knowledge_bank.json"

    # Verify zero cross-employer contamination in vault
    forbidden_employers = {"Value Labs", "Dunzo", "Tata Elxsi"}
    for item in eval_achievements:
        comp = item.get("company", "")
        assert comp not in forbidden_employers, (
            f"Contamination detected! AI evaluation achievement assigned to historical employer '{comp}': "
            f"{item.get('star_achievement', '')[:80]}"
        )
    print(
        f"   ✅ Master knowledge bank verified: {len(eval_achievements)} AI evaluation achievements cleanly isolated."
    )


if __name__ == "__main__":
    print("=" * 60)
    print("  GATE 82: SPRINT 5 AI EVALUATION & GROUNDING AUDIT")
    print("=" * 60)
    test_allowed_tools_whitelist()
    test_fabrication_detector_project_scope()
    test_fabrication_detector_employer_isolation()
    test_master_knowledge_bank_integrity()
    print("\n🎉 GATE 82 PASSED: 100% SUCCESS — AI EVALUATION GROUNDING VERIFIED!")
