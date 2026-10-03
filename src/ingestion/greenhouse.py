"""
Greenhouse ATS Keyless REST Ingestion Collector.
Directly ingests unauthenticated job boards from boards-api.greenhouse.io.
"""

from __future__ import annotations

import html
import re

import httpx

from src.storage.models import JobListing

SDET_TITLE_REGEX = re.compile(
    r"\b(sdet|qa|quality|test|automation|software engineer in test)\b",
    re.IGNORECASE,
)

INDIA_LOCATION_REGEX = re.compile(
    r"\b(bengaluru|bangalore|india|remote|hybrid|anywhere)\b",
    re.IGNORECASE,
)


def clean_html_description(raw_html: str) -> str:
    """Strips HTML tags, normalizes whitespace and decodes entities."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class GreenhouseCollector:
    """Async collector for Greenhouse public job boards."""

    BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout = timeout_seconds

    async def fetch_board_jobs(
        self,
        company_name: str,
        slug: str,
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        """
        Fetches all public jobs for a company slug from Greenhouse.
        """
        url = f"{self.BASE_URL}/{slug}/jobs?content=true"
        listings: list[JobListing] = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                res = await client.get(url)
                if res.status_code != 200:
                    return listings
                data = res.json()

            raw_jobs = data.get("jobs", [])
            for job in raw_jobs:
                title = job.get("title", "")
                location_name = job.get("location", {}).get("name", "")

                # Filtering for SDET / QA profile
                if filter_sdet and not SDET_TITLE_REGEX.search(title):
                    continue

                # Filtering location for India or Remote
                if (
                    filter_sdet
                    and not INDIA_LOCATION_REGEX.search(location_name)
                    and not any(INDIA_LOCATION_REGEX.search(str(m.get("value") or "")) for m in job.get("metadata", []))
                ):
                    continue

                job_id = str(job.get("id"))
                raw_content = job.get("content", "")
                clean_content = clean_html_description(raw_content)

                is_remote = bool(
                    re.search(r"\bremote\b", location_name, re.IGNORECASE)
                    or re.search(r"\bremote\b", title, re.IGNORECASE)
                )

                listing = JobListing(
                    id=f"greenhouse_{slug}_{job_id}",
                    source="greenhouse",
                    company_name=company_name,
                    job_title=title,
                    location=location_name or "Remote / Unspecified",
                    is_remote=is_remote,
                    job_description_raw=raw_content,
                    job_description_clean=clean_content,
                    url=job.get("absolute_url", f"https://boards.greenhouse.io/{slug}/jobs/{job_id}"),
                    status="pending",
                )
                listings.append(listing)

        except Exception as e:
            print(f"⚠️ Greenhouse fetch warning for {company_name} ({slug}): {e}")

        return listings
