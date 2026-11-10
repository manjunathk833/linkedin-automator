"""
Track 4: Keyless Global Remote (USD/GBP/EUR) & AI Evaluation Job Collectors.
Grounded in live HTTP/SSR reconnaissance across Mercor, Jobicy, Arbeitnow, RemoteOK,
Himalayas, WeWorkRemotely RSS, WorkingNomads, and Remotive.
"""

from __future__ import annotations

import asyncio
import datetime
import email.utils
import hashlib
import html
import json
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from src.ingestion.filters import (
    has_jurisdiction_restriction,
    is_ai_coding_eval_contract,
    is_global_remote_eligible,
    is_sdet_title,
)
from src.storage.models import JobListing

logger = logging.getLogger(__name__)

GLOBAL_REMOTE_SOURCES = (
    "mercor",
    "alignerr",
    "jobicy",
    "arbeitnow",
    "remoteok",
    "himalayas",
    "wwr",
    "workingnomads",
    "remotive",
    "global_remote",
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, application/rss+xml, text/html, */*",
}


def _strip_html(raw_html: str | None) -> str:
    if not raw_html:
        return ""
    unescaped = html.unescape(raw_html)
    cleaned = re.sub(r"<[^>]+>", " ", unescaped)
    return re.sub(r"\s+", " ", cleaned).strip()


def _parse_datetime_utc(raw_val: Any) -> datetime.datetime | None:
    if raw_val is None:
        return None
    if isinstance(raw_val, (int, float)):
        try:
            ts = float(raw_val)
            if ts > 1e12:
                ts /= 1000.0
            return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).replace(tzinfo=None)
        except Exception:
            return None
    if isinstance(raw_val, str):
        s = raw_val.strip()
        if not s:
            return None
        try:
            dt = datetime.datetime.fromisoformat(s.removesuffix("Z"))
            if dt.tzinfo is not None:
                dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            pass
        try:
            dt_rfc = email.utils.parsedate_to_datetime(s)
            if dt_rfc.tzinfo is not None:
                dt_rfc = dt_rfc.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            return dt_rfc
        except Exception:
            return None
    return None


class GlobalRemoteAggregatorCollector:
    """
    Collects verified Global Remote (USD/GBP/EUR) & AI Evaluation roles from
    keyless public APIs and SSR feeds without browser overhead.
    """

    JOBICY_VALID_TAGS = ("playwright", "selenium", "sdet", "pytest", "appium")

    @staticmethod
    def _is_mercor_location_eligible(obj: dict[str, Any]) -> bool:
        """Verifies Mercor listing is not geo-locked to US/UK/EU-only residency (supports ISO-3 'IND')."""
        for key in ("eligibleLocation", "eligibleResidenceLocation"):
            allowed = obj.get(key)
            if isinstance(allowed, list) and len(allowed) > 0:
                tokens = [str(x).strip().lower() for x in allowed]
                joined = " ".join(tokens)
                has_india_or_global = ("ind" in tokens) or any(
                    tok in joined for tok in ("india", "apac", "asia", "global", "worldwide", "all")
                )
                if not has_india_or_global:
                    return False

        for key in ("ineligibleLocation", "ineligibleResidenceLocation"):
            blocked = obj.get(key)
            if isinstance(blocked, list):
                blocked_tokens = [str(x).strip().lower() for x in blocked]
                if "ind" in blocked_tokens or any("india" in t for t in blocked_tokens):
                    return False

        loc = str(obj.get("location") or "Remote").strip()
        desc = str(obj.get("description") or "")
        return is_global_remote_eligible(loc, text_snippet=desc, allow_unspecified=True)

    def parse_mercor_html(self, html_text: str) -> list[JobListing]:
        """Decodes React Query dehydratedState listings directly from Mercor's /explore SSR HTML."""
        if not html_text:
            return []
        # Handle both direct JSON in HTML and escaped __next_f chunks
        candidates_text = [html_text]
        if '\\"listingId\\"' in html_text:
            candidates_text.append(html_text.replace('\\"', '"').replace("\\\\n", "\\n"))

        decoder = json.JSONDecoder()
        seen_ids: set[str] = set()
        results: list[JobListing] = []

        for stream in candidates_text:
            for match in re.finditer(r'\{\s*"listingId"\s*:\s*"list_', stream):
                idx = match.start()
                try:
                    obj, _end_idx = decoder.raw_decode(stream, idx)
                except Exception as exc:
                    logger.debug(f"[GlobalRemote:mercor] JSON decode skipped at idx {idx}: {exc}")
                    continue

                if not isinstance(obj, dict):
                    continue
                lid = str(obj.get("listingId") or "").strip()
                if not lid or lid in seen_ids:
                    continue
                seen_ids.add(lid)

                if str(obj.get("status") or "active").lower() != "active" or obj.get("disableApplications"):
                    continue

                title = str(obj.get("title") or "").strip()
                desc_raw = str(obj.get("description") or "")
                desc_clean = _strip_html(desc_raw)
                if not is_ai_coding_eval_contract(title, desc_clean, source="mercor"):
                    continue
                if not self._is_mercor_location_eligible(obj):
                    continue
                rmin = obj.get("rateMin")
                rmax = obj.get("rateMax")
                if rmin is not None and rmax is not None:
                    sal_str = f"${rmin}-${rmax}/hr USD"
                elif rmin is not None:
                    sal_str = f"${rmin}/hr USD"
                else:
                    sal_str = "USD Hourly Contract"

                comp_name = str(obj.get("companyName") or "Mercor AI Lab").strip()
                loc_str = str(obj.get("location") or "Remote - Worldwide").strip()
                if loc_str.lower() == "remote":
                    loc_str = "Remote - Worldwide"

                is_evergreen = str(obj.get("listingType") or "").strip().lower() == "evergreen"
                parsed_posted_at = (
                    None if is_evergreen else _parse_datetime_utc(obj.get("postedAt") or obj.get("createdAt"))
                )

                results.append(
                    JobListing(
                        id=f"mercor_{lid}",
                        source="mercor",
                        company_name=comp_name,
                        job_title=title,
                        location=loc_str,
                        url=f"https://work.mercor.com/jobs/{lid}",
                        is_remote=True,
                        salary_range=sal_str,
                        job_description_raw=desc_raw,
                        job_description_clean=f"{desc_clean} (Compensation: {sal_str} via Mercor global contractor platform)",
                        posted_at=parsed_posted_at,
                        is_dream_org=True,
                    )
                )
        return results

    def parse_jobicy_payload(self, data: dict[str, Any]) -> list[JobListing]:
        """Parses Jobicy v2 remote-jobs JSON payload."""
        jobs = data.get("jobs", []) if isinstance(data, dict) else []
        if not isinstance(jobs, list):
            return []
        results: list[JobListing] = []
        seen: set[str] = set()
        for j in jobs:
            if not isinstance(j, dict):
                continue
            raw_id = str(j.get("id") or "").strip()
            if not raw_id or raw_id in seen:
                continue
            title = html.unescape(str(j.get("jobTitle") or "").strip())
            if not is_sdet_title(title):
                continue
            geo = str(j.get("jobGeo") or "Worldwide").strip()
            desc_raw = str(j.get("jobDescription") or j.get("jobExcerpt") or "")
            desc_clean = _strip_html(desc_raw)
            if not is_global_remote_eligible(geo, text_snippet=desc_clean, allow_unspecified=False):
                continue

            seen.add(raw_id)
            company = html.unescape(str(j.get("companyName") or "Remote Tech").strip())
            cur = str(j.get("salaryCurrency") or "USD").strip()
            smin = j.get("salaryMin")
            smax = j.get("salaryMax")
            sal_str = f"{cur} {smin}-{smax}" if (smin and smax) else None

            results.append(
                JobListing(
                    id=f"jobicy_{raw_id}",
                    source="jobicy",
                    company_name=company,
                    job_title=title,
                    location=f"Remote ({geo})",
                    url=str(j.get("url") or f"https://jobicy.com/jobs/{raw_id}"),
                    is_remote=True,
                    salary_range=sal_str,
                    job_description_raw=desc_raw,
                    job_description_clean=desc_clean,
                    posted_at=_parse_datetime_utc(j.get("pubDate")),
                    is_dream_org=False,
                )
            )
        return results

    def parse_arbeitnow_payload(self, data: dict[str, Any]) -> list[JobListing]:
        """Parses Arbeitnow job-board-api JSON payload (EUR/GBP/Global remote roles)."""
        jobs = data.get("data", []) if isinstance(data, dict) else []
        if not isinstance(jobs, list):
            return []
        results: list[JobListing] = []
        for j in jobs:
            if not isinstance(j, dict) or not j.get("remote"):
                continue
            title = str(j.get("title") or "").strip()
            if not is_sdet_title(title):
                continue
            loc = str(j.get("location") or "Remote - Worldwide").strip()
            if loc.lower() in ("remote job", "remote"):
                loc = "Remote - Worldwide"
            desc_raw = str(j.get("description") or "")
            desc_clean = _strip_html(desc_raw)
            if not is_global_remote_eligible(loc, text_snippet=desc_clean, allow_unspecified=True):
                continue

            slug = str(j.get("slug") or hashlib.md5(title.encode()).hexdigest()[:10]).strip()
            results.append(
                JobListing(
                    id=f"arbeitnow_{slug}",
                    source="arbeitnow",
                    company_name=str(j.get("company_name") or "European Remote Org").strip(),
                    job_title=title,
                    location=loc,
                    url=str(j.get("url") or f"https://www.arbeitnow.com/jobs/{slug}"),
                    is_remote=True,
                    job_description_raw=desc_raw,
                    job_description_clean=desc_clean,
                    posted_at=_parse_datetime_utc(j.get("created_at")),
                    is_dream_org=False,
                )
            )
        return results

    def parse_remoteok_payload(self, data: list[Any]) -> list[JobListing]:
        """Parses RemoteOK /api JSON array (skipping index 0 legal header)."""
        if not isinstance(data, list):
            return []
        results: list[JobListing] = []
        for j in data:
            if not isinstance(j, dict) or "legal" in j:
                continue
            title = str(j.get("position") or j.get("title") or "").strip()
            if not is_sdet_title(title):
                continue
            loc = str(j.get("location") or "Worldwide").strip() or "Worldwide"
            desc_raw = str(j.get("description") or "")
            desc_clean = _strip_html(desc_raw)
            if not is_global_remote_eligible(loc, text_snippet=desc_clean, allow_unspecified=True):
                continue

            jid = str(j.get("id") or hashlib.md5(title.encode()).hexdigest()[:8]).strip()
            smin = j.get("salary_min")
            smax = j.get("salary_max")
            sal_str = f"USD {smin}-{smax}" if (smin and smax) else None
            results.append(
                JobListing(
                    id=f"remoteok_{jid}",
                    source="remoteok",
                    company_name=str(j.get("company") or "RemoteOK Partner").strip(),
                    job_title=title,
                    location=loc,
                    url=str(j.get("apply_url") or j.get("url") or f"https://remoteok.com/remote-jobs/{jid}"),
                    is_remote=True,
                    salary_range=sal_str,
                    job_description_raw=desc_raw,
                    job_description_clean=desc_clean,
                    posted_at=_parse_datetime_utc(j.get("date") or j.get("epoch")),
                    is_dream_org=False,
                )
            )
        return results

    def parse_himalayas_payload(self, data: dict[str, Any]) -> list[JobListing]:
        """Parses Himalayas /jobs/api JSON payload, enforcing locationRestrictions eligibility."""
        jobs = data.get("jobs", []) if isinstance(data, dict) else []
        if not isinstance(jobs, list):
            return []
        results: list[JobListing] = []
        for j in jobs:
            if not isinstance(j, dict):
                continue
            title = str(j.get("title") or "").strip()
            if not is_sdet_title(title):
                continue
            loc_restrictions = j.get("locationRestrictions") or []
            if isinstance(loc_restrictions, list) and len(loc_restrictions) > 0:
                joined_locs = ", ".join(str(x) for x in loc_restrictions)
                if not any(tok in joined_locs.lower() for tok in ("india", "worldwide", "global", "apac", "anywhere")):
                    continue
                loc_str = f"Remote ({joined_locs})"
            else:
                loc_str = "Remote - Worldwide"

            desc_raw = str(j.get("description") or j.get("excerpt") or "")
            desc_clean = _strip_html(desc_raw)
            if has_jurisdiction_restriction(desc_clean):
                continue

            guid = str(j.get("guid") or hashlib.md5(title.encode()).hexdigest()[:10]).strip()
            clean_guid = re.sub(r"[^a-zA-Z0-9_-]", "_", guid)[:48]
            cur = str(j.get("currency") or "USD").strip()
            smin = j.get("minSalary")
            smax = j.get("maxSalary")
            sal_str = f"{cur} {smin}-{smax}" if (smin and smax) else None

            results.append(
                JobListing(
                    id=f"himalayas_{clean_guid}",
                    source="himalayas",
                    company_name=str(j.get("companyName") or "Himalayas Remote").strip(),
                    job_title=title,
                    location=loc_str,
                    url=str(j.get("applicationLink") or guid),
                    is_remote=True,
                    salary_range=sal_str,
                    job_description_raw=desc_raw,
                    job_description_clean=desc_clean,
                    posted_at=_parse_datetime_utc(j.get("pubDate")),
                    is_dream_org=False,
                )
            )
        return results

    def parse_wwr_rss(self, xml_text: str) -> list[JobListing]:
        """Parses WeWorkRemotely RSS XML feed, checking <region> for global/India eligibility."""
        if not xml_text or "<rss" not in xml_text[:300]:
            return []
        results: list[JobListing] = []
        try:
            root = ET.fromstring(xml_text)
        except Exception:
            return []

        for item in root.findall(".//item"):
            raw_title = (item.findtext("title") or "").strip()
            if ":" in raw_title:
                company, title = [p.strip() for p in raw_title.split(":", 1)]
            else:
                company, title = "WeWorkRemotely Partner", raw_title

            if not is_sdet_title(title):
                continue

            region = (item.findtext("region") or "Anywhere in the World").strip()
            country = (item.findtext("country") or "").strip()
            loc_combined = f"{region} {country}".strip()
            desc_raw = item.findtext("description") or ""
            desc_clean = _strip_html(desc_raw)

            if not is_global_remote_eligible(loc_combined, text_snippet=desc_clean, allow_unspecified=True):
                continue

            link = (item.findtext("link") or item.findtext("guid") or "").strip()
            slug = link.rstrip("/").split("/")[-1] if link else hashlib.md5(raw_title.encode()).hexdigest()[:10]
            results.append(
                JobListing(
                    id=f"wwr_{slug[:48]}",
                    source="wwr",
                    company_name=company,
                    job_title=title,
                    location=f"Remote ({region})",
                    url=link,
                    is_remote=True,
                    job_description_raw=desc_raw,
                    job_description_clean=desc_clean,
                    posted_at=_parse_datetime_utc(item.findtext("pubDate")),
                    is_dream_org=False,
                )
            )
        return results

    def parse_workingnomads_payload(self, data: list[Any]) -> list[JobListing]:
        """Parses WorkingNomads /api/exposed_jobs/ JSON list."""
        if not isinstance(data, list):
            return []
        results: list[JobListing] = []
        for j in data:
            if not isinstance(j, dict):
                continue
            title = str(j.get("title") or "").strip()
            if not is_sdet_title(title):
                continue
            loc = str(j.get("location") or "Remote - Worldwide").strip()
            desc_raw = str(j.get("description") or "")
            desc_clean = _strip_html(desc_raw)
            if not is_global_remote_eligible(loc, text_snippet=desc_clean, allow_unspecified=True):
                continue
            url = str(j.get("url") or "").strip()
            uid = hashlib.md5(f"{j.get('company_name')}_{title}_{url}".encode()).hexdigest()[:10]
            results.append(
                JobListing(
                    id=f"workingnomads_{uid}",
                    source="workingnomads",
                    company_name=str(j.get("company_name") or "WorkingNomads Partner").strip(),
                    job_title=title,
                    location=loc,
                    url=url,
                    is_remote=True,
                    job_description_raw=desc_raw,
                    job_description_clean=desc_clean,
                    posted_at=_parse_datetime_utc(j.get("pub_date")),
                    is_dream_org=False,
                )
            )
        return results

    def parse_remotive_payload(self, data: dict[str, Any]) -> list[JobListing]:
        """Parses Remotive /api/remote-jobs JSON payload."""
        jobs = data.get("jobs", []) if isinstance(data, dict) else []
        if not isinstance(jobs, list):
            return []
        results: list[JobListing] = []
        for j in jobs:
            if not isinstance(j, dict):
                continue
            title = str(j.get("title") or "").strip()
            if not is_sdet_title(title):
                continue
            loc = str(j.get("candidate_required_location") or "Worldwide").strip()
            desc_raw = str(j.get("description") or "")
            desc_clean = _strip_html(desc_raw)
            if not is_global_remote_eligible(loc, text_snippet=desc_clean, allow_unspecified=True):
                continue
            jid = str(j.get("id") or hashlib.md5(title.encode()).hexdigest()[:8]).strip()
            results.append(
                JobListing(
                    id=f"remotive_{jid}",
                    source="remotive",
                    company_name=str(j.get("company_name") or "Remotive Partner").strip(),
                    job_title=title,
                    location=f"Remote ({loc})",
                    url=str(j.get("url") or f"https://remotive.com/remote-jobs/{jid}"),
                    is_remote=True,
                    salary_range=str(j.get("salary") or "") or None,
                    job_description_raw=desc_raw,
                    job_description_clean=desc_clean,
                    posted_at=_parse_datetime_utc(j.get("publication_date")),
                    is_dream_org=False,
                )
            )
        return results

    def parse_alignerr_html(self, html_text: str) -> list[JobListing]:
        """Parses Alignerr (Labelbox) SSR job cards from https://www.alignerr.com/jobs with SEO clone deduplication."""
        if not html_text:
            return []
        results: list[JobListing] = []
        seen_titles: set[str] = set()
        seen_ids: set[str] = set()

        for match in re.finditer(r'<a[^>]+href=["\'](/jobs/([0-9a-fA-F-]+))["\'][^>]*>(.*?)</a>', html_text, re.DOTALL):
            rel_href, job_uuid, card_inner = match.group(1), match.group(2).strip(), match.group(3)
            if not job_uuid or job_uuid in seen_ids:
                continue

            h3_match = re.search(r"<h[23][^>]*>(.*?)</h[23]>", card_inner, re.DOTALL)
            if not h3_match:
                continue
            title = _strip_html(h3_match.group(1))
            norm_title = title.lower().strip()
            if not norm_title or norm_title in seen_titles:
                continue

            p_tags = [_strip_html(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", card_inner, re.DOTALL)]
            snippet = p_tags[0] if p_tags else _strip_html(card_inner)
            rate_str = "USD Hourly Contract"
            loc_str = "Remote - Worldwide"
            for p_txt in p_tags[1:]:
                if "$" in p_txt or "/hr" in p_txt.lower():
                    rate_str = p_txt if "usd" in p_txt.lower() else f"{p_txt} USD"
                elif p_txt and len(p_txt) <= 45:
                    loc_str = p_txt
            if rate_str == "USD Hourly Contract":
                rate_match = re.search(r"(\$\s?\d+(?:\s*-\s*\$?\d+)?\s*/\s*hr)", card_inner, re.IGNORECASE)
                if rate_match:
                    rate_str = f"{rate_match.group(1).strip()} USD"

            if not is_ai_coding_eval_contract(title, snippet, source="alignerr"):
                continue
            if not is_global_remote_eligible(loc_str, text_snippet=snippet, allow_unspecified=True):
                continue

            seen_ids.add(job_uuid)
            seen_titles.add(norm_title)
            if loc_str.lower() == "remote":
                loc_str = "Remote - Worldwide"

            results.append(
                JobListing(
                    id=f"alignerr_{job_uuid}",
                    source="alignerr",
                    company_name="Alignerr (Labelbox AI)",
                    job_title=title,
                    location=loc_str,
                    url=f"https://www.alignerr.com{rel_href}",
                    is_remote=True,
                    salary_range=rate_str,
                    job_description_raw=snippet,
                    job_description_clean=f"{snippet} (Compensation: {rate_str} via Alignerr / Labelbox global AI evaluation platform)",
                    posted_at=None,
                    is_dream_org=True,
                )
            )
        return results

    async def fetch_board_jobs(self, company_name: str, slug: str) -> list[JobListing]:
        """Unified async entry point dispatched by ATSDiscoveryCoordinator for `global_remote` providers."""
        target = slug.strip().lower()
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, follow_redirects=True, timeout=16.0) as client:
            if target == "mercor":
                resp = await client.get("https://work.mercor.com/explore")
                if resp.status_code == 200:
                    return self.parse_mercor_html(resp.text)
                return []

            if target == "alignerr":
                resp = await client.get("https://www.alignerr.com/jobs")
                if resp.status_code == 200:
                    return self.parse_alignerr_html(resp.text)
                return []

            if target == "jobicy":
                seen_ids: set[str] = set()
                combined: list[JobListing] = []
                responses = await asyncio.gather(
                    *(
                        client.get(f"https://jobicy.com/api/v2/remote-jobs?count=50&tag={tag}")
                        for tag in self.JOBICY_VALID_TAGS
                    ),
                    return_exceptions=True,
                )
                for tag, resp in zip(self.JOBICY_VALID_TAGS, responses):
                    if isinstance(resp, Exception):
                        logger.debug(f"[GlobalRemote:jobicy] Tag '{tag}' fetch failed: {resp}")
                        continue
                    try:
                        if resp.status_code == 200:
                            for item in self.parse_jobicy_payload(resp.json()):
                                if item.id not in seen_ids:
                                    seen_ids.add(item.id)
                                    combined.append(item)
                    except Exception as exc:
                        logger.debug(f"[GlobalRemote:jobicy] Tag '{tag}' parse failed: {exc}")
                        continue
                return combined

            if target == "arbeitnow":
                resp = await client.get("https://www.arbeitnow.com/api/job-board-api")
                if resp.status_code == 200:
                    return self.parse_arbeitnow_payload(resp.json())
                return []

            if target == "remoteok":
                resp = await client.get("https://remoteok.com/api")
                if resp.status_code == 200:
                    return self.parse_remoteok_payload(resp.json())
                return []

            if target == "himalayas":
                resp = await client.get("https://himalayas.app/jobs/api?limit=20&offset=0")
                if resp.status_code == 200:
                    return self.parse_himalayas_payload(resp.json())
                return []

            if target == "wwr":
                resp = await client.get("https://weworkremotely.com/remote-jobs.rss")
                if resp.status_code == 200:
                    return self.parse_wwr_rss(resp.text)
                return []

            if target == "workingnomads":
                resp = await client.get("https://www.workingnomads.com/api/exposed_jobs/")
                if resp.status_code == 200:
                    return self.parse_workingnomads_payload(resp.json())
                return []

            if target == "remotive":
                resp = await client.get("https://remotive.com/api/remote-jobs?category=qa")
                if resp.status_code == 200:
                    return self.parse_remotive_payload(resp.json())
                return []

        return []
