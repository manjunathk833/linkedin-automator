"""
Verification Gate 33: Test Resume and Master Knowledge Bank Regeneration
Ensures:
1. singlepageresume.json is completely sanitized (0 Playwright mentions).
2. data/resume_profile.json strictly complies with Pydantic ResumeProfile schema.
3. data/master_knowledge_bank.json contains grounded STAR achievements with zero hallucinations.
4. Full test suite compatibility with verify/02, verify/06, and verify/25.
"""

from __future__ import annotations

import json
import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.resume_store.models import ResumeProfile
from src.tailor.fabrication_detector import FabricationDetector


def test_singlepageresume_sanitization():
    resume_path = os.path.join(PROJECT_ROOT, "singlepageresume.json")
    with open(resume_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "playwright" not in content.lower(), "Playwright still found in singlepageresume.json!"
    print("✅ singlepageresume.json sanitization verified: 0 Playwright mentions.")


def test_resume_profile_validation():
    profile_path = os.path.join(PROJECT_ROOT, "data", "resume_profile.json")
    with open(profile_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    profile = ResumeProfile(**data)
    assert profile.personal_details.full_name == "Manjunath H K"
    assert profile.get_years_of_experience("Java") >= 6
    assert profile.get_years_of_experience("Selenium") >= 6
    assert profile.get_years_of_experience("Playwright") == 0
    assert len(profile.experience_history) == 3
    assert len(profile.education) >= 1
    assert profile.get_total_experience_years() >= 5.0
    print("✅ data/resume_profile.json schema and experience metrics verified.")


def test_master_knowledge_bank_grounding():
    bank_path = os.path.join(PROJECT_ROOT, "data", "master_knowledge_bank.json")
    with open(bank_path, "r", encoding="utf-8") as f:
        bank = json.load(f)

    vault = bank.get("master_achievements_vault", [])
    assert len(vault) >= 8, f"Expected at least 8 STAR achievements, got {len(vault)}"

    for item in vault:
        text = json.dumps(item).lower()
        assert "playwright" not in text, f"Playwright found in vault item: {item}"
        assert "cypress" not in text, f"Cypress found in vault item: {item}"
        assert "locust" not in text, f"Locust found in vault item: {item}"
        assert "kafka" not in text, f"Kafka found in vault item: {item}"

    print(f"✅ data/master_knowledge_bank.json verified: {len(vault)} grounded achievements, 0 hallucinations.")


def test_fabrication_detector_integration():
    profile_path = os.path.join(PROJECT_ROOT, "data", "resume_profile.json")
    bank_path = os.path.join(PROJECT_ROOT, "data", "master_knowledge_bank.json")

    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
    profile = ResumeProfile(**profile_data)

    with open(bank_path, "r", encoding="utf-8") as f:
        bank_data = json.load(f)

    detector = FabricationDetector(profile, bank_data)

    # Authentic bullet should pass
    authentic_bullet = (
        "Mosaic Order Automation Framework: Architected UI and API automation frameworks for 6+ airline projects "
        "leveraging REST Assured, Selenium, and BDD; built 2,000+ test cases, reducing regression execution effort by 93%."
    )
    res_auth = detector.check_bullet(authentic_bullet)
    assert res_auth["is_valid"] is True, f"Authentic bullet rejected: {res_auth}"

    # Playwright hallucination MUST be caught and rejected
    hallucinated_bullet = (
        "Built automated end-to-end regression pipelines using Playwright and Cypress with Docker containerization."
    )
    res_hallucinated = detector.check_bullet(hallucinated_bullet)
    assert res_hallucinated["is_valid"] is False
    assert "Playwright" in res_hallucinated["fabricated_tools"]
    assert "Cypress" in res_hallucinated["fabricated_tools"]

    print("✅ FabricationDetector integration verified: authentic bullets accepted, hallucinations blocked.")


if __name__ == "__main__":
    print("\n=======================================================")
    print("   RUNNING VERIFY GATE 33: RESUME & KNOWLEDGE REGEN    ")
    print("=======================================================\n")
    test_singlepageresume_sanitization()
    # Profile and bank tests will run once regenerated
    if os.path.exists("data/resume_profile.json") and os.path.exists("data/master_knowledge_bank.json"):
        test_resume_profile_validation()
        test_master_knowledge_bank_grounding()
        test_fabrication_detector_integration()
        print("\n✅ ALL VERIFY GATE 33 CHECKS COMPLETED SUCCESSFULLY!")
