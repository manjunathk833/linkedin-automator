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
            combined: dict[str, JobListing] = {}
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                res = await client.get(url)
                if res.status_code != 200:
                    return []
                data = res.json()
                for item in self.parse_response(company_name, slug, data, filter_sdet=filter_sdet):
                    combined[item.id] = item
                if filter_sdet and int(data.get("totalFound") or 0) > 100:
                    res_in = await client.get(f"{self.BASE_URL}/{slug}/postings", params={"q": "India", "limit": 100})
                    if res_in.status_code == 200:
                        for item in self.parse_response(company_name, slug, res_in.json(), filter_sdet=filter_sdet):
                            combined[item.id] = item
            return list(combined.values())
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

    DEFAULT_QUERIES = ("Software Engineer in Test", "SDET", "Test Automation")

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
                        params={"domain": domain, "query": q, "location": "India", "start": 0, "sort_by": "relevance"},
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


class AMDJibeCollector:
    """Async collector for AMD's public Jibe JSON API (careers.amd.com/api/jobs)."""

    SEARCH_URL = "https://careers.amd.com/api/jobs"
    DEFAULT_QUERIES = ("Test", "QA", "SDET", "Automation")

    def __init__(self, timeout_seconds: float = 12.0):
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

        seen_ids: set[str] = set()
        for entry in jobs:
            job = entry.get("data") if isinstance(entry, dict) and isinstance(entry.get("data"), dict) else entry
            if not isinstance(job, dict):
                continue
            title = str(job.get("title") or "").strip()
            if filter_sdet and not is_sdet_title(title):
                continue

            location_name = str(
                job.get("location_name") or job.get("full_location") or job.get("city") or "Bengaluru, India"
            ).strip()
            if str(job.get("country_code") or "").upper() in ("IN", "IND") and "india" not in location_name.lower():
                location_name = f"{location_name}, India"
            is_remote = "remote" in location_name.lower()
            if filter_sdet and not is_india_or_remote_location(location_name):
                continue

            req_id = str(job.get("req_id") or job.get("slug") or "").strip()
            if not req_id or req_id in seen_ids:
                continue
            seen_ids.add(req_id)

            posted_dt = parse_iso_timestamp(job.get("posted_date") or job.get("create_date"))
            job_url = str(job.get("apply_url") or f"https://careers.amd.com/careers-home/jobs/{req_id}")
            raw_desc = (
                " ".join(str(job.get(k) or "") for k in ("description", "qualifications", "responsibilities")).strip()
                or f"{title} at {company_name} ({location_name})"
            )
            clean_desc = clean_html_description(raw_desc)

            listings.append(
                JobListing(
                    id=f"amd_{slug}_{req_id}",
                    source="amd",
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
        company_name: str = "AMD India",
        slug: str = "amd-india",
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
                        params={"keywords": q, "location": "India", "page": 1, "limit": 25},
                    )
                    if res.status_code != 200:
                        continue
                    for item in self.parse_response(company_name, slug, res.json(), filter_sdet=filter_sdet):
                        combined[item.id] = item
        except Exception as e:
            print(f"⚠️ AMD Jibe fetch warning for {company_name}: {e}")
        return list(combined.values())


class OracleCloudHCMCollector:
    """
    Async keyless collector for Oracle Cloud HCM Recruiting CE REST APIs.
    Powers Fortress GCC career portals such as JPMorgan Chase (jpmc.fa.oraclecloud.com)
    and Texas Instruments (edbz.fa.us2.oraclecloud.com).
    """

    DEFAULT_QUERIES = ("SDET", "QA", "Test Engineer", "Quality Engineer", "Automation")

    def __init__(self, timeout_seconds: float = 12.0):
        self.timeout = timeout_seconds

    @staticmethod
    def _extract_location(req: dict[str, Any]) -> str:
        primary = str(req.get("PrimaryLocation") or "").strip()
        country = str(req.get("PrimaryLocationCountry") or "").strip().upper()
        parts: list[str] = []
        if primary:
            parts.append(primary)
        sec = req.get("secondaryLocations") or []
        if isinstance(sec, list):
            for s in sec[:4]:
                if isinstance(s, dict):
                    sname = str(s.get("Name") or "").strip()
                    if sname and sname not in parts:
                        parts.append(sname)
        loc_text = " | ".join(parts)
        if country in ("IN", "IND") and "india" not in loc_text.lower():
            loc_text = f"{loc_text}, India".strip(", ")
        return loc_text

    def parse_response(
        self,
        company_name: str,
        slug: str,
        base_url: str,
        site_number: str,
        data: dict[str, Any],
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        listings: list[JobListing] = []
        items = data.get("items") or []
        if not isinstance(items, list) or not items:
            return listings

        reqs = items[0].get("requisitionList") if isinstance(items[0], dict) else []
        if not isinstance(reqs, list):
            return listings

        clean_base = base_url.rstrip("/")
        seen_ids: set[str] = set()
        for req in reqs:
            if not isinstance(req, dict):
                continue
            title = str(req.get("Title") or "").strip()
            if not title or (filter_sdet and not is_sdet_title(title)):
                continue

            location_name = self._extract_location(req)
            workplace = str(req.get("WorkplaceTypeCode") or "").lower()
            is_remote = "remote" in location_name.lower() or "remote" in workplace
            if filter_sdet and not is_india_or_remote_location(location_name):
                continue

            job_id = str(req.get("Id") or "").strip()
            if not job_id or job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            posted_dt = parse_iso_timestamp(req.get("PostedDate"))
            job_url = f"{clean_base}/hcmUI/CandidateExperience/en/sites/{site_number}/job/{job_id}"
            raw_desc = (
                str(req.get("ExternalDescriptionStr") or req.get("ShortDescriptionStr") or "").strip()
                or f"{title} at {company_name} ({location_name})"
            )
            clean_desc = clean_html_description(raw_desc) or f"{title} at {company_name} ({location_name})"

            listings.append(
                JobListing(
                    id=f"oracle_hcm_{slug}_{job_id}",
                    source="oracle_hcm",
                    company_name=company_name,
                    job_title=title,
                    location=location_name or "India",
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

    async def _hydrate_detail(
        self,
        client: httpx.AsyncClient,
        clean_base: str,
        site_number: str,
        listing: JobListing,
    ) -> None:
        raw_id = listing.id.rsplit("_", 1)[-1]
        detail_url = (
            f"{clean_base}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
            f'?expand=all&onlyData=true&finder=ById;Id="{raw_id}",siteNumber={site_number}'
        )
        try:
            res = await client.get(detail_url)
            if res.status_code != 200:
                return
            items = (res.json() or {}).get("items") or []
            if not items or not isinstance(items[0], dict):
                return
            detail = items[0]
            parts = [
                str(detail.get(k) or "")
                for k in (
                    "ExternalDescriptionStr",
                    "ExternalResponsibilitiesStr",
                    "ExternalQualificationsStr",
                    "ShortDescriptionStr",
                )
            ]
            combined_html = " ".join(p for p in parts if p.strip()).strip()
            if combined_html:
                listing.job_description_raw = combined_html
                listing.job_description_clean = clean_html_description(combined_html)
        except Exception:
            return

    async def fetch_board_jobs(
        self,
        company_name: str,
        slug: str,
        base_url: str,
        site_number: str = "CX",
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        if not base_url:
            return []
        clean_base = base_url.rstrip("/")
        combined: dict[str, JobListing] = {}
        queries = self.DEFAULT_QUERIES if filter_sdet else ("Software",)
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
                for q in queries:
                    url = (
                        f"{clean_base}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
                        f"?onlyData=true&expand=requisitionList.secondaryLocations"
                        f"&finder=findReqs;siteNumber={site_number},limit=25,offset=0,keyword={q}"
                    )
                    res = await client.get(url)
                    if res.status_code != 200:
                        continue
                    for item in self.parse_response(
                        company_name, slug, clean_base, site_number, res.json(), filter_sdet=filter_sdet
                    ):
                        combined[item.id] = item
                # Hydrate full descriptions for up to 12 matched roles
                for item in list(combined.values())[:12]:
                    await self._hydrate_detail(client, clean_base, site_number, item)
        except Exception as e:
            print(f"⚠️ Oracle Cloud HCM fetch warning for {company_name} ({slug}): {e}")
        return list(combined.values())


class AtlassianCareersCollector:
    """Async keyless collector for Atlassian's public JSON listings endpoint."""

    LISTINGS_URL = "https://www.atlassian.com/endpoint/careers/listings"

    def __init__(self, timeout_seconds: float = 12.0):
        self.timeout = timeout_seconds

    def parse_response(
        self,
        company_name: str,
        slug: str,
        data: list[dict[str, Any]],
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        listings: list[JobListing] = []
        if not isinstance(data, list):
            return listings

        seen_ids: set[str] = set()
        for job in data:
            if not isinstance(job, dict):
                continue
            title = str(job.get("title") or "").strip()
            if not title or (filter_sdet and not is_sdet_title(title)):
                continue

            locs = job.get("locations") or []
            loc_list = [str(x).strip() for x in locs if str(x).strip()] if isinstance(locs, list) else [str(locs)]
            matched_locs = [loc for loc in loc_list if is_india_or_remote_location(loc)]
            if filter_sdet and not matched_locs:
                continue

            location_name = ", ".join(matched_locs or loc_list) or "Bengaluru, India"
            is_remote = "remote" in location_name.lower()
            job_id = str(job.get("id") or "").strip()
            if not job_id or job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            portal_post = job.get("portalJobPost") or {}
            job_url = str(
                job.get("applyUrl")
                or (portal_post.get("portalUrl") if isinstance(portal_post, dict) else "")
                or f"https://www.atlassian.com/company/careers/details/{job_id}"
            ).strip()
            raw_desc = (
                " ".join(str(job.get(k) or "") for k in ("overview", "responsibilities", "qualifications")).strip()
                or f"{title} at {company_name} ({location_name})"
            )
            clean_desc = clean_html_description(raw_desc)

            listings.append(
                JobListing(
                    id=f"atlassian_{slug}_{job_id}",
                    source="atlassian",
                    company_name=company_name,
                    job_title=title,
                    location=location_name,
                    is_remote=is_remote,
                    is_dream_org=True,
                    job_description_raw=raw_desc,
                    job_description_clean=clean_desc,
                    url=job_url,
                    posted_at=None,
                    status="pending",
                )
            )
        return listings

    async def fetch_board_jobs(
        self,
        company_name: str = "Atlassian",
        slug: str = "atlassian",
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
                res = await client.get(self.LISTINGS_URL)
                if res.status_code != 200:
                    return []
                return self.parse_response(company_name, slug, res.json(), filter_sdet=filter_sdet)
        except Exception as e:
            print(f"⚠️ Atlassian Careers fetch warning for {company_name}: {e}")
            return []


class TalentBrewCollector:
    """
    Async keyless SSR HTML collector for Radancy / TalentBrew career portals.
    Powers Fortress GCC boards such as Synopsys (careers.synopsys.com) and Intuit (jobs.intuit.com).
    """

    DEFAULT_QUERIES = ("SDET", "QA", "Quality", "Test", "Automation")

    def __init__(self, timeout_seconds: float = 12.0):
        self.timeout = timeout_seconds

    @staticmethod
    def _clean_text(fragment: str) -> str:
        return clean_html_description(fragment)

    def parse_search_html(
        self,
        company_name: str,
        slug: str,
        base_url: str,
        html_text: str,
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        listings: list[JobListing] = []
        if not html_text:
            return listings

        clean_base = base_url.rstrip("/")
        # Match anchor blocks pointing to /job/<city>/<title-slug>/<org_id>/<job_id>
        anchor_pattern = re.compile(
            r'<a[^>]+href="(/job/[^"]+)"[^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        seen_ids: set[str] = set()
        for match in anchor_pattern.finditer(html_text):
            rel_path, inner_html = match.group(1), match.group(2)
            h2_m = re.search(r"<h2[^>]*>(.*?)</h2>", inner_html, re.IGNORECASE | re.DOTALL)
            if not h2_m:
                continue
            title = self._clean_text(h2_m.group(1))
            if not title or (filter_sdet and not is_sdet_title(title)):
                continue

            loc_m = re.search(
                r'class="[^"]*job-location[^"]*"[^>]*>(.*?)</',
                inner_html,
                re.IGNORECASE | re.DOTALL,
            )
            city_from_path = ""
            path_parts = [p for p in rel_path.strip("/").split("/") if p]
            if len(path_parts) >= 2:
                city_from_path = path_parts[1].replace("-", " ").title()
            location_name = self._clean_text(loc_m.group(1)) if loc_m else city_from_path
            if not location_name:
                location_name = city_from_path

            # Strictly verify India/Remote (TalentBrew ?k= queries may mix US/global cards)
            if filter_sdet and not is_india_or_remote_location(location_name):
                continue

            job_id = path_parts[-1] if path_parts else re.sub(r"[^a-zA-Z0-9]+", "_", rel_path)
            if not job_id or job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            date_m = re.search(
                r'class="[^"]*job-date-posted[^"]*"[^>]*>(.*?)</',
                inner_html,
                re.IGNORECASE | re.DOTALL,
            )
            posted_dt = None
            if date_m:
                raw_date = self._clean_text(date_m.group(1))
                for fmt in ("%m/%d/%Y", "%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
                    try:
                        posted_dt = datetime.strptime(raw_date, fmt).replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue

            job_url = f"{clean_base}{rel_path}"
            is_remote = "remote" in location_name.lower() or "remote" in title.lower()
            fallback_desc = f"{title} at {company_name} ({location_name})"

            listings.append(
                JobListing(
                    id=f"talentbrew_{slug}_{job_id}",
                    source="talentbrew",
                    company_name=company_name,
                    job_title=title,
                    location=location_name,
                    is_remote=is_remote,
                    is_dream_org=True,
                    job_description_raw=fallback_desc,
                    job_description_clean=fallback_desc,
                    url=job_url,
                    posted_at=posted_dt,
                    status="pending",
                )
            )
        return listings

    async def _hydrate_detail(self, client: httpx.AsyncClient, listing: JobListing) -> None:
        try:
            res = await client.get(listing.url)
            if res.status_code != 200:
                return
            desc_m = re.search(
                r'<div[^>]+class="[^"]*ats-description[^"]*"[^>]*>(.*?)</div>\s*</section>',
                res.text,
                re.IGNORECASE | re.DOTALL,
            )
            if not desc_m:
                desc_m = re.search(
                    r'<div[^>]+class="[^"]*ats-description[^"]*"[^>]*>(.*?)</div>',
                    res.text,
                    re.IGNORECASE | re.DOTALL,
                )
            if desc_m:
                raw_desc = desc_m.group(1)
                clean_desc = self._clean_text(raw_desc)
                if len(clean_desc) >= 60:
                    listing.job_description_raw = raw_desc
                    listing.job_description_clean = clean_desc
        except Exception:
            return

    async def fetch_board_jobs(
        self,
        company_name: str,
        slug: str,
        base_url: str,
        filter_sdet: bool = True,
    ) -> list[JobListing]:
        if not base_url:
            return []
        clean_base = base_url.rstrip("/")
        combined: dict[str, JobListing] = {}
        queries = self.DEFAULT_QUERIES if filter_sdet else ("Engineering",)
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
                for q in queries:
                    url = f"{clean_base}/search-jobs/India"
                    res = await client.get(url, params={"k": q})
                    if res.status_code != 200:
                        continue
                    for item in self.parse_search_html(
                        company_name, slug, clean_base, res.text, filter_sdet=filter_sdet
                    ):
                        combined[item.id] = item
                for item in list(combined.values())[:10]:
                    await self._hydrate_detail(client, item)
        except Exception as e:
            print(f"⚠️ TalentBrew fetch warning for {company_name} ({slug}): {e}")
        return list(combined.values())
