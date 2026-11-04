"""
Instahyre Curated Product & AI Startup Ingestion Collector.
Discovers and extracts curated SDET, AI QA, and Playwright roles from instahyre.com,
normalizing them into standardized JobListing objects for the application queue.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
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


class InstahyreCollector:
    """Collector for instahyre.com curated tech feeds and candidate opportunities."""

    BASE_URL = "https://www.instahyre.com"
    CURATED_SLUGS = (
        "playwright-jobs-in-bangalore",
        "remote-playwright-jobs",
        "remote-automation-testing-jobs",
        "sdet-jobs-in-bangalore",
    )

    def __init__(self, timeout_seconds: float = 12.0):
        self.timeout = timeout_seconds
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def parse_job_payload(self, item: dict[str, Any], filter_sdet: bool = True) -> JobListing | None:
        """Parses a structured JSON job object from Instahyre internal feeds or API responses."""
        raw_id = str(item.get("id") or item.get("job_id") or "")
        if not raw_id:
            return None

        title = str(item.get("title") or item.get("job_title") or item.get("position") or "").strip()
        if not title:
            return None

        if filter_sdet and not is_sdet_title(title):
            return None

        company = str(
            item.get("company_name")
            or item.get("company")
            or item.get("employer_name")
            or "Instahyre Verified Employer"
        ).strip()

        location = str(item.get("location") or item.get("city") or "Bengaluru, India").strip()
        if filter_sdet and not is_india_or_remote_location(location):
            return None

        is_remote = bool(
            re.search(r"\bremote\b", location, re.IGNORECASE)
            or re.search(r"\bremote\b", title, re.IGNORECASE)
            or item.get("is_remote")
        )

        job_url = str(item.get("url") or item.get("job_url") or f"{self.BASE_URL}/job-{raw_id}")
        if not job_url.startswith("http"):
            job_url = f"{self.BASE_URL}/{job_url.lstrip('/')}"

        desc_raw = str(item.get("description") or item.get("job_description") or "")
        desc_clean = clean_html_text(desc_raw) or f"{title} opportunity at {company}. High-impact QA Automation role."

        salary = str(item.get("salary") or item.get("compensation") or "")

        return JobListing(
            id=f"instahyre_{raw_id}",
            source="instahyre",
            company_name=company,
            job_title=title,
            location=location,
            is_remote=is_remote,
            is_dream_org=False,
            job_description_raw=desc_raw or desc_clean,
            job_description_clean=desc_clean,
            url=job_url,
            salary_range=salary or None,
            discovered_at=datetime.utcnow(),
            status="pending",
        )

    def parse_html_page(self, html_text: str, filter_sdet: bool = True) -> list[JobListing]:
        """Extracts job cards from server-rendered HTML or embedded script JSON."""
        listings: list[JobListing] = []
        if not html_text:
            return listings

        # 1. Look for embedded JSON script tags (schema.org or application/ld+json)
        for s in re.findall(
            r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", html_text, re.DOTALL
        ):
            try:
                data = json.loads(s)
                items = data if isinstance(data, list) else [data]
                for it in items:
                    if it.get("@type") == "JobPosting":
                        jid = str(it.get("identifier", {}).get("value") or hash(it.get("title", "")) % 100000)
                        hiring_org = it.get("hiringOrganization", {})
                        comp = hiring_org.get("name") if isinstance(hiring_org, dict) else str(hiring_org)
                        raw_payload = {
                            "id": jid,
                            "title": it.get("title"),
                            "company_name": comp,
                            "location": it.get("jobLocation", {})
                            .get("address", {})
                            .get("addressLocality", "Bengaluru"),
                            "description": it.get("description"),
                            "url": it.get("url"),
                        }
                        listing = self.parse_job_payload(raw_payload, filter_sdet=filter_sdet)
                        if listing:
                            listings.append(listing)
            except Exception:
                pass

        # 2. Look for DOM job card structures e.g. class="opportunity-row" or class="job-card"
        if not listings:
            card_regex = re.compile(
                r"<div[^>]*class=[\"'][^\"']*(?:opportunity-row|job-card)[^\"']*[\"'][^>]*>(.*?)</div>\s*</div>",
                re.DOTALL | re.IGNORECASE,
            )
            for m in card_regex.finditer(html_text):
                block = m.group(1)
                title_m = re.search(r"<span[^>]*class=[\"'][^\"']*position[^\"']*[\"'][^>]*>([^<]+)</span>", block)
                comp_m = re.search(r"<span[^>]*class=[\"'][^\"']*company-name[^\"']*[\"'][^>]*>([^<]+)</span>", block)
                link_m = re.search(r"href=[\"'](/job-[^\"']+)[\"']", block)

                if title_m and comp_m:
                    title = title_m.group(1).strip()
                    comp = comp_m.group(1).strip()
                    href = link_m.group(1).strip() if link_m else "/job-instahyre"
                    jid_m = re.search(r"/job-(\d+)", href)
                    jid = jid_m.group(1) if jid_m else "instahyre"

                    raw_payload = {
                        "id": jid,
                        "title": title,
                        "company_name": comp,
                        "location": "Bengaluru, India",
                        "url": f"{self.BASE_URL}{href}",
                    }
                    listing = self.parse_job_payload(raw_payload, filter_sdet=filter_sdet)
                    if listing:
                        listings.append(listing)

        return listings

    async def fetch_feed_jobs(self, slug: str, filter_sdet: bool = True) -> list[JobListing]:
        """Fetches jobs from a specific curated skill slug on Instahyre."""
        clean_slug = slug.strip("/ ")
        url = f"{self.BASE_URL}/{clean_slug}/"
        results: list[JobListing] = []

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    results = self.parse_html_page(resp.text, filter_sdet=filter_sdet)
        except Exception as e:
            print(f"⚠️ InstahyreCollector fetch warning for slug '{slug}': {e}")

        return results

    async def fetch_board_jobs(
        self,
        company_name: str,
        slug: str,
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        """Fetches jobs for a target company slug on Instahyre."""
        url = f"{self.BASE_URL}/company/{slug}/"
        results: list[JobListing] = []

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    items = self.parse_html_page(resp.text, filter_sdet=filter_sdet)
                    for it in items:
                        it.company_name = company_name
                    results.extend(items)
        except Exception as e:
            print(f"⚠️ InstahyreCollector board warning for {company_name} ({slug}): {e}")

        return results
