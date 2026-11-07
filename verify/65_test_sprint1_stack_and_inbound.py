#!/usr/bin/env python3
"""
Verification Gate 65: Sprint 1 Stack Realignment, Whitelist Expansion & Inbound Traps
=====================================================================================
Validates (evidence-gated model — the master resume is the single source of truth):
1. Tool registry: evidenced tools allowed, learning-roadmap and never-used tools blocked.
2. Anti-fabrication detector: evidenced tools accepted, roadmap/unverified tools flagged.
3. Master Knowledge Bank: zero roadmap-tool claims.
4. Candidate Resume Profile: Pydantic validation and skills matrix integrity.
5. Naukri Resdex visibility engine: CLI and logging contract.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

# Ensure repository root is on PYTHONPATH
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.resume_store.models import ResumeProfile
from src.tailor.fabrication_detector import FabricationDetector


def _load_registry() -> dict:
    whitelist_path = os.path.join(PROJECT_ROOT, "data", "profile", "allowed_tools_whitelist.json")
    with open(whitelist_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_whitelist_expansion_and_boundaries():
    print("--- 1. Testing Evidence-Gated Tool Registry & Boundary Integrity ---")
    data = _load_registry()

    allowed = {t.lower() for t in data.get("allowed_tools", [])}
    disallowed = {t.lower() for t in data.get("disallowed_hallucinations", [])}
    roadmap = {t.lower() for t in data.get("learning_roadmap", [])}
    evidence = data.get("tool_evidence", {})

    # Every allowed tool that is a real tool (not a generic practice) must carry master-resume evidence.
    for tool, boundaries in evidence.items():
        assert boundaries, f"Tool '{tool}' has an empty evidence list"
        assert tool in allowed, f"Evidenced tool '{tool}' must be present in allowed_tools"
    print(f"  ✓ {len(evidence)} evidenced tools all present in allowed_tools")

    # Learning-roadmap tools are blocked everywhere: never allowed, never evidenced.
    assert roadmap, "learning_roadmap must be defined in allowed_tools_whitelist.json"
    for tool in roadmap:
        assert tool not in allowed, f"Roadmap tool '{tool}' must NOT be in allowed_tools until it graduates"
        assert tool not in evidence, f"Roadmap tool '{tool}' must NOT have master-resume evidence"
    print(f"  ✓ Roadmap tools blocked: {sorted(roadmap)}")

    expected_blocked = ["cypress", "golang", "go", "rust", "terraform", "ansible"]
    for tool in expected_blocked:
        assert tool in disallowed, f"Unverified tool '{tool}' must remain in disallowed_hallucinations"
        assert tool not in allowed, f"Unverified tool '{tool}' must not be allowed"
    print("  ✓ Never-used tools remain in disallowed_hallucinations")

    print("✅ Evidence-gated tool registry verified.\n")


def test_fabrication_detector_grounding():
    print("--- 2. Testing FabricationDetector Grounding & Anti-Hallucination ---")
    profile_path = os.path.join(PROJECT_ROOT, "data", "resume_profile.json")
    bank_path = os.path.join(PROJECT_ROOT, "data", "master_knowledge_bank.json")

    if not os.path.exists(profile_path) or not os.path.exists(bank_path):
        from verify.synthetic_mock_fixtures import deploy_mock_fixtures_if_missing

        deploy_mock_fixtures_if_missing()

    with open(profile_path, "r", encoding="utf-8") as f:
        profile = ResumeProfile.model_validate_json(f.read())
    with open(bank_path, "r", encoding="utf-8") as f:
        bank = json.load(f)

    detector = FabricationDetector(profile=profile, master_knowledge_bank=bank)
    roadmap = sorted(detector.learning_roadmap)

    # Bullets with evidenced tools must pass the fabrication check
    evidenced = [
        t for t in ("docker", "kubernetes", "kafka", "selenium", "rest assured") if t in detector.allowed_tools
    ]
    for tool in evidenced:
        bullet = f"Ran regression suites with {tool} across microservices in CI/CD."
        res = detector.check_bullet(bullet)
        assert res["is_valid"], f"Evidenced tool bullet unexpectedly flagged: {bullet} -> {res}"
    print(f"  ✓ Evidenced tools accepted: {evidenced}")

    # Learning-roadmap tools must be flagged as fabricated
    for tool in roadmap:
        res = detector.check_bullet(f"Built contract tests using {tool} in CI.")
        assert not res["is_valid"], f"Roadmap tool '{tool}' must be flagged until it graduates"
    print(f"  ✓ Roadmap tools flagged: {roadmap}")

    # Invalid bullet utilizing unverified external tools
    invalid_bullet = "Engineered microservice end-to-end automation using Cypress, Golang, and Rust."
    res_invalid = detector.check_bullet(invalid_bullet)
    assert not res_invalid["is_valid"], "Unverified tools must be flagged by detector"
    print(f"  ✓ Successfully flagged fabricated tools: {res_invalid['fabricated_tools']}")

    print("✅ FabricationDetector grounding verified.\n")


def test_master_knowledge_bank_and_boundaries():
    print("--- 3. Testing Master Knowledge Bank & Evidence-Gated Boundary Isolation ---")
    bank_path = os.path.join(PROJECT_ROOT, "data", "master_knowledge_bank.json")
    with open(bank_path, "r", encoding="utf-8") as f:
        bank = json.load(f)
    roadmap = {t.lower() for t in _load_registry().get("learning_roadmap", [])}

    vault = bank.get("master_achievements_vault", [])
    assert len(vault) >= 10, f"Expected at least 10 STAR achievements in vault, found {len(vault)}"

    # No vault entry may claim a learning-roadmap tool
    from src.resume_store.master_resume import tool_mentioned

    for item in vault:
        text = item.get("star_achievement", "")
        leaked = [t for t in roadmap if tool_mentioned(t, text)]
        assert not leaked, f"Roadmap tool(s) {leaked} leaked into vault entry: {text[:80]}"
    print(f"  ✓ {len(vault)} vault entries contain zero roadmap tools")

    print("✅ Master Knowledge Bank and employment boundaries verified.\n")


def test_resume_profile_schema():
    print("--- 4. Testing ResumeProfile Pydantic Schema & Skills Matrix ---")
    profile_path = os.path.join(PROJECT_ROOT, "data", "resume_profile.json")
    with open(profile_path, "r", encoding="utf-8") as f:
        raw_json = f.read()

    profile = ResumeProfile.model_validate_json(raw_json)
    assert profile.personal_details.full_name in ["Manjunath H K", "Test Candidate"]

    skills = profile.skills_matrix
    assert isinstance(skills, dict)
    flat = {s.lower() for v in skills.values() if isinstance(v, list) for s in v}
    roadmap = {t.lower() for t in _load_registry().get("learning_roadmap", [])}
    leaked = sorted(flat & roadmap)
    assert not leaked, f"Roadmap tools listed in skills_matrix: {leaked}"
    for tool in ("java", "python", "selenium"):
        assert tool in flat, f"Core skill '{tool}' missing from skills_matrix"

    print("  ✓ Skills matrix contains core skills and zero roadmap tools")
    print("✅ ResumeProfile schema verified.\n")


def test_naukri_pinger_cli_contract():
    print("--- 5. Testing Naukri Pinger CLI & Log Contract ---")
    cmd = [sys.executable, os.path.join(PROJECT_ROOT, "scripts", "naukri_pinger.py"), "--dry-run", "--headless"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"naukri_pinger.py failed: {result.stderr}"

    log_path = os.path.join(PROJECT_ROOT, "data", "logs", "naukri_pinger.log")
    assert os.path.exists(log_path), "naukri_pinger.log must exist after execution"

    with open(log_path, "r", encoding="utf-8") as f:
        log_content = f.read()
    assert "[DRY_RUN]" in log_content, "Expected [DRY_RUN] log entry in naukri_pinger.log"

    print("  ✓ naukri_pinger.py executed cleanly and logged execution event")
    print("✅ Naukri pinger contract verified.\n")


def main():
    print("==========================================================================")
    print(" Verification Gate 65: Sprint 1 Stack Realignment & Inbound Traps Suite   ")
    print("==========================================================================\n")

    test_whitelist_expansion_and_boundaries()
    test_fabrication_detector_grounding()
    test_master_knowledge_bank_and_boundaries()
    test_resume_profile_schema()
    test_naukri_pinger_cli_contract()

    print("==========================================================================")
    print(" GATE 65 PASSED: 100% SUCCESS across whitelist, grounding, vault & pinger ")
    print("==========================================================================")


if __name__ == "__main__":
    main()
