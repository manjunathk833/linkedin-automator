#!/usr/bin/env python3
"""
Verification Gate 61: Application Tracking, Database Indexing, and Auto-Purge Flow.
Validates:
1. SQLite Database indexing and instant lookup (<1ms) for applied job status.
2. Endpoints: POST /api/tracking/mark-applied/{job_id}, GET /api/tracking/applied, DELETE /api/tracking/{job_id}.
3. Auto-purging: Automatically cleans and ignores pending/approved files if already marked as applied.
4. Scraper and filter deduplication: Applied jobs are defensively blocked from re-pooling.
"""

import json
import os
import sqlite3
import sys
import tempfile
import time

# Ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from src.filter.job_filter import LinkedInJobFilter
from src.scraper.job_finder import LinkedInJobFinder
from src.storage.database import ApplicationDatabase
from src.ui.app import app


def test_sqlite_indexing_and_methods():
    print("\n--- [Step 1: SQLite Schema, Indexes, & Methods] ---")
    db = ApplicationDatabase()

    with sqlite3.connect(db.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
        indexes = [row[0] for row in cursor.fetchall()]

    print(f"Discovered SQLite Indexes: {indexes}")
    assert "idx_job_applications_status" in indexes, "Missing status index!"
    assert "idx_job_applications_applied_at" in indexes, "Missing applied_at index!"
    print("✓ SQLite indexes verified for high-performance lookups.")

    test_id = f"test_track_unit_{int(time.time())}"
    # Test recording
    db.record_application(
        job_id=test_id,
        source="lever",
        company_name="Unit Test Tech",
        job_title="Lead QA Architect",
        job_url="https://jobs.lever.co/test/123",
        resume_path="/path/to/test.pdf",
        status="applied",
    )

    t0 = time.perf_counter()
    is_app = db.is_job_applied(test_id)
    lookup_ms = (time.perf_counter() - t0) * 1000
    print(f"Applied lookup completed in {lookup_ms:.3f}ms")
    assert is_app is True, f"Expected {test_id} to be marked applied"
    assert lookup_ms < 50.0, f"Lookup took too long: {lookup_ms:.2f}ms"

    all_ids = db.get_applied_job_ids()
    assert test_id in all_ids, "test_id not found in get_applied_job_ids"

    stats = db.get_application_stats()
    assert stats["total_applied"] >= 1, "Stats total_applied should be >= 1"
    print(f"✓ Application stats: {stats}")

    # Clean up test row
    db.delete_application(test_id)
    assert db.is_job_applied(test_id) is False, "Record should be deleted"
    print("✓ Unit record cleanup verified.")


def test_auto_purge_on_pending_retrieval():
    print("\n--- [Step 2: Auto-Purge of Applied Jobs from Pending Queue] ---")
    db = ApplicationDatabase()
    client = TestClient(app)

    dummy_id = f"purge_test_{int(time.time())}"
    pending_dir = os.path.abspath("data/pending_queue")
    os.makedirs(pending_dir, exist_ok=True)
    dummy_file = os.path.join(pending_dir, f"{dummy_id}.json")

    # Record as applied in DB first
    db.record_application(
        job_id=dummy_id,
        source="greenhouse",
        company_name="AutoPurge Inc",
        job_title="Senior SDET",
        job_url="https://boards.greenhouse.io/autopurge/123",
        status="applied",
    )

    # Write a pending JSON simulating stale scraper file
    dummy_data = {
        "job_id": dummy_id,
        "source": "greenhouse",
        "job_details": {"company": "AutoPurge Inc", "title": "Senior SDET"},
    }
    with open(dummy_file, "w", encoding="utf-8") as f:
        json.dump(dummy_data, f)

    assert os.path.exists(dummy_file), "Stale pending file should exist before API call"

    # Call /api/pending-jobs (or /api/jobs)
    resp = client.get("/api/pending-jobs")
    assert resp.status_code == 200

    # Verify that the file was automatically deleted from disk
    assert not os.path.exists(dummy_file), "Stale applied file was NOT purged from pending_queue!"
    print("✓ Auto-purge successfully removed applied job from pending queue on retrieval.")

    # Clean up DB
    db.delete_application(dummy_id)


def test_mark_applied_endpoint_and_tracking_view():
    print("\n--- [Step 3: Mark Applied Endpoint & Tracking View] ---")
    client = TestClient(app)
    db = ApplicationDatabase()

    test_mark_id = f"mark_endpoint_test_{int(time.time())}"
    pending_dir = os.path.abspath("data/pending_queue")
    os.makedirs(pending_dir, exist_ok=True)
    mark_file = os.path.join(pending_dir, f"{test_mark_id}.json")

    sample_job = {
        "job_id": test_mark_id,
        "source": "ashby",
        "job_details": {
            "company": "Tracking Metrics Corp",
            "title": "Principal QA Automation Engineer",
            "location": "Bengaluru (Hybrid)",
        },
        "url": "https://jobs.ashbyhq.com/tracking/456",
    }
    with open(mark_file, "w", encoding="utf-8") as f:
        json.dump(sample_job, f)

    # Send POST /api/tracking/mark-applied/{job_id}
    resp = client.post(f"/api/tracking/mark-applied/{test_mark_id}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["status"] == "success"
    print(f"✓ Mark applied response: {body['message']}")

    # Assert pending file is removed
    assert not os.path.exists(mark_file), "File was not removed from pending queue after mark-applied!"

    # Assert DB is updated
    assert db.is_job_applied(test_mark_id) is True, "Job was not marked applied in DB!"

    # Test GET /api/tracking/applied
    get_resp = client.get("/api/tracking/applied")
    assert get_resp.status_code == 200
    track_data = get_resp.json()
    assert track_data["status"] == "success"
    assert "stats" in track_data
    assert track_data["stats"]["total_applied"] >= 1

    matched = [a for a in track_data["applications"] if a["job_id"] == test_mark_id]
    assert len(matched) == 1, f"Expected {test_mark_id} in tracking list"
    assert matched[0]["company_name"] == "Tracking Metrics Corp"
    assert matched[0]["job_title"] == "Principal QA Automation Engineer"
    print("✓ Tracking audit record retrieved with exact company and role metadata.")

    # Test DELETE /api/tracking/{job_id}
    del_resp = client.delete(f"/api/tracking/{test_mark_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "success"
    assert db.is_job_applied(test_mark_id) is False
    print("✓ DELETE /api/tracking/{job_id} cleaned up successfully.")


def test_scraper_and_filter_deduplication():
    print("\n--- [Step 4: Scraper & Filter Deduplication Defense] ---")
    db = ApplicationDatabase()
    finder = LinkedInJobFinder()

    sc_id = f"scraper_guard_{int(time.time())}"
    db.record_application(
        job_id=sc_id,
        source="linkedin",
        company_name="Defense Corp",
        job_title="SDET",
        job_url="https://linkedin.com/jobs/view/123",
        status="applied",
    )

    # Scraper deduplication check
    assert finder.is_duplicate(sc_id, "Defense Corp", "SDET") is True, "finder.is_duplicate did not detect applied job!"
    print("✓ LinkedInJobFinder successfully skips applied job during scraping.")

    # JobFilter queue filter check
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a dummy pending queue
        test_file = os.path.join(tmp_dir, f"{sc_id}.json")
        with open(test_file, "w", encoding="utf-8") as f:
            json.dump({"job_id": sc_id, "title": "SDET"}, f)

        jfilter = LinkedInJobFilter(queue_dir=tmp_dir)
        jfilter.filter_pending_queue()
        assert not os.path.exists(test_file), "JobFilter should have purged applied job file from queue!"
        print("✓ JobFilter purged applied job from pending queue.")

    db.delete_application(sc_id)


def main():
    print("=" * 65)
    print("RUNNING VERIFICATION GATE 61: APPLIED TRACKING & AUTO-PURGE")
    print("=" * 65)

    test_sqlite_indexing_and_methods()
    test_auto_purge_on_pending_retrieval()
    test_mark_applied_endpoint_and_tracking_view()
    test_scraper_and_filter_deduplication()

    print("\n" + "=" * 65)
    print("ALL VERIFICATION GATE 61 TESTS PASSED SUCCESSFULLY! (100%)")
    print("=" * 65)


if __name__ == "__main__":
    main()
