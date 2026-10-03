"""
Verification script for Sprint 5: Governance, SQLite Audit Trails & Rate Governor.
Tests SQLite database persistence, application tracking transactions,
and daily submission budget enforcement (≤15 applications/day).
"""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.autofill.governor import ApplicationGovernor
from src.storage.database import ApplicationDatabase

TEST_DB_PATH = os.path.join(PROJECT_ROOT, "data", "test_app_database.db")


def test_sqlite_persistence_and_governor():
    print("==================================================")
    print("  Testing Sprint 5: SQLite Database & Rate Governor")
    print("==================================================")

    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    db = ApplicationDatabase(db_path=TEST_DB_PATH)
    assert os.path.exists(TEST_DB_PATH), "Failed to initialize test SQLite database"
    print(f"📦 SQLite database initialized successfully at: {TEST_DB_PATH}")

    # 1. Test initial daily submission counter
    initial_count = db.get_today_submission_count()
    assert initial_count == 0, f"Expected 0 initial submissions, got {initial_count}"
    print("✅ Initial daily submission count is 0.")

    # 2. Test recording application audit events
    mock_job_id = "test_sprint5_job_101"
    db.record_application(
        job_id=mock_job_id,
        source="greenhouse",
        company_name="Cloudflare",
        job_title="Senior QA Engineer",
        job_url="https://boards.greenhouse.io/cloudflare/jobs/101",
        resume_path="/data/resumes/cloudflare_101.pdf",
        tailored_data={"summary": "Senior SDET with 6 years experience"},
        status="applied",
    )

    record = db.get_application(mock_job_id)
    assert record is not None, "Failed to retrieve recorded application from SQLite"
    assert record["company_name"] == "Cloudflare"
    assert record["status"] == "applied"
    print(f"✅ Application audit record retrieved: {record['job_title']} @ {record['company_name']}")

    count_after_one = db.get_today_submission_count()
    assert count_after_one == 1, f"Expected count 1, got {count_after_one}"

    # 3. Test Application Rate Governor (Limit = 15)
    governor = ApplicationGovernor(db=db, daily_limit=15)
    budget = governor.check_budget()
    assert budget["allowed"] is True
    assert budget["remaining"] == 14
    print(f"✅ Governor status: {budget['message']}")

    # 4. Simulate reaching quota limit (simulate 14 more submissions)
    print("\n⚡ Simulating remaining daily submissions to test safety cutoff...")
    for i in range(2, 16):
        db.record_application(
            job_id=f"test_sim_job_{i}",
            source="lever",
            company_name=f"Company_{i}",
            job_title="Senior SDET",
            job_url=f"https://jobs.lever.co/company_{i}/100",
            resume_path=f"/data/resumes/sim_{i}.pdf",
            tailored_data={"test": True},
        )

    capped_budget = governor.check_budget()
    assert capped_budget["allowed"] is False, "Governor failed to lock after 15 applications!"
    assert capped_budget["remaining"] == 0
    assert governor.can_proceed() is False
    print(f"🛑 Governor limit strictly enforced: {capped_budget['message']}")

    # Cleanup test DB
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    print("\n✅ SQLite transactions and rate governor safety cutoff verified successfully!")


def main():
    test_sqlite_persistence_and_governor()
    print("\n" + "=" * 50)
    print("✅ VERIFICATION SCRIPT 32 (GOVERNANCE & SQLITE) PASSED!")
    print("=" * 50)


if __name__ == "__main__":
    main()
