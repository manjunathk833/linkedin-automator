from __future__ import annotations

import json
import os
import sys

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.tailor.resume_tailorer import ResumeTailorer


def test_master_knowledge_tailoring():
    print("==================================================")
    print("  Testing Master Knowledge Bank & Few-Shot Tailoring")
    print("==================================================")

    # 1. Verify Master Knowledge Bank File
    bank_path = "data/master_knowledge_bank.json"
    assert os.path.exists(bank_path), f"Missing {bank_path}"
    with open(bank_path, "r") as f:
        bank = json.load(f)

    assert "master_achievements_vault" in bank
    assert len(bank["master_achievements_vault"]) >= 5
    print(f"✅ Loaded {len(bank['master_achievements_vault'])} STAR achievements from Master Knowledge Bank!")

    # 2. Test ResumeTailorer Ingestion & Tailoring
    tailorer = ResumeTailorer(use_ai=False)
    sample_job = {
        "job_id": "test_kb_101",
        "job_details": {
            "title": "Senior SDET",
            "company": "Salesforce",
            "requirements": "Looking for Senior SDET proficient in Playwright, Python, REST Assured, and BDD.",
        },
    }

    result = tailorer.tailor_job_payload(sample_job)
    assert "matched_keywords" in result
    assert "Playwright" in result["matched_keywords"] or "REST Assured" in result["matched_keywords"]
    assert "$schema" in result["tailored_resume"]
    assert "basics" in result["tailored_resume"]
    print("✅ Tailor job payload successfully generated ATS JSON Resume standard schema!")

    print("\n" + "=" * 50)
    print("✅ MASTER KNOWLEDGE BANK & FEW-SHOT TAILORING VERIFIED!")
    print("=" * 50)


if __name__ == "__main__":
    test_master_knowledge_tailoring()
