import json
import os
import sys

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.filter.job_filter import LinkedInJobFilter
from src.scraper.job_finder import LinkedInJobFinder
from src.tailor.llm_provider import GeminiLLMProvider


def test_search_and_filter():
    print("==================================================")
    print("  Testing Sprint 6: Search & Filter Optimization")
    print("==================================================")

    # 1. Test Gemini Provider Auth Fix
    print("\n🔍 Step 1: Testing Gemini LLM Provider Auth Setup...")
    gemini = GeminiLLMProvider()
    print(f"   Gemini API Key Loaded: {bool(gemini.api_key)}")
    print(f"   Gemini Client Available: {gemini.is_available()}")
    assert gemini.is_available() is True
    print("✅ Gemini API Auth setup verified!")

    # 2. Test Job Deduplication Index
    print("\n🔍 Step 2: Testing Job Deduplication Engine...")
    test_db = os.path.join(os.path.dirname(__file__), "..", "data", "test_processed_jobs.json")
    finder = LinkedInJobFinder(use_ai=False, db_file=test_db)

    # Mark a job processed
    finder.mark_job_processed("job_dup_101", "NextGen AI", "Automation Engineer")

    # Check duplicates
    assert finder.is_duplicate("job_dup_101", "NextGen AI", "Automation Engineer") is True
    assert finder.is_duplicate("job_dup_999", "Other Corp", "SDET") is False
    print("✅ Deduplication logic (primary key + composite hash) verified!")

    # Clean test file
    if os.path.exists(test_db):
        os.remove(test_db)

    # 3. Test Standalone Job Filter Module
    print("\n🔍 Step 3: Testing Standalone Job Filter Module...")
    queue_dir = os.path.join(os.path.dirname(__file__), "..", "data", "test_pending_queue")
    os.makedirs(queue_dir, exist_ok=True)

    # Add 2 test job files (one qualified, one overqualified)
    qual_job = {
        "job_id": "job_qual_101",
        "application_type": "EASY_APPLY",
        "job_details": {
            "title": "Senior SDET Automation Engineer",
            "company": "FastTech",
            "requirements": "Looking for 5+ years experience in Python, Playwright, REST Assured automation.",
        },
    }
    over_job = {
        "job_id": "job_over_102",
        "application_type": "EASY_APPLY",
        "job_details": {
            "title": "Director of QA Engineering",
            "company": "MegaCorp",
            "requirements": "Requires 15+ years of experience leading global enterprise teams.",
        },
    }

    with open(os.path.join(queue_dir, "job_qual_101.json"), "w") as f:
        json.dump(qual_job, f)
    with open(os.path.join(queue_dir, "job_over_102.json"), "w") as f:
        json.dump(over_job, f)

    job_filter = LinkedInJobFilter(queue_dir=queue_dir)
    results = job_filter.filter_pending_queue()

    assert results["retained"] == 1
    assert results["filtered"] == 1
    assert not os.path.exists(os.path.join(queue_dir, "job_over_102.json"))
    assert os.path.exists(os.path.join(queue_dir, "job_qual_101.json"))
    print("✅ Job Filter successfully retained qualified job and removed overqualified job!")

    # Cleanup test queue
    if os.path.exists(os.path.join(queue_dir, "job_qual_101.json")):
        os.remove(os.path.join(queue_dir, "job_qual_101.json"))
    if os.path.exists(queue_dir):
        os.rmdir(queue_dir)

    print("\n" + "=" * 50)
    print("✅ SEARCH & FILTERING ARCHITECTURE VERIFIED SUCCESSFULLY!")
    print("=" * 50)


if __name__ == "__main__":
    test_search_and_filter()
