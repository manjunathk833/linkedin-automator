"""
Extended Keyless ATS Ingestion Collectors (SmartRecruiters, Rippling, Workable, Recruitee).
Directly queries unauthenticated public JSON career board endpoints across target product companies.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import httpx

from src.ingestion.filters import (
    is_india_or_remote_location,
    is_sdet_title,
)
from src.ingestion.greenhouse import clean_html_description, parse_iso_timestamp
from src.storage.models import JobListing


class SmartRecruitersCollector:
    """Async collector for SmartRecruiters public job postings API."""

    BASE_URL = "https://api.smartrecruiters.com/v1/companies"

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout = timeout_seconds

    def parse_response(
        self,
        company_name: str,
        slug: str,
        data: dict[str, Any],
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        listings: list[JobListing] = []
        postings = data.get("content", [])
        if not isinstance(postings, list):
            return listings

        for job in postings:
            title = str(job.get("name") or job.get("title") or "").strip()
            if filter_sdet and not is_sdet_title(title):
                continue

            loc_obj = job.get("location") or {}
            city = str(loc_obj.get("city") or "").strip()
            region = str(loc_obj.get("region") or "").strip()
            country = str(loc_obj.get("country") or "").strip()
            is_remote = bool(loc_obj.get("remote", False)) or "remote" in title.lower()
            country_norm = "India" if country.lower() in ("in", "ind", "india") else country
            loc_parts = [p for p in (city, region, country_norm) if p]
            location_name = ", ".join(loc_parts)
            if is_remote and "remote" not in location_name.lower():
                location_name = f"{location_name} (Remote)".strip()

            if filter_sdet and not is_india_or_remote_location(location_name):
                continue

            job_id = str(job.get("id") or job.get("uuid") or "")
            if not job_id:
                continue

            posted_dt = parse_iso_timestamp(job.get("releasedDate") or job.get("createdOn"))
            job_url = f"https://jobs.smartrecruiters.com/{slug}/{job_id}"
            raw_desc = str(job.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text") or title)
            clean_desc = clean_html_description(raw_desc) or f"{title} at {company_name} ({location_name})"

            listings.append(
                JobListing(
                    id=f"smartrecruiters_{slug}_{job_id}",
                    source="smartrecruiters",
                    company_name=company_name,
                    job_title=title,
                    location=location_name or "India",
                    is_remote=is_remote,
                    job_description_raw=raw_desc,
                    job_description_clean=clean_desc,
                    url=job_url,
                    posted_at=posted_dt,
                    status="pending",
                )
            )
        return listings

    async def fetch_board_jobs(
        self,
        company_name: str,
        slug: str,
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        url = f"{self.BASE_URL}/{slug}/postings?limit=100"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                res = await client.get(url)
                if res.status_code != 200:
                    return []
                data = res.json()
            return self.parse_response(company_name, slug, data, filter_sdet=filter_sdet)
        except Exception as e:
            print(f"⚠️ SmartRecruiters fetch warning for {company_name} ({slug}): {e}")
            return []


class RipplingCollector:
    """Async collector for Rippling ATS public career boards."""

    BASE_URL = "https://api.rippling.com/platform/api/ats/v1/board"

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout = timeout_seconds

    def parse_response(
        self,
        company_name: str,
        slug: str,
        data: list[dict[str, Any]] | dict[str, Any],
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        listings: list[JobListing] = []
        jobs = data if isinstance(data, list) else data.get("jobs", data.get("results", []))
        if not isinstance(jobs, list):
            return listings

        for job in jobs:
            title = str(job.get("name") or job.get("title") or "").strip()
            if filter_sdet and not is_sdet_title(title):
                continue

            loc_raw = job.get("workLocation") or job.get("location") or ""
            if isinstance(loc_raw, dict):
                location_name = str(loc_raw.get("name") or loc_raw.get("city") or "")
            elif isinstance(loc_raw, list):
                location_name = ", ".join(str(x) for x in loc_raw)
            else:
                location_name = str(loc_raw)

            is_remote = bool(re.search(r"\bremote\b", f"{title} {location_name}", re.IGNORECASE))
            if filter_sdet and not is_india_or_remote_location(location_name):
                continue

            job_id = str(job.get("uuid") or job.get("id") or "")
            if not job_id:
                continue

            posted_dt = parse_iso_timestamp(job.get("created_at") or job.get("published_at") or job.get("updated_at"))
            job_url = str(job.get("url") or f"https://ats.rippling.com/{slug}/jobs/{job_id}")
            raw_desc = str(job.get("description") or f"{title} at {company_name} ({location_name})")
            clean_desc = clean_html_description(raw_desc)

            listings.append(
                JobListing(
                    id=f"rippling_{slug}_{job_id}",
                    source="rippling",
                    company_name=company_name,
                    job_title=title,
                    location=location_name or "Remote / India",
                    is_remote=is_remote,
                    job_description_raw=raw_desc,
                    job_description_clean=clean_desc,
                    url=job_url,
                    posted_at=posted_dt,
                    status="pending",
                )
            )
        return listings

    async def fetch_board_jobs(
        self,
        company_name: str,
        slug: str,
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        url = f"{self.BASE_URL}/{slug}/jobs"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                res = await client.get(url)
                if res.status_code != 200:
                    return []
                data = res.json()
            return self.parse_response(company_name, slug, data, filter_sdet=filter_sdet)
        except Exception as e:
            print(f"⚠️ Rippling fetch warning for {company_name} ({slug}): {e}")
            return []


class WorkableCollector:
    """Async collector for Workable public widget job boards."""

    BASE_URL = "https://apply.workable.com/api/v1/widget/accounts"

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout = timeout_seconds

    def parse_response(
        self,
        company_name: str,
        slug: str,
        data: dict[str, Any],
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        listings: list[JobListing] = []
        jobs = data.get("jobs", [])
        if not isinstance(jobs, list):
            return listings

        for job in jobs:
            title = str(job.get("title") or "").strip()
            if filter_sdet and not is_sdet_title(title):
                continue

            city = str(job.get("city") or "").strip()
            country = str(job.get("country") or "").strip()
            is_remote = bool(job.get("telecommuting", False)) or "remote" in title.lower()
            loc_parts = [p for p in (city, country) if p]
            location_name = ", ".join(loc_parts)
            if is_remote and "remote" not in location_name.lower():
                location_name = f"{location_name} (Remote)".strip()

            if filter_sdet and not is_india_or_remote_location(location_name):
                continue

            shortcode = str(job.get("shortcode") or job.get("id") or "")
            if not shortcode:
                continue

            pub_raw = str(job.get("published_on") or job.get("created_at") or "").strip()
            posted_dt: datetime | None = None
            if pub_raw:
                posted_dt = parse_iso_timestamp(pub_raw)
                if posted_dt is None:
                    try:
                        posted_dt = datetime.strptime(f"{pub_raw[:10]} +0000", "%Y-%m-%d %z").replace(tzinfo=None)
                    except Exception:
                        posted_dt = None

            job_url = str(job.get("url") or f"https://apply.workable.com/{slug}/j/{shortcode}/")
            raw_desc = str(job.get("description") or f"{title} at {company_name} ({location_name})")
            clean_desc = clean_html_description(raw_desc)

            listings.append(
                JobListing(
                    id=f"workable_{slug}_{shortcode}",
                    source="workable",
                    company_name=company_name,
                    job_title=title,
                    location=location_name or "Remote / India",
                    is_remote=is_remote,
                    job_description_raw=raw_desc,
                    job_description_clean=clean_desc,
                    url=job_url,
                    posted_at=posted_dt,
                    status="pending",
                )
            )
        return listings

    async def fetch_board_jobs(
        self,
        company_name: str,
        slug: str,
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        url = f"{self.BASE_URL}/{slug}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                res = await client.get(url)
                if res.status_code != 200:
                    return []
                data = res.json()
            return self.parse_response(company_name, slug, data, filter_sdet=filter_sdet)
        except Exception as e:
            print(f"⚠️ Workable fetch warning for {company_name} ({slug}): {e}")
            return []


class RecruiteeCollector:
    """Async collector for Recruitee public offers API."""

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout = timeout_seconds

    def parse_response(
        self,
        company_name: str,
        slug: str,
        data: dict[str, Any],
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        listings: list[JobListing] = []
        offers = data.get("offers", [])
        if not isinstance(offers, list):
            return listings

        for job in offers:
            title = str(job.get("title") or "").strip()
            if filter_sdet and not is_sdet_title(title):
                continue

            location_name = str(job.get("location") or job.get("city") or "").strip()
            is_remote = bool(job.get("remote", False)) or "remote" in location_name.lower()
            if is_remote and "remote" not in location_name.lower():
                location_name = f"{location_name} (Remote)".strip()

            if filter_sdet and not is_india_or_remote_location(location_name):
                continue

            job_id = str(job.get("id") or job.get("slug") or "")
            if not job_id:
                continue

            posted_dt = parse_iso_timestamp(job.get("published_at") or job.get("created_at"))
            job_url = str(job.get("careers_url") or f"https://{slug}.recruitee.com/o/{job_id}")
            raw_desc = str(job.get("description") or f"{title} at {company_name}")
            clean_desc = clean_html_description(raw_desc)

            listings.append(
                JobListing(
                    id=f"recruitee_{slug}_{job_id}",
                    source="recruitee",
                    company_name=company_name,
                    job_title=title,
                    location=location_name or "Remote / India",
                    is_remote=is_remote,
                    job_description_raw=raw_desc,
                    job_description_clean=clean_desc,
                    url=job_url,
                    posted_at=posted_dt,
                    status="pending",
                )
            )
        return listings

    async def fetch_board_jobs(
        self,
        company_name: str,
        slug: str,
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        url = f"https://{slug}.recruitee.com/api/offers"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                res = await client.get(url)
                if res.status_code != 200:
                    return []
                data = res.json()
            return self.parse_response(company_name, slug, data, filter_sdet=filter_sdet)
        except Exception as e:
            print(f"⚠️ Recruitee fetch warning for {company_name} ({slug}): {e}")
            return []
