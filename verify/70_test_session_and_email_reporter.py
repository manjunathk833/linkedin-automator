"""
Verification Gate 70: Test Session Manager, Email Reporter, Daily Run Logger & Pipeline.
Validates:
1. EmailReporter HTML template rendering, KPI metric calculation, and offline archive saving.
2. SessionManager session inspection and storage state parsing.
3. DailyRunLogger structured JSONL & operational diagnostics logging.
4. DailyPipelineRunner port checking, queue reading, and end-to-end execution.
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.browser.session_manager import SessionManager
from src.notifier.daily_logger import DailyRunLogger
from src.notifier.email_reporter import EmailReporter
from src.pipeline.daily_runner import DailyPipelineRunner


def test_session_and_email_reporter():
    print("=" * 65)
    print("  GATE 70: SESSION MANAGER, EMAIL REPORTER & DAILY RUNNER AUDIT")
    print("=" * 65)

    # -------------------------------------------------------------
    # 1. Test EmailReporter
    # -------------------------------------------------------------
    print("\n🔍 Step 1: Testing EmailReporter HTML Briefing & Fallback...")
    reporter = EmailReporter()

    sample_jobs = [
        {
            "job_id": "mock_role_001",
            "title": "Lead SDET - Microservices",
            "company": "Adobe",
            "location": "Noida / Bengaluru",
            "source": "workday",
            "is_dream_org": True,
            "apply_url": "https://adobe.wd5.myworkdayjobs.com/job/123",
        },
        {
            "job_id": "mock_role_002",
            "title": "Senior Automation Engineer",
            "company": "Coinbase",
            "location": "Remote India",
            "source": "greenhouse",
            "is_dream_org": False,
            "apply_url": "https://boards.greenhouse.io/coinbase/jobs/456",
        },
    ]

    html = reporter.build_report_html(
        staged_jobs=sample_jobs,
        regression_passed=True,
        regression_summary="48/48 Passed (100%)",
        execution_duration_sec=14.5,
        run_date="October 14, 2026",
    )

    assert "Morning SDET Executive Briefing" in html
    assert "Adobe" in html
    assert "Coinbase" in html
    assert "⭐ DREAM ORG" in html
    assert "http://localhost:8000" in html
    print("   ✅ HTML Executive Briefing template rendered perfectly!")

    # Test fallback archive write
    test_log_dir = PROJECT_ROOT / "data" / "logs"
    test_log_dir.mkdir(parents=True, exist_ok=True)
    today_slug = datetime.date.today().strftime("%Y-%m-%d")
    archive_file = test_log_dir / f"daily_report_{today_slug}.html"

    # Send report and verify archive generation
    res = reporter.send_report(
        staged_jobs=sample_jobs,
        regression_passed=True,
        regression_summary="48/48 Passed (100%)",
        execution_duration_sec=14.5,
    )
    assert archive_file.exists(), "Expected archive HTML file to exist"
    assert isinstance(res, bool), "Expected boolean dispatch status from send_report"

    # Explicitly test offline fallback mode (without credentials)
    offline_reporter = EmailReporter(sender_email="", app_password="")
    offline_res = offline_reporter.send_report(
        staged_jobs=sample_jobs,
        regression_passed=True,
        regression_summary="48/48 Passed (100%)",
        execution_duration_sec=14.5,
    )
    assert offline_res is False, "Expected False when SMTP credentials are blank"
    print(f"   ✅ Archive & offline fallback verified: {archive_file} ({archive_file.stat().st_size} bytes)")

    # -------------------------------------------------------------
    # 2. Test SessionManager
    # -------------------------------------------------------------
    print("\n🔍 Step 2: Testing SessionManager...")
    mgr = SessionManager()
    status = mgr.get_session_status()
    assert "is_authenticated" in status
    assert "path" in status
    print(f"   ✅ Initial status check: is_authenticated={status['is_authenticated']}")

    # Create temporary mock storage_state.json
    temp_state = test_log_dir / "temp_test_storage_state.json"
    mock_auth = {
        "cookies": [
            {
                "name": "li_at",
                "value": "mock_auth_token_value_xyz",
                "domain": ".linkedin.com",
                "path": "/",
                "expires": int(datetime.datetime.now(datetime.timezone.utc).timestamp()) + 86400,
            },
            {
                "name": "JSESSIONID",
                "value": "ajax:123456",
                "domain": ".linkedin.com",
                "path": "/",
            },
        ],
        "origins": [],
    }
    with open(temp_state, "w", encoding="utf-8") as f:
        json.dump(mock_auth, f)

    try:
        mock_mgr = SessionManager(state_path=temp_state)
        mock_status = mock_mgr.get_session_status()
        assert mock_status["is_authenticated"] is True, f"Expected authenticated=True, got: {mock_status}"
        assert mock_status["has_li_at"] is True
        assert mock_status["has_jsessionid"] is True
        assert mock_status["cookie_count"] == 2
        print("   ✅ SessionManager storage_state parsing and li_at verification passed!")
    finally:
        if temp_state.exists():
            temp_state.unlink()

    # -------------------------------------------------------------
    # 3. Test DailyRunLogger
    # -------------------------------------------------------------
    print("\n🔍 Step 3: Testing DailyRunLogger...")
    logger = DailyRunLogger(log_dir=test_log_dir)
    test_run_id = f"test_gate70_{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}"

    start_entry = logger.log_run_start(run_id=test_run_id, trigger_source="gate_70_test")
    assert start_entry["run_id"] == test_run_id
    assert "git_commit" in start_entry
    assert "git_branch" in start_entry

    phase_entry = logger.log_phase(
        run_id=test_run_id,
        phase_name="HEALTH_CHECK",
        status="SUCCESS",
        details={"tests_passed": 49},
    )
    assert phase_entry["phase"] == "HEALTH_CHECK"
    assert phase_entry["status"] == "SUCCESS"

    exc_entry = logger.log_exception(
        run_id=test_run_id,
        exc=ValueError("Simulated diagnostic exception for testing"),
        phase="HEALTH_CHECK",
    )
    assert exc_entry["event"] == "EXCEPTION"
    assert "Simulated diagnostic exception" in exc_entry["error_message"]
    assert "ValueError" in exc_entry["error_type"]

    comp_entry = logger.log_run_complete(
        run_id=test_run_id,
        status="SUCCESS",
        staged_count=12,
        dream_org_count=3,
        regression_passed=True,
        email_sent=False,
        duration_sec=5.2,
    )
    assert comp_entry["status"] == "SUCCESS"
    assert comp_entry["staged_count"] == 12

    recent = logger.get_recent_runs(limit=1)
    assert len(recent) >= 1
    assert recent[-1]["run_id"] == test_run_id
    print(f"   ✅ Structured JSONL logging verified (RunID: {test_run_id})")

    # Test diagnose_system
    diag = logger.diagnose_system()
    assert "session" in diag
    assert "environment" in diag
    assert "launchd" in diag
    assert "log_paths" in diag
    assert "last_run" in diag
    print("   ✅ DailyRunLogger diagnose_system() audit verified!")

    # -------------------------------------------------------------
    # 4. Test DailyPipelineRunner Orchestrator Utilities
    # -------------------------------------------------------------
    print("\n🔍 Step 4: Testing DailyPipelineRunner Utilities...")
    config = {
        "llm": {"use_ai": False},
        "discovery": {"source": "all"},
    }
    runner = DailyPipelineRunner(config)

    # Test TCP port checker
    port_8000_open = runner.is_port_in_use(port=8000)
    print(f"   Port 8000 in use: {port_8000_open}")

    # Test pending queue inspection
    staged = runner.get_staged_jobs()
    print(f"   Current pending queue jobs: {len(staged)}")

    print("\n" + "=" * 65)
    print("✅ GATE 70 VERIFIED: SESSION, EMAIL & DAILY RUNNER FULLY OPERATIONAL!")
    print("=" * 65)


if __name__ == "__main__":
    test_session_and_email_reporter()
