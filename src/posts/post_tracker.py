"""
LinkedIn Post Tracker & Inbound Lead Discovery Engine (Track 3).
Scrapes, classifies, and tracks hiring updates and referral opportunities from
recruiter, engineering lead, and peer posts across LinkedIn Content Search
and Candidate Activity.
"""

from __future__ import annotations

import asyncio
import hashlib
import urllib.parse
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

from src.browser.cdp_connector import DEFAULT_PROFILE_DIR, launch_persistent_browser
from src.posts.outreach_composer import PostOutreachComposer
from src.posts.post_classifier import PostClassifier
from src.storage.database import ApplicationDatabase

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STORAGE_STATE = PROJECT_ROOT / ".browser_data" / "storage_state.json"

DEFAULT_SEARCH_QUERIES = [
    '("hiring" OR "looking for") AND ("SDET" OR "QA" OR "Automation") AND ("India" OR "Bengaluru" OR "Bangalore" OR "Remote")',
    '("my team is hiring" OR "we are hiring" OR "open roles") AND ("SDET" OR "Lead SDET" OR "QA Automation")',
    '("referral" OR "referrals" OR "dm for referral" OR "openings") AND ("SDET" OR "QA" OR "SET") AND ("India" OR "Bengaluru")',
    '("looking for SDET" OR "looking for QA" OR "hiring SDET") AND ("India" OR "Bengaluru" OR "Remote")',
]


class LinkedInPostTracker:
    """
    Automated discovery engine for LinkedIn hiring & referral posts.
    """

    def __init__(self, db: ApplicationDatabase | None = None):
        self.db = db or ApplicationDatabase()
        self.classifier = PostClassifier()
        self.composer = PostOutreachComposer()

    async def _extract_post_from_card(self, card: Any, page: Any) -> dict[str, Any] | None:
        """Extracts text, author, and links from a single DOM update card."""
        try:
            # 1. Expand '...see more' if present
            see_more = card.locator(
                ".feed-shared-inline-show-more-text__see-more-less-toggle, button:has-text('see more')"
            ).first
            if await see_more.count() > 0 and await see_more.is_visible():
                try:
                    await see_more.click(timeout=1000)
                    await asyncio.sleep(0.2)
                except Exception:
                    pass

            # 2. Extract Author details
            author_name_loc = card.locator(
                ".update-components-actor__name, .feed-shared-actor__name, a[data-field='actor_name']"
            ).first
            author_name = (
                (await author_name_loc.text_content()).strip() if await author_name_loc.count() > 0 else "Unknown"
            )

            author_title_loc = card.locator(
                ".update-components-actor__description, .feed-shared-actor__description, .update-components-actor__headline"
            ).first
            author_headline = (
                (await author_title_loc.text_content()).strip() if await author_title_loc.count() > 0 else ""
            )

            author_link_loc = card.locator("a[href*='/in/']").first
            author_url = (
                (await author_link_loc.get_attribute("href") or "").split("?")[0]
                if await author_link_loc.count() > 0
                else ""
            )

            # 3. Extract Post text
            text_loc = card.locator(
                ".feed-shared-update-v2__description, .feed-shared-text, .update-components-text"
            ).first
            text_content = (await text_loc.text_content()).strip() if await text_loc.count() > 0 else ""
            if len(text_content) < 25:
                return None

            # 4. Extract relative timestamp
            time_loc = card.locator(
                ".update-components-actor__sub-description, .feed-shared-actor__sub-description, time"
            ).first
            posted_time = (await time_loc.text_content()).strip() if await time_loc.count() > 0 else ""
            relative_time = posted_time.split("•")[0].strip() if "•" in posted_time else posted_time

            # 5. Extract Post permalink / URN
            post_urn = await card.get_attribute("data-urn") or ""
            post_url = ""
            if "activity:" in post_urn:
                activity_id = post_urn.split("activity:")[1].split(",")[0]
                post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"
            else:
                link_loc = card.locator("a[href*='/feed/update/urn:li:activity']").first
                if await link_loc.count() > 0:
                    post_url = (await link_loc.get_attribute("href") or "").split("?")[0]

            if not post_url:
                post_hash = hashlib.md5((author_name + text_content[:100]).encode("utf-8")).hexdigest()[:12]
                post_url = f"https://www.linkedin.com/feed/update/{post_hash}"

            raw_post = {
                "author_name": author_name,
                "author_headline": author_headline,
                "author_profile_url": author_url,
                "post_url": post_url,
                "post_text": text_content,
                "posted_at_relative": relative_time,
            }

            # 6. Classify and enrich
            processed = self.classifier.process_raw_post(raw_post)
            if not processed:
                return None

            # 7. Generate personalized outreach drafts
            processed["custom_dm_draft"] = self.composer.generate_connection_note(processed)
            processed["custom_inmail_draft"] = self.composer.generate_inmail_pitch(processed)

            return processed
        except Exception:
            return None

    async def discover_posts(
        self,
        queries: list[str] | None = None,
        date_filter: str = "past-24h",
        max_scrolls: int = 4,
        headless: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Executes search on LinkedIn /search/results/content/ and collects qualified posts.
        """
        target_queries = queries or DEFAULT_SEARCH_QUERIES
        discovered_leads: list[dict[str, Any]] = []

        async with async_playwright() as p:
            context, page = await launch_persistent_browser(p, profile_dir=str(DEFAULT_PROFILE_DIR), headless=headless)
            print(f"🚀 Launching LinkedIn Posts Tracker (Headless: {headless})")

            try:
                for q_idx, query in enumerate(target_queries):
                    encoded_query = urllib.parse.quote(query)
                    url = (
                        f"https://www.linkedin.com/search/results/content/?"
                        f"datePosted=%22{date_filter}%22&keywords={encoded_query}&sortBy=%22date_posted%22"
                    )
                    print(f"\n🔍 [Query {q_idx + 1}/{len(target_queries)}] Searching: {query[:60]}...")
                    print(f"🌐 URL: {url}")

                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=35000)
                        await asyncio.sleep(3.0)

                        # Progressive smooth scrolls to hydrate feed updates
                        for s in range(max_scrolls):
                            await page.evaluate("window.scrollBy(0, 900)")
                            await asyncio.sleep(1.8)

                        # Match modern card locators
                        cards_loc = page.locator(
                            ".feed-shared-update-v2, .occludable-update, "
                            "div[data-view-name*='search-entity-result'], "
                            ".artdeco-card:has(.feed-shared-text, .update-components-text)"
                        )
                        card_count = await cards_loc.count()
                        print(f"📦 Scanned {card_count} raw feed update(s).")

                        for c_idx in range(card_count):
                            card = cards_loc.nth(c_idx)
                            post_lead = await self._extract_post_from_card(card, page)
                            if post_lead:
                                post_id = post_lead["post_id"]
                                if not self.db.is_hiring_post_saved(post_id):
                                    self.db.save_hiring_post(post_lead)
                                    discovered_leads.append(post_lead)
                                    author = post_lead["author_name"]
                                    company = post_lead["company_name"]
                                    role_cat = post_lead["author_role_category"]
                                    score = post_lead["quality_score"]
                                    print(f"  ✨ [Saved Post] {author} ({role_cat}) @ {company} [Score: {score}]")
                    except Exception as e:
                        print(f"⚠️ Error running post query '{query[:30]}': {e}")
            finally:
                await context.close()

        print(f"\n✅ Post Discovery completed. Added {len(discovered_leads)} new qualified lead(s).")
        return discovered_leads
