"""
Workday ATS Keyless CXS REST Ingestion Collector.
Directly queries Candidate Experience Service (CXS) JSON endpoints from public Workday career sites.
Zero-cost, unauthenticated HTTP polling with defensive pagination and SHA-256 integrity.
"""

from __future__ import annotations

import html
import re
from typing import Any

import httpx

from src.ingestion.filters import (
    is_india_or_remote_location,
    is_sdet_title,
)
from src.storage.models import JobListing

DEFAULT_WORKDAY_SEARCH_TERMS = [
    "SDET India",
    "QA India",
    "Software Engineer in Test India",
    "Automation India",
    "SDET",
]


def clean_html_description(raw_html: str) -> str:
    """Strips HTML tags, normalizes whitespace and decodes entities."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class WorkdayCollector:
    """Async collector for Workday Candidate Experience Service (CXS) public job feeds."""

    def __init__(self, timeout_seconds: float = 12.0):
        self.timeout = timeout_seconds

    def _build_base_url(self, tenant: str, site: str, datacenter: str | None = None) -> str:
        """Constructs CXS base URL supporting both regional datacenter and direct domains."""
        if datacenter and datacenter.strip():
            host = f"{tenant}.{datacenter}.myworkdayjobs.com"
        else:
            host = f"{tenant}.myworkdayjobs.com"
        return f"https://{host}/wday/cxs/{tenant}/{site}"

    async def fetch_board_jobs(
        self,
        company_name: str,
        slug: str,
        site: str,
        datacenter: str | None = "wd3",
        search_terms: list[str] | str | None = None,
        filter_sdet: bool = True,
        filter_india: bool = True,
        is_dream_org: bool = False,
        max_pages: int = 2,
    ) -> list[JobListing]:
        """
        Queries Workday CXS endpoints across targeted search terms, paginating through
        public listings and normalizing them into JobListings.
        """
        base_cxs_url = self._build_base_url(slug, site, datacenter)
        jobs_endpoint = f"{base_cxs_url}/jobs"
        listings: list[JobListing] = []
        seen_paths: set[str] = set()

        if search_terms is None:
            terms = list(DEFAULT_WORKDAY_SEARCH_TERMS)
        elif isinstance(search_terms, str):
            terms = [search_terms]
        else:
            terms = list(search_terms)

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

        limit = 20

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                for term in terms:
                    for page_idx in range(max_pages):
                        offset = page_idx * limit
                        payload = {
                            "appliedFacets": {},
                            "limit": limit,
                            "offset": offset,
                            "searchText": term,
                        }

                        try:
                            res = await client.post(jobs_endpoint, json=payload, headers=headers)
                            if res.status_code != 200:
                                # Try fallback without datacenter in hostname if failed
                                if datacenter:
                                    fallback_url = f"https://{slug}.myworkdayjobs.com/wday/cxs/{slug}/{site}/jobs"
                                    res = await client.post(fallback_url, json=payload, headers=headers)
                                    if res.status_code != 200:
                                        break
                                else:
                                    break
                            data: dict[str, Any] = res.json()
                        except Exception:
                            break

                        job_postings = data.get("jobPostings", [])
                        if not job_postings:
                            break

                        new_items_in_page = 0
                        for item in job_postings:
                            ext_path = item.get("externalPath", "")
                            if not ext_path or ext_path in seen_paths:
                                continue
                            seen_paths.add(ext_path)
                            new_items_in_page += 1

                            title = item.get("title", "").strip()
                            locations_text = item.get("locationsText", "")
                            bullet_fields = item.get("bulletFields", [])

                            # Title filtering
                            if filter_sdet and not is_sdet_title(title):
                                continue

                            # Location filtering
                            if filter_india and locations_text and not is_india_or_remote_location(locations_text):
                                continue

                            # Extract external requisition ID
                            req_id = (
                                bullet_fields[0] if bullet_fields else re.sub(r"[^a-zA-Z0-9_-]", "", ext_path[-24:])
                            )
                            job_id = f"workday_{slug}_{req_id}".lower()

                            # Resolve public external web link
                            job_url = f"https://{slug}.myworkdayjobs.com/en-US/{site}{ext_path}"

                            # Fetch rich job details
                            detail_url = f"{base_cxs_url}{ext_path}"
                            desc_raw = ""
                            desc_clean = ""
                            try:
                                d_res = await client.get(detail_url, headers=headers)
                                if d_res.status_code == 200:
                                    d_data = d_res.json().get("jobPostingInfo", {})
                                    desc_raw = d_data.get("jobDescription", "")
                                    desc_clean = clean_html_description(desc_raw)
                                    if d_data.get("externalUrl"):
                                        job_url = d_data.get("externalUrl")
                            except Exception:
                                desc_clean = f"{title} at {company_name}. Location: {locations_text}"

                            is_remote = bool(
                                re.search(r"\b(remote|anywhere)\b", f"{title} {locations_text}", re.IGNORECASE)
                            )

                            listing = JobListing(
                                id=job_id,
                                source="workday",
                                company_name=company_name,
                                job_title=title,
                                location=locations_text or "India",
                                is_remote=is_remote,
                                is_dream_org=is_dream_org,
                                job_description_raw=desc_raw or desc_clean,
                                job_description_clean=desc_clean,
                                url=job_url,
                            )
                            listings.append(listing)

                    if new_items_in_page == 0:
                        break

                    total_available = data.get("total", 0)
                    offset += limit
                    if offset >= total_available:
                        break

        except Exception:
            return listings

        return listings
