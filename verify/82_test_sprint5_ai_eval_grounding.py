#!/usr/bin/env python3
"""
Verification Gate 82: Sprint 5 AI Evaluation & Red-Teaming Knowledge Grounding.

Evidence-gated model (master resume = single source of truth). AI-evaluation tools
(DeepEval, RAGAS, Promptfoo, Garak, OWASP LLM, LangSmith...) are on the candidate's
learning roadmap until a built project is added to the master resume.

Asserts:
1. allowed_tools_whitelist.json lists the AI-eval tools under learning_roadmap and NOT in allowed_tools.
2. FabricationDetector flags a project bullet claiming DeepEval/RAGAS/Promptfoo (not yet built).
3. FabricationDetector rejects AI-eval tools inside Tata Elxsi, Dunzo, or Value Labs employer bullets.
4. master_knowledge_bank.json contains zero AI-eval roadmap claims.
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

AI_EVAL_TOOLS = ["deepeval", "ragas", "promptfoo", "owasp llm", "garak", "langsmith"]


def test_allowed_tools_whitelist():
    print("🔍 Step 1: Validating allowed_tools_whitelist.json (AI-eval tools on learning roadmap)...")
    whitelist_path = os.path.join(PROJECT_ROOT, "data", "profile", "allowed_tools_whitelist.json")
    assert os.path.exists(whitelist_path), f"Whitelist not found: {whitelist_path}"

    with open(whitelist_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    allowed = {t.lower() for t in data.get("allowed_tools", [])}
    roadmap = {t.lower() for t in data.get("learning_roadmap", [])}
    for t in AI_EVAL_TOOLS:
        if t in data.get("tool_evidence", {}):
            continue  # graduated via the master resume — allowed by design
        assert t in roadmap, f"AI-eval tool '{t}' must be listed in learning_roadmap until it graduates"
        assert t not in allowed, f"AI-eval tool '{t}' must NOT be in allowed_tools without master-resume evidence"
    print("   ✅ AI-eval tools are blocked on the learning roadmap (no master-resume evidence yet).")


def test_fabrication_detector_project_scope():
    print("\n🔍 Step 2: Testing FabricationDetector flags unbuilt AI-eval project claims...")
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
    check_res = detector.check_bullet(project_bullet)
    if any(t in detector.allowed_tools for t in ("deepeval", "ragas", "promptfoo")):
        print("   ℹ️ AI-eval tools graduated via master resume; skipping roadmap block assertion.")
        return
    assert not check_res["is_valid"], "Unbuilt AI-eval project bullet must be flagged until it graduates"
    print(f"   ✅ Unbuilt AI-eval claims flagged: {check_res['fabricated_tools']}")


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

    # Verify zero AI-eval roadmap claims anywhere in the vault
    from src.resume_store.master_resume import tool_mentioned

    leaked = [
        item.get("star_achievement", "")[:80]
        for item in vault
        if any(tool_mentioned(t, item.get("star_achievement", "")) for t in AI_EVAL_TOOLS)
        or any(tool.lower() in AI_EVAL_TOOLS for tool in item.get("tools", []))
    ]
    assert not leaked, f"AI-eval roadmap claims found in knowledge bank: {leaked}"
    print(f"   ✅ Master knowledge bank verified: {len(vault)} entries, zero AI-eval roadmap claims.")


if __name__ == "__main__":
    print("=" * 60)
    print("  GATE 82: SPRINT 5 AI EVALUATION & GROUNDING AUDIT")
    print("=" * 60)
    test_allowed_tools_whitelist()
    test_fabrication_detector_project_scope()
    test_fabrication_detector_employer_isolation()
    test_master_knowledge_bank_integrity()
    print("\n🎉 GATE 82 PASSED: 100% SUCCESS — AI EVALUATION GROUNDING VERIFIED!")
