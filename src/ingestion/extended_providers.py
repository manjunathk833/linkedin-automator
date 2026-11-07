"""
Extended Keyless ATS Ingestion Collectors (SmartRecruiters, Rippling, Workable, Recruitee).
Directly queries unauthenticated public JSON career board endpoints across target product companies.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
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


class AmazonJobsCollector:
    """Async collector for Amazon Jobs public search.json endpoint (India & Global Remote)."""

    SEARCH_URL = "https://www.amazon.jobs/en/search.json"
    DEFAULT_QUERIES = ("SDET", "Quality Assurance Engineer", "Software Dev Engineer Test")

    def __init__(self, timeout_seconds: float = 12.0):
        self.timeout = timeout_seconds

    @staticmethod
    def _parse_amazon_date(raw_date: str | None) -> datetime | None:
        if not raw_date:
            return None
        s = str(raw_date).strip()
        iso = parse_iso_timestamp(s)
        if iso:
            return iso
        for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(f"{s} +0000", f"{fmt} %z").replace(tzinfo=None)
            except ValueError:
                pass
        return None

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

        seen_ids: set[str] = set()
        for job in jobs:
            title = str(job.get("title") or "").strip()
            if filter_sdet and not is_sdet_title(title):
                continue

            location_name = str(
                job.get("normalized_location") or job.get("location") or job.get("city") or "India"
            ).strip()
            if job.get("country_code") == "IND" and "india" not in location_name.lower():
                location_name = f"{location_name}, India"
            is_remote = "remote" in location_name.lower() or "virtual" in location_name.lower()
            if filter_sdet and not is_india_or_remote_location(location_name):
                continue

            job_id = str(job.get("id_icims") or job.get("id") or "").strip()
            if not job_id or job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            posted_dt = self._parse_amazon_date(job.get("posted_date"))
            job_path = str(job.get("job_path") or f"/en/jobs/{job_id}")
            job_url = job_path if job_path.startswith("http") else f"https://www.amazon.jobs{job_path}"
            raw_desc = (
                " ".join(
                    str(job.get(k) or "")
                    for k in ("description_short", "description", "basic_qualifications", "preferred_qualifications")
                ).strip()
                or f"{title} at {company_name} ({location_name})"
            )
            clean_desc = clean_html_description(raw_desc)

            listings.append(
                JobListing(
                    id=f"amazon_{slug}_{job_id}",
                    source="amazon",
                    company_name=company_name,
                    job_title=title,
                    location=location_name,
                    is_remote=is_remote,
                    is_dream_org=True,
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
        company_name: str = "Amazon",
        slug: str = "amazon-india",
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        combined: dict[str, JobListing] = {}
        queries = self.DEFAULT_QUERIES if filter_sdet else ("Software",)
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
                for q in queries:
                    res = await client.get(
                        self.SEARCH_URL,
                        params={"base_query": q, "country": "IND", "sort": "recent", "result_limit": 25},
                    )
                    if res.status_code != 200:
                        continue
                    for item in self.parse_response(company_name, slug, res.json(), filter_sdet=filter_sdet):
                        combined[item.id] = item
            return list(combined.values())
        except Exception as e:
            print(f"⚠️ Amazon Jobs fetch warning for {company_name}: {e}")
            return []


class EightfoldCollector:
    """Async collector for Eightfold AI PCSX Career Portals (Microsoft, Qualcomm, PayPal, Micron, Booking, etc.)."""

    DEFAULT_QUERIES = ("SDET", "Quality Engineer", "Test Automation")

    def __init__(self, timeout_seconds: float = 12.0):
        self.timeout = timeout_seconds

    def parse_response(
        self,
        company_name: str,
        slug: str,
        data: dict[str, Any],
        base_portal_url: str = "https://apply.careers.microsoft.com",
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        listings: list[JobListing] = []
        positions = (
            (data.get("data") or {}).get("positions")
            if isinstance(data.get("data"), dict)
            else data.get("positions", [])
        )
        if not isinstance(positions, list):
            return listings

        base_root = base_portal_url.rstrip("/")
        for pos in positions:
            title = str(pos.get("name") or pos.get("title") or "").strip()
            if filter_sdet and not is_sdet_title(title):
                continue

            locs = pos.get("locations") or []
            location_name = ", ".join(str(x) for x in locs[:3]) if isinstance(locs, list) else str(locs)
            if not location_name:
                location_name = str(pos.get("location") or "India")
            is_remote = (
                "remote" in location_name.lower() or str(pos.get("workLocationOption") or "").lower() == "remote"
            )
            if filter_sdet and not is_india_or_remote_location(location_name):
                continue

            job_id = str(pos.get("id") or pos.get("displayJobId") or "").strip()
            if not job_id:
                continue

            posted_dt: datetime | None = None
            ts_val = pos.get("postedTs") or pos.get("creationTs")
            if isinstance(ts_val, (int, float)) and ts_val > 1_000_000_000:
                try:
                    posted_dt = datetime.fromtimestamp(float(ts_val), tz=timezone.utc).replace(tzinfo=None)
                except Exception:
                    posted_dt = None

            pos_url = str(pos.get("positionUrl") or f"/careers/job/{job_id}")
            job_url = pos_url if pos_url.startswith("http") else f"{base_root}{pos_url}"
            dept = str(pos.get("department") or "")
            raw_desc = str(pos.get("jobDescription") or f"{title} ({dept}) at {company_name} — {location_name}")
            clean_desc = clean_html_description(raw_desc)

            listings.append(
                JobListing(
                    id=f"eightfold_{slug}_{job_id}",
                    source="eightfold",
                    company_name=company_name,
                    job_title=title,
                    location=location_name,
                    is_remote=is_remote,
                    is_dream_org=True,
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
        domain: str = "microsoft.com",
        career_url: str | None = None,
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        base_portal = (career_url or f"https://apply.careers.{domain}").rstrip("/")
        api_url = f"{base_portal}/api/pcsx/search"
        queries = self.DEFAULT_QUERIES if filter_sdet else ("Software",)
        combined: dict[str, JobListing] = {}
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
                for q in queries:
                    res = await client.get(
                        api_url,
                        params={"domain": domain, "query": q, "location": "India", "start": 0, "sort_by": "timestamp"},
                    )
                    if res.status_code != 200:
                        continue
                    for item in self.parse_response(
                        company_name, slug, res.json(), base_portal_url=base_portal, filter_sdet=filter_sdet
                    ):
                        combined[item.id] = item
            return list(combined.values())
        except Exception as e:
            print(f"⚠️ Eightfold PCSX fetch warning for {company_name} ({slug}): {e}")
            return []


class AppleJobsCollector:
    """Async SSR collector for Apple Jobs India portal (jobs.apple.com/en-in/search)."""

    SEARCH_URL = "https://jobs.apple.com/en-in/search"
    LINK_REGEX = re.compile(
        r'href=["\'](/en-in/details/([0-9A-Za-z-]+?)/([^"\'?]+)[^"\']*)["\'][^>]*>([^<]+)<',
        re.IGNORECASE,
    )
    DATE_REGEX = re.compile(r"\b(\d{1,2}\s+[A-Z][a-z]{2}\s+202\d)\b")

    def __init__(self, timeout_seconds: float = 12.0):
        self.timeout = timeout_seconds

    def parse_response(
        self,
        company_name: str,
        slug: str,
        html_text: str,
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        listings: list[JobListing] = []
        if not html_text:
            return listings

        seen_ids: set[str] = set()
        for match in self.LINK_REGEX.finditer(html_text):
            rel_href, job_id, _role_slug, link_text = match.groups()
            title = link_text.strip()
            if not title or "see full role" in title.lower():
                continue
            if job_id in seen_ids:
                continue
            if filter_sdet and not is_sdet_title(title):
                continue

            seen_ids.add(job_id)
            window_slice = html_text[max(0, match.start() - 200) : min(len(html_text), match.end() + 500)]
            posted_dt: datetime | None = None
            d_match = self.DATE_REGEX.search(window_slice)
            if d_match:
                try:
                    posted_dt = datetime.strptime(f"{d_match.group(1)} +0000", "%d %b %Y %z").replace(tzinfo=None)
                except ValueError:
                    posted_dt = None

            job_url = f"https://jobs.apple.com{rel_href}"
            desc = f"{title} at {company_name} (Bengaluru / Hyderabad, India)"
            listings.append(
                JobListing(
                    id=f"apple_{slug}_{job_id}",
                    source="apple",
                    company_name=company_name,
                    job_title=title,
                    location="Bengaluru / Hyderabad, India",
                    is_remote=False,
                    is_dream_org=True,
                    job_description_raw=desc,
                    job_description_clean=desc,
                    url=job_url,
                    posted_at=posted_dt,
                    status="pending",
                )
            )
        return listings

    async def fetch_board_jobs(
        self,
        company_name: str = "Apple",
        slug: str = "apple-india",
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
                res = await client.get(
                    self.SEARCH_URL,
                    params={"search": "SDET", "sort": "newest", "location": "india-INDC"},
                )
                if res.status_code != 200:
                    return []
                return self.parse_response(company_name, slug, res.text, filter_sdet=filter_sdet)
        except Exception as e:
            print(f"⚠️ Apple Jobs fetch warning for {company_name}: {e}")
            return []


class GoogleCareersCollector:
    """Async SSR collector for Google Careers India (google.com/about/careers/applications/jobs/results)."""

    SEARCH_URL = "https://www.google.com/about/careers/applications/jobs/results/"
    CARD_REGEX = re.compile(
        r"<h3[^>]*>([^<]+)</h3>.*?href=[\"'](jobs/results/(\d+)-[a-z0-9-]+[^\"']*)[\"']",
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(self, timeout_seconds: float = 12.0):
        self.timeout = timeout_seconds

    def parse_response(
        self,
        company_name: str,
        slug: str,
        html_text: str,
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        listings: list[JobListing] = []
        if not html_text:
            return listings

        seen_ids: set[str] = set()
        for match in self.CARD_REGEX.finditer(html_text):
            title, rel_href, job_id = match.groups()
            title = title.strip()
            if not title or title.lower() in ("locations", "experience", "skills & qualifications"):
                continue
            if job_id in seen_ids:
                continue
            if filter_sdet and not is_sdet_title(title):
                continue

            seen_ids.add(job_id)
            clean_href = rel_href.replace("&amp;", "&")
            job_url = f"https://www.google.com/about/careers/applications/{clean_href.lstrip('/')}"
            desc = f"{title} at {company_name} (Bengaluru / Hyderabad, India)"
            listings.append(
                JobListing(
                    id=f"google_{slug}_{job_id}",
                    source="google",
                    company_name=company_name,
                    job_title=title,
                    location="Bengaluru / Hyderabad, India",
                    is_remote=False,
                    is_dream_org=True,
                    job_description_raw=desc,
                    job_description_clean=desc,
                    url=job_url,
                    posted_at=None,
                    status="pending",
                )
            )
        return listings

    async def fetch_board_jobs(
        self,
        company_name: str = "Google",
        slug: str = "google-india",
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        combined: dict[str, JobListing] = {}
        queries = (
            ("Software Engineer in Test", "Test Engineer", "QA Automation") if filter_sdet else ("Software Engineer",)
        )
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
                for q in queries:
                    res = await client.get(
                        self.SEARCH_URL,
                        params={"location": "India", "q": q, "sort_by": "date"},
                    )
                    if res.status_code != 200:
                        continue
                    for item in self.parse_response(company_name, slug, res.text, filter_sdet=filter_sdet):
                        combined[item.id] = item
            return list(combined.values())
        except Exception as e:
            print(f"⚠️ Google Careers fetch warning for {company_name}: {e}")
            return []


class ComeetCollector:
    """Async collector for Comeet public careers API (e.g. Onyx Security)."""

    BASE_URL = "https://www.comeet.co/careers-api/2.0/company"

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
        positions = data if isinstance(data, list) else data.get("positions", [])
        if not isinstance(positions, list):
            return listings

        for job in positions:
            title = str(job.get("name") or job.get("title") or "").strip()
            if filter_sdet and not is_sdet_title(title):
                continue

            loc_obj = job.get("location") or {}
            location_name = str(loc_obj.get("name") or loc_obj.get("city") or "").strip()
            is_remote = bool(loc_obj.get("is_remote")) or "remote" in location_name.lower()
            if is_remote and "remote" not in location_name.lower():
                location_name = f"{location_name} (Remote)".strip()
            if filter_sdet and not is_india_or_remote_location(location_name):
                continue

            job_id = str(job.get("uid") or job.get("id") or "").strip()
            if not job_id:
                continue

            posted_dt = parse_iso_timestamp(job.get("time_updated") or job.get("created_at"))
            job_url = str(
                job.get("url_active_page")
                or job.get("url_comeet_hosted_page")
                or f"https://www.comeet.com/jobs/{slug}/{job_id}"
            )
            raw_desc = str(job.get("details") or f"{title} at {company_name} ({location_name})")
            clean_desc = clean_html_description(raw_desc)

            listings.append(
                JobListing(
                    id=f"comeet_{slug}_{job_id}",
                    source="comeet",
                    company_name=company_name,
                    job_title=title,
                    location=location_name or "Remote",
                    is_remote=is_remote,
                    is_dream_org=True,
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
        company_uid: str,
        token: str,
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        url = f"{self.BASE_URL}/{company_uid}/positions"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                res = await client.get(url, params={"token": token})
                if res.status_code != 200:
                    return []
                return self.parse_response(company_name, slug, res.json(), filter_sdet=filter_sdet)
        except Exception as e:
            print(f"⚠️ Comeet fetch warning for {company_name} ({slug}): {e}")
            return []
