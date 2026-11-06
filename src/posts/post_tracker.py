"""
LinkedIn Post Tracker & Inbound Lead Discovery Engine (Track 3).
Scrapes, classifies, and tracks hiring updates and referral opportunities from
recruiter, engineering lead, and peer posts across LinkedIn Content Search
and Candidate Activity.
"""

from __future__ import annotations

import asyncio
import json
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
CANDIDATE_MASTER_DATA = PROJECT_ROOT / "data" / "profile" / "candidate_master_data.json"
DEFAULT_CANDIDATE_LINKEDIN = "https://www.linkedin.com/in/manjunath-h-k-ab30b1146/"

DEFAULT_SEARCH_QUERIES = [
    '("SDET" OR "Software Engineer in Test") hiring (Bangalore OR Bengaluru OR India OR Remote)',
    '("Staff SDET" OR "Principal SDET" OR "Lead SDET") hiring',
    '("SDET" OR "QA Automation") referral (Bangalore OR Bengaluru OR India OR Remote)',
    '("Test Automation Architect" OR "Automation Lead") hiring',
    '"SDET" referral',
]


def sanitize_post_text(text: str, author_name: str = "") -> str:
    """
    Sanitizes post commentary text:
    0. Removes candidate reaction banners ('Manjunath H K likes this', '<Name> reacted to this')
    1. Removes prepended author metadata header (<Name> • <Degree> <Headline> <Time> • (Follow|Connect))
    2. Strips trailing reaction junk ('… more5 reactions', '12 reactions • 3 comments', etc.)
    3. Strips residual '… see more' / 'Show less' expansion artifacts.
    4. Normalizes whitespace while preserving authentic paragraph line breaks (\\n\\n).
    """
    if not text:
        return ""

    cleaned = text.strip()

    # Case 0: Strip leading reaction banner (e.g. "Feed post Manjunath H K likes this")
    cleaned = re.sub(
        r"^(?:Feed post\s+)?(?:[A-Z][a-zA-Z\s\.\-]{2,35}\s+(?:likes?|reacted\s+to|loves?|celebrates?|supports?|finds?\s+this\s+insightful)\s+this\s*)+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    # Case 1: Text starts with author name (e.g. "VISHAL PATIL • 2nd...")
    stripped = False
    if author_name and len(author_name) >= 3:
        name_pattern = (
            r"^(?:Feed post\s+)?"
            + re.escape(author_name)
            + r"\b.*?(?:\d+[hmdw]\s*•|\b\d+[hmdw]\b)\s*(?:•\s*)?(?:Follow|Connect|Following)?\s*"
        )
        new_text = re.sub(name_pattern, "", cleaned, count=1, flags=re.DOTALL | re.IGNORECASE)
        if new_text != cleaned and len(new_text) >= 15:
            cleaned = new_text
            stripped = True

    # Case 2: Text starts with Name + connection degree (e.g. "Some Name • 2nd...")
    # Supports single-line and multi-line headers (e.g. group updates with "Join")
    if not stripped:
        degree_pattern = (
            r"^(?:Feed post\s+)?[\s\S]{0,120}?•\s*(?:1st|2nd|3rd|\d+[a-z]+)"
            r"[\s\S]*?(?:\d+[hmdw]\s*•|\b\d+[hmdw]\b)\s*(?:•\s*)?(?:Follow|Connect|Following|Join|Subscribe)?\s*"
        )
        new_text = re.sub(degree_pattern, "", cleaned, count=1, flags=re.IGNORECASE)
        if new_text != cleaned and len(new_text) >= 15:
            cleaned = new_text
            stripped = True

    # Case 3: Company post header (e.g. "Velion IT consulting PVT LTD3h • Follow...")
    if not stripped:
        co_pattern = (
            r"^(?:Feed post\s+)?[\s\S]{0,120}?\s*\d+[hmdw]\s*•\s*(?:Follow|Connect|Following|Join|Subscribe)?\s*"
        )
        new_text = re.sub(co_pattern, "", cleaned, count=1, flags=re.IGNORECASE)
        if new_text != cleaned and len(new_text) >= 15:
            cleaned = new_text
            stripped = True

    # Trailing reaction metrics, comments, and zero-width spaces across single or multiple lines
    cleaned = re.sub(
        r"(?:…\s*more)?[\s\u200b]*\d+[\s\u200b\d]*(?:reactions?|comments?)?[\s\u200b]*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    # Trailing see more / show less toggles
    cleaned = re.sub(
        r"\s*…\s*(?:see\s+more|more|show\s+less)\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    # Normalize excessive blank lines while preserving genuine paragraph breaks
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_relative_timestamp_from_card_text(raw_text: str) -> str:
    """
    Extracts relative timestamp (e.g. '2h', '16m', '1d', '6d', '1w', '2mo', '1yr')
    from LinkedIn feed/search card text, including SDUI cards where the timestamp
    is concatenated directly onto the end of the author headline without a leading
    space (e.g. 'Manual & Automation Testing6d •' or 'Business Analysis1w • Edited').
    """
    if not raw_text:
        return "recent"

    header_window = raw_text[:450]

    # 1. Explicit '<N> <unit> •' pattern (supports concatenated prefix like 'Testing6d •' or 'Company3h •')
    m_bullet = re.search(
        r"(?:^|[\s•|)\].a-zA-Z])(\d+\s*(?:yr|mo|wk|hr|min|sec|w|d|h|m|s))\s*•",
        header_window,
        re.IGNORECASE,
    )
    if m_bullet:
        return re.sub(r"\s+", "", m_bullet.group(1).lower())

    # 2. Explicit '<N> (hour|minute|day|week|month|year)s ago' pattern
    m_ago = re.search(
        r"(\d+)\s*(second|sec|minute|min|hour|hr|day|week|wk|month|mo|year|yr)s?(?:\s+ago)?\b",
        header_window,
        re.IGNORECASE,
    )
    if m_ago:
        num = m_ago.group(1)
        unit_raw = m_ago.group(2).lower()
        unit_map = {
            "second": "s",
            "sec": "s",
            "minute": "m",
            "min": "m",
            "hour": "h",
            "hr": "h",
            "day": "d",
            "week": "w",
            "wk": "w",
            "month": "mo",
            "mo": "mo",
            "year": "yr",
            "yr": "yr",
        }
        return f"{num}{unit_map.get(unit_raw, unit_raw)}"

    # 3. Standalone word-boundary token fallback
    m_token = re.search(r"\b(\d+(?:yr|mo|w|d|h|m))\b", header_window, re.IGNORECASE)
    if m_token:
        return m_token.group(1).lower()

    return "recent"


class LinkedInPostTracker:
    """
    Automated discovery engine for LinkedIn hiring & referral posts.
    """

    def __init__(self, db: ApplicationDatabase | None = None):
        self.db = db or ApplicationDatabase()
        self.classifier = PostClassifier()
        self.composer = PostOutreachComposer()
        self.candidate_linkedin_url = self._load_candidate_linkedin_url()
        self.candidate_slug = (
            self.candidate_linkedin_url.rstrip("/").split("/in/")[-1].lower()
            if "/in/" in self.candidate_linkedin_url
            else "manjunath-h-k-ab30b1146"
        )

    @staticmethod
    def _load_candidate_linkedin_url() -> str:
        """Loads candidate's canonical LinkedIn profile URL from candidate_master_data.json."""
        try:
            if CANDIDATE_MASTER_DATA.exists():
                data = json.loads(CANDIDATE_MASTER_DATA.read_text(encoding="utf-8"))
                li_url = str(data.get("profiles", {}).get("linkedin") or "").strip()
                if li_url and "/in/" in li_url:
                    return li_url.rstrip("/") + "/"
        except Exception:
            pass
        return DEFAULT_CANDIDATE_LINKEDIN

    def resolve_candidate_reactions_url(self) -> str:
        """Returns the candidate's LinkedIn Recent Activity -> Reactions URL."""
        return f"{self.candidate_linkedin_url.rstrip('/')}/recent-activity/reactions/"

    @staticmethod
    def build_company_hiring_post_query(
        company_name: str, role_keywords: str = '"SDET" OR "QA" OR "Automation"'
    ) -> str:
        """Builds a targeted LinkedIn Content Search query to find hiring/referral posts for a specific company."""
        clean_co = (company_name or "").strip()
        return f'"{clean_co}" AND ("hiring" OR "referral" OR "openings" OR "refer") AND ({role_keywords})'

    def find_matching_posts_for_job(self, job_payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Cross-links a job posting against saved hiring posts in SQLite by company name or post text."""
        details = job_payload.get("job_details") or {}
        company = str(
            job_payload.get("company_name")
            or job_payload.get("company")
            or details.get("company")
            or details.get("company_name")
            or ""
        ).strip()
        if not company:
            return []
        comp_low = company.lower()
        comp_tokens = [t for t in re.split(r"[^a-z0-9]+", comp_low) if len(t) >= 3]
        primary_tok = comp_tokens[0] if comp_tokens else comp_low

        all_posts = self.db.get_hiring_posts(limit=200)
        matched: list[dict[str, Any]] = []
        for post in all_posts:
            p_comp = str(post.get("company_name") or "").lower()
            p_text = str(post.get("post_text") or "").lower()
            p_hl = str(post.get("author_headline") or "").lower()
            if comp_low in p_comp or (
                primary_tok and re.search(rf"\b{re.escape(primary_tok)}\b", f"{p_comp} {p_hl} {p_text}")
            ):
                matched.append(post)
        return matched

    async def _extract_post_permalink(self, card: Any, author_url: str, raw_text: str) -> str:
        """
        Extracts an authentic LinkedIn post permalink or authentic author activity URL.
        Multi-tier extraction:
        1. Direct post permalinks in card DOM (/posts/ or /feed/update/urn:li:activity:)
        2. Attribute inspection (data-chameleon-result-urn, data-urn, data-activity-urn, data-id)
        3. React Fiber & SDUI props evaluation (<5ms)
        4. Link href regex matching across all anchors inside card
        5. Guaranteed Fallback: Author recent activity or posts (ZERO HTTP 404s)
        """
        post_url = ""

        # 1. Direct post links in DOM (anchors explicitly linking to posts/updates)
        try:
            direct_link_loc = card.locator(
                "a[href*='/posts/'], a[href*='/feed/update/urn:li:activity'], a[href*='/feed/update/urn:li:ugcPost'], a[href*='/feed/update/urn:li:share'], a.update-components-actor__sub-description-link"
            ).first
            if await direct_link_loc.count() > 0:
                href = (await direct_link_loc.get_attribute("href") or "").strip()
                clean_href = href.split("?")[0].strip()
                if clean_href.startswith("/"):
                    clean_href = f"https://www.linkedin.com{clean_href}"

                if "/posts/" in clean_href or "/feed/update/urn:li:" in clean_href:
                    post_url = clean_href
                else:
                    m = re.search(
                        r"urn:li:(?:activity|ugcPost|share):(\d{18,20})|(?:activity|ugcPost|share)[:\-](\d{18,20})",
                        clean_href,
                    )
                    if m:
                        act_id = m.group(1) or m.group(2)
                        post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{act_id}/"
        except Exception:
            pass

        # 2. Check data-chameleon-result-urn, data-urn, or data-activity-urn on card or child elements
        if not post_url:
            try:
                for attr in ["data-chameleon-result-urn", "data-urn", "data-activity-urn", "data-id"]:
                    val = await card.get_attribute(attr) or ""
                    m = re.search(
                        r"urn:li:(?:activity|ugcPost|share):(\d{18,20})|(?:activity|ugcPost|share)[:\-](\d{18,20})", val
                    )
                    if m:
                        act_id = m.group(1) or m.group(2)
                        post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{act_id}/"
                        break

                if not post_url:
                    urn_elem = card.locator(
                        "[data-chameleon-result-urn], [data-urn*='activity'], [data-urn*='ugcPost'], [data-urn*='share'], [data-activity-urn]"
                    ).first
                    if await urn_elem.count() > 0:
                        for attr in ["data-chameleon-result-urn", "data-urn", "data-activity-urn"]:
                            val = await urn_elem.get_attribute(attr) or ""
                            m = re.search(
                                r"urn:li:(?:activity|ugcPost|share):(\d{18,20})|(?:activity|ugcPost|share)[:\-](\d{18,20})",
                                val,
                            )
                            if m:
                                act_id = m.group(1) or m.group(2)
                                post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{act_id}/"
                                break
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
                                    const act = str.match(/urn:li:(?:activity|ugcPost|share):(\\d{18,20})/);
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
                    m = re.search(
                        r"urn:li:(?:activity|ugcPost|share):(\d{18,20})|(?:activity|ugcPost|share)[:\-](\d{18,20})",
                        href,
                    )
                    if m:
                        act_id = m.group(1) or m.group(2)
                        post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{act_id}/"
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
            if await see_more.count() > 0:
                try:
                    if await see_more.is_visible(timeout=500):
                        await see_more.click(timeout=1000)
                        await asyncio.sleep(0.1)
                except Exception:
                    pass

            # 2. Extract Author details (skipping candidate's own reaction header link on /recent-activity/reactions/)
            author_links = await card.locator("a[href*='/in/'], a[href*='/company/']").all()
            author_name = "Unknown"
            author_url = ""
            for al in author_links:
                href_val = (await al.get_attribute("href") or "").split("?")[0]
                if self.candidate_slug and self.candidate_slug in href_val.lower():
                    continue
                ltxt = (await al.text_content(timeout=1000) or "").strip()
                clean_name = ltxt.split("•")[0].strip()
                if clean_name and clean_name.lower() not in [
                    "view profile",
                    "follow",
                    "connect",
                    "feed post",
                    "manjunath h k",
                ]:
                    author_name = clean_name
                    author_url = href_val
                    break

            if author_name == "Unknown":
                author_name_loc = card.locator(
                    ".update-components-actor__name, .feed-shared-actor__name, a[data-field='actor_name']"
                ).first
                if await author_name_loc.count() > 0:
                    author_name = (await author_name_loc.text_content(timeout=1000) or "").strip()

            # 3. Extract Post text
            raw_text = (await card.text_content(timeout=2000) or "").strip()
            if raw_text.startswith("Feed post"):
                raw_text = raw_text[len("Feed post") :].strip()

            author_title_loc = card.locator(
                ".update-components-actor__description, .feed-shared-actor__description, .update-components-actor__headline, .entity-result__primary-subtitle, span[data-anonymize='headline']"
            ).first
            author_headline = (
                (await author_title_loc.text_content(timeout=1000)).strip()
                if await author_title_loc.count() > 0
                else ""
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

            commentary_loc = card.locator(
                ".feed-shared-inline-show-more-text, "
                ".update-components-update-v2__commentary, "
                ".feed-shared-update-v2__description, "
                ".feed-shared-text, "
                "span.break-words"
            ).first
            if await commentary_loc.count() > 0:
                try:
                    raw_commentary = (await commentary_loc.inner_text(timeout=1500)).strip()
                except Exception:
                    raw_commentary = (await commentary_loc.text_content(timeout=1500) or "").strip()
            else:
                try:
                    raw_commentary = (await card.inner_text(timeout=1500)).strip()
                except Exception:
                    raw_commentary = raw_text

            if author_name == "Unknown":
                hdr_match = re.search(
                    r"(?:^|\n)([A-Z][a-zA-Z\s\.\-]{2,30})\s*•\s*(?:1st|2nd|3rd|\d+[a-z]+)",
                    raw_commentary,
                )
                if hdr_match:
                    cand_name = hdr_match.group(1).strip()
                    if cand_name and len(cand_name) > 3 and cand_name.lower() not in ["feed post"]:
                        author_name = cand_name

            text_content = sanitize_post_text(raw_commentary, author_name=author_name)
            if len(text_content) < 25:
                return None

            # 4. Extract relative timestamp (supporting SDUI concatenated header timestamps)
            relative_time = "recent"
            time_loc = card.locator(
                ".update-components-actor__sub-description, .feed-shared-actor__sub-description, time"
            ).first
            if await time_loc.count() > 0:
                posted_time = (await time_loc.text_content(timeout=1000) or "").strip()
                cand_time = posted_time.split("•")[0].strip() if "•" in posted_time else posted_time
                parsed_cand = extract_relative_timestamp_from_card_text(cand_time)
                relative_time = parsed_cand if parsed_cand != "recent" else cand_time
            if not relative_time or relative_time == "recent":
                relative_time = extract_relative_timestamp_from_card_text(raw_text)

            # 5. Extract Post permalink / URN with multi-tier resilience
            post_url = await self._extract_post_permalink(card, author_url, raw_text)

            # 5b. Extract clean DOM anchor links
            dom_links = []
            try:
                anchor_locs = await card.locator(
                    ".feed-shared-update-v2__description a[href], .update-components-text a[href], .feed-shared-text a[href]"
                ).all()
                for al in anchor_locs:
                    ahref = await al.get_attribute("href")
                    if ahref and "linkedin.com/in/" not in ahref and "linkedin.com/company/" not in ahref:
                        dom_links.append(ahref.strip())
            except Exception:
                pass

            raw_post = {
                "author_name": author_name,
                "author_headline": author_headline,
                "author_profile_url": author_url,
                "post_url": post_url,
                "post_text": text_content,
                "posted_at_relative": relative_time,
                "dom_links": dom_links,
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

    @staticmethod
    def is_post_within_age_limit(relative_time: str, date_filter: str = "past-72h") -> bool:
        """
        Enforces strict post age filtering on extracted LinkedIn feed cards.
        Supports 'past-24h' (<=1d), 'past-48h' (<=2d), 'past-72h' (<=3d), and 'past-week' (<=7d).
        Rejects unverified 'recent' placeholders when a strict sub-week filter ('past-24h', 'past-48h', 'past-72h')
        is requested so 4d-1w cards from LinkedIn's 'past-week' URL bucket cannot sneak in.
        """
        df = (date_filter or "past-week").lower().strip()
        max_days = 7.0
        if df in ("past-24h", "past_24h", "24h"):
            max_days = 1.0
        elif df in ("past-48h", "past_48h", "48h"):
            max_days = 2.0
        elif df in ("past-72h", "past_72h", "72h"):
            max_days = 3.0
        elif df in ("past-month", "past_month"):
            max_days = 30.0

        if not relative_time or relative_time.lower().strip() in ("recent", "unknown"):
            return max_days >= 7.0

        t = relative_time.lower().strip()
        if any(u in t for u in ("now", "sec", "min", "hr", "hour")) or re.search(r"\b\d+\s*[smh]\b", t):
            return True
        m_day = re.search(r"\b(\d+)\s*d(?:ay)?s?\b", t)
        if m_day:
            return float(m_day.group(1)) <= max_days
        m_wk = re.search(r"\b(\d+)\s*w(?:eek|k)?s?\b", t)
        if m_wk:
            return (float(m_wk.group(1)) * 7.0) <= max_days
        m_mo = re.search(r"\b(\d+)\s*mo(?:nth)?s?\b", t)
        if m_mo:
            return (float(m_mo.group(1)) * 30.0) <= max_days
        m_yr = re.search(r"\b(\d+)\s*(?:yr|year)s?\b", t)
        if m_yr:
            return (float(m_yr.group(1)) * 365.0) <= max_days
        return max_days >= 7.0

    async def scrape_liked_posts(
        self,
        page: Any,
        max_scrolls: int = 4,
        date_filter: str = "past-72h",
    ) -> list[dict[str, Any]]:
        """
        Scrapes the candidate's own LinkedIn Recent Activity -> Reactions feed
        (e.g., https://www.linkedin.com/in/<slug>/recent-activity/reactions/)
        to capture hiring/referral posts the user liked on their daily feed.
        """
        reactions_url = self.resolve_candidate_reactions_url()
        liked_leads: list[dict[str, Any]] = []
        print(f"\n❤️ [Step 0] Scanning Candidate Liked Posts / Reactions: {reactions_url}")
        try:
            await page.goto(reactions_url, wait_until="domcontentloaded", timeout=35000)
            await asyncio.sleep(3.0)

            for _ in range(max_scrolls):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1.2)

            cards_loc = page.locator(
                "div:has(> h2:has-text('Feed post')), div:has(> span:has-text('Feed post')), "
                ".feed-shared-update-v2, .occludable-update, "
                "div[data-view-name*='feed-full-update'], div[data-view-name*='search-entity-result'], "
                ".artdeco-card:has(.feed-shared-text, .update-components-text, span.break-words)"
            )
            card_count = await cards_loc.count()
            self.last_raw_updates_scanned = getattr(self, "last_raw_updates_scanned", 0) + int(card_count)
            print(f"📦 Scanned {card_count} candidate-liked reaction card(s).")

            for c_idx in range(card_count):
                card = cards_loc.nth(c_idx)
                post_lead = await self._extract_post_from_card(card, page)
                if post_lead:
                    rel_t = str(post_lead.get("posted_at_relative") or "")
                    if date_filter and not self.is_post_within_age_limit(rel_t, date_filter):
                        continue
                    post_lead["source"] = "liked_activity"
                    post_lead["is_candidate_liked"] = True
                    post_lead["quality_score"] = min(100, int(post_lead.get("quality_score", 75)) + 20)
                    post_id = post_lead["post_id"]
                    if not self.db.is_hiring_post_saved(
                        post_id, content_hash=post_lead.get("content_hash")
                    ) and self.db.save_hiring_post(post_lead):
                        liked_leads.append(post_lead)
                        author = post_lead["author_name"]
                        company = post_lead["company_name"]
                        role_cat = post_lead["author_role_category"]
                        score = post_lead["quality_score"]
                        print(f"  ❤️ [Saved Liked Post] {author} ({role_cat}) @ {company} [Score: {score}]")
        except Exception as e:
            print(f"⚠️ Warning scanning candidate liked posts ({reactions_url}): {e}")

        return liked_leads

    async def discover_posts(
        self,
        queries: list[str] | None = None,
        date_filter: str = "past-72h",
        max_scrolls: int = 12,
        headless: bool = False,
        include_liked: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Executes candidate liked-posts scan (/recent-activity/reactions/) followed by
        keyword search on LinkedIn /search/results/content/ and collects qualified posts.
        Maps custom sub-week filters ('past-72h', 'past-48h') to LinkedIn's native 'past-week'
        URL enum while enforcing exact relative-age cutoff per card.
        """
        target_queries = queries if queries is not None else DEFAULT_SEARCH_QUERIES
        discovered_leads: list[dict[str, Any]] = []
        self.last_raw_updates_scanned = 0
        self.last_auth_status: dict[str, Any] = {}
        self.last_yield_verdict = "NOT_RUN"

        url_date_filter = (
            "past-24h"
            if date_filter in ("past-24h", "past_24h")
            else ("past-month" if date_filter in ("past-month", "past_month") else "past-week")
        )

        from src.browser.cdp_stealth import ensure_cdp_page_target, is_cdp_port_open
        from src.browser.linkedin_auth import (
            capture_zero_yield_evidence,
            check_profile_session,
            verify_live_session,
        )

        async with async_playwright() as p:
            owns_context = False
            if is_cdp_port_open(9222):
                ensure_cdp_page_target(9222)
                browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=10000)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = await context.new_page()
            else:
                context, page = await launch_persistent_browser(
                    p, profile_dir=str(DEFAULT_PROFILE_DIR), headless=headless
                )
                owns_context = True
            print(f"🚀 Launching LinkedIn Posts Tracker (Headless: {headless}, Filter: {date_filter})")

            try:
                offline_auth = check_profile_session(DEFAULT_PROFILE_DIR)
                live_auth = await verify_live_session(page)
                self.last_auth_status = {**offline_auth, **live_auth}
                if live_auth.get("status") == "AUTHWALL" or not offline_auth.get("is_authenticated"):
                    print(f"🚨 TRACK 3 LINKEDIN AUTH PREFLIGHT FAILED: {self.last_auth_status.get('message')}")
                    await capture_zero_yield_evidence(page, "posts_tracker_auth_preflight")
                    self.last_yield_verdict = "AUTH_FAILED"
                    return discovered_leads

                # Step 0: Scan candidate's own Liked Posts / Reactions feed (enforcing same date_filter)
                if include_liked:
                    liked_leads = await self.scrape_liked_posts(
                        page, max_scrolls=min(max_scrolls, 4), date_filter=date_filter
                    )
                    discovered_leads.extend(liked_leads)

                for q_idx, query in enumerate(target_queries):
                    encoded_query = urllib.parse.quote(query)
                    url = (
                        f"https://www.linkedin.com/search/results/content/?"
                        f"datePosted=%22{url_date_filter}%22&keywords={encoded_query}&sortBy=%22date_posted%22"
                    )
                    print(f"\n🔍 [Query {q_idx + 1}/{len(target_queries)}] Searching: {query[:60]}...")
                    print(f"🌐 URL: {url} (card cutoff: {date_filter})")

                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=35000)
                        await asyncio.sleep(3.0)

                        # Progressive smooth scrolls to hydrate feed updates deep into the feed
                        for s in range(max_scrolls):
                            await page.evaluate("window.scrollBy(0, 1000)")
                            await asyncio.sleep(1.5)

                        # Match modern card locators
                        cards_loc = page.locator(
                            "div:has(> h2:has-text('Feed post')), div:has(> span:has-text('Feed post')), "
                            ".feed-shared-update-v2, .occludable-update, "
                            "div[data-view-name*='search-entity-result'], "
                            ".artdeco-card:has(.feed-shared-text, .update-components-text)"
                        )
                        card_count = await cards_loc.count()
                        self.last_raw_updates_scanned += int(card_count)
                        print(f"📦 Scanned {card_count} raw feed update(s).")

                        for c_idx in range(card_count):
                            card = cards_loc.nth(c_idx)
                            post_lead = await self._extract_post_from_card(card, page)
                            if post_lead:
                                rel_t = str(post_lead.get("posted_at_relative") or "")
                                if not self.is_post_within_age_limit(rel_t, date_filter):
                                    continue
                                post_id = post_lead["post_id"]
                                if not self.db.is_hiring_post_saved(
                                    post_id, content_hash=post_lead.get("content_hash")
                                ) and self.db.save_hiring_post(post_lead):
                                    discovered_leads.append(post_lead)
                                    author = post_lead["author_name"]
                                    company = post_lead["company_name"]
                                    role_cat = post_lead["author_role_category"]
                                    score = post_lead["quality_score"]
                                    print(f"  ✨ [Saved Post] {author} ({role_cat}) @ {company} [Score: {score}]")
                    except Exception as e:
                        print(f"⚠️ Error running post query '{query[:30]}': {e}")

                if self.last_raw_updates_scanned == 0:
                    self.last_yield_verdict = "ZERO_YIELD_SUSPECT"
                    print("⚠️ TRACK 3 ZERO-YIELD SUSPECT: All post search queries returned 0 feed updates.")
                    await capture_zero_yield_evidence(page, "posts_tracker_zero_yield")
                else:
                    self.last_yield_verdict = "OK"
            finally:
                try:
                    await page.close()
                except Exception:
                    pass
                if owns_context:
                    try:
                        await context.close()
                    except Exception:
                        pass

        print(
            f"\n✅ Post Discovery completed. Scanned {self.last_raw_updates_scanned} raw update(s), "
            f"added {len(discovered_leads)} new qualified lead(s). (Verdict: {self.last_yield_verdict})"
        )
        return discovered_leads
