"""
verify/52_audit_queue_zero_contamination.py — Verification Gate 52:
Audit all seeded jobs in data/pending_queue/ to verify 100% zero cross-company contamination.
"""

from __future__ import annotations

import glob
import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.resume_store.models import ResumeProfile
from src.tailor.fabrication_detector import FabricationDetector


def audit_pending_queue():
    print("=" * 60)
    print("  GATE 52: AUDIT PENDING QUEUE FOR ZERO CROSS-CONTAMINATION")
    print("=" * 60)

    queue_dir = os.path.join(PROJECT_ROOT, "data", "pending_queue")
    files = glob.glob(os.path.join(queue_dir, "*.json"))

    if not files:
        print("⚠️ No job files found in data/pending_queue/ to audit yet.")
        return False

    print(f"📦 Found {len(files)} jobs in pending queue. Auditing company boundaries...")

    profile_path = os.path.join(PROJECT_ROOT, "data", "resume_profile.json")
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
    profile = ResumeProfile(**profile_data)
    detector = FabricationDetector(profile=profile)

    total_bullets_audited = 0
    total_violations = 0
    ai_tailored_jobs = 0
    heuristic_jobs = 0

    for fpath in files:
        fname = os.path.basename(fpath)
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        tailoring_method = data.get("tailoring_method", "unknown")
        if "ai" in tailoring_method:
            ai_tailored_jobs += 1
        else:
            heuristic_jobs += 1

        exps = data.get("tailored_resume", {}).get("experience_history", [])
        if not exps:
            # Fallback to direct experience_history if present
            exps = data.get("experience_history", [])

        for exp in exps:
            comp_name = exp.get("company", "")
            bullets = exp.get("achievements", [])
            for b in bullets:
                total_bullets_audited += 1
                res = detector.check_company_contamination(comp_name, b)
                if not res["is_clean"]:
                    total_violations += 1
                    print(f"❌ CONTAMINATION VIOLATION in {fname} under '{comp_name}':")
                    print(f"   Bullet: {b}")
                    print(f"   Violating companies: {res['violating_companies']}")

    print("\n" + "-" * 60)
    print("📊 Audit Summary:")
    print(f"   Total Jobs Audited: {len(files)}")
    print(f"   AI Grounded STAR Jobs: {ai_tailored_jobs}")
    print(f"   Heuristic Reordered Jobs: {heuristic_jobs}")
    print(f"   Total Bullets Audited: {total_bullets_audited}")
    print(f"   Total Contamination Violations: {total_violations}")
    print("-" * 60)

    assert total_violations == 0, f"FAILED: Found {total_violations} cross-company contamination violations!"
    print("✅ 100% SUCCESS: ZERO cross-company contamination detected across all staged jobs!\n")
    return True


if __name__ == "__main__":
    success = audit_pending_queue()
    if not success:
        sys.exit(1)
