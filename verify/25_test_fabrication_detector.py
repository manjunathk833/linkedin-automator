from __future__ import annotations

import json
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.resume_store.models import ResumeProfile
from src.tailor.fabrication_detector import FabricationDetector
from src.tailor.resume_tailorer import ResumeTailorer


def test_fabrication_detector():
    print("==================================================")
    print("  Testing Zero-Cost Anti-Fabrication Verification Gate")
    print("==================================================")

    # 1. Load Master Resume Profile & Master Knowledge Bank
    with open("data/resume_profile.json", "r") as f:
        profile_data = json.load(f)
    profile = ResumeProfile(**profile_data)

    with open("data/master_knowledge_bank.json", "r") as f:
        bank_data = json.load(f)

    detector = FabricationDetector(profile, bank_data)

    # 2. Test Grounded Bullet
    valid_bullet = "PNR Linking & SSR [REST Assured · ReadyAPI · BDD]: Architected automated testing frameworks for airline domain; built 1000+ API test cases cutting execution effort by 93%."
    res_valid = detector.check_bullet(valid_bullet)
    assert res_valid["is_valid"] is True
    print("✅ Grounded bullet verified PASS!")

    # 3. Test Fabricated Playwright & Cypress Bullet
    fabricated_bullet = "Spearheaded web UI automation using Playwright and Cypress with Jenkins CI/CD integration; designed parallel cross-browser execution pipelines."
    res_fab = detector.check_bullet(fabricated_bullet)
    assert res_fab["is_valid"] is False
    assert "Playwright" in res_fab["fabricated_tools"]
    assert "Cypress" in res_fab["fabricated_tools"]
    print(f"✅ Fabricated bullet successfully FLAGGED & REJECTED! Detected tools: {res_fab['fabricated_tools']}")

    # 4. Test validate_all_bullets filtering
    test_bullets = [valid_bullet, fabricated_bullet]
    clean_bullets = detector.validate_all_bullets(test_bullets)
    assert len(clean_bullets) == 1
    assert clean_bullets[0] == valid_bullet
    print("✅ Bullet filtering verified! Stripped fabricated bullet (1 clean bullet remaining).")

    # 5. Verify Master Knowledge Bank data clean-up
    vault = bank_data.get("master_achievements_vault", [])
    playwright_entries = [item for item in vault if "playwright" in str(item).lower()]
    assert len(playwright_entries) == 0
    print("✅ Master Knowledge Bank verified CLEAN! Zero Playwright fabrications found in vault.")

    # 6. Test full ResumeTailorer integration against a JD asking for Playwright
    tailorer = ResumeTailorer(use_ai=False)
    mock_job = {
        "job_id": "test_999",
        "job_details": {
            "title": "Senior Playwright QA Engineer",
            "requirements": "Must have extensive experience in Playwright, Cypress, Python, and REST Assured.",
        },
    }
    tailored = tailorer.tailor_job_payload(mock_job)
    achievements = tailored["tailored_resume"]["experience_history"][0]["achievements"]

    for b in achievements:
        assert "Playwright" not in b
        assert "Cypress" not in b
    print("✅ ResumeTailorer pipeline integration verified! Generated payload is 100% grounded.")

    print("\n" + "=" * 50)
    print("✅ ANTI-FABRICATION VERIFICATION GATE TEST PASSED 100%!")
    print("=" * 50)


if __name__ == "__main__":
    test_fabrication_detector()
