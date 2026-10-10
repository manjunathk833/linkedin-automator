"""
Ashby ATS Keyless REST Ingestion Collector.
Directly ingests unauthenticated job postings from api.ashbyhq.com.
"""

from __future__ import annotations

import httpx

from src.ingestion.filters import (
    is_india_or_remote_location,
    is_sdet_title,
)
from src.storage.models import JobListing


class AshbyCollector:
    """Async collector for Ashby public job boards."""

    BASE_URL = "https://api.ashbyhq.com/posting-api/job-board"

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout = timeout_seconds

    async def fetch_board_jobs(
        self,
        company_name: str,
        slug: str,
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        """
        Fetches all public jobs for a company slug from Ashby.
        """
        url = f"{self.BASE_URL}/{slug}?includeCompensation=true"
        listings: list[JobListing] = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                res = await client.get(url)
                if res.status_code != 200:
                    return listings
                data = res.json()

            jobs = data.get("jobs", [])
            for job in jobs:
                title = job.get("title", "")
                location_name = str(job.get("locationName", "") or job.get("location", ""))
                is_remote = bool(job.get("isRemote", False))
                combined_loc = location_name
                if is_remote and not combined_loc:
                    combined_loc = "Remote"
                elif is_remote and "remote" not in combined_loc.lower():
                    combined_loc = f"{combined_loc} (Remote)"

                # Filtering for SDET / QA profile
                if filter_sdet and not is_sdet_title(title):
                    continue

                # Filtering location for India or Remote
                if filter_sdet and not is_india_or_remote_location(combined_loc):
                    continue

                job_id = str(job.get("id"))
                raw_desc = job.get("descriptionHtml", "")
                clean_desc = job.get("descriptionPlain", "") or raw_desc

                # Format compensation if available
                compensation_info = job.get("compensation", {})
                salary_str = None
                if compensation_info:
                    min_val = compensation_info.get("minSummary")
                    max_val = compensation_info.get("maxSummary")
                    currency = compensation_info.get("currency", "")
                    if min_val or max_val:
                        salary_str = f"{currency} {min_val or ''} - {max_val or ''}".strip()

                listing = JobListing(
                    id=f"ashby_{slug}_{job_id}",
                    source="ashby",
                    company_name=company_name,
                    job_title=title,
                    location=location_name or ("Remote" if is_remote else "Unspecified"),
                    is_remote=is_remote,
                    job_description_raw=raw_desc,
                    job_description_clean=clean_desc,
                    url=job.get("jobUrl", f"https://jobs.ashbyhq.com/{slug}/{job_id}"),
                    salary_range=salary_str,
                    status="pending",
                )
                listings.append(listing)

        except Exception as e:
            print(f"⚠️ Ashby fetch warning for {company_name} ({slug}): {e}")

        return listings
