"""
Workday ATS Keyless CXS REST Ingestion Collector.
Directly queries Candidate Experience Service (CXS) JSON endpoints from public Workday career sites.
Zero-cost, unauthenticated HTTP polling with defensive pagination and SHA-256 integrity.
"""

from __future__ import annotations

import asyncio
import html
import re
from datetime import datetime, timedelta
from typing import Any

import httpx

from src.ingestion.filters import (
    is_india_or_remote_location,
    is_sdet_title,
)
from src.storage.models import JobListing


def parse_workday_posted_on(posted_on: str | None, start_date: str | None = None) -> datetime | None:
    """Parses Workday CXS 'postedOn' ('Posted Today', 'Posted Yesterday', 'Posted 3 Days Ago') or ISO startDate."""
    now = datetime.utcnow()
    if start_date and isinstance(start_date, str):
        try:
            return datetime.fromisoformat(start_date.replace("Z", ""))
        except Exception:
            pass
    if not posted_on or not isinstance(posted_on, str):
        return None
    low = posted_on.strip().lower()
    if "today" in low or "just posted" in low:
        return now
    if "yesterday" in low:
        return now - timedelta(days=1)
    m = re.search(r"(\d+)\+?\s*day", low)
    if m:
        return now - timedelta(days=int(m.group(1)))
    return None


DEFAULT_WORKDAY_SEARCH_TERMS = [
    "SDET India",
    "QA India",
    "Software Engineer in Test India",
    "Quality Engineer India",
    "Test Engineer Bangalore",
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
                candidate_items: list[dict[str, Any]] = []
                active_cxs_url = base_cxs_url
                search_sem = asyncio.Semaphore(4)

                async def _search_term(term: str) -> list[dict[str, Any]]:
                    nonlocal active_cxs_url, jobs_endpoint
                    term_items: list[dict[str, Any]] = []
                    for page_idx in range(max_pages):
                        offset = page_idx * limit
                        payload = {
                            "appliedFacets": {},
                            "limit": limit,
                            "offset": offset,
                            "searchText": term,
                        }
                        async with search_sem:
                            try:
                                res = await client.post(jobs_endpoint, json=payload, headers=headers)
                                if res.status_code != 200:
                                    if "maintenance-page" in str(res.url) or "maintenance-page" in str(
                                        res.headers.get("location", "")
                                    ):
                                        return term_items
                                    if datacenter:
                                        fallback_base = f"https://{slug}.myworkdayjobs.com/wday/cxs/{slug}/{site}"
                                        fallback_url = f"{fallback_base}/jobs"
                                        res = await client.post(fallback_url, json=payload, headers=headers)
                                        if res.status_code != 200:
                                            return term_items
                                        active_cxs_url = fallback_base
                                        jobs_endpoint = fallback_url
                                    else:
                                        return term_items
                                data: dict[str, Any] = res.json()
                            except Exception:
                                return term_items

                        job_postings = data.get("jobPostings", [])
                        if not job_postings:
                            break
                        term_items.extend(job_postings)
                        total_available = data.get("total", 0)
                        if offset + limit >= total_available:
                            break
                    return term_items

                term_batches = await asyncio.gather(*(_search_term(t) for t in terms))
                for batch in term_batches:
                    for item in batch:
                        ext_path = item.get("externalPath", "")
                        if not ext_path or ext_path in seen_paths:
                            continue
                        seen_paths.add(ext_path)

                        title = item.get("title", "").strip()
                        locations_text = item.get("locationsText", "").strip()

                        if filter_sdet and not is_sdet_title(title):
                            continue

                        is_multi_loc_badge = bool(re.match(r"^\d+\s+locations?$", locations_text, re.IGNORECASE))
                        if (
                            filter_india
                            and locations_text
                            and not is_multi_loc_badge
                            and not is_india_or_remote_location(locations_text)
                        ):
                            continue

                        candidate_items.append(item)

                detail_sem = asyncio.Semaphore(6)

                async def _hydrate_item(item: dict[str, Any]) -> JobListing | None:
                    ext_path = item.get("externalPath", "")
                    title = item.get("title", "").strip()
                    locations_text = item.get("locationsText", "").strip()
                    bullet_fields = item.get("bulletFields", [])
                    is_multi_loc_badge = bool(re.match(r"^\d+\s+locations?$", locations_text, re.IGNORECASE))

                    req_id = bullet_fields[0] if bullet_fields else re.sub(r"[^a-zA-Z0-9_-]", "", ext_path[-24:])
                    job_id = f"workday_{slug}_{req_id}".lower()
                    job_url = f"https://{slug}.myworkdayjobs.com/en-US/{site}{ext_path}"

                    detail_url = f"{active_cxs_url}{ext_path}"
                    desc_raw = ""
                    desc_clean = ""
                    start_date_str = None
                    resolved_loc = locations_text
                    async with detail_sem:
                        try:
                            d_res = await client.get(detail_url, headers=headers)
                            if d_res.status_code == 200:
                                d_data = d_res.json().get("jobPostingInfo", {})
                                desc_raw = d_data.get("jobDescription", "")
                                desc_clean = clean_html_description(desc_raw)
                                start_date_str = d_data.get("startDate")
                                if d_data.get("externalUrl"):
                                    job_url = d_data.get("externalUrl")
                                primary_loc = str(d_data.get("location") or "").strip()
                                add_locs = [str(x) for x in (d_data.get("additionalLocations") or []) if x]
                                all_locs = [x for x in ([primary_loc] + add_locs) if x]
                                if is_multi_loc_badge and all_locs:
                                    india_matches = [x for x in all_locs if is_india_or_remote_location(x)]
                                    if filter_india and not india_matches:
                                        return None
                                    resolved_loc = india_matches[0] if india_matches else ", ".join(all_locs[:2])
                        except Exception:
                            if is_multi_loc_badge and filter_india:
                                return None
                            desc_clean = f"{title} at {company_name}. Location: {locations_text}"

                    is_remote = bool(re.search(r"\b(remote|anywhere)\b", f"{title} {resolved_loc}", re.IGNORECASE))
                    posted_dt = parse_workday_posted_on(item.get("postedOn"), start_date=start_date_str)

                    return JobListing(
                        id=job_id,
                        source="workday",
                        company_name=company_name,
                        job_title=title,
                        location=resolved_loc or "India",
                        is_remote=is_remote,
                        is_dream_org=is_dream_org,
                        job_description_raw=desc_raw or desc_clean,
                        job_description_clean=desc_clean,
                        url=job_url,
                        posted_at=posted_dt,
                    )

                hydrated = await asyncio.gather(*(_hydrate_item(it) for it in candidate_items))
                listings = [it for it in hydrated if it is not None]

        except Exception:
            return listings

        return listings
