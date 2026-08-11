from __future__ import annotations

import json
import os
import sys

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.filter.job_filter import LinkedInJobFilter


def test_job_filter_status_sync():
    print("==================================================")
    print("  Testing Job Filter Status Sync & Context Guard")
    print("==================================================")

    job_filter = LinkedInJobFilter()

    # 1. Test Context-Aware Experience Parsing
    print("\n🔍 Step 1: Testing Context-Aware Experience Parsing...")
    sample_text_1 = "Founded 20+ years ago with 15+ locations globally."
    sample_text_2 = "Requires 5+ years of hands-on SDET and API automation experience."

    years_1 = job_filter.parse_required_years(sample_text_1)
    years_2 = job_filter.parse_required_years(sample_text_2)

    print(f"   Company history snippet ('20+ years ago'): {years_1}")
    print(f"   Experience requirement snippet ('5+ years SDET'): {years_2}")

    assert len(years_1) == 0, "Failed: False positive match on company history years!"
    assert 5 in years_2, "Failed: Could not extract 5+ years experience!"
    print("✅ Context-aware experience regex parsing verified!")

    # 2. Test Status Synchronization in processed_jobs.json
    print("\n🔍 Step 2: Testing Status Synchronization Method...")
    temp_db = "data/test_processed_jobs_temp.json"
    temp_data = {"job_ids": {"test_job_1": {"title": "SDET", "company": "TestCo", "status": "PENDING"}}}
    with open(temp_db, "w") as f:
        json.dump(temp_data, f, indent=2)

    test_filter = LinkedInJobFilter(db_file=temp_db)
    test_filter.update_processed_jobs_status({"test_job_1": "RETAINED"})

    with open(temp_db, "r") as f:
        res = json.load(f)

    assert res["job_ids"]["test_job_1"]["status"] == "RETAINED"
    print("✅ Status synchronization method verified!")

    if os.path.exists(temp_db):
        os.remove(temp_db)

    print("\n" + "=" * 50)
    print("✅ JOB FILTER STATUS SYNC & CONTEXT GUARD VERIFIED SUCCESSFULLY!")
    print("=" * 50)


if __name__ == "__main__":
    test_job_filter_status_sync()
