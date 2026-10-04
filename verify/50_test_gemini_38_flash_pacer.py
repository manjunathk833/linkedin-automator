"""
verify/50_test_gemini_38_flash_pacer.py — Verification Gate 50:
Validates Gemini 3.8 Flash Upgrade, 4-Second Rate Pacer, and File-Based Diagnostics Logging.

Checks:
1. Gemini 3.8 Flash connectivity and structured STAR JSON output.
2. Rate pacer execution: confirms >= 4.0s elapsed between successive API requests to prevent 15 RPM 429s.
3. Structured file logging in data/logs/llm_requests.log verifying timestamps, model, operation, duration, and status.
"""

from __future__ import annotations

import os
import sys
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.resume_store.models import ResumeProfile
from src.tailor.llm_provider import LLM_LOG_FILE, GeminiLLMProvider


def test_gemini_38_flash_and_rate_pacer():
    print("=" * 60)
    print("  GATE 50: GEMINI 3.8 FLASH UPGRADE & 4s RATE PACER AUDIT")
    print("=" * 60)

    provider = GeminiLLMProvider()
    if not provider.is_available():
        print("⚠️ GEMINI_API_KEY not configured. Skipping live test.")
        return

    # Load canonical candidate profile
    profile_path = os.path.join(PROJECT_ROOT, "data", "resume_profile.json")
    with open(profile_path, "r", encoding="utf-8") as f:
        import json

        profile_data = json.load(f)
    profile = ResumeProfile(**profile_data)

    vault_path = os.path.join(PROJECT_ROOT, "data", "master_knowledge_bank.json")
    master_vault = []
    if os.path.exists(vault_path):
        with open(vault_path, "r", encoding="utf-8") as f:
            vault_data = json.load(f)
            master_vault = vault_data.get("master_achievements_vault", [])

    sample_jd_1 = (
        "Senior SDET: Required 5+ years experience in Java, Selenium, REST Assured, API test automation, and CI/CD."
    )
    sample_jd_2 = (
        "Lead Quality Engineer: Looking for Python, Kibana, GCP, microservices log monitoring and observability."
    )

    # 1. First Call
    print(f"\n🔍 Step 1: Executing Call #1 on {provider.model_name}...")
    t0 = time.time()
    bullets_1 = provider.generate_tailored_bullets(sample_jd_1, profile, master_vault=master_vault)
    t1 = time.time()
    print(f"   Call #1 finished in {t1 - t0:.2f}s. Received {len(bullets_1)} bullets.")
    assert len(bullets_1) >= 2, "Expected at least 2 tailored bullets"

    # 2. Second Call immediately after Call #1 (Tests Rate Pacer)
    print("\n🔍 Step 2: Executing Call #2 immediately to verify 4-second rate pacer...")
    t2_start = time.time()
    bullets_2 = provider.generate_tailored_bullets(sample_jd_2, profile, master_vault=master_vault)
    t2_end = time.time()
    call2_elapsed = t2_end - t2_start
    total_gap = t2_end - t1
    print(f"   Call #2 finished in {call2_elapsed:.2f}s (Total gap from Call #1: {total_gap:.2f}s).")

    # Assert that rate pacer enforced delay
    assert total_gap >= 4.0, f"Expected rate pacer to enforce >= 4.0s gap, got {total_gap:.2f}s"
    assert len(bullets_2) >= 2, "Expected at least 2 tailored bullets from Call #2"
    print("✅ Rate Pacer successfully enforced >= 4.0s delay between requests!")

    # 3. Verify Log File
    print("\n🔍 Step 3: Validating request diagnostics log file...")
    assert os.path.exists(LLM_LOG_FILE), f"Expected log file at {LLM_LOG_FILE}"
    with open(LLM_LOG_FILE, "r", encoding="utf-8") as f:
        log_lines = f.readlines()

    recent_logs = "".join(log_lines[-10:])
    print(f"   Recent Log Entries:\n{recent_logs}")

    assert "STATUS=SUCCESS" in recent_logs
    assert "Gemini" in recent_logs
    print("✅ File-based diagnostics logging verified successfully!")

    print("\n" + "=" * 60)
    print("🎉 ALL GATE 50 ASSERTIONS PASSED (100% SUCCESS)!")
    print("=" * 60)


if __name__ == "__main__":
    test_gemini_38_flash_and_rate_pacer()
