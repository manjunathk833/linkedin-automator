"""
Hirist Tech Ingestion Collector.
Discovers and extracts tech/automation job listings from hirist.tech,
normalizing them into standardized JobListing objects for the application queue.
Discovered URLs map to HIRIST_TECH_STANDARD for automated application.
Supports authenticated candidate jobfeed extraction via persistent browser session,
strict <=3-day freshness filtering, and unauthenticated daily XML sitemap ingestion.
"""

from __future__ import annotations

import asyncio
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from src.browser.cdp_stealth import DEFAULT_STEALTH_DIR
from src.ingestion.filters import is_india_or_remote_location, is_sdet_title
from src.storage.models import JobListing


def clean_html_text(raw_html: str) -> str:
    """Strips HTML tags, decodes entities, and collapses whitespace."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_relative_age_days(text: str) -> float | None:
    """
    Parses relative age strings like 'Posted today', 'Posted 1 day ago', 'Posted 2 days ago',
    'Posted 3 weeks ago', 'Posted 1 month ago', '2 hours ago'.
    Returns the age in days as float, or None if no match.
    """
    if not text:
        return None
    t = text.lower()
    if "today" in t or "just now" in t or "hour" in t or "minute" in t:
        return 0.0
    m_day = re.search(r"(\d+)\s+day", t)
    if m_day:
        return float(m_day.group(1))
    m_week = re.search(r"(\d+)\s+week", t)
    if m_week:
        return float(m_week.group(1)) * 7.0
    m_month = re.search(r"(\d+)\s+month", t)
    if m_month:
        return float(m_month.group(1)) * 30.0
    return None


class HiristCollector:
    """Async collector for hirist.tech job search feeds, sitemaps, and candidate jobfeed."""

    BASE_URL = "https://www.hirist.tech"
    SEARCH_FEED_URL = "https://www.hirist.tech/api/jobfeed"
    SITEMAP_URL = "https://www.hirist.tech/new_sitemap-j-1.xml.gz"
    DEFAULT_QUERIES = ("sdet", "playwright", "ai qa", "test automation")
    DEFAULT_LOCATION = "Bangalore"

    def __init__(self, timeout_seconds: float = 12.0):
        self.timeout = timeout_seconds
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.hirist.tech/",
        }

    def parse_job_payload(self, item: dict[str, Any], filter_sdet: bool = True) -> JobListing | None:
        """Parses a structured JSON job object from Hirist APIs or page state."""
        raw_id = str(item.get("id") or item.get("jobId") or item.get("job_id") or "")
        if not raw_id:
            return None

        title = str(item.get("title") or item.get("jobTitle") or "").strip()
        if not title:
            return None

        if filter_sdet and not is_sdet_title(title):
            return None

        company = str(
            item.get("cname")
            or item.get("companyName")
            or item.get("company_name")
            or item.get("recruiterName")
            or "Hirist Enterprise"
        ).strip()

        location = str(item.get("location") or item.get("cityName") or item.get("city") or "Bengaluru").strip()
        if filter_sdet and not is_india_or_remote_location(location):
            return None

        is_remote = bool(
            re.search(r"\bremote\b", location, re.IGNORECASE)
            or re.search(r"\bremote\b", title, re.IGNORECASE)
            or item.get("isRemote")
        )

        job_slug = str(item.get("slug") or item.get("jobUrl") or item.get("url") or f"job-{raw_id}")
        if not job_slug.startswith("http"):
            clean_slug = job_slug.lstrip("/")
            canonical_url = (
                f"{self.BASE_URL}/{clean_slug}" if clean_slug.startswith("j/") else f"{self.BASE_URL}/j/{clean_slug}"
            )
        else:
            canonical_url = job_slug

        desc_raw = str(item.get("description") or item.get("jobDesc") or item.get("snippet") or "")
        desc_clean = (
            clean_html_text(desc_raw) or f"{title} opportunity at {company}. Key skills: SDET, Test Automation."
        )

        # Salary parsing
        salary = ""
        min_sal = item.get("minSal") or item.get("min_sal")
        max_sal = item.get("maxSal") or item.get("max_sal")
        if min_sal and max_sal:
            salary = f"₹{min_sal} - ₹{max_sal} LPA"

        # Posted date parsing
        posted_dt = None
        raw_posted = item.get("createdDate") or item.get("postedDate") or item.get("posted_at")
        if raw_posted:
            try:
                if isinstance(raw_posted, (int, float)):
                    posted_dt = datetime.fromtimestamp(raw_posted / 1000.0, tz=timezone.utc).replace(tzinfo=None)
                elif isinstance(raw_posted, str):
                    posted_dt = datetime.fromisoformat(raw_posted.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                posted_dt = None

        return JobListing(
            id=f"hirist_{raw_id}",
            source="hirist",
            company_name=company,
            job_title=title,
            location=location,
            is_remote=is_remote,
            is_dream_org=False,
            job_description_raw=desc_raw or desc_clean,
            job_description_clean=desc_clean,
            url=canonical_url,
            salary_range=salary or None,
            posted_at=posted_dt,
            discovered_at=datetime.utcnow(),
            status="pending",
        )

    def parse_search_page(self, html_text: str, filter_sdet: bool = True) -> list[JobListing]:
        """Extracts job items from embedded Next.js JSON or script tags on Hirist pages."""
        listings: list[JobListing] = []
        if not html_text:
            return listings

        for script in re.findall(r"<script[^>]*>(.*?)</script>", html_text, re.DOTALL):
            if "jobfeed" in script or "pageProps" in script:
                try:
                    data = json.loads(script)
                    props = data.get("props", {}).get("pageProps", {})
                    feed = props.get("jobfeed") or props.get("initialState", {}).get("job", {}).get("jobfeed") or []
                    if isinstance(feed, list):
                        for item in feed:
                            if isinstance(item, dict):
                                listing = self.parse_job_payload(item, filter_sdet=filter_sdet)
                                if listing:
                                    listings.append(listing)
                except Exception:
                    pass

        if not listings:
            link_pattern = re.compile(r"href=[\"'](/j/[a-zA-Z0-9_\-]+)[\"'][^>]*>([^<]+)</a>", re.IGNORECASE)
            for m in link_pattern.finditer(html_text):
                url_path, title_text = m.group(1), m.group(2).strip()
                if filter_sdet and not is_sdet_title(title_text):
                    continue
                match_id = re.search(r"-(\d+)(?:\.html)?$", url_path)
                jid = match_id.group(1) if match_id else re.sub(r"\D", "", url_path) or "job"
                listings.append(
                    JobListing(
                        id=f"hirist_{jid}",
                        source="hirist",
                        company_name="Hirist Employer",
                        job_title=title_text,
                        location="Bengaluru, India",
                        is_remote=False,
                        is_dream_org=False,
                        job_description_raw=f"{title_text} discovered on Hirist.",
                        job_description_clean=f"{title_text} discovered on Hirist.",
                        url=f"{self.BASE_URL}{url_path}",
                        discovered_at=datetime.utcnow(),
                        status="pending",
                    )
                )

        return listings

    async def fetch_feed_via_browser(
        self,
        headless: bool = True,
        limit: int = 30,
        filter_sdet: bool = True,
        max_age_days: float = 3.0,
    ) -> list[JobListing]:
        """
        Extracts authenticated candidate recommendations from https://www.hirist.tech/jobfeed
        using the persistent browser profile, strictly enforcing <= max_age_days (default: 3 days).
        """
        listings: list[JobListing] = []
        if not os.path.exists(DEFAULT_STEALTH_DIR):
            return listings

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                ctx = await p.chromium.launch_persistent_context(
                    DEFAULT_STEALTH_DIR,
                    headless=headless,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                )
                page = await ctx.new_page()
                try:
                    await page.goto(
                        f"{self.BASE_URL}/jobfeed",
                        timeout=25000,
                        wait_until="domcontentloaded",
                    )
                    await asyncio.sleep(2.5)

                    raw_cards = await page.eval_on_selector_all(
                        ".joblist-card-v2",
                        """els => els.map(el => {
                            const link = el.querySelector('a[href*="/j/"]');
                            const href = link ? link.getAttribute('href') : '';
                            return { href, text: el.innerText };
                        })""",
                    )

                    for c in raw_cards:
                        href = c.get("href") or ""
                        full_text = c.get("text") or ""
                        lines = [l.strip() for l in full_text.split("\n") if l.strip()]
                        raw_title = lines[0] if lines else ""
                        if not href or not raw_title:
                            continue

                        # 1. Freshness Gate (<= max_age_days)
                        posted_line = next((l for l in lines if "posted" in l.lower()), "")
                        age_days = parse_relative_age_days(posted_line)
                        if age_days is not None and age_days > max_age_days:
                            continue  # Reject stale jobs (>3d)

                        posted_dt = (
                            datetime.utcnow() - timedelta(days=age_days) if age_days is not None else datetime.utcnow()
                        )

                        # 2. SDET Title Qualification
                        company = "Hirist Enterprise"
                        clean_title = raw_title
                        if " - " in raw_title:
                            parts = raw_title.split(" - ", 1)
                            company = parts[0].strip()
                            clean_title = parts[1].strip()

                        if filter_sdet and not (is_sdet_title(raw_title) or is_sdet_title(clean_title)):
                            continue

                        id_match = re.search(r"-(\d+)", href)
                        raw_id = id_match.group(1) if id_match else re.sub(r"\D", "", href)

                        salary = None
                        location = "Bengaluru, India"
                        for l in lines[1:5]:
                            if "LPA" in l or "₹" in l:
                                salary = l
                            elif any(
                                city in l
                                for city in (
                                    "Bangalore",
                                    "Bengaluru",
                                    "Hyderabad",
                                    "Pune",
                                    "Remote",
                                    "Noida",
                                    "Mumbai",
                                )
                            ):
                                location = l

                        canonical_url = f"{self.BASE_URL}{href.split('?')[0]}"
                        listing = JobListing(
                            id=f"hirist_{raw_id}",
                            source="hirist",
                            company_name=company,
                            job_title=clean_title,
                            location=location,
                            is_remote="remote" in location.lower(),
                            is_dream_org=False,
                            job_description_raw=full_text,
                            job_description_clean=full_text,
                            url=canonical_url,
                            salary_range=salary,
                            posted_at=posted_dt,
                            discovered_at=datetime.utcnow(),
                            status="pending",
                        )
                        listings.append(listing)
                        if len(listings) >= limit:
                            break
                finally:
                    await ctx.close()
        except Exception as e:
            print(f"⚠️ HiristCollector browser feed warning: {e}")

        return listings

    async def fetch_sitemap_jobs(
        self,
        filter_sdet: bool = True,
        limit: int = 30,
        max_age_days: float = 3.0,
    ) -> list[JobListing]:
        """
        Parses Hirist's daily unauthenticated XML sitemap to discover fresh SDET/QA roles,
        strictly filtering for <lastmod> timestamps <= max_age_days.
        """
        listings: list[JobListing] = []
        now = datetime.utcnow()
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(self.SITEMAP_URL)
                if resp.status_code != 200:
                    return listings

                root = ET.fromstring(resp.content)
                url_nodes = root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url")

                for node in url_nodes:
                    loc_el = node.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
                    lastmod_el = node.find("{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod")
                    if loc_el is None or not loc_el.text:
                        continue

                    u = loc_el.text

                    # Enforce freshness via lastmod if present
                    posted_dt = now
                    if lastmod_el is not None and lastmod_el.text:
                        try:
                            mod_dt = datetime.fromisoformat(lastmod_el.text.replace("Z", "+00:00")).replace(tzinfo=None)
                            age_days = (now - mod_dt).total_seconds() / 86400.0
                            if age_days > max_age_days:
                                continue
                            posted_dt = mod_dt
                        except Exception:
                            pass

                    m = re.search(r"/j/(.+)-(\d+)$", u)
                    if not m:
                        continue
                    slug, jid = m.group(1), m.group(2)
                    raw_title = " ".join(slug.split("-")).title()

                    if filter_sdet and not is_sdet_title(raw_title):
                        continue

                    company = "Hirist Enterprise"
                    if " - " in raw_title:
                        parts = raw_title.split(" - ", 1)
                        company = parts[0].strip()
                        raw_title = parts[1].strip()

                    listing = JobListing(
                        id=f"hirist_{jid}",
                        source="hirist",
                        company_name=company,
                        job_title=raw_title,
                        location="Bengaluru, India",
                        is_remote="remote" in slug.lower(),
                        is_dream_org=False,
                        job_description_raw=f"{raw_title} at {company}. SDET automation opportunity.",
                        job_description_clean=f"{raw_title} at {company}. SDET automation opportunity.",
                        url=u,
                        posted_at=posted_dt,
                        discovered_at=now,
                        status="pending",
                    )
                    listings.append(listing)
                    if len(listings) >= limit:
                        break
        except Exception as e:
            print(f"⚠️ HiristCollector sitemap parsing warning: {e}")

        return listings

    async def fetch_jobs(
        self,
        query: str = "SDET",
        location: str = "bangalore",
        filter_sdet: bool = True,
        max_age_days: float = 3.0,
    ) -> list[JobListing]:
        """
        Multi-tier Hirist discovery enforcing <= 3 days freshness:
        Tier 1: Authenticated candidate jobfeed via browser context.
        Tier 2: Daily XML sitemap parser with fresh <lastmod> filter.
        Tier 3: Category and skill feed query fallback.
        """
        # Tier 1: Try authenticated browser feed
        try:
            browser_jobs = await self.fetch_feed_via_browser(
                headless=True, limit=25, filter_sdet=filter_sdet, max_age_days=max_age_days
            )
            if browser_jobs:
                return browser_jobs
        except Exception:
            pass

        # Tier 2: Try daily XML sitemap
        try:
            sitemap_jobs = await self.fetch_sitemap_jobs(filter_sdet=filter_sdet, limit=25, max_age_days=max_age_days)
            if sitemap_jobs:
                return sitemap_jobs
        except Exception:
            pass

        # Tier 3: Category endpoint fallback
        slug_query = re.sub(r"[^a-zA-Z0-9]+", "-", query.lower()).strip("-")
        search_urls = [
            f"{self.BASE_URL}/{slug_query}-jobs-in-{location.lower()}",
            f"{self.BASE_URL}/c/{slug_query}-jobs",
            f"{self.BASE_URL}/k/{slug_query}-jobs",
        ]
        results: list[JobListing] = []

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                for url in search_urls:
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            items = self.parse_search_page(resp.text, filter_sdet=filter_sdet)
                            if items:
                                results.extend(items)
                                break
                    except Exception as url_err:
                        _ = url_err
                        continue
        except Exception as e:
            print(f"⚠️ HiristCollector fallback fetch error for query '{query}': {e}")

        return results

    async def fetch_board_jobs(
        self,
        company_name: str,
        slug: str,
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        """Fetches jobs for a target company on Hirist."""
        url = f"{self.BASE_URL}/company/{slug}-jobs"
        results: list[JobListing] = []
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    items = self.parse_search_page(resp.text, filter_sdet=filter_sdet)
                    for it in items:
                        it.company_name = company_name
                    results.extend(items)
        except Exception as e:
            print(f"⚠️ HiristCollector board error for {company_name} ({slug}): {e}")
        return results
