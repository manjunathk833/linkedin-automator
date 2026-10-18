#!/usr/bin/env python3
"""
Verification Gate 75: LinkedIn Post Text Formatting & Permalink Extraction Resilience.

Validates:
1. Post text sanitization cleanly isolates post commentary from author metadata headers
   (author name, connection degree, headline, timestamp, Follow/Connect buttons).
2. Natural formatting, block layout, and paragraph line breaks (\\n\\n) are strictly preserved.
3. Trailing reaction junk ('… more5 reactions') and expansion toggles ('… see more') are stripped.
4. Multi-tier permalink extraction resolves authentic post URLs across:
   - data-chameleon-result-urn (LinkedIn search content result containers)
   - data-urn with ugcPost and share URN variants
   - Relative timestamp anchors (/feed/update/urn:li:activity:...)
   - Guaranteed zero-404 author feed fallbacks.
5. SQLite self-healing migration cleans legacy records in hiring_posts.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.posts.post_tracker import LinkedInPostTracker, sanitize_post_text
from src.storage.database import ApplicationDatabase


def test_sanitize_post_text_author_headers():
    """Validates that author headers are stripped and post commentary is isolated."""
    # Sample 1: Vishal Patil (real scraped post from Content Search)
    t1 = (
        "VISHAL PATIL  • 2ndQuality Engineering Specialist | Helping IT professionals get referrals | "
        "Follow for daily job updates.2h • Connect🚀 Blitz is Hiring SDET-1 (1–2 years) & SDET-2 (3–5 years) | Bangalore"
        "📌 Job OverviewCompany: Blitz"
    )
    res1 = sanitize_post_text(t1, author_name="VISHAL PATIL")
    assert res1.startswith("🚀 Blitz is Hiring SDET-1"), f"Failed on t1: {res1[:60]}"
    assert "VISHAL PATIL" not in res1
    assert "Connect" not in res1
    assert "2h •" not in res1
    print("   ✅ Sample 1: Vishal Patil author header successfully stripped")

    # Sample 2: Callum Baker
    t2 = (
        "Callum Baker • 3rd+Senior Human Resources Recruiter at Jobs in Germany & USA40m • Follow"
        "🚨 WE ARE HIRING – REMOTE POSITIONS AVAILABLE | USA & UK"
    )
    res2 = sanitize_post_text(t2, author_name="Callum Baker")
    assert res2.startswith("🚨 WE ARE HIRING"), f"Failed on t2: {res2[:60]}"
    assert "Callum Baker" not in res2
    assert "Follow" not in res2
    print("   ✅ Sample 2: Callum Baker author header successfully stripped")

    # Sample 3: Company post (Velion IT)
    t3 = "Velion IT consulting PVT LTD3h • Follow🚨 **URGENT HIRING | SDET – TOSCA / SELENIUM / JAVA / AI** 🚨"
    res3 = sanitize_post_text(t3, author_name="Velion IT consulting PVT LTD")
    assert res3.startswith("🚨 **URGENT HIRING"), f"Failed on t3: {res3[:60]}"
    assert "Velion IT" not in res3
    print("   ✅ Sample 3: Company post header successfully stripped")

    # Sample 4: Already clean post with numbers and follow keyword
    t4 = (
        "🚀 Blitz is Hiring SDET-1!\n\n"
        "Requirements:\n"
        "• 2h daily overlap with US team\n"
        "• Follow our standard testing practices\n"
        "• 3-5 years automation experience\n\n"
        "Apply at https://blitz.io/jobs"
    )
    res4 = sanitize_post_text(t4, author_name="VISHAL PATIL")
    assert res4 == t4, f"Clean post was improperly modified: {res4}"
    assert "\n\n" in res4, "Paragraph line breaks must be preserved"
    print("   ✅ Sample 4: Clean post with formatting and natural text preserved 100%")


def test_sanitize_trailing_reactions_and_toggles():
    """Validates stripping of trailing reaction counts, zero-width spaces, and see-more toggles."""
    raw = "🚀 Blitz is Hiring SDETs!\n\nApply here: https://jobviareferral.com… more5\u200b\u200b\u200b5 reactions"
    cleaned = sanitize_post_text(raw, author_name="")
    assert cleaned.endswith("https://jobviareferral.com"), f"Trailing reactions not cleaned: {cleaned}"
    assert "reactions" not in cleaned
    assert "… more" not in cleaned
    print("   ✅ Trailing reaction junk and see-more toggles stripped cleanly")


def test_multi_tier_permalink_extraction():
    """Validates permalink extraction across data-chameleon-result-urn, ugcPost, and relative links."""
    tracker = LinkedInPostTracker()

    async def _run():
        # Tier 1: data-chameleon-result-urn on container
        mock_card_cham = MagicMock()
        mock_empty_loc = MagicMock()
        mock_empty_loc.count = AsyncMock(return_value=0)
        mock_empty_loc.all = AsyncMock(return_value=[])
        mock_card_cham.locator.return_value = mock_empty_loc
        mock_card_cham.get_attribute = AsyncMock(
            side_effect=lambda attr: (
                "urn:li:activity:7289123456789012345" if attr == "data-chameleon-result-urn" else None
            )
        )
        mock_card_cham.evaluate = AsyncMock(return_value=None)

        url1 = await tracker._extract_post_permalink(
            mock_card_cham, "https://www.linkedin.com/in/vishal-patil-9306aa211/", "raw text"
        )
        assert url1 == "https://www.linkedin.com/feed/update/urn:li:activity:7289123456789012345/"
        print("   ✅ Tier 1: data-chameleon-result-urn resolved to direct post permalink")

        # Tier 2: data-urn with ugcPost
        mock_card_ugc = MagicMock()
        mock_card_ugc.locator.return_value = mock_empty_loc
        mock_card_ugc.get_attribute = AsyncMock(
            side_effect=lambda attr: "urn:li:ugcPost:7299888777666555444" if attr == "data-urn" else None
        )
        mock_card_ugc.evaluate = AsyncMock(return_value=None)

        url2 = await tracker._extract_post_permalink(mock_card_ugc, "https://www.linkedin.com/in/qa-lead/", "raw text")
        assert url2 == "https://www.linkedin.com/feed/update/urn:li:activity:7299888777666555444/"
        print("   ✅ Tier 2: ugcPost URN resolved to direct post permalink")

        # Tier 3: Relative timestamp anchor href
        mock_card_anchor = MagicMock()
        mock_anchor_loc = MagicMock()
        mock_anchor_loc.get_attribute = AsyncMock(
            return_value="/feed/update/urn:li:activity:7311222333444555666?updateEntityUrn=urn%3Ali%3Aactivity%3A7311222333444555666"
        )
        mock_anchors_list = MagicMock()
        mock_anchors_list.all = AsyncMock(return_value=[mock_anchor_loc])
        mock_anchors_list.count = AsyncMock(return_value=1)
        mock_card_anchor.locator.return_value = mock_anchors_list
        mock_card_anchor.get_attribute = AsyncMock(return_value=None)
        mock_card_anchor.evaluate = AsyncMock(return_value=None)

        url3 = await tracker._extract_post_permalink(
            mock_card_anchor, "https://www.linkedin.com/in/recruiter-lead/", "raw text"
        )
        assert url3 == "https://www.linkedin.com/feed/update/urn:li:activity:7311222333444555666/"
        print("   ✅ Tier 3: Relative timestamp anchor resolved to direct post permalink")

        # Tier 4: Fallback to author recent activity
        mock_card_fallback = MagicMock()
        mock_card_fallback.locator.return_value = mock_empty_loc
        mock_card_fallback.get_attribute = AsyncMock(return_value=None)
        mock_card_fallback.evaluate = AsyncMock(return_value=None)

        url4 = await tracker._extract_post_permalink(
            mock_card_fallback, "https://www.linkedin.com/in/vishal-patil-9306aa211/", "raw text"
        )
        assert url4 == "https://www.linkedin.com/in/vishal-patil-9306aa211/recent-activity/all/"
        print("   ✅ Tier 4: Guaranteed fallback to author activity feed (zero 404s)")

    asyncio.run(_run())


def test_database_self_healing_migration():
    """Validates that ApplicationDatabase cleans post_text on existing records."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        temp_db_path = tf.name

    try:
        db = ApplicationDatabase(db_path=temp_db_path)

        # Seed record with polluted author header and trailing reactions
        with db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO hiring_posts (
                    post_id, author_name, author_headline, author_profile_url,
                    company_name, post_url, post_text, posted_at_relative
                ) VALUES
                (
                    'post_polluted_1', 'VISHAL PATIL', 'Quality Specialist',
                    'https://www.linkedin.com/in/vishal-patil-9306aa211/',
                    'Blitz', 'https://www.linkedin.com/in/vishal-patil-9306aa211/recent-activity/all/',
                    'VISHAL PATIL  • 2ndQuality Specialist2h • Connect🚀 Blitz is Hiring SDET-1 (1–2 years) | Bangalore Apply: https://jobviareferral.com… more5 reactions',
                    '2h'
                )
                """
            )
            conn.commit()

        # Run database repair
        db.repair_posts_metadata_and_links()

        with db._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT post_text FROM hiring_posts WHERE post_id = 'post_polluted_1'")
            row = cur.fetchone()
            assert row is not None
            cleaned_text = row[0]
            assert cleaned_text.startswith("🚀 Blitz is Hiring SDET-1"), f"DB not cleaned: {cleaned_text}"
            assert "VISHAL PATIL" not in cleaned_text
            assert "Connect" not in cleaned_text
            assert "reactions" not in cleaned_text
            print("   ✅ Database self-healing: existing post text successfully sanitized in SQLite")

    finally:
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)


if __name__ == "__main__":
    print("\n🔍 Running Verification Gate 75: Post Formatting & Permalink Resilience...")
    test_sanitize_post_text_author_headers()
    test_sanitize_trailing_reactions_and_toggles()
    test_multi_tier_permalink_extraction()
    test_database_self_healing_migration()
    print("\n🏆 Verification Gate 75: 100% SUCCESS — All tests passed cleanly.\n")
