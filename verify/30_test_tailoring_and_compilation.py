"""
Verification script for Sprint 3: Grounded Tailoring, Verification Gate & PDF Compilation.
Tests deterministic whitelist enforcement, intentional false-skill injection,
and single-column ATS PDF compilation.
"""

from __future__ import annotations

import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.compiler.typst_generator import TypstResumeCompiler
from src.llm.validator import ResumeVerificationGate


def test_verification_gate_purging():
    print("==================================================")
    print("  Testing Sprint 3: Deterministic Verification Gate")
    print("==================================================")

    gate = ResumeVerificationGate()
    assert len(gate.allowed_tools) > 10, "Failed to load allowed tools from whitelist"
    assert len(gate.disallowed_tools) > 0, "Failed to load disallowed tools"
    print(
        f"🛡️ Whitelist Loaded: {len(gate.allowed_tools)} allowed tools, {len(gate.disallowed_tools)} disallowed targets."
    )

    # 1. Deliberately inject unauthorized tools
    injected_bullets = [
        "Architected E2E test suites using Cypress and Kubernetes pipelines for CI/CD.",
        "Built microservice testing frameworks in Golang and Playwright for real-time Kafka event streams.",
        "Spearheaded API automation using REST Assured and Java with Jenkins CI/CD integration.",
    ]

    print("\n🧪 Testing intentional false skill injections:")
    for b in injected_bullets:
        print(f"   Input: '{b}'")

    sanitized = gate.validate_and_sanitize(injected_bullets)

    print("\n🔍 Sanitized Output:")
    for s in sanitized:
        print(f"   Output: '{s}'")

    # Assertions
    for item in sanitized:
        lower_item = item.lower()
        for forbidden in ["cypress", "kubernetes", "golang", "playwright", "kafka"]:
            assert forbidden not in lower_item, f"LEAK DETECTED! Forbidden skill '{forbidden}' survived in: {item}"

    assert "REST Assured" in sanitized[2], "Authentic skill REST Assured was erroneously removed!"
    assert "Java" in sanitized[2], "Authentic skill Java was erroneously removed!"
    print(
        "\n✅ 100% of injected unauthorized skills (Cypress, Kubernetes, Golang, Playwright, Kafka) were purged or substituted!"
    )


def test_pdf_compilation():
    print("\n==================================================")
    print("  Testing Single-Column ATS PDF Compilation")
    print("==================================================")

    profile_path = os.path.join(PROJECT_ROOT, "data", "resume_profile.json")
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)

    compiler = TypstResumeCompiler(output_dir=os.path.join(PROJECT_ROOT, "data", "resumes"))
    pdf_path = compiler.compile(
        profile=profile_data,
        company="Stripe",
        job_id="sprint3_test_99",
        role_title="Senior SDET",
    )

    assert os.path.exists(pdf_path), f"Expected PDF at {pdf_path}, but file not found"
    file_size = os.path.getsize(pdf_path)
    assert file_size > 1000, f"Generated PDF is unexpectedly small: {file_size} bytes"
    print(f"✅ ATS-compliant PDF generated successfully: {pdf_path} ({file_size} bytes)")


def main():
    test_verification_gate_purging()
    test_pdf_compilation()
    print("\n" + "=" * 50)
    print("✅ VERIFICATION SCRIPT 30 (TAILORING & COMPILATION) PASSED!")
    print("=" * 50)


if __name__ == "__main__":
    main()
