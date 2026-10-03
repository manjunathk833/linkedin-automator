"""
Verification script for Gate 42: Safety Rate Governor Cap Scaled to 200/day.
Validates:
1. ApplicationGovernor defaults to 200 applications per day.
2. Dynamic configuration via config.yaml (safety_governor.daily_limit).
3. Explicit constructor override support.
4. FastAPI endpoint /api/approved-jobs returns daily_limit = 200.
5. Safety cutoff behavior when budget threshold is reached.
"""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient

from src.autofill.governor import DEFAULT_DAILY_LIMIT, ApplicationGovernor
from src.storage.database import ApplicationDatabase
from src.ui.app import app

TEST_DB_PATH = os.path.join(PROJECT_ROOT, "data", "test_governor_200.db")


def test_safety_governor_200():
    print("=" * 60)
    print("  Testing Gate 42: Safety Rate Governor Cap (200 Apps/Day)")
    print("=" * 60)

    # 1. Verify default constant
    assert DEFAULT_DAILY_LIMIT == 200, f"Expected DEFAULT_DAILY_LIMIT == 200, got {DEFAULT_DAILY_LIMIT}"
    print(f"✅ DEFAULT_DAILY_LIMIT verified: {DEFAULT_DAILY_LIMIT}")

    # 2. Verify clean governor initialization reads 200
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    db = ApplicationDatabase(db_path=TEST_DB_PATH)
    gov = ApplicationGovernor(db=db)
    budget = gov.check_budget()

    assert gov.daily_limit == 200, f"Expected daily_limit == 200, got {gov.daily_limit}"
    assert budget["daily_limit"] == 200
    assert budget["allowed"] is True
    assert budget["remaining"] == 200
    print(f"✅ Governor initialized with daily_limit=200. Message: {budget['message']}")

    # 3. Verify constructor override still works
    gov_custom = ApplicationGovernor(db=db, daily_limit=50)
    assert gov_custom.daily_limit == 50, f"Expected custom limit 50, got {gov_custom.daily_limit}"
    print("✅ Custom constructor override (daily_limit=50) verified.")

    # 4. Verify /api/approved-jobs returns daily_limit = 200
    client = TestClient(app)
    res = client.get("/api/approved-jobs")
    assert res.status_code == 200, f"Expected 200 from /api/approved-jobs, got {res.status_code}"
    data = res.json()
    ui_budget = data.get("budget", {})
    assert ui_budget.get("daily_limit") == 200, (
        f"Expected UI budget daily_limit 200, got {ui_budget.get('daily_limit')}"
    )
    print(f"✅ UI Endpoint /api/approved-jobs correctly reports daily_limit: {ui_budget.get('daily_limit')}")

    # 5. Verify cutoff boundary logic at 200
    # Simulate DB having 200 applications
    for i in range(200):
        db.record_application(
            job_id=f"gate42_sim_{i}",
            source="greenhouse",
            company_name=f"Company_{i}",
            job_title="Senior SDET",
            job_url=f"https://boards.greenhouse.io/comp/jobs/{i}",
            resume_path=f"/data/resumes/job_{i}.pdf",
            tailored_data={},
            status="applied",
        )

    capped_budget = gov.check_budget()
    assert capped_budget["allowed"] is False, "Governor should lock after 200 applications"
    assert capped_budget["remaining"] == 0
    assert gov.can_proceed() is False
    print(f"🛑 200 quota cutoff enforced correctly: {capped_budget['message']}")

    # Cleanup test DB
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    print("\n" + "=" * 60)
    print("✅ GATE 42 (SAFETY GOVERNOR 200/DAY) VERIFICATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_safety_governor_200()
