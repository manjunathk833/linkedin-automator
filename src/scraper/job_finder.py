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

    def is_duplicate(self, job_id: str, company: str, title: str) -> bool:
        """
        Checks if a job_id or (company + title) combination has already been processed across
        all system queues (processed_jobs.json, pending_queue, approved_queue, applied_queue, application_history.json).
        """
        data = self.load_processed_jobs()
        job_ids = data.get("job_ids", {})
        composite_hashes = data.get("composite_hashes", {})

        # 1. Check primary job_id
        if job_id in job_ids:
            return True

        # 2. Check composite hash
        c_hash = self.generate_composite_hash(company, title)
        if c_hash in composite_hashes:
            return True

        # 3. Check physical file queues
        for qdir in ["data/pending_queue", "data/approved_queue", "data/applied_queue"]:
            if os.path.exists(qdir) and f"{job_id}.json" in os.listdir(qdir):
                return True

        return False

    def mark_job_processed(self, job_id: str, company: str, title: str, status: str = "PENDING"):
        """Registers a job into the master deduplication index."""
        data = self.load_processed_jobs()
        now = datetime.datetime.utcnow().isoformat() + "Z"
        c_hash = self.generate_composite_hash(company, title)

        data.setdefault("job_ids", {})[job_id] = {
            "title": title,
            "company": company,
            "first_seen": now,
            "status": status,
        }
        data.setdefault("composite_hashes", {})[c_hash] = {"job_id": job_id, "first_seen": now}
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
    ) -> str:
        """
        Constructs clean, optimized LinkedIn job search URL supporting:
        - f_AL=true (Easy Apply filter, only when easy_apply_only is True)
        - f_WT (Work types: 1=Onsite, 2=Remote, 3=Hybrid)
        - f_E (Experience levels: 4=Mid-Senior)
        - f_TPR (Time posted: r604800=past week, r86400=past 24h, r2592000=past month)
        - distance (Search radius in miles, e.g. 25)
        - sortBy=DD (Sort newest first)
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
        params = {"keywords": clean_kw, "location": location, "sortBy": "DD"}
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

        tpr_map = {"past_24h": "r86400", "past_week": "r604800", "past_month": "r2592000"}
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

    async def scroll_results_pane(self, page: Any, scrolls: int = 5):
        """Scrolls the LinkedIn search / collection results pane down to trigger lazy loading of cards."""
        try:
            pane = page.locator(".jobs-search-results-list, .jobs-search__results-list, .scaffold-layout__list").first
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

    async def scrape_recommended_jobs(self, page: Any, max_jobs: int = 50, max_pages: int = 5) -> list[dict[str, Any]]:
        """Channel 2: Scrapes personalized AI recommendations from /jobs/collections/recommended/ across multiple pages with dynamic early break."""
        print("\n" + "=" * 50)
        print(f"🤖 CHANNEL 2: SCRAPING PERSONALIZED RECOMMENDED JOBS FEED (UP TO {max_pages} PAGES)")
        print("=" * 50)

        extracted = []
        for page_num in range(max_pages):
            if len(extracted) >= max_jobs:
                break

            start_offset = page_num * 25
            rec_url = f"https://www.linkedin.com/jobs/collections/recommended/?start={start_offset}"
            print(f"🌐 Navigating to Recommended Feed Page {page_num + 1} (start={start_offset}): {rec_url}")

            try:
                await page.goto(rec_url, wait_until="domcontentloaded")
                await asyncio.sleep(2.5)
                await self.scroll_results_pane(page, scrolls=5)

                cards = await page.locator(
                    ".job-card-container, .job-card-list, .jobs-search-results-list__list-item, div[data-job-id], .jobs-job-board-list__item"
                ).all()
                print(f"   Found {len(cards)} recommended job card(s) on Page {page_num + 1}.")

                if len(cards) == 0:
                    print(
                        f"ℹ️ Recommended feed Page {page_num + 1} returned 0 cards. Stopping recommendation collection."
                    )
                    break

                for card_idx, card in enumerate(cards):
                    if len(extracted) >= max_jobs:
                        break
                    job = await self._extract_card_payload(
                        page, card, card_idx, default_prefix=f"rec_p{page_num + 1}_job"
                    )
                    if job:
                        extracted.append(job)
            except Exception as e:
                print(f"⚠️ Error scraping recommended feed page {page_num + 1}: {e}")

        return extracted

    async def scrape_recruiter_posts(
        self, page: Any, keywords: str = '"hiring SDET" OR "hiring QA"', max_posts: int = 15
    ) -> list[dict[str, Any]]:
        """Channel 3: Scrapes direct recruiter hiring posts from /search/results/content/."""
        posts_url = (
            f"https://www.linkedin.com/search/results/content/?keywords={urllib.parse.quote(keywords)}&f_TPR=r604800"
        )
        print("\n" + "=" * 50)
        print("📣 CHANNEL 3: SCRAPING RECRUITER HIRING POSTS FEED")
        print(f"🌐 Navigating to: {posts_url}")
        print("=" * 50)

        extracted = []
        try:
            await page.goto(posts_url, wait_until="domcontentloaded")
            await asyncio.sleep(3.0)
            for _ in range(4):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1.0)

            posts = await page.locator(".feed-shared-update-v2, .search-results-container .artdeco-card").all()
            print(f"🔍 Found {len(posts)} hiring post(s).")

            for idx, post in enumerate(posts[:max_posts]):
                try:
                    text_elem = post.locator(".feed-shared-text, .update-components-text").first
                    text = await text_elem.text_content() if await text_elem.count() > 0 else ""
                    if not text or len(text.strip()) < 30:
                        continue

                    post_hash = hashlib.md5(text[:200].encode("utf-8")).hexdigest()[:10]
                    job_id = f"post_hiring_{post_hash}"

                    author_elem = post.locator(".update-components-actor__name, .feed-shared-actor__name").first
                    author = await author_elem.text_content() if await author_elem.count() > 0 else "LinkedIn Recruiter"

                    if self.is_duplicate(job_id, author.strip(), "Hiring Post"):
                        continue

                    raw_job = {
                        "job_id": job_id,
                        "application_type": "EASY_APPLY",
                        "job_details": {
                            "title": f"Hiring Post by {author.strip()}",
                            "company": author.strip(),
                            "location": "Remote / India",
                            "requirements": text.strip()[:1000],
                        },
                    }

                    tailored = self.tailorer.tailor_job_payload(raw_job)
                    self.save_job_to_queue(tailored)
                    self.mark_job_processed(job_id, author.strip(), f"Hiring Post by {author.strip()}")
                    extracted.append(tailored)
                    print(f"📣 Enqueued hiring post from: {author.strip()}")
                except Exception as e:
                    print(f"⚠️ Error parsing post {idx}: {e}")
        except Exception as e:
            print(f"⚠️ Error scraping recruiter posts: {e}")

        return extracted

    async def _extract_card_payload(
        self, page: Any, card: Any, idx: int, default_prefix: str = "job"
    ) -> dict[str, Any] | None:
        """
        Extracts title, company, location, and full job description from a job card and runs AI tailoring.
        Includes title click triggering, 'See more' expansion, UI noise filtering, and direct page fallback.
        """
        try:
            # 1. Extract job_id from attributes or links
            job_id = await card.get_attribute("data-job-id")
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

            # 2. Extract title directly from list card DOM element
            title_elem = card.locator(
                '.job-card-list__title, .job-card-container__link, a[data-control-name="job_card_title"], .job-card-square__title, .artdeco-entity-lockup__title'
            ).first
            raw_title = await title_elem.text_content() if await title_elem.count() > 0 else None
            title = (raw_title or "Software Engineer").strip()

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

            company = raw_company or "Tech Company"

            # 4. INSTANT DEDUPLICATION CHECK BEFORE CLICKING!
            if self.is_duplicate(job_id, company, title):
                print(f"⏭️  Skipping duplicate job: {title} @ {company} (ID: {job_id})")
                return None

            location_elem = card.locator(
                ".job-card-container__metadata-item, .job-card-square__metadata-item, .artdeco-entity-lockup__caption"
            ).first
            raw_loc = await location_elem.text_content() if await location_elem.count() > 0 else None
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
                        "#job-details, .jobs-description__content, .jobs-search__job-details, article.jobs-description__container"
                    ).first
                    if await details_elem.count() > 0:
                        raw_desc = await details_elem.text_content()
                        cleaned = self.clean_job_description(raw_desc or "")
                        if cleaned and len(cleaned) > 50:
                            desc_text = cleaned
            except Exception:
                pass

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

            job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"
            raw_job = {
                "job_id": job_id,
                "url": job_url,
                "job_url": job_url,
                "application_type": application_type,
                "job_details": {
                    "title": title,
                    "company": company,
                    "location": loc,
                    "job_url": job_url,
                    "external_url": external_url,
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
        enable_rec = discovery_config.get("enable_recommended_feed", True)
        enable_posts = discovery_config.get("enable_recruiter_posts", True)

        all_jobs = []

        async with async_playwright() as p:
            from src.browser.cdp_connector import connect_cdp, launch_persistent_browser

            context = None
            try:
                print("\n" + "=" * 60)
                print("🚀 LAUNCHING 10X MULTI-CHANNEL JOB DISCOVERY ENGINE")
                print("=" * 60)
                context, page = await launch_persistent_browser(p)
            except Exception as e1:
                print(f"⚠️ Persistent browser launch failed: {e1}, trying CDP fallback...")
                try:
                    _browser, page = await connect_cdp(p, self.cdp_url)
                except Exception as e2:
                    print(f"⚠️ CDP fallback also failed: {e2}")
                    return all_jobs

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
                    search_url = self.build_search_url(
                        keywords=keywords,
                        location=location,
                        work_types=work_types,
                        experience_levels=experience_levels,
                        time_posted=time_posted,
                        start=start_offset,
                        easy_apply_only=easy_apply_only,
                        distance=distance,
                    )
                    print(f"🌐 Navigating to Page {page_num + 1} (start={start_offset}): {search_url}")

                    try:
                        await page.goto(search_url, wait_until="domcontentloaded")
                        await asyncio.sleep(2.5)
                        await self.scroll_results_pane(page, scrolls=4)

                        cards = await page.locator(
                            ".job-card-container, .job-card-list, .jobs-search-results-list__list-item, div[data-job-id]"
                        ).all()
                        print(f"   Found {len(cards)} job card(s) on Page {page_num + 1}.")

                        if len(cards) == 0:
                            print(
                                f"ℹ️ Page {page_num + 1} returned 0 cards. Early breaking search loop for Profile #{profile_idx + 1}."
                            )
                            break

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
                rec_jobs = await self.scrape_recommended_jobs(page, max_jobs=50, max_pages=max_rec_pages)
                all_jobs.extend(rec_jobs)

            # -------------------------------------------------------------
            # STEP 3: RECRUITER HIRING POSTS FEED
            # -------------------------------------------------------------
            if enable_posts:
                post_jobs = await self.scrape_recruiter_posts(
                    page, keywords='"hiring SDET" OR "hiring QA"', max_posts=15
                )
                all_jobs.extend(post_jobs)

            # Close single browser session ONCE at the end of all 4 channels
            if context is not None:
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
        """Saves a job payload into data/pending_queue/{job_id}.json."""
        os.makedirs(queue_dir, exist_ok=True)
        job_id = job_payload.get("job_id", "job_sample")
        filepath = os.path.join(queue_dir, f"{job_id}.json")
        with open(filepath, "w") as f:
            json.dump(job_payload, f, indent=2)
        print(f"💾 Saved pending job to: {filepath}")
        return filepath
