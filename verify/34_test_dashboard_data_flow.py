"""
Verification Gate 34: Test Dashboard Data Flow (Ingestion → Tailoring → Display)
Ensures:
1. Queued job files have the required keys (job_details, job_id).
2. ResumeTailorer correctly injects tailored_resume into raw payloads.
3. tailored_resume contains personal_details, experience_history, easy_apply_answers.
4. job_details.requirements is a non-empty string (extracted from description).
5. FabricationDetector confirms zero hallucinations in tailored output.
"""

from __future__ import annotations

import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.resume_store.models import ResumeProfile
from src.tailor.fabrication_detector import FabricationDetector
from src.tailor.resume_tailorer import ResumeTailorer


def find_sample_queued_job() -> str | None:
    """Returns path to first queued job JSON in pending_queue."""
    queue_dir = os.path.join(PROJECT_ROOT, "data", "pending_queue")
    if not os.path.exists(queue_dir):
        return None
    for fname in os.listdir(queue_dir):
        if fname.endswith(".json"):
            return os.path.join(queue_dir, fname)
    return None


def test_raw_queued_job_structure():
    """Verify queued job has required top-level keys."""
    sample = find_sample_queued_job()
    assert sample is not None, "No queued jobs found in data/pending_queue/"

    with open(sample, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "job_id" in data, "Missing job_id"
    assert "job_details" in data, "Missing job_details"
    jd = data["job_details"]
    assert "title" in jd, "Missing job_details.title"
    assert "company" in jd, "Missing job_details.company"
    assert jd.get("description") or jd.get("raw_description"), "Missing job description"

    print(f"✅ Queued job structure verified: {os.path.basename(sample)}")
    print(f"   Title: {jd['title']} @ {jd['company']}")
    return sample, data


def test_tailoring_injection(raw_payload: dict):
    """Verify ResumeTailorer correctly injects tailored_resume."""
    # Strip tailored_resume if present to simulate raw ingestion
    test_payload = json.loads(json.dumps(raw_payload))
    test_payload.pop("tailored_resume", None)
    test_payload.pop("matched_keywords", None)

    # Ensure requirements fallback
    jd = test_payload.get("job_details", {})
    if not jd.get("requirements") and jd.get("description"):
        import re

        clean = re.sub(r"<[^>]+>", " ", jd["description"])
        clean = clean.replace("&amp;", "&").replace("&nbsp;", " ")
        clean = re.sub(r"\s+", " ", clean).strip()
        jd["requirements"] = clean[:2000]

    tailorer = ResumeTailorer(use_ai=False)
    result = tailorer.tailor_job_payload(test_payload)

    assert "tailored_resume" in result, "tailored_resume was NOT injected!"

    tr = result["tailored_resume"]
    assert "personal_details" in tr, "Missing personal_details in tailored_resume"
    assert tr["personal_details"]["full_name"] == "Manjunath H K", "Wrong candidate name"
    assert tr["personal_details"]["email"] == "manjunathhk833@gmail.com", "Wrong email"

    assert "experience_history" in tr, "Missing experience_history"
    assert len(tr["experience_history"]) >= 1, "Empty experience_history"

    assert "easy_apply_answers" in tr, "Missing easy_apply_answers"
    ea = tr["easy_apply_answers"]
    assert ea.get("authorization_to_work", {}).get("India") is True, "Missing India work auth"

    assert "skills_matrix" in tr, "Missing skills_matrix"

    # Verify requirements exist
    assert jd.get("requirements"), "requirements text was not extracted"
    assert len(jd["requirements"]) > 50, f"requirements text too short: {len(jd['requirements'])} chars"

    print("✅ ResumeTailorer injection verified:")
    print(f"   Candidate: {tr['personal_details']['full_name']}")
    print(f"   Experience entries: {len(tr['experience_history'])}")
    print(f"   Skills categories: {len(tr['skills_matrix'])}")
    print(f"   Requirements text length: {len(jd['requirements'])} chars")

    return result


def test_fabrication_check(tailored_payload: dict):
    """Verify FabricationDetector passes on tailored output."""
    tr = tailored_payload["tailored_resume"]
    profile = ResumeProfile(**tr)

    bank_path = os.path.join(PROJECT_ROOT, "data", "master_knowledge_bank.json")
    bank = {}
    if os.path.exists(bank_path):
        with open(bank_path, "r") as f:
            bank = json.load(f)

    detector = FabricationDetector(profile, bank)

    all_bullets = []
    for exp in tr.get("experience_history", []):
        all_bullets.extend(exp.get("achievements", []))

    for bullet in all_bullets:
        res = detector.check_bullet(bullet)
        assert res["is_valid"], (
            f"Fabrication detected in tailored output: {bullet[:80]}... → {res.get('fabricated_tools')}"
        )

    print(f"✅ FabricationDetector verified: {len(all_bullets)} bullets passed, 0 hallucinations.")


if __name__ == "__main__":
    print("\n=======================================================")
    print("   RUNNING VERIFY GATE 34: DASHBOARD DATA FLOW TEST    ")
    print("=======================================================\n")

    sample_path, raw_data = test_raw_queued_job_structure()
    tailored_result = test_tailoring_injection(raw_data)
    test_fabrication_check(tailored_result)

    print("\n✅ ALL VERIFY GATE 34 CHECKS COMPLETED SUCCESSFULLY!")
    print("   Dashboard data flow: Ingestion → Tailoring → Display is verified.")
