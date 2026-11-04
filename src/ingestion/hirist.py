"""
Hirist Tech Ingestion Collector.
Discovers and extracts tech/automation job listings from hirist.tech,
normalizing them into standardized JobListing objects for the application queue.
Discovered URLs map to HIRIST_TECH_STANDARD for automated application.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from src.ingestion.filters import is_india_or_remote_location, is_sdet_title
from src.storage.models import JobListing


def clean_html_text(raw_html: str) -> str:
    """Strips HTML tags, decodes entities, and collapses whitespace."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


class HiristCollector:
    """Async collector for hirist.tech job search feeds and categories."""

    BASE_URL = "https://www.hirist.tech"
    SEARCH_FEED_URL = "https://www.hirist.tech/api/jobfeed"
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

        # 1. Search for Next.js props or Redux initialState scripts
        for script in re.findall(r"<script[^>]*>(.*?)</script>", html_text, re.DOTALL):
            if "jobfeed" in script or "pageProps" in script:
                try:
                    data = json.loads(script)
                    props = data.get("props", {}).get("pageProps", {})
                    # Direct jobfeed in props or inside initialState
                    feed = props.get("jobfeed") or props.get("initialState", {}).get("job", {}).get("jobfeed") or []
                    if isinstance(feed, list):
                        for item in feed:
                            if isinstance(item, dict):
                                listing = self.parse_job_payload(item, filter_sdet=filter_sdet)
                                if listing:
                                    listings.append(listing)
                except Exception:
                    pass

        # 2. Regex fallback for inline job cards if script state is stripped
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

    async def fetch_jobs(
        self,
        query: str = "SDET",
        location: str = "bangalore",
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        """Queries Hirist category / skill feeds for target keyword."""
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
                                break  # Successfully gathered from primary category
                    except Exception as url_err:
                        # Fall through to secondary category endpoint
                        _ = url_err
        except Exception as e:
            print(f"⚠️ HiristCollector fetch error for query '{query}': {e}")

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
