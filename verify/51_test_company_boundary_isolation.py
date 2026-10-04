"""
verify/51_test_company_boundary_isolation.py — Verification Gate 51:
Validates Company Boundary Isolation, Cross-Company Contamination Blocking, and Company-Scoped Tailoring.

Ensures that:
1. Value Labs experience NEVER receives Appium, OTT, Charles Proxy, Burp Suite (Tata Elxsi) or Ekam (Dunzo).
2. Tata Elxsi experience retains authentic Mobile/Appium/OTT achievements.
3. Dunzo experience retains authentic Ekam/GCP achievements.
4. FabricationDetector strictly blocks cross-company contamination.
"""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.resume_store.models import ResumeProfile
from src.tailor.fabrication_detector import FabricationDetector
from src.tailor.resume_tailorer import ResumeTailorer


def test_company_boundary_isolation():
    print("=" * 60)
    print("  GATE 51: COMPANY BOUNDARY ISOLATION & CONTAMINATION AUDIT")
    print("=" * 60)

    # 1. Test FabricationDetector cross-company contamination logic directly
    profile_path = os.path.join(PROJECT_ROOT, "data", "resume_profile.json")
    import json

    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
    profile = ResumeProfile(**profile_data)

    detector = FabricationDetector(profile=profile)

    print("\n🔍 Step 1: Testing direct contamination detection on synthetic bullets...")
    # Attempting to assign Tata Elxsi bullet to Value Labs
    fake_vl_bullet = "Mobile & UI Automation Framework [Python · Appium · TestRail API]: Automated 50% of sanity suite."
    res_vl = detector.check_company_contamination("Value Labs", fake_vl_bullet)
    print(
        f"   Value Labs with Appium bullet -> is_clean={res_vl['is_clean']}, violations={res_vl['violating_companies']}"
    )
    assert not res_vl["is_clean"], "Expected detector to flag Tata Elxsi bullet under Value Labs"

    # Attempting to assign Dunzo bullet to Value Labs
    fake_dunzo_bullet = "Ekam Microservices Framework [Java · Ekam · PostgreSQL]: Automated Merchant Service."
    res_dunzo = detector.check_company_contamination("Value Labs", fake_dunzo_bullet)
    print(
        f"   Value Labs with Ekam bullet -> is_clean={res_dunzo['is_clean']}, violations={res_dunzo['violating_companies']}"
    )
    assert not res_dunzo["is_clean"], "Expected detector to flag Dunzo bullet under Value Labs"

    # Genuine Value Labs bullet
    genuine_vl_bullet = (
        "Mosaic Order Automation Framework [REST Assured · Selenium · BDD · Java]: Built 2000+ test cases."
    )
    res_gen = detector.check_company_contamination("Value Labs", genuine_vl_bullet)
    print(f"   Genuine Value Labs bullet -> is_clean={res_gen['is_clean']}")
    assert res_gen["is_clean"], "Expected genuine Value Labs bullet to be clean"

    print("✅ FabricationDetector successfully isolates company boundaries!")

    # 2. Test End-to-End ResumeTailorer with a Mobile Testing JD (Media.net scenario)
    print("\n🔍 Step 2: Testing ResumeTailorer against Mobile Testing (Media.net) JD...")
    tailorer = ResumeTailorer(use_ai=False)  # Deterministic test
    sample_job = {
        "job_id": "9999999999",
        "job_details": {
            "title": "Software Test Engineer - II (Mobile Testing)",
            "company": "Media.net",
            "requirements": "Looking for 4+ years in Mobile Application Testing, Appium, Python, Charles Proxy, Burp Suite, and OTT streaming testing.",
        },
    }

    tailored_job = tailorer.tailor_job_payload(sample_job)
    tailored_exps = tailored_job["tailored_resume"]["experience_history"]

    assert len(tailored_exps) >= 3, "Expected at least 3 experience entries"

    # Check Value Labs (exp[0])
    vl_exp = tailored_exps[0]
    assert vl_exp["company"] == "Value Labs"
    vl_bullets = vl_exp["achievements"]
    print(f"   Value Labs achievements count: {len(vl_bullets)}")
    for b in vl_bullets:
        print(f"     * {b[:85]}...")
        b_lower = b.lower()
        assert "appium" not in b_lower, f"CONTAMINATION: Appium found in Value Labs! Bullet: {b}"
        assert "ott app" not in b_lower, f"CONTAMINATION: OTT app found in Value Labs! Bullet: {b}"
        assert "burp suite" not in b_lower, f"CONTAMINATION: Burp Suite found in Value Labs! Bullet: {b}"
        assert "charles proxy" not in b_lower, f"CONTAMINATION: Charles Proxy found in Value Labs! Bullet: {b}"
        assert "ekam" not in b_lower, f"CONTAMINATION: Ekam found in Value Labs! Bullet: {b}"

    # Check Tata Elxsi (exp[2])
    tata_exp = tailored_exps[2]
    assert tata_exp["company"] == "Tata Elxsi"
    tata_bullets = tata_exp["achievements"]
    print(f"   Tata Elxsi achievements count: {len(tata_bullets)}")
    assert any("appium" in b.lower() for b in tata_bullets), "Expected Appium achievement to remain in Tata Elxsi"
    for b in tata_bullets:
        print(f"     * {b[:85]}...")
        assert "mosaic" not in b.lower(), f"CONTAMINATION: Mosaic found in Tata Elxsi! Bullet: {b}"
        assert "ekam" not in b.lower(), f"CONTAMINATION: Ekam found in Tata Elxsi! Bullet: {b}"

    # Check Dunzo (exp[1])
    dunzo_exp = tailored_exps[1]
    assert dunzo_exp["company"] == "Dunzo"
    dunzo_bullets = dunzo_exp["achievements"]
    print(f"   Dunzo achievements count: {len(dunzo_bullets)}")
    assert any("ekam" in b.lower() for b in dunzo_bullets), "Expected Ekam achievement to remain in Dunzo"
    for b in dunzo_bullets:
        print(f"     * {b[:85]}...")
        assert "appium" not in b.lower(), f"CONTAMINATION: Appium found in Dunzo! Bullet: {b}"
        assert "mosaic" not in b.lower(), f"CONTAMINATION: Mosaic found in Dunzo! Bullet: {b}"

    print("✅ End-to-End ResumeTailorer guarantees 0% cross-company contamination!")

    print("\n" + "=" * 60)
    print("🎉 ALL GATE 51 ASSERTIONS PASSED (100% SUCCESS)!")
    print("=" * 60)


if __name__ == "__main__":
    test_company_boundary_isolation()
