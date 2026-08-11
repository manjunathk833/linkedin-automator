from __future__ import annotations

import os
import sys

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scraper.job_finder import LinkedInJobFinder


def test_scraper_bug_fixes():
    print("==================================================")
    print("  Testing Job Finder Scraper & Recommended Feed Bug Fixes")
    print("==================================================")

    finder = LinkedInJobFinder(use_ai=False)

    # 1. Test Clean Keyword Outer Parentheses Stripping
    print("\n🔍 Step 1: Testing Outer Bracket Query Cleaning...")
    raw_query = '("Senior SDET" OR "Lead SDET" OR "Principal SDET")'
    url = finder.build_search_url(keywords=raw_query, location="Bengaluru")
    print(f"   Generated Search URL:\n   {url}")

    assert "%28%22Senior+SDET%22" not in url
    assert "keywords=%22Senior+SDET%22+OR+%22Lead+SDET%22+OR+%22Principal+SDET%22" in url
    print("✅ Search query brackets cleaned successfully (no literal outer brackets in URL or UI box)!")

    # 2. Test Instant Deduplication without DOM Navigation
    print("\n🔍 Step 2: Testing Instant Deduplication Check...")
    test_db = os.path.join(os.path.dirname(__file__), "..", "data", "test_bugfix_db.json")
    f_db = LinkedInJobFinder(use_ai=False, db_file=test_db)

    f_db.mark_job_processed("job_rec_99", "Alpha Systems", "Lead SDET")
    assert f_db.is_duplicate("job_rec_99", "Alpha Systems", "Lead SDET") is True
    print("✅ Instant deduplication check verified!")

    if os.path.exists(test_db):
        os.remove(test_db)

    print("\n" + "=" * 50)
    print("✅ SCRAPER BUG FIXES VERIFIED SUCCESSFULLY!")
    print("=" * 50)


if __name__ == "__main__":
    test_scraper_bug_fixes()
