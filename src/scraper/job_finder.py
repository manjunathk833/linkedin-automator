from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import os
import re
import urllib.parse
from typing import Any

from playwright.async_api import async_playwright

from src.tailor.resume_tailorer import ResumeTailorer


class LinkedInJobFinder:
    def __init__(
        self, cdp_url: str = "http://localhost:9222", use_ai: bool = True, db_file: str = "data/processed_jobs.json"
    ):
        self.cdp_url = cdp_url
        self.use_ai = use_ai
        self.db_file = db_file
        self.tailorer = ResumeTailorer(use_ai=use_ai)
        # Raw card counts per LinkedIn surface (pre-dedup) + live auth status of the last run.
        # Consumed by the daily runner to detect logged-out / zero-yield runs instead of reporting SUCCESS.
        self.channel_yield: dict[str, int] = {}
        self.last_auth_status: dict[str, Any] = {}
        self.last_yield_verdict: str = "NOT_RUN"

    def _record_yield(self, surface: str, count: int) -> None:
        """Accumulates raw card counts per LinkedIn surface for zero-yield diagnostics."""
        self.channel_yield[surface] = self.channel_yield.get(surface, 0) + int(count)

    def load_processed_jobs(self) -> dict[str, Any]:
        """Loads master deduplication index from data/processed_jobs.json."""
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        if not os.path.exists(self.db_file):
            return {"job_ids": {}, "composite_hashes": {}}
        try:
            with open(self.db_file, "r") as f:
                return json.load(f)
        except Exception:
            return {"job_ids": {}, "composite_hashes": {}}

    def save_processed_jobs(self, data: dict[str, Any]):
        """Saves master deduplication index back to disk."""
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        with open(self.db_file, "w") as f:
            json.dump(data, f, indent=2)

    def generate_composite_hash(self, company: str, title: str) -> str:
        """Generates a composite hash md5(company_title) for reposted duplicate detection."""
        norm = f"{company.strip().lower()}_{title.strip().lower()}"
        return hashlib.md5(norm.encode("utf-8")).hexdigest()

    def is_duplicate(self, job_id: str, company: str, title: str, reopened_fresh: bool = False) -> bool:
        """
        Checks if a job_id or (company + title) combination has already been processed across
        all system queues (processed_jobs.json, pending_queue, approved_queue, applied_queue, application_history.json).
        If `reopened_fresh=True` (freshly reposted <24h after >=24h gap), allows re-staging when not
        currently sitting in pending/approved queues and not applied within 30 days.
        """
        # 0. Check active pending/approved queues first
        for qdir in ["data/pending_queue", "data/approved_queue"]:
            if os.path.exists(qdir) and f"{job_id}.json" in os.listdir(qdir):
                return True

        # 1. Check SQLite persistent database for completed applications (exact ID & company+role)
        try:
            from src.storage.database import ApplicationDatabase

            db = ApplicationDatabase()
            if db.is_job_applied(job_id) or db.is_company_role_applied(company, title):
                return not (reopened_fresh and db.is_reapply_eligible(job_id, company, title, min_days=30.0))
        except Exception:
            pass

        if (
            not reopened_fresh
            and os.path.exists("data/applied_queue")
            and f"{job_id}.json" in os.listdir("data/applied_queue")
        ):
            return True

        data = self.load_processed_jobs()
        job_ids = data.get("job_ids", {})
        composite_hashes = data.get("composite_hashes", {})

        # 2. Check primary job_id and composite hash
        c_hash = self.generate_composite_hash(company, title)
        if job_id in job_ids or c_hash in composite_hashes:
            return not reopened_fresh

        return False

    def _was_seen_more_than_24h_ago(self, job_id: str, company: str, title: str) -> bool:
        """Returns True if job_id or (company, title) was recorded in processed_jobs.json >= 24h ago."""
        data = self.load_processed_jobs()
        job_ids = data.get("job_ids", {})
        composite_hashes = data.get("composite_hashes", {})
        c_hash = self.generate_composite_hash(company, title)
        entry = job_ids.get(job_id) or composite_hashes.get(c_hash)
        if not isinstance(entry, dict):
            return False
        raw_ts = str(entry.get("last_seen") or entry.get("first_seen") or "").strip()
        if not raw_ts:
            return False
        try:
            dt = datetime.datetime.fromisoformat(raw_ts.replace("Z", ""))
            if dt.tzinfo is not None:
                dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            return (datetime.datetime.utcnow() - dt).total_seconds() >= 24.0 * 3600.0
        except Exception:
            return False

    def mark_job_processed(self, job_id: str, company: str, title: str, status: str = "PENDING"):
        """Registers a job into the master deduplication index."""
        data = self.load_processed_jobs()
        now = datetime.datetime.utcnow().isoformat() + "Z"
        c_hash = self.generate_composite_hash(company, title)
        existing = data.get("job_ids", {}).get(job_id) or {}

        data.setdefault("job_ids", {})[job_id] = {
            "title": title,
            "company": company,
            "first_seen": existing.get("first_seen") or now,
            "last_seen": now,
            "status": status,
        }
        data.setdefault("composite_hashes", {})[c_hash] = {
            "job_id": job_id,
            "first_seen": existing.get("first_seen") or now,
            "last_seen": now,
        }
        self.save_processed_jobs(data)

    def build_search_url(
        self,
        keywords: str,
        location: str = "Remote",
        work_types: list[str] | None = None,
        experience_levels: list[str] | None = None,
        time_posted: str = "past_week",
        start: int = 0,
        easy_apply_only: bool = False,
        distance: int | None = None,
        sort_by: str = "relevance",
    ) -> str:
        """
        Constructs clean, optimized LinkedIn job search URL supporting:
        - f_AL=true (Easy Apply filter, only when easy_apply_only is True)
        - f_WT (Work types: 1=Onsite, 2=Remote, 3=Hybrid)
        - f_E (Experience levels: 4=Mid-Senior)
        - f_TPR (Time posted: r604800=past week, r86400=past 24h, r2592000=past month)
        - distance (Search radius in miles, e.g. 25)
        - sortBy (Relevance by default, or DD when sort_by='date')
        - start (Pagination offset: 0, 25, 50)
        """
        clean_kw = keywords.strip()
        if (
            clean_kw.startswith("(")
            and clean_kw.endswith(")")
            and clean_kw.count("(") == 1
            and clean_kw.count(")") == 1
        ):
            clean_kw = clean_kw[1:-1].strip()

        base_url = "https://www.linkedin.com/jobs/search/?"
        params = {"keywords": clean_kw, "location": location}
        if sort_by and sort_by.lower() in ["date", "dd", "newest"]:
            params["sortBy"] = "DD"
        elif sort_by and sort_by.lower() in ["relevance_explicit", "r"]:
            params["sortBy"] = "R"
        if easy_apply_only:
            params["f_AL"] = "true"
        if distance is not None and int(distance) > 0:
            params["distance"] = str(distance)
        if start > 0:
            params["start"] = str(start)

        wt_map = {"onsite": "1", "remote": "2", "hybrid": "3"}
        if work_types:
            wt_codes = [wt_map[wt.lower()] for wt in work_types if wt.lower() in wt_map]
            if wt_codes:
                params["f_WT"] = ",".join(wt_codes)

        exp_map = {
            "internship": "1",
            "entry": "2",
            "associate": "3",
            "mid_senior": "4",
            "director": "5",
            "executive": "6",
        }
        if experience_levels:
            exp_codes = [exp_map[el.lower()] for el in experience_levels if el.lower() in exp_map]
            if exp_codes:
                params["f_E"] = ",".join(exp_codes)

        tpr_map = {
            "past_1h": "r3600",
            "past_3h": "r10800",
            "past_6h": "r21600",
            "past_12h": "r43200",
            "past_24h": "r86400",
            "past_48h": "r172800",
            "past_72h": "r259200",
            "past_week": "r604800",
            "past_month": "r2592000",
        }
        if time_posted and time_posted.lower() in tpr_map:
            params["f_TPR"] = tpr_map[time_posted.lower()]

        return base_url + urllib.parse.urlencode(params)

    def clean_job_description(self, raw_text: str) -> str:
        """Removes layout noise, metadata artifacts, and share buttons from scraped job descriptions."""
        if not raw_text:
            return ""
        noise_patterns = [
            r"^\s*Share\s*$",
            r"^\s*Show\s+more\s+options\s*$",
            r"^\s*Reposted\s+.*$",
            r"^\s*Over\s+\d+\s+people\s+clicked\s+apply.*$",
            r"^\s*Responses\s+managed\s+off\s+LinkedIn\s*$",
            r"^\s*Promoted\s+by\s+hirer\s*$",
            r"^\s*Report\s+this\s+job\s*$",
            r"^\s*Easy\s+Apply\s*$",
            r"^\s*Save\s*$",
            r"^\s*Apply\s*$",
            r"^\s*Show\s+more\s*$",
        ]
        lines = raw_text.split("\n")
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            is_noise = any(re.match(p, stripped, re.IGNORECASE) for p in noise_patterns)
            if not is_noise:
                cleaned_lines.append(stripped)
        return "\n\n".join(cleaned_lines)

    async def _recover_closed_page(self, page: Any) -> Any:
        """
        Self-healing tab recovery: if the active Playwright page was closed mid-run
        (e.g. 'Target page, context or browser has been closed' on shared CDP port 9222),
        spawns a fresh tab from `self._active_context`.
        """
        ctx = getattr(self, "_active_context", None)
        if ctx is None:
            return page
        try:
            if hasattr(page, "is_closed") and page.is_closed():
                new_page = await ctx.new_page()
                self._active_page = new_page
                print("🔄 Self-healed closed Playwright tab via context.new_page().")
                return new_page
        except Exception:
            try:
                new_page = await ctx.new_page()
                self._active_page = new_page
                print("🔄 Self-healed closed Playwright tab via context.new_page().")
                return new_page
            except Exception:
                pass
        return page

    async def _safe_goto(self, page: Any, url: str, timeout: int = 35000) -> bool:
        """
        Resilient Playwright navigation wrapper that recovers from timeouts, net::ERR_TIMED_OUT
        (`chrome-error://chromewebdata/`), closed tab targets (`Target page, context or browser has been closed`),
        and LinkedIn client-side redirect interruptions.
        """
        active_page = await self._recover_closed_page(getattr(self, "_active_page", None) or page)
        try:
            await active_page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            return True
        except Exception as first_err:
            err_line = str(first_err).splitlines()[0] if str(first_err) else "Navigation error"
            print(f"⚠️ Navigation warning on {url[:90]}...: {err_line}")
            if "has been closed" in err_line.lower():
                try:
                    ctx = getattr(self, "_active_context", None)
                    if ctx is not None:
                        active_page = await ctx.new_page()
                        self._active_page = active_page
                        print("🔄 Recreated closed discovery tab for navigation retry.")
                except Exception:
                    pass
            await asyncio.sleep(1.5)
            try:
                await active_page.evaluate("() => window.stop()")
            except Exception:
                pass
            try:
                await active_page.goto("about:blank", wait_until="commit", timeout=5000)
            except Exception:
                pass
            await asyncio.sleep(0.8)
            try:
                await active_page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                return True
            except Exception as retry_err:
                retry_line = str(retry_err).splitlines()[0] if str(retry_err) else "Retry failed"
                print(f"⚠️ Navigation retry failed for {url[:90]}...: {retry_line}")
                await asyncio.sleep(1.0)
                try:
                    await active_page.evaluate("() => window.stop()")
                except Exception:
                    pass
                try:
                    await active_page.goto("about:blank", wait_until="commit", timeout=5000)
                except Exception:
                    pass
                await asyncio.sleep(0.5)
                return False

    async def scroll_results_pane(self, page: Any, scrolls: int = 5):
        """Scrolls the LinkedIn search / collection results pane down to trigger lazy loading of cards."""
        try:
            pane = page.locator(
                ".jobs-search-results-list, .jobs-search__results-list, .scaffold-layout__list, div[componentkey='SearchResultsMainContent']"
            ).first
            if await pane.count() > 0:
                for _ in range(scrolls):
                    await pane.evaluate("node => node.scrollTop += 700")
                    await asyncio.sleep(0.8)
            else:
                for _ in range(scrolls):
                    await page.evaluate("window.scrollBy(0, 800)")
                    await asyncio.sleep(0.8)
        except Exception as e:
            print(f"⚠️ Scroll warning: {e}")

    async def scrape_recommended_jobs(
        self,
        page: Any,
        max_jobs: int = 50,
        max_pages: int = 5,
        collections: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Channel 2: Scrapes personalized AI recommendations across multiple LinkedIn collection feeds
        (recommended, top-applicant) and main /jobs/ hub carousels with dynamic early break and deduplication."""
        target_collections = collections or ["recommended", "top-applicant"]
        print("\n" + "=" * 50)
        print(f"🤖 CHANNEL 2: SCRAPING MULTI-COLLECTION RECOMMENDED FEEDS {target_collections}")
        print("=" * 50)

        extracted = []
        seen_ids = set()

        # Step A: Scrape carousel cards from main /jobs/ landing hub
        try:
            print("🌐 Navigating to LinkedIn Jobs Main Hub (https://www.linkedin.com/jobs/)...")
            if await self._safe_goto(page, "https://www.linkedin.com/jobs/"):
                await asyncio.sleep(2.5)
                await self.scroll_results_pane(page, scrolls=3)
                hub_cards = await page.locator(
                    ".job-card-container, .job-card-list, .jobs-search-results-list__list-item, div[data-job-id], div[role='button'][componentkey^='job-card-component-ref-']"
                ).all()
                print(f"   Found {len(hub_cards)} card(s) on main /jobs/ hub.")
                self._record_yield("jobs_hub", len(hub_cards))
                self._active_channel = "recommended_hub"
                for c_idx, card in enumerate(hub_cards):
                    if len(extracted) >= max_jobs:
                        break
                    job = await self._extract_card_payload(page, card, c_idx, default_prefix="jobshub")
                    if job:
                        job.setdefault("discovery_track", "TRACK_2_LINKEDIN")
                        job.setdefault("discovery_channel", "recommended_hub")
                        jid = str(job.get("job_id", ""))
                        if jid and jid not in seen_ids:
                            seen_ids.add(jid)
                            extracted.append(job)
        except Exception as e:
            print(f"⚠️ Notice exploring main /jobs/ hub: {e}")

        # Step B: Scrape each configured collection feed
        for col in target_collections:
            if len(extracted) >= max_jobs:
                break

            self._active_channel = col
            print(f"\n📂 Scraping LinkedIn Collection: [{col}] (up to {max_pages} pages)")
            for page_num in range(max_pages):
                if len(extracted) >= max_jobs:
                    break

                start_offset = page_num * 25
                col_url = f"https://www.linkedin.com/jobs/collections/{col}/?start={start_offset}"
                print(f"🌐 Navigating to [{col}] Page {page_num + 1} (start={start_offset}): {col_url}")

                try:
                    if not await self._safe_goto(page, col_url):
                        break
                    await asyncio.sleep(2.5)
                    await self.scroll_results_pane(page, scrolls=4)

                    cards = await page.locator(
                        ".job-card-container, .job-card-list, .jobs-search-results-list__list-item, div[data-job-id], .jobs-job-board-list__item, div[role='button'][componentkey^='job-card-component-ref-']"
                    ).all()
                    print(f"   Found {len(cards)} card(s) in collection [{col}] on Page {page_num + 1}.")
                    self._record_yield(f"collection:{col}", len(cards))

                    if len(cards) == 0:
                        print(f"ℹ️ Collection [{col}] Page {page_num + 1} returned 0 cards. Moving to next collection.")
                        break

                    col_new_count = 0
                    for card_idx, card in enumerate(cards):
                        if len(extracted) >= max_jobs:
                            break
                        job = await self._extract_card_payload(
                            page, card, card_idx, default_prefix=f"{col}_p{page_num + 1}_job"
                        )
                        if job:
                            job.setdefault("discovery_track", "TRACK_2_LINKEDIN")
                            job.setdefault("discovery_channel", col)
                            jid = str(job.get("job_id", ""))
                            if jid and jid not in seen_ids:
                                seen_ids.add(jid)
                                extracted.append(job)
                                col_new_count += 1

                    print(f"   Extracted {col_new_count} new unique job(s) from [{col}] Page {page_num + 1}.")
                    if col_new_count == 0 and page_num > 0:
                        print(f"ℹ️ No new unique cards on [{col}] Page {page_num + 1}. Advancing collection.")
                        break
                except Exception as e:
                    print(f"⚠️ Error scraping collection [{col}] page {page_num + 1}: {e}")
                    break

        print(f"\n✅ Total unique recommended jobs extracted across collections: {len(extracted)}")
        return extracted

    async def scrape_company_jobs(
        self,
        page: Any,
        company_slugs: list[str],
        max_jobs_per_company: int = 10,
    ) -> list[dict[str, Any]]:
        """Channel 5: Scrapes job openings directly published on target enterprise LinkedIn company pages
        (e.g., https://www.linkedin.com/company/swiggy-in/jobs/)."""
        print("\n" + "=" * 50)
        print(f"🏢 CHANNEL 5: SCRAPING TARGET ENTERPRISE COMPANY JOBS ({len(company_slugs)} companies)")
        print("=" * 50)

        extracted = []
        seen_ids = set()

        for slug in company_slugs:
            clean_slug = slug.strip().strip("/")
            company_url = f"https://www.linkedin.com/company/{clean_slug}/jobs/"
            print(f"\n🌐 Navigating to Company Jobs: [{clean_slug}] -> {company_url}")

            try:
                if not await self._safe_goto(page, company_url):
                    continue
                await asyncio.sleep(2.5)
                await self.scroll_results_pane(page, scrolls=3)

                cards = await page.locator(
                    ".job-card-container, div[data-job-id], .org-jobs-job-search-results-list__list-item, section.job-card-square, div[data-view-name*='recommended-jobs-card'], div[role='button'][componentkey^='job-card-component-ref-']"
                ).all()
                print(f"   Found {len(cards)} card(s) for [{clean_slug}].")
                self._record_yield("company_pages", len(cards))

                comp_new_count = 0
                for card_idx, card in enumerate(cards):
                    if comp_new_count >= max_jobs_per_company:
                        break

                    # 1. Quick title relevance check to avoid tailoring non-SDET roles
                    try:
                        title_text = ""
                        title_el = card.locator(
                            ".job-card-square__title, .artdeco-entity-lockup__title, .job-card-list__title, strong"
                        ).first
                        if await title_el.count() > 0:
                            title_text = (await title_el.text_content() or "").strip()
                            if "Job Title" in title_text:
                                title_text = title_text.replace("Job Title", "").strip()

                        t_lower = title_text.lower()
                        is_relevant = any(
                            k in t_lower for k in ["sdet", "qa", "test", "quality", "automation", "set", "qe"]
                        )
                        if not is_relevant and title_text:
                            continue
                    except Exception:
                        pass

                    self._active_channel = "company_pages"
                    job = await self._extract_card_payload(page, card, card_idx, default_prefix=f"{clean_slug}_job")
                    if job:
                        job.setdefault("discovery_track", "TRACK_2_LINKEDIN")
                        job.setdefault("discovery_channel", "company_pages")
                        jid = str(job.get("job_id", ""))
                        if jid and jid not in seen_ids:
                            seen_ids.add(jid)
                            extracted.append(job)
                            comp_new_count += 1

                print(f"   Extracted {comp_new_count} relevant job(s) from [{clean_slug}].")
            except Exception as e:
                print(f"⚠️ Error scraping company jobs for [{clean_slug}]: {e}")

        print(f"\n✅ Total unique company jobs extracted: {len(extracted)}")
        return extracted

    async def scrape_recruiter_posts(
        self,
        page: Any,
        keywords: str = '"hiring SDET" OR "hiring QA"',
        max_posts: int = 15,
        tpr_seconds: str = "r259200",
    ) -> list[dict[str, Any]]:
        """
        Channel 3: Scrapes direct recruiter hiring posts from /search/results/content/ (<=72h)
        using LinkedInPostTracker SDUI selectors and banks leads directly into SQLite hiring_posts
        (avoiding duplicate fake EASY_APPLY cards in pending_queue/).
        """
        url_date_filter = "past-24h" if tpr_seconds == "r86400" else "past-week"
        age_cutoff = "past-24h" if tpr_seconds == "r86400" else "past-72h"
        posts_url = (
            f"https://www.linkedin.com/search/results/content/?"
            f"datePosted=%22{url_date_filter}%22&keywords={urllib.parse.quote(keywords)}&sortBy=%22date_posted%22"
        )
        print("\n" + "=" * 50)
        print("📣 CHANNEL 3: SCRAPING RECRUITER HIRING POSTS FEED (Delegating to Track 3 PostTracker)")
        print(f"🌐 Navigating to: {posts_url}")
        print("=" * 50)

        try:
            from src.posts.post_tracker import LinkedInPostTracker
            from src.storage.database import ApplicationDatabase

            tracker = LinkedInPostTracker(db=ApplicationDatabase())
            if not await self._safe_goto(page, posts_url):
                return []
            await asyncio.sleep(3.0)
            for _ in range(4):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1.0)

            cards_loc = page.locator(
                "div:has(> h2:has-text('Feed post')), div:has(> span:has-text('Feed post')), "
                ".feed-shared-update-v2, .occludable-update, "
                "div[data-view-name*='search-entity-result'], "
                ".artdeco-card:has(.feed-shared-text, .update-components-text, span.break-words)"
            )
            card_count = await cards_loc.count()
            print(f"🔍 Found {card_count} raw hiring post card(s).")
            self._record_yield("recruiter_posts", card_count)

            saved_count = 0
            for idx in range(min(card_count, max_posts)):
                try:
                    card = cards_loc.nth(idx)
                    post_lead = await tracker._extract_post_from_card(card, page)
                    if post_lead:
                        rel_t = str(post_lead.get("posted_at_relative") or "")
                        if not tracker.is_post_within_age_limit(rel_t, age_cutoff):
                            continue
                        post_id = post_lead["post_id"]
                        if not tracker.db.is_hiring_post_saved(
                            post_id, content_hash=post_lead.get("content_hash")
                        ) and tracker.db.save_hiring_post(post_lead):
                            saved_count += 1
                            print(
                                f"📣 Banked hiring post lead to Track 3 DB: {post_lead.get('author_name')} @ {post_lead.get('company_name')}"
                            )
                except Exception as e:
                    print(f"⚠️ Error parsing post {idx}: {e}")
            print(f"✅ Channel 3 banked {saved_count} qualified hiring post lead(s) into SQLite hiring_posts.")
        except Exception as e:
            print(f"⚠️ Error scraping recruiter posts: {e}")

        return []

    async def scrape_similar_jobs(
        self,
        page: Any,
        seed_job_ids: list[str] | None = None,
        max_seeds: int = 3,
        max_per_seed: int = 3,
    ) -> list[dict[str, Any]]:
        """Channel 4: Scrapes LinkedIn's 'Similar jobs' / 'More jobs' sidebar module from seed job view pages."""
        print("\n" + "=" * 50)
        print("🔗 CHANNEL 4: SCRAPING SIMILAR JOBS SIDEBAR MODULE")
        print("=" * 50)

        seeds = [str(jid) for jid in (seed_job_ids or []) if str(jid).isdigit()]
        if not seeds:
            processed = self.load_processed_jobs().get("job_ids", {})
            seeds = [str(jid) for jid in reversed(list(processed.keys())) if str(jid).isdigit()]
        seeds = seeds[:max_seeds]

        if not seeds:
            print("ℹ️ No numeric LinkedIn seed job IDs available yet for Similar Jobs traversal.")
            self._record_yield("similar_jobs", 0)
            return []

        extracted: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for seed_id in seeds:
            view_url = f"https://www.linkedin.com/jobs/view/{seed_id}/"
            print(f"\n🌐 Navigating to Seed Job View [{seed_id}]: {view_url}")
            try:
                if not await self._safe_goto(page, view_url):
                    continue
                await asyncio.sleep(2.5)
                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, 900)")
                    await asyncio.sleep(0.8)

                cards = await page.locator(
                    "section:has(h2:has-text('Similar jobs')) .job-card-container, "
                    "section:has(h2:has-text('More jobs')) .job-card-container, "
                    ".jobs-similar-jobs .job-card-container, "
                    ".jobs-similar-jobs div[data-job-id], "
                    "aside .job-card-container, "
                    "div[data-view-name*='similar-jobs'] a[href*='/jobs/view/']"
                ).all()
                print(f"   Found {len(cards)} similar job card(s) for seed [{seed_id}].")
                self._record_yield("similar_jobs", len(cards))

                seed_extracted = 0
                for c_idx, card in enumerate(cards):
                    if seed_extracted >= max_per_seed:
                        break
                    try:
                        raw_text = (await card.text_content() or "").lower()
                        if raw_text and not any(
                            k in raw_text for k in ("sdet", "qa", "test", "quality", "automation", "qe")
                        ):
                            continue
                    except Exception:
                        pass

                    self._active_channel = "similar_jobs"
                    job = await self._extract_card_payload(page, card, c_idx, default_prefix=f"sim_{seed_id}")
                    if job:
                        job.setdefault("discovery_track", "TRACK_2_LINKEDIN")
                        job.setdefault("discovery_channel", "similar_jobs")
                        jid = str(job.get("job_id", ""))
                        if jid and jid not in seen_ids:
                            seen_ids.add(jid)
                            extracted.append(job)
                            seed_extracted += 1
            except Exception as e:
                print(f"⚠️ Error scraping similar jobs for seed [{seed_id}]: {e}")

        print(f"\n✅ Total unique similar jobs extracted: {len(extracted)}")
        return extracted

    async def _extract_card_payload(
        self, page: Any, card: Any, idx: int, default_prefix: str = "job", channel: str | None = None
    ) -> dict[str, Any] | None:
        """
        Extracts title, company, location, and full job description from a job card and runs AI tailoring.
        Includes title click triggering, 'See more' expansion, UI noise filtering, and direct page fallback.
        """
        try:
            # 1. Extract job_id from attributes, SDUI componentkey, or links
            job_id = await card.get_attribute("data-job-id")
            if not job_id:
                comp_key = await card.get_attribute("componentkey")
                if comp_key and "job-card-component-ref-" in comp_key:
                    job_id = comp_key.split("job-card-component-ref-")[-1].strip()
            if not job_id:
                urn = await card.get_attribute("data-entity-urn")
                if urn and "jobPosting:" in urn:
                    job_id = urn.split("jobPosting:")[-1].strip()

            if not job_id:
                link = card.locator('a[href*="/jobs/"]').first
                if await link.count() > 0:
                    href = await link.get_attribute("href") or ""
                    if "currentJobId=" in href:
                        job_id = href.split("currentJobId=")[1].split("&")[0].strip()
                    elif "/jobs/view/" in href:
                        raw_id = href.split("/jobs/view/")[1].split("/")[0].split("?")[0].strip()
                        if raw_id and raw_id.isdigit():
                            job_id = raw_id

            if not job_id or not job_id.isdigit():
                job_id = f"{default_prefix}_{idx + 1}"

            # 2. Extract title directly from list card DOM element (stripping LinkedIn .sr-only prefix)
            title_elem = card.locator(
                '.job-card-list__title, .job-card-container__link, a[data-control-name="job_card_title"], .job-card-square__title, .artdeco-entity-lockup__title'
            ).first
            raw_title = await title_elem.text_content() if await title_elem.count() > 0 else None

            # 3. Extract company name directly from list card DOM element or company link
            raw_company = None
            company_elem = card.locator(
                "span.job-card-container__primary-description, a.job-card-container__company-name, .job-card-container__company-name, .job-card-container__primary-description, .job-card-square__company-name, .artdeco-entity-lockup__subtitle, .job-card-list__company-name"
            ).first
            if await company_elem.count() > 0:
                text = await company_elem.text_content()
                if text and text.strip():
                    raw_company = text.strip()

            if not raw_company:
                comp_link = card.locator("a[href*='/company/']").first
                if await comp_link.count() > 0:
                    c_text = await comp_link.text_content()
                    if c_text and c_text.strip():
                        raw_company = c_text.strip()

            location_elem = card.locator(
                ".job-card-container__metadata-item, .job-card-square__metadata-item, .artdeco-entity-lockup__caption"
            ).first
            raw_loc = await location_elem.text_content() if await location_elem.count() > 0 else None

            # 3b. SDUI AI-Search Card Fallback (div[role="button"][componentkey^="job-card-component-ref-"])
            if not raw_title or not raw_company:
                try:
                    sdui_text = await card.inner_text()
                    if isinstance(sdui_text, str) and sdui_text.strip():
                        sdui_lines: list[str] = []
                        for ln in sdui_text.splitlines():
                            s_ln = ln.strip()
                            if not s_ln or s_ln == "·" or s_ln.lower().startswith("selected,"):
                                continue
                            s_ln = re.sub(r"\s*\(Verified job\)\s*$", "", s_ln, flags=re.IGNORECASE).strip()
                            if s_ln and (not sdui_lines or sdui_lines[-1].lower() != s_ln.lower()):
                                sdui_lines.append(s_ln)
                        if not raw_title and len(sdui_lines) >= 1:
                            raw_title = sdui_lines[0]
                        if not raw_company and len(sdui_lines) >= 2:
                            raw_company = sdui_lines[1]
                        if not raw_loc and len(sdui_lines) >= 3:
                            raw_loc = sdui_lines[2]
                except Exception:
                    pass

            title = re.sub(
                r"^Job\s+Title\s+", "", (raw_title or "Software Engineer").strip(), flags=re.IGNORECASE
            ).strip()
            company = re.sub(
                r"^Company\s+Name\s+", "", (raw_company or "Tech Company").strip(), flags=re.IGNORECASE
            ).strip()

            # 3c. Enforce SDET/QA/AI-QA title relevance before clicking or tailoring
            if raw_title:
                from src.ingestion.filters import is_sdet_title

                if not is_sdet_title(title):
                    print(f"⏭️  Skipping non-SDET LinkedIn card: {title} @ {company} (ID: {job_id})")
                    return None

            # 3d. Pre-Click Location Gate: Reject explicit foreign/US/UK/EU card locations before clicking or invoking Gemini
            if raw_loc and raw_loc.strip():
                from src.ingestion.filters import is_india_or_remote_location

                if not is_india_or_remote_location(raw_loc.strip(), allow_unspecified=True):
                    print(
                        f"⏭️  Skipping foreign-location LinkedIn card (pre-click): {title} @ {company} [{raw_loc.strip()}] (ID: {job_id})"
                    )
                    return None

            resolved_channel = channel or getattr(self, "_active_channel", "search") or "search"
            raw_meta_and_desc = ""
            try:
                card_meta = await card.inner_text()
                if isinstance(card_meta, str) and card_meta.strip():
                    raw_meta_and_desc = card_meta.strip()
            except Exception:
                pass

            is_card_reposted_or_24h = bool(
                resolved_channel in ("sniper_fresh_24h", "sniper_ultra_3h")
                or re.search(
                    r"\b(?:reposted|\d+\s+(?:minute|hour)s?\s+ago|1\s+day\s+ago)\b",
                    raw_meta_and_desc,
                    re.IGNORECASE,
                )
            )

            # 4. SMART DEDUPLICATION, RE-OPENED (<24h) & REPOSTED-APPLIED FOLLOW-UP GATE BEFORE CLICKING!
            reopened_fresh = False
            try:
                from src.storage.database import ApplicationDatabase

                db = ApplicationDatabase()
                applied_details = db.get_applied_job_details(job_id, company, title)
                if applied_details is not None:
                    if is_card_reposted_or_24h and db.is_reapply_eligible(job_id, company, title, min_days=30.0):
                        reopened_fresh = True
                        print(
                            f"🔄 Re-staging reposted role (>30d since applied on new ID): {title} @ {company} (ID: {job_id})"
                        )
                    else:
                        days_ago = float(applied_details.get("days_since_applied") or 0.0)
                        if is_card_reposted_or_24h and 2.0 <= days_ago < 30.0:
                            try:
                                from src.tailor.referral_generator import (
                                    ReferralNoteGenerator,
                                    resolve_direct_ats_portal_url,
                                )

                                existing_outreach = db.get_referral_outreach(job_id=job_id, limit=5)
                                if not any(r.get("outreach_type") == "REPOST_FOLLOWUP" for r in existing_outreach):
                                    direct_portal = resolve_direct_ats_portal_url(company)
                                    followup_note = ReferralNoteGenerator.generate_repost_followup_note(
                                        {
                                            "job_id": job_id,
                                            "company_name": company,
                                            "job_title": title,
                                            "job_url": f"https://www.linkedin.com/jobs/view/{job_id}/",
                                        },
                                        days_since_applied=days_ago,
                                    )
                                    db.log_referral_outreach(
                                        job_id=job_id,
                                        company_name=company,
                                        job_title=title,
                                        outreach_type="REPOST_FOLLOWUP",
                                        note_content=followup_note,
                                        requisition_id=job_id,
                                        contact_linkedin_url=direct_portal
                                        or f"https://www.linkedin.com/jobs/view/{job_id}/",
                                    )
                                    print(
                                        f"📨 Logged REPOST_FOLLOWUP note for reposted applied role ({days_ago:.1f}d ago): {title} @ {company}"
                                    )
                            except Exception:
                                pass
                        print(f"⏭️  Skipping already-applied job: {title} @ {company} (ID: {job_id})")
                        return None
                elif is_card_reposted_or_24h and self._was_seen_more_than_24h_ago(job_id, company, title):
                    reopened_fresh = True
            except Exception:
                pass

            if self.is_duplicate(job_id, company, title, reopened_fresh=reopened_fresh):
                print(f"⏭️  Skipping duplicate job: {title} @ {company} (ID: {job_id})")
                return None

            loc = (raw_loc or "Remote").strip()

            # 5. Full Job Description Scraping with Title Click, "See more" expansion, and noise cleaning
            desc_text = f"Position for {title} @ {company} requiring automation experience in Python, Java, API testing, REST Assured, Playwright, and CI/CD."

            try:
                from src.storage.database import ApplicationDatabase

                db = ApplicationDatabase()
                applied_details = db.get_applied_job_details(job_id, company, title)
                if applied_details is not None:
                    if is_card_reposted_or_24h and db.is_reapply_eligible(job_id, company, title, min_days=30.0):
                        reopened_fresh = True
                        print(
                            f"🔄 Re-staging reposted role (>30d since applied on new ID): {title} @ {company} (ID: {job_id})"
                        )
                    else:
                        days_ago = float(applied_details.get("days_since_applied") or 0.0)
                        if is_card_reposted_or_24h and 2.0 <= days_ago < 30.0:
                            try:
                                from src.tailor.referral_generator import (
                                    ReferralNoteGenerator,
                                    resolve_direct_ats_portal_url,
                                )

                                existing_outreach = db.get_referral_outreach(job_id=job_id, limit=5)
                                if not any(r.get("outreach_type") == "REPOST_FOLLOWUP" for r in existing_outreach):
                                    direct_portal = resolve_direct_ats_portal_url(company)
                                    followup_note = ReferralNoteGenerator.generate_repost_followup_note(
                                        {
                                            "job_id": job_id,
                                            "company_name": company,
                                            "job_title": title,
                                            "job_url": f"https://www.linkedin.com/jobs/view/{job_id}/",
                                        },
                                        days_since_applied=days_ago,
                                    )
                                    db.log_referral_outreach(
                                        job_id=job_id,
                                        company_name=company,
                                        job_title=title,
                                        outreach_type="REPOST_FOLLOWUP",
                                        note_content=followup_note,
                                        requisition_id=job_id,
                                        contact_linkedin_url=direct_portal
                                        or f"https://www.linkedin.com/jobs/view/{job_id}/",
                                    )
                                    print(
                                        f"📨 Logged REPOST_FOLLOWUP note for reposted applied role ({days_ago:.1f}d ago): {title} @ {company}"
                                    )
                            except Exception:
                                pass
                        print(f"⏭️  Skipping already-applied job: {title} @ {company} (ID: {job_id})")
                        return None
                elif is_card_reposted_or_24h and self._was_seen_more_than_24h_ago(job_id, company, title):
                    reopened_fresh = True
            except Exception:
                pass

            if self.is_duplicate(job_id, company, title, reopened_fresh=reopened_fresh):
                print(f"⏭️  Skipping duplicate job: {title} @ {company} (ID: {job_id})")
                return None

            loc = (raw_loc or "Remote").strip()

            # 5. Full Job Description Scraping with Title Click, "See more" expansion, and noise cleaning
            desc_text = f"Position for {title} @ {company} requiring automation experience in Python, Java, API testing, REST Assured, Playwright, and CI/CD."

            try:
                if await card.is_visible():
                    # Click title link explicitly for reliable detail pane rendering
                    title_click_elem = card.locator(
                        '.job-card-list__title, .job-card-container__link, a[data-control-name="job_card_title"]'
                    ).first
                    if await title_click_elem.count() > 0:
                        await title_click_elem.click(timeout=2000)
                    else:
                        await card.click(timeout=2000)
                    await asyncio.sleep(1.2)

                    # Capture top-card metadata (posting age, Reposted flag, applicant volume) if rendered separately
                    top_card_elem = page.locator(
                        ".job-details-jobs-unified-top-card__container, "
                        ".job-details-jobs-unified-top-card__primary-description-container, "
                        ".job-details-jobs-unified-top-card__tertiary-description-container, "
                        ".jobs-unified-top-card__subtitle-secondary-grouping"
                    ).first
                    if await top_card_elem.count() > 0:
                        top_txt = (await top_card_elem.text_content() or "").strip()
                        if top_txt:
                            raw_meta_and_desc = f"{raw_meta_and_desc}\n{top_txt}".strip()

                    # Expand "See more" if present
                    see_more_btn = page.locator(
                        "button.jobs-description__footer-button, button[aria-label*='Expand'], button.jobs-description-content__footer-button"
                    ).first
                    if await see_more_btn.count() > 0 and await see_more_btn.is_visible():
                        try:
                            await see_more_btn.click(timeout=1000)
                            await asyncio.sleep(0.5)
                        except Exception:
                            pass

                    details_elem = page.locator(
                        "#job-details, .jobs-description__content, .jobs-search__job-details, article.jobs-description__container, [data-testid='expandable-text-box'], [data-sdui-screen*='SemanticJobDetails']"
                    ).first
                    if await details_elem.count() > 0:
                        raw_desc = await details_elem.text_content()
                        raw_meta_and_desc = f"{raw_meta_and_desc}\n{raw_desc or ''}".strip()
                        cleaned = self.clean_job_description(raw_desc or "")
                        if cleaned and len(cleaned) > 50:
                            desc_text = cleaned
            except Exception:
                pass

            # 5b. Enforce Post-Extraction Freshness & Repost-Saturation Gate (<=1d for Sniper, <=3d for other channels)
            if raw_meta_and_desc:
                from src.ingestion.filters import is_linkedin_posting_fresh_and_unsaturated

                is_sniper = resolved_channel == "sniper_fresh_24h"
                is_fresh, fresh_reason = is_linkedin_posting_fresh_and_unsaturated(
                    raw_meta_and_desc,
                    max_days=1 if is_sniper else 3,
                    is_sniper_24h=is_sniper,
                )
                if not is_fresh:
                    print(
                        f"⏭️  Skipping stale/saturated LinkedIn job ({fresh_reason}, channel={resolved_channel}): {title} @ {company} (ID: {job_id})"
                    )
                    return None

            # 6. Detect Application Type (EASY_APPLY vs LINKEDIN_EXTERNAL)
            application_type = "LINKEDIN_EXTERNAL"
            external_url = None
            try:
                apply_btn = page.locator(
                    ".jobs-apply-button, .jobs-s-apply button, button.jobs-apply-button--top-card, button[data-control-name*='apply'], a.jobs-apply-button"
                ).first
                if await apply_btn.count() > 0:
                    btn_text = (await apply_btn.text_content() or "").strip().lower()
                    aria_label = (await apply_btn.get_attribute("aria-label") or "").strip().lower()
                    combined_btn_desc = f"{btn_text} {aria_label}"
                    if "easy apply" in combined_btn_desc:
                        application_type = "EASY_APPLY"
                    else:
                        application_type = "LINKEDIN_EXTERNAL"
                        href = await apply_btn.get_attribute("href")
                        if href and href.startswith("http"):
                            external_url = href
            except Exception:
                pass

            # Check upfront if company is a categorized Dream Org
            is_dream = False
            try:
                from src.storage.database import ApplicationDatabase

                is_dream = ApplicationDatabase().is_dream_company(company)
            except Exception:
                pass

            from src.ingestion.filters import extract_linkedin_applicant_metrics

            applicant_metrics = extract_linkedin_applicant_metrics(raw_meta_and_desc, application_type=application_type)

            job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"
            resolved_channel = channel or getattr(self, "_active_channel", "search") or "search"
            raw_job = {
                "job_id": job_id,
                "source": "linkedin",
                "discovery_track": "TRACK_2_LINKEDIN",
                "discovery_channel": resolved_channel,
                "url": job_url,
                "job_url": job_url,
                "is_dream_org": is_dream,
                "application_type": application_type,
                "reopened_fresh": reopened_fresh,
                "applicant_metrics": applicant_metrics,
                "job_details": {
                    "title": title,
                    "company": company,
                    "location": loc,
                    "job_url": job_url,
                    "external_url": external_url,
                    "is_dream_org": is_dream,
                    "reopened_fresh": reopened_fresh,
                    "applicant_metrics": applicant_metrics,
                    "requirements": desc_text[:3000],
                },
            }

            tailored = self.tailorer.tailor_job_payload(raw_job)
            self.save_job_to_queue(tailored)
            self.mark_job_processed(job_id, company, title)
            return tailored
        except Exception as e:
            print(f"⚠️ Error extracting card payload {idx}: {e}")
            return None

    async def search_all_channels(
        self, search_profiles: list[dict[str, Any]], discovery_config: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        MASTER 4-CHANNEL DISCOVERY ENGINE:
        Runs Step 1 (Deep Paginated Search with Early Break), Step 2 (Recommended Feed Multi-Page), Step 3 (Recruiter Posts),
        and Step 4 (Similar Jobs Sidebar) in a SINGLE persistent Chrome session in one fell swoop!
        """
        discovery_config = discovery_config or {}
        max_pages = discovery_config.get("max_pages_per_search", 3)
        max_rec_pages = discovery_config.get("max_recommended_pages", 5)
        rec_collections = discovery_config.get(
            "recommendation_collections", ["recommended", "top-applicant", "still-hiring"]
        )
        sort_by_default = discovery_config.get("sort_by", "relevance")
        enable_rec = discovery_config.get("enable_recommended_feed", True)
        enable_posts = discovery_config.get("enable_recruiter_posts", True)
        enable_similar = bool(discovery_config.get("enable_similar_jobs", True))
        enable_sniper = bool(discovery_config.get("enable_sniper_fresh_drops", True))
        sniper_time_posted = discovery_config.get("sniper_time_posted", "past_24h")
        sniper_sort_by = discovery_config.get("sniper_sort_by", "date")
        enable_company_pages = bool(discovery_config.get("enable_target_company_pages", True))
        company_slugs = discovery_config.get(
            "target_company_slugs",
            ["swiggy-in", "dunzo-in", "cred-club", "flipkart", "postman-platform", "browserstack"],
        )
        is_headless = bool(discovery_config.get("headless", False))

        self.channel_yield = {}
        all_jobs = []

        async with async_playwright() as p:
            from src.browser.cdp_connector import connect_cdp, launch_persistent_browser
            from src.browser.linkedin_auth import (
                capture_zero_yield_evidence,
                check_profile_session,
                summarize_yield,
                verify_live_session,
            )

            context = None
            try:
                print("\n" + "=" * 60)
                print(f"🚀 LAUNCHING 10X MULTI-CHANNEL JOB DISCOVERY ENGINE (Headless: {is_headless})")
                print("=" * 60)
                context, page = await launch_persistent_browser(p, headless=is_headless)
            except Exception as e1:
                print(f"⚠️ Persistent browser launch failed: {e1}, trying CDP fallback...")
                try:
                    _browser, page = await connect_cdp(p, self.cdp_url)
                except Exception as e2:
                    print(f"⚠️ CDP fallback also failed: {e2}")
                    return all_jobs

            self._active_context = context
            self._active_page = page

            # -------------------------------------------------------------
            # PRE-FLIGHT: LINKEDIN SESSION & AUTHWALL VERIFICATION
            # -------------------------------------------------------------
            offline_auth = check_profile_session()
            live_auth = await verify_live_session(page)
            self.last_auth_status = {**offline_auth, **live_auth}
            if live_auth.get("status") == "AUTHWALL" or not offline_auth.get("is_authenticated"):
                print(f"🚨 LINKEDIN AUTH PREFLIGHT FAILED: {self.last_auth_status.get('message')}")
                await capture_zero_yield_evidence(page, "linkedin_auth_preflight")
                self.last_yield_verdict = "AUTH_FAILED"
                if getattr(context, "_is_shared_cdp", False):
                    try:
                        await page.close()
                    except Exception:
                        pass
                elif context is not None:
                    await context.close()
                return all_jobs

            # -------------------------------------------------------------
            # STEP 0: SNIPER FRESH DROPS PASS (Wave 1: <3h Ultra-Fresh First-25, Wave 2: <24h)
            # -------------------------------------------------------------
            if enable_sniper and search_profiles:
                print("\n" + "=" * 50)
                print(
                    f"🎯 STEP 0: LINKEDIN SNIPER FRESH DROPS PASS (Wave 1: past_3h [First-25], Wave 2: {sniper_time_posted}, sort={sniper_sort_by})"
                )
                print("=" * 50)
                sniper_waves: list[tuple[str, list[dict[str, Any]]]] = []
                if sniper_time_posted != "past_3h":
                    sniper_waves.append(("past_3h", search_profiles[:2]))
                sniper_waves.append((sniper_time_posted, search_profiles))

                for wave_tpr, wave_profiles in sniper_waves:
                    for s_idx, sp in enumerate(wave_profiles):
                        s_kw = sp.get("keywords", "Senior SDET")
                        s_loc = sp.get("location", "Remote")
                        s_url = self.build_search_url(
                            keywords=s_kw,
                            location=s_loc,
                            work_types=sp.get("work_types"),
                            experience_levels=sp.get("experience_levels"),
                            time_posted=wave_tpr,
                            start=0,
                            easy_apply_only=sp.get("easy_apply_only", discovery_config.get("easy_apply_only", False)),
                            distance=sp.get("distance", discovery_config.get("distance")),
                            sort_by=sniper_sort_by,
                        )
                        print(f"🎯 Sniper [{wave_tpr}] Profile #{s_idx + 1}: {s_url}")
                        try:
                            if not await self._safe_goto(page, s_url):
                                page = getattr(self, "_active_page", None) or page
                                continue
                            page = getattr(self, "_active_page", None) or page
                            await asyncio.sleep(2.5)
                            await self.scroll_results_pane(page, scrolls=3)
                            s_cards = await page.locator(
                                ".job-card-container, .job-card-list, .jobs-search-results-list__list-item, div[data-job-id], div[role='button'][componentkey^='job-card-component-ref-']"
                            ).all()
                            print(f"   Found {len(s_cards)} fresh ({wave_tpr}) card(s) on Sniper Profile #{s_idx + 1}.")
                            self._record_yield("sniper_fresh_24h", len(s_cards))
                            self._active_channel = "sniper_fresh_24h"
                            for c_idx, card in enumerate(s_cards[:15]):
                                job = await self._extract_card_payload(
                                    page, card, c_idx, default_prefix=f"sniper_{wave_tpr}_{s_idx + 1}"
                                )
                                if job:
                                    all_jobs.append(job)
                        except Exception as e:
                            print(f"⚠️ Sniper pass warning on profile #{s_idx + 1} ({wave_tpr}): {e}")

            # -------------------------------------------------------------
            # STEP 1: DEEP PAGINATED SEARCH (Pages 1, 2, 3 + Early Break)
            # -------------------------------------------------------------
            for profile_idx, sp in enumerate(search_profiles):
                keywords = sp.get("keywords", "Senior SDET")
                location = sp.get("location", "Remote")
                max_jobs = sp.get("max_jobs", 25)
                work_types = sp.get("work_types")
                experience_levels = sp.get("experience_levels")
                time_posted = sp.get("time_posted", "past_week")
                easy_apply_only = sp.get(
                    "easy_apply_only",
                    discovery_config.get("easy_apply_only", False),
                )
                distance = sp.get("distance", discovery_config.get("distance"))

                print(f"\n🔍 Search Profile #{profile_idx + 1}: '{keywords}' in '{location}' (max: {max_jobs})")

                extracted_for_profile = 0
                for page_num in range(max_pages):
                    if extracted_for_profile >= max_jobs:
                        break

                    start_offset = page_num * 25
                    profile_sort_by = sp.get("sort_by") or sort_by_default
                    search_url = self.build_search_url(
                        keywords=keywords,
                        location=location,
                        work_types=work_types,
                        experience_levels=experience_levels,
                        time_posted=time_posted,
                        start=start_offset,
                        easy_apply_only=easy_apply_only,
                        distance=distance,
                        sort_by=profile_sort_by,
                    )
                    print(f"🌐 Navigating to Page {page_num + 1} (start={start_offset}): {search_url}")

                    try:
                        if not await self._safe_goto(page, search_url):
                            continue
                        await asyncio.sleep(2.5)
                        await self.scroll_results_pane(page, scrolls=4)

                        cards = await page.locator(
                            ".job-card-container, .job-card-list, .jobs-search-results-list__list-item, div[data-job-id], div[role='button'][componentkey^='job-card-component-ref-']"
                        ).all()
                        print(f"   Found {len(cards)} job card(s) on Page {page_num + 1}.")
                        self._record_yield("search", len(cards))

                        if len(cards) == 0:
                            print(
                                f"ℹ️ Page {page_num + 1} returned 0 cards. Early breaking search loop for Profile #{profile_idx + 1}."
                            )
                            break

                        self._active_channel = "search"
                        for card_idx, card in enumerate(cards):
                            if extracted_for_profile >= max_jobs:
                                break
                            job = await self._extract_card_payload(
                                page, card, card_idx, default_prefix=f"p{page_num + 1}_job"
                            )
                            if job:
                                all_jobs.append(job)
                                extracted_for_profile += 1

                    except Exception as e:
                        print(f"⚠️ Error on page {page_num + 1} for '{keywords}': {e}")

            # -------------------------------------------------------------
            # STEP 2: PERSONALIZED RECOMMENDED JOBS FEED (MULTI-PAGE)
            # -------------------------------------------------------------
            if enable_rec:
                rec_jobs = await self.scrape_recommended_jobs(
                    page, max_jobs=50, max_pages=max_rec_pages, collections=rec_collections
                )
                all_jobs.extend(rec_jobs)

            # -------------------------------------------------------------
            # STEP 2B: TARGET ENTERPRISE COMPANY JOBS (CHANNEL 5)
            # -------------------------------------------------------------
            if enable_company_pages and company_slugs:
                company_jobs = await self.scrape_company_jobs(page, company_slugs=company_slugs, max_jobs_per_company=5)
                all_jobs.extend(company_jobs)

            # -------------------------------------------------------------
            # STEP 3: RECRUITER HIRING POSTS FEED
            # -------------------------------------------------------------
            if enable_posts:
                post_jobs = await self.scrape_recruiter_posts(
                    page, keywords='"hiring SDET" OR "hiring QA"', max_posts=15
                )
                all_jobs.extend(post_jobs)

            # -------------------------------------------------------------
            # STEP 4: SIMILAR JOBS SIDEBAR MODULE (CHANNEL 4)
            # -------------------------------------------------------------
            if enable_similar:
                seed_ids = [str(j.get("job_id")) for j in all_jobs if str(j.get("job_id", "")).isdigit()]
                sim_jobs = await self.scrape_similar_jobs(page, seed_job_ids=seed_ids, max_seeds=3, max_per_seed=3)
                all_jobs.extend(sim_jobs)

            # -------------------------------------------------------------
            # ZERO-YIELD VERDICT ON AUTH-ONLY SURFACES
            # -------------------------------------------------------------
            if max_pages == 0 and not enable_rec and not enable_company_pages and not enable_posts:
                auth_surfaces = ("sniper_fresh_24h",)
            else:
                auth_surfaces = tuple(
                    ["jobs_hub", "company_pages", "recruiter_posts"] + [f"collection:{c}" for c in rec_collections]
                )
            self.last_yield_verdict = summarize_yield(self.channel_yield, auth_surfaces)
            if self.last_yield_verdict == "ZERO_YIELD_SUSPECT":
                print(f"⚠️ ZERO-YIELD SUSPECT: All auth-only LinkedIn surfaces returned 0 cards ({self.channel_yield}).")
                await capture_zero_yield_evidence(page, "linkedin_channels_zero_yield")
            else:
                print(f"📊 LinkedIn Channel Raw Card Yield: {self.channel_yield} (Verdict: {self.last_yield_verdict})")

            # Close single browser session ONCE at the end of all channels
            if getattr(context, "_is_shared_cdp", False):
                try:
                    await page.close()
                except Exception:
                    pass
                print("\n🔒 Closed temporary discovery tab on shared Chrome CDP session.")
            elif context is not None:
                await context.close()
                print("\n🔒 Closed multi-channel batch Chrome session successfully.")

        return all_jobs

    async def search_jobs_batch(self, search_profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Backwards compatible batch search method."""
        return await self.search_all_channels(search_profiles)

    async def search_jobs(self, keywords: str, location: str = "Remote", max_jobs: int = 5) -> list[dict[str, Any]]:
        """Backwards compatible single search query method."""
        return await self.search_all_channels([{"keywords": keywords, "location": location, "max_jobs": max_jobs}])

    def save_job_to_queue(self, job_payload: dict[str, Any], queue_dir: str = "data/pending_queue") -> str:
        """Saves a job payload into data/pending_queue/{job_id}.json (enriched with 3-Tier InterviewRouter strategy)."""
        os.makedirs(queue_dir, exist_ok=True)
        if "routing_strategy" not in job_payload:
            try:
                from src.posts.post_tracker import LinkedInPostTracker
                from src.tailor.referral_generator import InterviewRouter

                matched = LinkedInPostTracker().find_matching_posts_for_job(job_payload)
                job_payload["routing_strategy"] = InterviewRouter.classify_job_strategy(
                    job_payload, matched_posts=matched
                )
            except Exception:
                pass
        job_id = job_payload.get("job_id", "job_sample")
        filepath = os.path.join(queue_dir, f"{job_id}.json")
        with open(filepath, "w") as f:
            json.dump(job_payload, f, indent=2)
        print(f"💾 Saved pending job to: {filepath}")
        return filepath
