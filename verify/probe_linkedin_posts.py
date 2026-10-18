"""
Exploratory Probing Script for LinkedIn Posts & Reactions.
1. Inspects https://www.linkedin.com/in/manjunath-h-k-ab30b1146/recent-activity/reactions/
   to extract authentic liked hiring posts and discover DOM selectors & content patterns.
2. Experiments with LinkedIn Content Search (/search/results/content/)
   using recency sorting and date filters (<24h / <48h).
"""

import asyncio
import json
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
STORAGE_STATE = PROJECT_ROOT / ".browser_data" / "storage_state.json"
LOGS_DIR = PROJECT_ROOT / "data" / "logs"
SCREENSHOTS_DIR = LOGS_DIR / "screenshots"

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
URL_REGEX = re.compile(r"https?://[^\s<>\"'()]+")


async def probe_posts():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    if not STORAGE_STATE.exists():
        print(f"❌ Storage state not found at {STORAGE_STATE}")
        return

    from src.browser.cdp_connector import DEFAULT_PROFILE_DIR, launch_persistent_browser

    async with async_playwright() as p:
        # Launch real Chrome with persistent profile containing your authenticated session
        context, page = await launch_persistent_browser(p, profile_dir=str(DEFAULT_PROFILE_DIR), headless=False)
        print("🔗 Chrome window launched with persistent session profile.")

        reactions_url = "https://www.linkedin.com/in/manjunath-h-k-ab30b1146/recent-activity/reactions/"
        print("\n" + "=" * 60)
        print("🔍 STEP 1: PROBING USER-LIKED RECENT ACTIVITY / REACTIONS")
        print("=" * 60)
        print(f"🌐 Navigating to: {reactions_url}")

        try:
            await page.goto(reactions_url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(4.0)

            # Human-in-the-Loop Takeover Gate (Zero Premature Exit)
            if (
                "/login" in page.url
                or "/authwall" in page.url
                or "/checkpoint" in page.url
                or await page.locator("a:has-text('Sign in'), button:has-text('Sign in')").count() > 0
            ):
                print("\a" * 3)
                print("\n" + "!" * 60)
                print("🔔 [HUMAN-IN-THE-LOOP TAKEOVER REQUIRED]")
                print("LinkedIn session authentication / challenge detected.")
                print("The Chrome browser window is OPEN on your screen.")
                print("👉 Please log in or complete the verification challenge now.")
                print("Execution will automatically detect login and resume seamlessly!")
                print("!" * 60 + "\n")

                # Wait interactively without exiting
                while True:
                    await asyncio.sleep(3.0)
                    current_url = page.url
                    is_logged_in = (
                        "/feed" in current_url or "/in/" in current_url or "/recent-activity" in current_url
                    ) and not any(k in current_url for k in ["/login", "/authwall", "/checkpoint"])

                    # Also check for global nav
                    has_nav = await page.locator(".global-nav, #global-nav, .feed-shared-update-v2").count() > 0
                    if is_logged_in and has_nav:
                        print("🎉 Authentication detected! Refreshing stored session snapshot...")
                        await context.storage_state(path=str(STORAGE_STATE))
                        print("💾 Stored storage_state.json updated successfully.")
                        break

            # Ensure we are on reactions page
            if "recent-activity/reactions" not in page.url:
                print(f"🌐 Navigating back to reactions feed: {reactions_url}")
                await page.goto(reactions_url, wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(4.0)

            # Scroll a few times to load posts
            for i in range(3):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(2.0)

            await page.screenshot(path=str(SCREENSHOTS_DIR / "probe_reactions_page.png"))
            print(f"📸 Saved screenshot: {SCREENSHOTS_DIR / 'probe_reactions_page.png'}")

            # Inspect feed update containers
            # Modern LinkedIn feed posts use .feed-shared-update-v2, .occludable-update, or div[data-urn*='activity']
            post_locators = page.locator(
                ".feed-shared-update-v2, .occludable-update, div[data-urn*='activity'], [data-view-name*='feed-full-update'], .artdeco-card:has(.feed-shared-text, .update-components-text)"
            )
            post_count = await post_locators.count()
            print(f"📦 Discovered {post_count} potential post card(s) on reactions page.")

            liked_posts = []
            for i in range(min(post_count, 15)):
                card = post_locators.nth(i)
                try:
                    # Expand 'see more' if present
                    see_more = card.locator(
                        ".feed-shared-inline-show-more-text__see-more-less-toggle, button:has-text('see more')"
                    ).first
                    if await see_more.count() > 0 and await see_more.is_visible():
                        try:
                            await see_more.click(timeout=1000)
                            await asyncio.sleep(0.3)
                        except Exception:
                            pass

                    # Extract Author details
                    author_name_loc = card.locator(
                        ".update-components-actor__name, .feed-shared-actor__name, a[data-field='actor_name']"
                    ).first
                    author_name = (
                        (await author_name_loc.text_content()).strip()
                        if await author_name_loc.count() > 0
                        else "Unknown"
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

                    # Extract Post Text
                    text_loc = card.locator(
                        ".feed-shared-update-v2__description, .feed-shared-text, .update-components-text"
                    ).first
                    text_content = (await text_loc.text_content()).strip() if await text_loc.count() > 0 else ""

                    # Extract timestamp / relative time
                    time_loc = card.locator(
                        ".update-components-actor__sub-description, .feed-shared-actor__sub-description, time"
                    ).first
                    posted_time = (await time_loc.text_content()).strip() if await time_loc.count() > 0 else ""
                    # Clean up time text (e.g. '1d • Edited • ' -> '1d')
                    relative_time = posted_time.split("•")[0].strip() if "•" in posted_time else posted_time

                    # Extract Post URL / URN
                    post_urn = await card.get_attribute("data-urn") or ""
                    post_url = ""
                    if "activity:" in post_urn:
                        activity_id = post_urn.split("activity:")[1].split(",")[0]
                        post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"
                    else:
                        link_loc = card.locator("a[href*='/feed/update/urn:li:activity']").first
                        if await link_loc.count() > 0:
                            post_url = (await link_loc.get_attribute("href") or "").split("?")[0]

                    # Extract emails and URLs from post text
                    emails = EMAIL_REGEX.findall(text_content)
                    urls = [
                        u
                        for u in URL_REGEX.findall(text_content)
                        if "linkedin.com" not in u and not u.endswith((".png", ".jpg", ".jpeg"))
                    ]

                    # Detect if this is a hiring post
                    is_hiring = any(
                        k in text_content.lower()
                        for k in [
                            "hiring",
                            "looking for",
                            "opening",
                            "opportunity",
                            "referral",
                            "vacancy",
                            "role",
                            "sdet",
                            "qa",
                            "test",
                        ]
                    )

                    liked_posts.append(
                        {
                            "index": i + 1,
                            "author_name": author_name,
                            "author_headline": author_headline,
                            "author_url": author_url,
                            "post_url": post_url,
                            "relative_time": relative_time,
                            "is_hiring_candidate": is_hiring,
                            "emails": emails,
                            "links": urls,
                            "text_snippet": text_content[:300] + ("..." if len(text_content) > 300 else ""),
                        }
                    )

                    print(f"\n--- [Post {i + 1}] by {author_name} ({author_headline[:50]}) ---")
                    print(f"    Time: {relative_time} | Hiring Signal: {is_hiring}")
                    if emails:
                        print(f"    📧 Emails: {emails}")
                    if urls:
                        print(f"    🔗 Links: {urls}")
                    print(f"    Body: {text_content[:160]}...")
                except Exception as ex:
                    print(f"    ⚠️ Error parsing card {i}: {ex}")

            # Save extracted liked posts
            output_file = LOGS_DIR / "liked_posts_sample.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(liked_posts, f, indent=2)
            print(f"\n💾 Saved {len(liked_posts)} liked posts sample to: {output_file}")

        except Exception as e:
            print(f"❌ Error during reactions probe: {e}")

        print("\n" + "=" * 60)
        print("🔍 STEP 2: PROBING LINKEDIN CONTENT SEARCH (<24H & RECENCY SORT)")
        print("=" * 60)

        # Test Query with URL parameters
        search_query = '("hiring" OR "looking for") AND ("SDET" OR "QA Lead" OR "Software Engineer in Test") AND ("India" OR "Bengaluru" OR "Bangalore" OR "Remote")'
        import urllib.parse

        encoded_query = urllib.parse.quote(search_query)
        # Content search with sortBy=date_posted and datePosted="past-24h"
        search_url = f"https://www.linkedin.com/search/results/content/?datePosted=%22past-24h%22&keywords={encoded_query}&sortBy=%22date_posted%22"
        print(f"🌐 Navigating to search URL: {search_url}")

        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(4.0)

            for i in range(2):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(2.0)

            await page.screenshot(path=str(SCREENSHOTS_DIR / "probe_content_search.png"))
            print(f"📸 Saved search screenshot: {SCREENSHOTS_DIR / 'probe_content_search.png'}")

            search_cards = page.locator(
                ".feed-shared-update-v2, .occludable-update, div[data-view-name*='search-entity-result'], .artdeco-card:has(.feed-shared-text, .update-components-text)"
            )
            search_count = await search_cards.count()
            print(f"📦 Discovered {search_count} search post card(s) from past 24h.")

            search_posts = []
            for i in range(min(search_count, 10)):
                card = search_cards.nth(i)
                try:
                    see_more = card.locator(
                        ".feed-shared-inline-show-more-text__see-more-less-toggle, button:has-text('see more')"
                    ).first
                    if await see_more.count() > 0 and await see_more.is_visible():
                        try:
                            await see_more.click(timeout=1000)
                            await asyncio.sleep(0.3)
                        except Exception:
                            pass

                    author_name_loc = card.locator(
                        ".update-components-actor__name, .feed-shared-actor__name, a[data-field='actor_name']"
                    ).first
                    author_name = (
                        (await author_name_loc.text_content()).strip()
                        if await author_name_loc.count() > 0
                        else "Unknown"
                    )

                    author_title_loc = card.locator(
                        ".update-components-actor__description, .feed-shared-actor__description, .update-components-actor__headline"
                    ).first
                    author_headline = (
                        (await author_title_loc.text_content()).strip() if await author_title_loc.count() > 0 else ""
                    )

                    text_loc = card.locator(
                        ".feed-shared-update-v2__description, .feed-shared-text, .update-components-text"
                    ).first
                    text_content = (await text_loc.text_content()).strip() if await text_loc.count() > 0 else ""

                    time_loc = card.locator(
                        ".update-components-actor__sub-description, .feed-shared-actor__sub-description, time"
                    ).first
                    posted_time = (await time_loc.text_content()).strip() if await time_loc.count() > 0 else ""
                    relative_time = posted_time.split("•")[0].strip() if "•" in posted_time else posted_time

                    emails = EMAIL_REGEX.findall(text_content)
                    urls = [
                        u
                        for u in URL_REGEX.findall(text_content)
                        if "linkedin.com" not in u and not u.endswith((".png", ".jpg", ".jpeg"))
                    ]

                    search_posts.append(
                        {
                            "index": i + 1,
                            "author_name": author_name,
                            "author_headline": author_headline,
                            "relative_time": relative_time,
                            "emails": emails,
                            "links": urls,
                            "text_snippet": text_content[:300] + ("..." if len(text_content) > 300 else ""),
                        }
                    )

                    print(f"\n--- [Search Result {i + 1}] by {author_name} ({author_headline[:50]}) ---")
                    print(f"    Time: {relative_time}")
                    if emails:
                        print(f"    📧 Emails: {emails}")
                    if urls:
                        print(f"    🔗 Links: {urls}")
                    print(f"    Body: {text_content[:160]}...")
                except Exception as ex:
                    print(f"    ⚠️ Error parsing search card {i}: {ex}")

            search_output_file = LOGS_DIR / "search_posts_sample.json"
            with open(search_output_file, "w", encoding="utf-8") as f:
                json.dump(search_posts, f, indent=2)
            print(f"\n💾 Saved {len(search_posts)} search posts sample to: {search_output_file}")

        except Exception as e:
            print(f"❌ Error during content search probe: {e}")

        await context.close()
        print("\n✅ Probing completed successfully.")


if __name__ == "__main__":
    asyncio.run(probe_posts())
