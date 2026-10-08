#!/usr/bin/env python3
"""
Verification Gate 65: Sprint 1 Stack Realignment, Whitelist Expansion & Inbound Traps
=====================================================================================
Validates:
1. Tool whitelist expansion: modern product tools authorized, unverified tools blocked.
2. Anti-fabrication detector: zero-rejection on modern tools, catching unverified tools.
3. Master Knowledge Bank & Employment Boundary Isolation: independent projects cleanly scoped.
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


def test_whitelist_expansion_and_boundaries():
    print("--- 1. Testing Tool Whitelist Expansion & Boundary Integrity ---")
    whitelist_path = os.path.join(PROJECT_ROOT, "data", "profile", "allowed_tools_whitelist.json")
    with open(whitelist_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    allowed = set(data.get("allowed_tools", []))
    disallowed = set(data.get("disallowed_hallucinations", []))

    expected_allowed = [
        "playwright",
        "typescript",
        "docker",
        "kubernetes",
        "k8s",
        "kafka",
        "wiremock",
        "pact",
    ]
    for tool in expected_allowed:
        assert tool in allowed, f"Tool '{tool}' must be present in allowed_tools"
        assert tool not in disallowed, f"Tool '{tool}' must NOT be in disallowed_hallucinations"
        print(f"  ✓ Verified allowed: {tool}")

    expected_blocked = ["cypress", "golang", "go", "rust", "terraform", "ansible"]
    for tool in expected_blocked:
        assert tool in disallowed, f"Unverified tool '{tool}' must remain in disallowed_hallucinations"
        print(f"  ✓ Verified blocked boundary: {tool}")

    print("✅ Tool whitelist expansion and boundaries verified.\n")


def test_fabrication_detector_grounding():
    print("--- 2. Testing FabricationDetector Grounding & Anti-Hallucination ---")
    profile_path = os.path.join(PROJECT_ROOT, "data", "resume_profile.json")
    bank_path = os.path.join(PROJECT_ROOT, "data", "master_knowledge_bank.json")

    with open(profile_path, "r", encoding="utf-8") as f:
        profile = ResumeProfile.model_validate_json(f.read())
    with open(bank_path, "r", encoding="utf-8") as f:
        bank = json.load(f)

    detector = FabricationDetector(profile=profile, master_knowledge_bank=bank)

    # Valid bullets utilizing the newly whitelisted product tools
    valid_bullets = [
        "Architected a modular Playwright + TypeScript test automation framework with parallel test execution.",
        "Containerized ephemeral test runners using Docker and Kubernetes across GitHub Actions CI workflows.",
        "Engineered asynchronous event-driven validation pipelines for Kafka message queues with latency monitoring.",
        "Implemented microservice API contract testing using Pact and WireMock service virtualization.",
    ]
    for b in valid_bullets:
        res = detector.check_bullet(b)
        assert res["is_valid"], f"Bullet was unexpectedly flagged as fabricated: {b} -> {res}"
        assert len(res["fabricated_tools"]) == 0
        print(f"  ✓ Validated authentic: {b[:70]}...")

    # Invalid bullet utilizing unverified external tools
    invalid_bullet = "Engineered microservice end-to-end automation using Cypress, Golang, and Rust."
    res_invalid = detector.check_bullet(invalid_bullet)
    assert not res_invalid["is_valid"], "Unverified tools must be flagged by detector"
    assert "Cypress" in res_invalid["fabricated_tools"] or "Golang" in res_invalid["fabricated_tools"]
    print(f"  ✓ Successfully flagged fabricated tools: {res_invalid['fabricated_tools']}")

    print("✅ FabricationDetector grounding verified.\n")


def test_master_knowledge_bank_and_boundaries():
    print("--- 3. Testing Master Knowledge Bank & Employment Boundary Isolation ---")
    bank_path = os.path.join(PROJECT_ROOT, "data", "master_knowledge_bank.json")
    with open(bank_path, "r", encoding="utf-8") as f:
        bank = json.load(f)

    vault = bank.get("master_achievements_vault", [])
    assert len(vault) >= 15, f"Expected at least 15 STAR achievements in vault, found {len(vault)}"

    project_achievements = [a for a in vault if a.get("company") == "Technical Projects"]
    assert len(project_achievements) == 4, (
        f"Expected 4 Technical Projects achievements, found {len(project_achievements)}"
    )

    for pa in project_achievements:
        print(f"  ✓ Project achievement: {pa['domain']} -> {pa['tools']}")

    # Verify that company boundaries are strictly preserved
    valuelabs_bullets = [a for a in vault if a.get("company") == "Value Labs"]
    for v in valuelabs_bullets:
        star_lower = v["star_achievement"].lower()
        assert "playwright" not in star_lower, "Value Labs history must not claim Playwright"
        assert "kubernetes" not in star_lower, "Value Labs history must not claim Kubernetes"

    print("✅ Master Knowledge Bank and employment boundaries verified.\n")


def test_resume_profile_schema():
    print("--- 4. Testing ResumeProfile Pydantic Schema & Skills Matrix ---")
    profile_path = os.path.join(PROJECT_ROOT, "data", "resume_profile.json")
    with open(profile_path, "r", encoding="utf-8") as f:
        raw_json = f.read()

    profile = ResumeProfile.model_validate_json(raw_json)
    assert profile.personal_details.full_name == "Manjunath H K"

    skills = profile.skills_matrix
    assert isinstance(skills, dict)
    assert "Playwright" in skills.get("Languages & UI Automation", [])
    assert "TypeScript" in skills.get("Languages & UI Automation", [])
    assert "Kubernetes" in skills.get("CI/CD & Infra", [])
    assert "Kafka" in skills.get("API Automation", [])
    assert "WireMock" in skills.get("API Automation", [])
    assert "Pact" in skills.get("API Automation", [])

    print("  ✓ Verified skills matrix contains Playwright, TypeScript, Kubernetes, Kafka, WireMock, Pact")
    print("✅ ResumeProfile schema verified.\n")


def test_naukri_pinger_cli_contract():
    print("--- 5. Testing Naukri Pinger CLI & Log Contract ---")
    cmd = [sys.executable, os.path.join(PROJECT_ROOT, "scripts", "naukri_pinger.py"), "--dry-run"]
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
