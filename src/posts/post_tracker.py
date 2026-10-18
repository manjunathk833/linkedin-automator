"""
LinkedIn Post Tracker & Inbound Lead Discovery Engine (Track 3).
Scrapes, classifies, and tracks hiring updates and referral opportunities from
recruiter, engineering lead, and peer posts across LinkedIn Content Search
and Candidate Activity.
"""

from __future__ import annotations

import asyncio
import re
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
    "SDET hiring",
    "QA automation hiring",
    "SDET referral",
    "Lead SDET hiring",
]


class LinkedInPostTracker:
    """
    Automated discovery engine for LinkedIn hiring & referral posts.
    """

    def __init__(self, db: ApplicationDatabase | None = None):
        self.db = db or ApplicationDatabase()
        self.classifier = PostClassifier()
        self.composer = PostOutreachComposer()

    async def _extract_post_permalink(self, card: Any, author_url: str, raw_text: str) -> str:
        """
        Extracts an authentic LinkedIn post permalink or authentic author activity URL.
        Multi-tier extraction:
        1. Direct post permalinks in card DOM (/posts/ or /feed/update/urn:li:activity:)
        2. Attribute inspection (data-urn, data-activity-urn, data-id)
        3. React Fiber & SDUI props evaluation (<5ms)
        4. Link href regex matching for activity URNs
        5. Guaranteed Fallback: Author recent activity or posts (ZERO HTTP 404s)
        """
        post_url = ""

        # 1. Direct post links in DOM
        try:
            direct_link_loc = card.locator(
                "a[href*='/posts/'], a[href*='/feed/update/urn:li:activity'], a[href*='/feed/update/urn:li:share'], a.update-components-actor__sub-description-link"
            ).first
            if await direct_link_loc.count() > 0:
                href = (await direct_link_loc.get_attribute("href") or "").split("?")[0].strip()
                if "/posts/" in href or "/feed/update/urn:li:" in href:
                    post_url = href
        except Exception:
            pass

        # 2. Check data-urn or other attributes on card or child elements
        if not post_url:
            try:
                post_urn = await card.get_attribute("data-urn") or ""
                if not post_urn:
                    urn_elem = card.locator("[data-urn*='activity'], [data-activity-urn]").first
                    if await urn_elem.count() > 0:
                        post_urn = (
                            await urn_elem.get_attribute("data-urn")
                            or await urn_elem.get_attribute("data-activity-urn")
                            or ""
                        )
                act_match = re.search(r"activity[:\-](\d{18,20})", post_urn)
                if act_match:
                    post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{act_match.group(1)}/"
            except Exception:
                pass

        # 3. React Fiber / SDUI Props Inspection (<5ms)
        if not post_url:
            try:
                fiber_url = await card.evaluate("""
                    (el) => {
                        function searchFiber(fiber, depth = 0) {
                            if (!fiber || depth > 12) return null;
                            const props = fiber.memoizedProps;
                            if (props) {
                                if (typeof props.url === 'string' && props.url.includes('linkedin.com/posts/')) {
                                    return props.url.split('?')[0];
                                }
                                try {
                                    const str = JSON.stringify(props);
                                    const act = str.match(/urn:li:activity:(\\d{18,20})/);
                                    if (act) return `https://www.linkedin.com/feed/update/urn:li:activity:${act[1]}/`;
                                    const postMatch = str.match(/https:\\\\/\\\\/www\\.linkedin\\.com\\\\/posts\\\\/[^"\'\\s\\\\]+/);
                                    if (postMatch) return postMatch[0].replace(/\\\\/g, '').split('?')[0];
                                } catch (e) {}
                            }
                            return searchFiber(fiber.return, depth + 1) || searchFiber(fiber.child, depth + 1);
                        }
                        const key = Object.keys(el).find(k => k.startsWith('__reactFiber$') || k.startsWith('__reactInternalInstance$'));
                        if (key && el[key]) {
                            return searchFiber(el[key]);
                        }
                        return null;
                    }
                """)
                if fiber_url and ("linkedin.com/posts/" in fiber_url or "urn:li:activity" in fiber_url):
                    post_url = fiber_url.strip()
            except Exception:
                pass

        # 4. Check for activity ID regex across all anchors inside card
        if not post_url:
            try:
                all_anchors = await card.locator("a[href]").all()
                for a in all_anchors:
                    href = await a.get_attribute("href") or ""
                    act_match = re.search(r"activity[:\-](\d{18,20})", href)
                    if act_match:
                        post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{act_match.group(1)}/"
                        break
            except Exception:
                pass

        # 5. Guaranteed Fallback: Author authentic activity / posts (ZERO 404s)
        if not post_url:
            clean_author_url = (author_url or "").split("?")[0].rstrip("/")
            if "/in/" in clean_author_url:
                post_url = f"{clean_author_url}/recent-activity/all/"
            elif "/company/" in clean_author_url:
                post_url = f"{clean_author_url}/posts/"
            elif clean_author_url:
                post_url = clean_author_url
            else:
                post_url = "https://www.linkedin.com/feed/"

        return post_url

    async def _extract_post_from_card(self, card: Any, page: Any) -> dict[str, Any] | None:
        """Extracts text, author, and links from a single DOM update card."""
        try:
            # 1. Expand '...see more' if present
            see_more = card.locator(
                ".feed-shared-inline-show-more-text__see-more-less-toggle, button:has-text('see more'), button:has-text('...more')"
            ).first
            if await see_more.count() > 0 and await see_more.is_visible():
                try:
                    await see_more.click(timeout=1000)
                    await asyncio.sleep(0.2)
                except Exception:
                    pass

            # 2. Extract Author details
            author_links = await card.locator("a[href*='/in/'], a[href*='/company/']").all()
            author_name = "Unknown"
            author_url = ""
            for al in author_links:
                ltxt = (await al.text_content() or "").strip()
                clean_name = ltxt.split("•")[0].strip()
                if clean_name and clean_name.lower() not in ["view profile", "follow", "connect", "feed post"]:
                    author_name = clean_name
                    author_url = (await al.get_attribute("href") or "").split("?")[0]
                    break

            if author_name == "Unknown":
                author_name_loc = card.locator(
                    ".update-components-actor__name, .feed-shared-actor__name, a[data-field='actor_name']"
                ).first
                if await author_name_loc.count() > 0:
                    author_name = (await author_name_loc.text_content() or "").strip()

            # 3. Extract Post text
            raw_text = (await card.text_content() or "").strip()
            if raw_text.startswith("Feed post"):
                raw_text = raw_text[len("Feed post") :].strip()

            author_title_loc = card.locator(
                ".update-components-actor__description, .feed-shared-actor__description, .update-components-actor__headline, .entity-result__primary-subtitle, span[data-anonymize='headline']"
            ).first
            author_headline = (
                (await author_title_loc.text_content()).strip() if await author_title_loc.count() > 0 else ""
            )

            if not author_headline or author_headline == author_name:
                # Fallback: Extract from raw_text header pattern: <Author> • [degree] <Headline> <Time> • (Follow|Connect)
                hl_match = re.search(
                    re.escape(author_name)
                    + r"\s*(?:•\s*(?:1st|2nd|3rd|\d+[a-z]+)?)?\s*(.*?)(?:\d+[hmdw]\s*•|\d+[hmdw]\b|Follow|Connect)",
                    raw_text,
                    re.DOTALL,
                )
                if hl_match:
                    candidate_hl = hl_match.group(1).strip()
                    if candidate_hl and len(candidate_hl) > 3:
                        author_headline = candidate_hl
                if not author_headline:
                    author_headline = author_name

            text_loc = card.locator(
                ".feed-shared-update-v2__description, .feed-shared-text, .update-components-text"
            ).first
            text_content = (await text_loc.text_content()).strip() if await text_loc.count() > 0 else raw_text
            if len(text_content) < 25:
                return None

            # 4. Extract relative timestamp
            time_loc = card.locator(
                ".update-components-actor__sub-description, .feed-shared-actor__sub-description, time"
            ).first
            if await time_loc.count() > 0:
                posted_time = (await time_loc.text_content()).strip()
                relative_time = posted_time.split("•")[0].strip() if "•" in posted_time else posted_time
            else:
                time_match = re.search(r"\b(\d+[hmdw])\b", raw_text)
                relative_time = time_match.group(1) if time_match else "recent"

            # 5. Extract Post permalink / URN with multi-tier resilience
            post_url = await self._extract_post_permalink(card, author_url, raw_text)

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
        headless: bool = False,
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
                            "div:has(> h2:has-text('Feed post')), div:has(> span:has-text('Feed post')), "
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
