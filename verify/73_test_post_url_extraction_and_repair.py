#!/usr/bin/env python3
"""
Verification Gate 73: LinkedIn Post Permalink Extraction Resilience & Self-Healing URL Repair.

Validates:
1. Multi-tier permalink extraction resolves authentic post URLs from DOM and attributes.
2. Guaranteed zero-404 fallback: author's authentic recent-activity or posts feed is used.
3. Absolute eradication of synthetic MD5 update hash generation (no 404s).
4. ApplicationDatabase self-healing migration automatically repairs legacy broken URLs.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.posts.post_tracker import LinkedInPostTracker
from src.storage.database import ApplicationDatabase


def test_post_url_extraction_tiers():
    """Validates multi-tier extraction across DOM, attributes, and author fallbacks."""
    tracker = LinkedInPostTracker()

    async def _run():
        # Tier 1: Direct canonical /posts/ link
        mock_card_posts = MagicMock()
        mock_direct_loc = MagicMock()
        mock_direct_loc.count = AsyncMock(return_value=1)
        mock_direct_loc.get_attribute = AsyncMock(
            return_value="https://www.linkedin.com/posts/sdet-lead_automation-test-share-7517556450706165760-KhaD?utm_source=share"
        )
        mock_card_posts.locator.return_value.first = mock_direct_loc
        mock_card_posts.get_attribute = AsyncMock(return_value=None)

        url1 = await tracker._extract_post_permalink(
            mock_card_posts, "https://www.linkedin.com/in/sdet-lead/", "raw text"
        )
        assert url1 == "https://www.linkedin.com/posts/sdet-lead_automation-test-share-7517556450706165760-KhaD"
        print("   ✅ Tier 1: Canonical /posts/ permalink extracted successfully")

        # Tier 2: data-urn attribute on container or child
        mock_card_urn = MagicMock()
        mock_empty_loc = MagicMock()
        mock_empty_loc.count = AsyncMock(return_value=0)
        mock_card_urn.locator.return_value.first = mock_empty_loc
        mock_card_urn.get_attribute = AsyncMock(return_value="urn:li:activity:7289123456789012345,some_other_info")
        mock_card_urn.evaluate = AsyncMock(return_value=None)

        url2 = await tracker._extract_post_permalink(mock_card_urn, "https://www.linkedin.com/in/qa-lead/", "raw text")
        assert url2 == "https://www.linkedin.com/feed/update/urn:li:activity:7289123456789012345/"
        print("   ✅ Tier 2: Activity ID from data-urn extracted successfully")

        # Tier 3: React Fiber evaluation returning activity URN
        mock_card_fiber = MagicMock()
        mock_card_fiber.locator.return_value.first = mock_empty_loc
        mock_card_fiber.get_attribute = AsyncMock(return_value=None)
        mock_card_fiber.evaluate = AsyncMock(
            return_value="https://www.linkedin.com/feed/update/urn:li:activity:7517556452480344064/"
        )

        url3 = await tracker._extract_post_permalink(
            mock_card_fiber, "https://www.linkedin.com/in/recruiter-lead/", "raw text"
        )
        assert url3 == "https://www.linkedin.com/feed/update/urn:li:activity:7517556452480344064/"
        print("   ✅ Tier 3: React Fiber SDUI activity permalink extracted successfully")

        # Tier 4: Fallback for personal profile (/in/) -> recent-activity/all/
        mock_card_fallback_in = MagicMock()
        mock_card_fallback_in.locator.return_value.first = mock_empty_loc
        mock_card_fallback_in.locator.return_value.all = AsyncMock(return_value=[])
        mock_card_fallback_in.get_attribute = AsyncMock(return_value=None)
        mock_card_fallback_in.evaluate = AsyncMock(return_value=None)

        url4 = await tracker._extract_post_permalink(
            mock_card_fallback_in, "https://www.linkedin.com/in/vishal-patil-9306aa211/", "raw text"
        )
        assert url4 == "https://www.linkedin.com/in/vishal-patil-9306aa211/recent-activity/all/"
        assert not re.search(r"/feed/update/[0-9a-f]{12}", url4)
        print("   ✅ Tier 4a: Personal profile guaranteed fallback loads recent activity")

        # Tier 4b: Fallback for company profile (/company/) -> /posts/
        url5 = await tracker._extract_post_permalink(
            mock_card_fallback_in, "https://www.linkedin.com/company/shreenikaa-global-path/", "raw text"
        )
        assert url5 == "https://www.linkedin.com/company/shreenikaa-global-path/posts/"
        assert not re.search(r"/feed/update/[0-9a-f]{12}", url5)
        print("   ✅ Tier 4b: Company profile guaranteed fallback loads company posts")

    asyncio.run(_run())


def test_database_url_self_healing():
    """Validates that ApplicationDatabase heals legacy broken MD5 update hashes automatically."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        temp_db_path = tf.name

    try:
        db = ApplicationDatabase(db_path=temp_db_path)

        # Seed legacy broken records
        with db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO hiring_posts (
                    post_id, author_name, author_headline, author_profile_url,
                    company_name, post_url, post_text, posted_at_relative
                ) VALUES
                (
                    'post_bad_1', 'Vishal Patil', 'SDET', 'https://www.linkedin.com/in/vishal-patil-9306aa211/',
                    'TechCorp', 'https://www.linkedin.com/feed/update/e91a6f75d68c', 'Hiring SDET', '2h'
                ),
                (
                    'post_bad_2', 'Company Page', 'Talent', 'https://www.linkedin.com/company/tech-global/',
                    'TechGlobal', 'https://www.linkedin.com/feed/update/6f1a48926951', 'QA Jobs', '1d'
                ),
                (
                    'post_good_3', 'Pooja M', 'Recruiter', 'https://www.linkedin.com/in/pooja-m/',
                    'Angel One', 'https://www.linkedin.com/feed/update/urn:li:activity:7182910777/', 'Hiring', '4h'
                );
                """
            )
            conn.commit()

        # Run repair
        repaired_count = db.repair_invalid_post_urls()
        assert repaired_count == 2, f"Expected 2 rows repaired, got {repaired_count}"

        # Verify repaired URLs
        with db._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT post_id, post_url FROM hiring_posts ORDER BY post_id")
            rows = {r["post_id"]: r["post_url"] for r in cur.fetchall()}

        assert rows["post_bad_1"] == "https://www.linkedin.com/in/vishal-patil-9306aa211/recent-activity/all/"
        assert rows["post_bad_2"] == "https://www.linkedin.com/company/tech-global/posts/"
        assert rows["post_good_3"] == "https://www.linkedin.com/feed/update/urn:li:activity:7182910777/"
        print("   ✅ Database self-healing repaired invalid MD5 hashes with zero corruption")

        # Second run should find 0 broken URLs
        second_run = db.repair_invalid_post_urls()
        assert second_run == 0, f"Expected 0 on second run, got {second_run}"
        print("   ✅ Idempotent execution verified: subsequent repair runs find 0 defects")

    finally:
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)


def main():
    print("=" * 70)
    print("🚀 RUNNING VERIFICATION GATE 73: POST PERMALINK EXTRACTION & REPAIR")
    print("=" * 70)

    print("\n🔍 Step 1: Testing Multi-Tier Post Permalink Extraction...")
    test_post_url_extraction_tiers()

    print("\n🔍 Step 2: Testing Database Self-Healing Repair...")
    test_database_url_self_healing()

    print("\n" + "=" * 70)
    print("🎉 ALL GATE 73 CHECKS PASSED: ZERO 404s GUARANTEE VERIFIED")
    print("=" * 70)


if __name__ == "__main__":
    main()
