#!/usr/bin/env python3
"""
Verification Gate 85: Full-Lifecycle Funnel Tracking, Attribution & Stealth Hardening.
=====================================================================================
Validates:
1. SQLite schema extension with 7 lifecycle & funnel attribution columns.
2. update_funnel_stage() transitions across valid stages (APPLIED, RECRUITER_SCREEN, TECH_ROUND_1, OFFER).
3. get_funnel_metrics() calculation of application-to-screen conversion rate.
4. FastAPI REST endpoints: POST /api/tracking/update-stage/{job_id} and GET /api/tracking/funnel-metrics.
5. cdp_connector persistent browser launch incorporates STEALTH_EVASION_JS.
6. scripts/run_daily_prod.sh contains network wait loop and caffeinate sleep prevention.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.storage.database import ApplicationDatabase


def test_sqlite_funnel_schema_and_columns():
    """Validates that ApplicationDatabase migrates and exposes all 7 funnel tracking columns."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_app.db")
        ApplicationDatabase(db_path=db_path)

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(job_applications);")
            columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            "id",
            "source",
            "company_name",
            "job_title",
            "job_url",
            "resume_path",
            "tailored_data_json",
            "screening_qa_json",
            "applied_at",
            "status",
            "discovery_track",
            "discovery_channel",
            "application_mode",
            "funnel_stage",
            "last_stage_update",
            "recruiter_contact",
            "notes",
        }
        for col in expected_columns:
            assert col in columns, f"Column '{col}' missing from job_applications schema."


def test_record_application_with_track_deduction_and_funnel_transitions():
    """Validates record_application track deduction and update_funnel_stage lifecycle updates."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_app.db")
        db = ApplicationDatabase(db_path=db_path)

        # 1. Record an application with automatic track deduction
        db.record_application(
            job_id="greenhouse_test_123",
            source="greenhouse",
            company_name="Zscaler",
            job_title="Staff SDET",
            job_url="https://boards.greenhouse.io/zscaler/jobs/123",
            status="applied",
        )

        app = db.get_application("greenhouse_test_123")
        assert app is not None
        assert app["discovery_track"] == "TRACK_1_DIRECT_ATS"
        assert app["funnel_stage"] == "APPLIED"

        # 2. Transition stage to RECRUITER_SCREEN
        success = db.update_funnel_stage(
            job_id="greenhouse_test_123",
            new_stage="RECRUITER_SCREEN",
            notes="30-min recruiter intro scheduled via Calendly",
            recruiter_contact="Jane Doe (jane@zscaler.com)",
        )
        assert success is True

        app_updated = db.get_application("greenhouse_test_123")
        assert app_updated["funnel_stage"] == "RECRUITER_SCREEN"
        assert "Jane Doe" in app_updated["recruiter_contact"]
        assert "Calendly" in app_updated["notes"]

        # 3. Add second application that remains APPLIED
        db.record_application(
            job_id="linkedin_test_456",
            source="linkedin",
            company_name="Swiggy",
            job_title="Lead SDET",
            job_url="https://linkedin.com/jobs/view/456",
            status="applied",
        )

        # 4. Check funnel metrics
        metrics = db.get_funnel_metrics()
        assert metrics["total_applications"] == 2
        assert metrics["stages"].get("RECRUITER_SCREEN") == 1
        assert metrics["stages"].get("APPLIED") == 1
        assert metrics["total_interviews_or_screens"] == 1
        assert metrics["application_to_screen_rate_pct"] == 50.0
        assert "channels" in metrics
        assert "application_modes" in metrics


def test_repair_application_funnel_attribution_and_dict_coercion():
    """Validates retroactive attribution backfill and dict-coercion guard when routing_strategy dict is passed."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_backfill.db")
        db = ApplicationDatabase(db_path=db_path)

        # Simulate legacy row that received default TRACK_2_LINKEDIN on ALTER TABLE despite source='greenhouse'
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO job_applications (
                    id, source, company_name, job_title, job_url,
                    resume_path, tailored_data_json, status, discovery_track, discovery_channel, application_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    "legacy_gh_001",
                    "greenhouse",
                    "Datadog",
                    "Senior QA Engineer",
                    "https://boards.greenhouse.io/datadog/jobs/001",
                    "",
                    "{}",
                    "applied_manual",
                    "TRACK_2_LINKEDIN",
                    "search",
                    "batch_autofill",
                ),
            )
            conn.commit()

        # Run repair migration
        db.repair_application_funnel_attribution()
        repaired = db.get_application("legacy_gh_001")
        assert repaired["discovery_track"] == "TRACK_1_DIRECT_ATS"
        assert repaired["discovery_channel"] == "greenhouse"
        assert repaired["application_mode"] == "manual_takeover"

        # Test dict-coercion guard when routing_strategy dict is accidentally passed as discovery_track
        db.record_application(
            job_id="ashby_dict_test_002",
            source="ashby",
            company_name="Linear",
            job_title="Staff SDET",
            job_url="https://jobs.ashbyhq.com/linear/002",
            discovery_track={"routing_tier": "TIER_1_SNIPER_APPLY"},  # type: ignore[arg-type]
        )
        coerced = db.get_application("ashby_dict_test_002")
        assert coerced["discovery_track"] == "TRACK_1_DIRECT_ATS"
        assert coerced["discovery_channel"] == "ashby"


def test_fastapi_stage_update_and_metrics_endpoints():
    """Validates POST /api/tracking/update-stage/{job_id} and GET /api/tracking/funnel-metrics."""
    from fastapi.testclient import TestClient

    from src.ui.app import app

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_ui.db")
        test_db = ApplicationDatabase(db_path=db_path)
        test_db.record_application(
            job_id="postman_sdet_789",
            source="linkedin",
            company_name="Postman",
            job_title="Senior SDET",
            job_url="https://linkedin.com/jobs/view/789",
            status="applied",
        )

        with patch("src.storage.database.ApplicationDatabase", return_value=test_db):
            client = TestClient(app)

            # Test stage update
            res = client.post(
                "/api/tracking/update-stage/postman_sdet_789",
                json={"stage": "TECH_ROUND_1", "notes": "Hands-on Playwright framework coding round"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "success"
            assert data["funnel_stage"] == "TECH_ROUND_1"

            # Test metrics retrieval
            m_res = client.get("/api/tracking/funnel-metrics")
            assert m_res.status_code == 200
            m_data = m_res.json()["metrics"]
            assert m_data["total_applications"] == 1
            assert m_data["stages"]["TECH_ROUND_1"] == 1
            assert m_data["application_to_screen_rate_pct"] == 100.0


def test_cdp_connector_incorporates_stealth():
    """Verifies that launch_persistent_browser in cdp_connector injects STEALTH_EVASION_JS and --headless=new."""
    import inspect

    from src.browser.cdp_connector import launch_persistent_browser

    source = inspect.getsource(launch_persistent_browser)
    assert "STEALTH_EVASION_JS" in source
    assert "add_init_script" in source
    assert "--disable-infobars" in source
    assert "--no-first-run" in source
    assert "--headless=new" in source
    assert "clean_stale_browser_processes" in source


def test_run_daily_prod_network_and_sleep_guards():
    """Verifies that scripts/run_daily_prod.sh contains the 90s network retry check and caffeinate wrapper."""
    prod_script = PROJECT_ROOT / "scripts" / "run_daily_prod.sh"
    assert prod_script.exists()
    content = prod_script.read_text(encoding="utf-8")

    assert "18" in content, "Expected 18 attempts for 90s network wait loop"
    assert "EX_TEMPFAIL" in content or "75" in content, "Expected exit code 75 on network timeout"
    assert "caffeinate" in content, "Expected caffeinate sleep prevention wrapper"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
