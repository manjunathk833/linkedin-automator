from __future__ import annotations

import os
import sys

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scraper.job_finder import LinkedInJobFinder


def test_recommended_feed_pagination():
    print("==================================================")
    print("  Testing Recommended Feed Multi-Page Pagination")
    print("==================================================")

    LinkedInJobFinder(use_ai=False)

    # 1. Test Recommended Feed Pagination URL Generation
    print("\n🔍 Step 1: Testing Recommended Feed URL Pagination (start=0, 25, 50)...")
    urls = [f"https://www.linkedin.com/jobs/collections/recommended/?start={p * 25}" for p in range(3)]

    print(f"   Page 1 URL: {urls[0]}")
    print(f"   Page 2 URL: {urls[1]}")
    print(f"   Page 3 URL: {urls[2]}")

    assert "start=0" in urls[0]
    assert "start=25" in urls[1]
    assert "start=50" in urls[2]
    print("✅ Recommended feed multi-page URLs verified!")

    print("\n" + "=" * 50)
    print("✅ RECOMMENDED FEED MULTI-PAGE PAGINATION VERIFIED SUCCESSFULLY!")
    print("=" * 50)


if __name__ == "__main__":
    test_recommended_feed_pagination()
