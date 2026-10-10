"""
Lever ATS Keyless REST Ingestion Collector.
Directly ingests unauthenticated job postings from api.lever.co.
"""

from __future__ import annotations

import re

import httpx

from src.ingestion.filters import (
    is_india_or_remote_location,
    is_sdet_title,
)
from src.storage.models import JobListing


class LeverCollector:
    """Async collector for Lever public job postings."""

    BASE_URL = "https://api.lever.co/v0/postings"

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout = timeout_seconds

    async def fetch_board_jobs(
        self,
        company_name: str,
        slug: str,
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        """
        Fetches all public jobs for a company slug from Lever.
        """
        url = f"{self.BASE_URL}/{slug}?mode=json"
        listings: list[JobListing] = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                res = await client.get(url)
                if res.status_code != 200:
                    return listings
                postings = res.json()

            if not isinstance(postings, list):
                return listings

            for post in postings:
                title = post.get("text", "")
                categories = post.get("categories", {}) or {}
                location_name = categories.get("location", "")
                workplace_type = post.get("workplaceType", "")
                combined_loc = f"{location_name} {workplace_type}".strip()

                # Filtering for SDET / QA profile
                if filter_sdet and not is_sdet_title(title):
                    continue

                # Filtering location for India or Remote
                if filter_sdet and not is_india_or_remote_location(combined_loc):
                    continue

                post_id = str(post.get("id"))
                raw_desc = post.get("description", "")
                plain_desc = post.get("descriptionPlain", "") or raw_desc

                # Check additional lists (requirements, responsibilities)
                additional_lists = post.get("lists", [])
                extra_text = "\n".join(
                    f"{item.get('text')}: " + "; ".join(item.get("content", []))
                    for item in additional_lists
                    if isinstance(item, dict)
                )
                if extra_text:
                    plain_desc = f"{plain_desc}\n\n{extra_text}"

                is_remote = workplace_type.lower() == "remote" or bool(
                    re.search(r"\bremote\b", location_name, re.IGNORECASE)
                )

                listing = JobListing(
                    id=f"lever_{slug}_{post_id}",
                    source="lever",
                    company_name=company_name,
                    job_title=title,
                    location=location_name or "Remote / Unspecified",
                    is_remote=is_remote,
                    job_description_raw=raw_desc,
                    job_description_clean=plain_desc,
                    url=post.get("hostedUrl", f"https://jobs.lever.co/{slug}/{post_id}"),
                    status="pending",
                )
                listings.append(listing)

        except Exception as e:
            print(f"⚠️ Lever fetch warning for {company_name} ({slug}): {e}")

        return listings
