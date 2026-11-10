"""
Unified ATS Ingestion Coordinator.
Dispatches parallel asynchronous collectors across Greenhouse, Lever, and Ashby boards,
normalizes payloads, and queues them for tailoring and human-in-the-loop review.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import os
import re
from typing import Any

from src.ingestion.ashby import AshbyCollector
from src.ingestion.extended_providers import (
    AmazonJobsCollector,
    AppleJobsCollector,
    ComeetCollector,
    EightfoldCollector,
    GoogleCareersCollector,
    RecruiteeCollector,
    RipplingCollector,
    SmartRecruitersCollector,
    WorkableCollector,
)
from src.ingestion.filters import evaluate_global_remote_signal
from src.ingestion.global_remote_providers import GLOBAL_REMOTE_SOURCES, GlobalRemoteAggregatorCollector
from src.ingestion.greenhouse import GreenhouseCollector
from src.ingestion.hirist import HiristCollector
from src.ingestion.instahyre import InstahyreCollector
from src.ingestion.lever import LeverCollector
from src.ingestion.workday import WorkdayCollector
from src.storage.models import JobListing, TargetCompany

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "data", "config", "target_companies.json")
DEFAULT_QUEUE_DIR = os.path.join(PROJECT_ROOT, "data", "pending_queue")
DEFAULT_DB_FILE = os.path.join(PROJECT_ROOT, "data", "processed_jobs.json")


class ATSDiscoveryCoordinator:
    """Coordinates multi-source keyless ATS ingestion across target enterprises."""

    def __init__(
        self,
        config_path: str = DEFAULT_CONFIG_PATH,
        queue_dir: str = DEFAULT_QUEUE_DIR,
        max_concurrency: int = 60,
        db_file: str = DEFAULT_DB_FILE,
        use_ai: bool = True,
    ):
        self.config_path = config_path
        self.queue_dir = queue_dir
        self.db_file = db_file
        self.use_ai = use_ai
        self.max_concurrency = max_concurrency
        self.semaphore: asyncio.Semaphore | None = None

        self.greenhouse = GreenhouseCollector()
        self.lever = LeverCollector()
        self.ashby = AshbyCollector()
        self.workday = WorkdayCollector()
        self.smartrecruiters = SmartRecruitersCollector()
        self.rippling = RipplingCollector()
        self.workable = WorkableCollector()
        self.recruitee = RecruiteeCollector()
        self.amazon = AmazonJobsCollector()
        self.eightfold = EightfoldCollector()
        self.apple = AppleJobsCollector()
        self.google = GoogleCareersCollector()
        self.comeet = ComeetCollector()
        self.hirist = HiristCollector()
        self.instahyre = InstahyreCollector()
        self.global_remote = GlobalRemoteAggregatorCollector()

    def load_processed_jobs(self) -> dict[str, Any]:
        """Loads master deduplication index from data/processed_jobs.json."""
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        if not os.path.exists(self.db_file):
            return {"job_ids": {}, "composite_hashes": {}}
        try:
            with open(self.db_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"job_ids": {}, "composite_hashes": {}}

    def save_processed_jobs(self, data: dict[str, Any]):
        """Saves master deduplication index back to disk."""
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        with open(self.db_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def normalize_company_name_for_dedup(company: str) -> str:
        """
        Normalizes corporate/portal suffixes (e.g. 'Alcon Digital Health' -> 'alcon',
        'Qualcomm India (Careers)' -> 'qualcomm', 'Citi Technology' -> 'citi') so cross-channel
        listings (Workday vs LinkedIn) map to a shared canonical composite hash.
        """
        raw = re.sub(r"\(.*?\)", " ", (company or "").strip().lower())
        raw = re.sub(r"[^a-z0-9\s]", " ", raw)
        raw = re.sub(r"\s+", " ", raw).strip()
        if not raw:
            return ""
        suffix_pattern = re.compile(
            r"\b("
            r"digital\s+health|"
            r"global\s+software|"
            r"global\s+tech|"
            r"technology\s+center|"
            r"technologies|"
            r"technology|"
            r"engineering|"
            r"careers|"
            r"private\s+limited|"
            r"pvt\s+ltd|"
            r"limited|"
            r"ltd|"
            r"inc|"
            r"llc|"
            r"corp|"
            r"corporation|"
            r"group|"
            r"systems|"
            r"solutions|"
            r"india|"
            r"global|"
            r"digital"
            r")\s*$"
        )
        cleaned = raw
        for _ in range(3):
            candidate = suffix_pattern.sub("", cleaned).strip()
            if candidate:
                cleaned = candidate
            else:
                break
        return cleaned or raw

    def generate_composite_hash(self, company: str, title: str) -> str:
        """Generates a composite hash md5(company_title) for cross-platform duplicate detection."""
        norm = f"{company.strip().lower()}_{title.strip().lower()}"
        return hashlib.md5(norm.encode("utf-8")).hexdigest()

    @classmethod
    def generate_normalized_composite_hash(cls, company: str, title: str) -> str:
        """Generates a suffix-normalized composite hash so 'Alcon Digital Health' and 'Alcon' deduplicate."""
        norm_comp = cls.normalize_company_name_for_dedup(company)
        norm_title = re.sub(r"\s+", " ", (title or "").strip().lower())
        norm = f"{norm_comp}_{norm_title}"
        return hashlib.md5(norm.encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_iso_naive_utc(raw_val: datetime.datetime | str | None) -> datetime.datetime | None:
        if raw_val is None:
            return None
        if isinstance(raw_val, datetime.datetime):
            if raw_val.tzinfo is not None:
                return raw_val.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            return raw_val
        if isinstance(raw_val, str):
            cleaned = raw_val.strip()
            cleaned = cleaned.removesuffix("Z")
            try:
                dt = datetime.datetime.fromisoformat(cleaned)
                if dt.tzinfo is not None:
                    return dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                return dt
            except Exception:
                return None
        return None

    @classmethod
    def _is_entry_reopened_within_24h(
        cls,
        posted_at: datetime.datetime | str | None,
        prev_entry: dict[str, Any] | None,
    ) -> bool:
        """
        Returns True if `posted_at` is within <=24h (or <=48h/96h for date-only 00:00:00 timestamps)
        of UTC now AND at least 24h newer than the previous `posted_at` or `first_seen` recorded in `processed_jobs.json`.
        """
        post_dt = cls._parse_iso_naive_utc(posted_at)
        if post_dt is None or not isinstance(prev_entry, dict):
            return False
        now_utc = datetime.datetime.utcnow()
        age_hours = (now_utc - post_dt).total_seconds() / 3600.0
        prev_ts = prev_entry.get("posted_at") or prev_entry.get("first_seen")
        prev_dt = cls._parse_iso_naive_utc(prev_ts)
        if prev_dt is None:
            return False
        refresh_gap_hours = (post_dt - prev_dt).total_seconds() / 3600.0
        if refresh_gap_hours < 24.0:
            return False
        is_date_only = post_dt.hour == 0 and post_dt.minute == 0 and post_dt.second == 0 and post_dt.microsecond == 0
        max_allowed_age = (96.0 if refresh_gap_hours >= 7 * 24.0 else 48.0) if is_date_only else 24.0
        return age_hours <= max_allowed_age

    def is_duplicate(
        self,
        job_id: str,
        company: str,
        title: str,
        posted_at: datetime.datetime | str | None = None,
        reopened_fresh: bool = False,
    ) -> bool:
        """
        Checks if a job_id or (company + title) has already been applied or processed across
        SQLite persistent database, processed_jobs.json, and physical file queues.
        Allows genuinely re-opened (<24h refreshed) requisitions through if they are not currently
        sitting in pending/approved queues and were not applied within the last 30 days.
        """
        # 0. Check physical file queues first: if already sitting in pending or approved queue, it's active
        for qdir in [
            self.queue_dir,
            os.path.join(PROJECT_ROOT, "data", "approved_queue"),
        ]:
            if os.path.exists(qdir) and f"{job_id}.json" in os.listdir(qdir):
                return True

        data = self.load_processed_jobs()
        job_ids = data.get("job_ids", {})
        composite_hashes = data.get("composite_hashes", {})
        c_hash = self.generate_composite_hash(company, title)
        norm_c_hash = self.generate_normalized_composite_hash(company, title)

        prev_entry = job_ids.get(job_id) or composite_hashes.get(c_hash) or composite_hashes.get(norm_c_hash)
        is_reopened = reopened_fresh or self._is_entry_reopened_within_24h(posted_at, prev_entry)

        # 1. Check SQLite persistent database for completed applications (exact ID & company+role)
        try:
            from src.storage.database import ApplicationDatabase

            db = ApplicationDatabase()
            norm_comp = self.normalize_company_name_for_dedup(company)
            if (
                db.is_job_applied(job_id)
                or db.is_company_role_applied(company, title)
                or (norm_comp and db.is_company_role_applied(norm_comp, title))
            ):
                return not (is_reopened and db.is_reapply_eligible(job_id, company, title, min_days=30.0))
        except Exception:
            pass

        if not is_reopened:
            applied_qdir = os.path.join(PROJECT_ROOT, "data", "applied_queue")
            if os.path.exists(applied_qdir) and f"{job_id}.json" in os.listdir(applied_qdir):
                return True

        # 2. Check primary job_id and composite hash (both exact and suffix-normalized) in processed_jobs.json
        if job_id in job_ids or c_hash in composite_hashes or norm_c_hash in composite_hashes:
            return not is_reopened

        return False

    def mark_job_processed(
        self,
        job_id: str,
        company: str,
        title: str,
        status: str = "PENDING",
        posted_at: str | None = None,
    ):
        """Registers an ATS job into the master deduplication index."""
        data = self.load_processed_jobs()
        now = datetime.datetime.utcnow().isoformat() + "Z"
        c_hash = self.generate_composite_hash(company, title)
        norm_c_hash = self.generate_normalized_composite_hash(company, title)
        existing = data.get("job_ids", {}).get(job_id) or {}

        data.setdefault("job_ids", {})[job_id] = {
            "title": title,
            "company": company,
            "first_seen": existing.get("first_seen") or now,
            "last_seen": now,
            "posted_at": posted_at or existing.get("posted_at") or now,
            "status": status,
        }
        hash_entry = {
            "job_id": job_id,
            "first_seen": existing.get("first_seen") or now,
            "posted_at": posted_at or existing.get("posted_at") or now,
        }
        data.setdefault("composite_hashes", {})[c_hash] = hash_entry
        data.setdefault("composite_hashes", {})[norm_c_hash] = hash_entry
        self.save_processed_jobs(data)

    def load_target_companies(self) -> list[TargetCompany]:
        """Loads and parses configured target companies."""
        if not os.path.exists(self.config_path):
            return []
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [TargetCompany(**item) for item in data if item.get("active", True)]

    async def _fetch_company_jobs(self, company: TargetCompany) -> list[JobListing]:
        """Fetches jobs for a single target company using its respective ATS collector with a strict 15s timeout."""
        if self.semaphore is None:
            self.semaphore = asyncio.Semaphore(self.max_concurrency)
        async with self.semaphore:
            provider = company.ats_provider.lower()
            listings: list[JobListing] = []
            try:
                if provider == "greenhouse":
                    coro = self.greenhouse.fetch_board_jobs(company.name, company.slug)
                elif provider == "lever":
                    coro = self.lever.fetch_board_jobs(company.name, company.slug)
                elif provider == "ashby":
                    coro = self.ashby.fetch_board_jobs(company.name, company.slug)
                elif provider == "workday":
                    coro = self.workday.fetch_board_jobs(
                        company_name=company.name,
                        slug=company.slug,
                        site=company.site or company.slug,
                        datacenter=company.datacenter or "wd3",
                        is_dream_org=company.is_dream_org,
                    )
                elif provider == "smartrecruiters":
                    coro = self.smartrecruiters.fetch_board_jobs(company.name, company.slug)
                elif provider == "rippling":
                    coro = self.rippling.fetch_board_jobs(company.name, company.slug)
                elif provider == "workable":
                    coro = self.workable.fetch_board_jobs(company.name, company.slug)
                elif provider == "recruitee":
                    coro = self.recruitee.fetch_board_jobs(company.name, company.slug)
                elif provider == "amazon":
                    coro = self.amazon.fetch_board_jobs(company.name, company.slug)
                elif provider == "eightfold":
                    coro = self.eightfold.fetch_board_jobs(
                        company_name=company.name,
                        slug=company.slug,
                        domain=company.domain or "microsoft.com",
                        career_url=company.career_url,
                    )
                elif provider == "apple":
                    coro = self.apple.fetch_board_jobs(company.name, company.slug)
                elif provider == "google":
                    coro = self.google.fetch_board_jobs(company.name, company.slug)
                elif provider == "comeet":
                    coro = self.comeet.fetch_board_jobs(
                        company_name=company.name,
                        slug=company.slug,
                        company_uid=company.site or "BA.005",
                        token=company.career_url or "",
                    )
                elif provider == "hirist":
                    coro = self.hirist.fetch_board_jobs(company.name, company.slug)
                elif provider == "instahyre":
                    coro = self.instahyre.fetch_board_jobs(company.name, company.slug)
                elif provider in GLOBAL_REMOTE_SOURCES:
                    coro = self.global_remote.fetch_board_jobs(company.name, company.slug)
                else:
                    return []
                timeout_sec = 22.0 if provider in GLOBAL_REMOTE_SOURCES else 10.0
                listings = await asyncio.wait_for(coro, timeout=timeout_sec)
            except asyncio.TimeoutError:
                return []
            except Exception:
                return []
            for item in listings:
                item.is_dream_org = company.is_dream_org
            return listings

    @staticmethod
    def is_listing_within_age_limit(listing: JobListing, max_age_days: float | None = 3.0) -> bool:
        """
        Returns True if the listing's posted_at timestamp is within max_age_days (default 3.0 days / 72h),
        or if posted_at is not provided by the ATS vendor.
        """
        if max_age_days is None or max_age_days <= 0 or listing.posted_at is None:
            return True
        now = datetime.datetime.utcnow()
        dt = listing.posted_at
        if dt.tzinfo is not None:
            dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        age_days = (now - dt).total_seconds() / 86400.0
        return age_days <= max_age_days

    async def ingest_all_sources(self, filter_sdet: bool = True, max_age_days: float | None = 3.0) -> list[JobListing]:
        """
        Ingests public job boards across all target companies concurrently,
        filtering out stale requisitions older than max_age_days (default <=3 days / 72h).
        """
        companies = self.load_target_companies()
        if not companies:
            print(f"⚠️ No target companies found in {self.config_path}")
            return []

        print(f"🌐 Ingesting ATS boards across {len(companies)} target enterprises (max_age_days={max_age_days})...")
        self.semaphore = asyncio.Semaphore(self.max_concurrency)
        tasks = [self._fetch_company_jobs(c) for c in companies]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_listings: list[JobListing] = []
        skipped_stale = 0
        provider_stats: dict[str, dict[str, Any]] = {}

        for comp, res in zip(companies, results):
            prov = comp.ats_provider.lower().strip()
            pstat = provider_stats.setdefault(
                prov,
                {
                    "orgs_polled": 0,
                    "orgs_with_matches": 0,
                    "sdet_matches_found": 0,
                    "retained_within_window": 0,
                    "matched_orgs": [],
                },
            )
            pstat["orgs_polled"] += 1

            if isinstance(res, list):
                if res:
                    pstat["orgs_with_matches"] += 1
                    pstat["sdet_matches_found"] += len(res)
                    if len(pstat["matched_orgs"]) < 8:
                        pstat["matched_orgs"].append(f"{comp.name} ({len(res)})")
                for item in res:
                    if self.is_listing_within_age_limit(item, max_age_days=max_age_days):
                        all_listings.append(item)
                        pstat["retained_within_window"] += 1
                    else:
                        skipped_stale += 1
            elif isinstance(res, Exception):
                print(f"⚠️ Ingestion error ({comp.name}): {res}")

        self.last_ingestion_telemetry = provider_stats
        print("  📊 Per-Provider Ingestion Telemetry:")
        for prov_name, st in sorted(
            provider_stats.items(), key=lambda kv: (-kv[1]["sdet_matches_found"], -kv[1]["orgs_polled"])
        ):
            orgs_str = ", ".join(st["matched_orgs"][:5]) if st["matched_orgs"] else "-"
            print(
                f"     • {prov_name:<16} | Orgs: {st['orgs_polled']:<4} | "
                f"Matches: {st['sdet_matches_found']:<4} (Retained: {st['retained_within_window']:<4}) | {orgs_str}"
            )

        print(
            f"✅ Ingestion complete: {len(all_listings)} fresh SDET/QA role(s) retained "
            f"({skipped_stale} stale role(s) >{max_age_days}d filtered out)."
        )
        return all_listings

    async def ingest_direct_portals(
        self, filter_sdet: bool = True, max_age_days: float | None = None
    ) -> list[JobListing]:
        """
        Ingests curated direct technology portal listings from Hirist and Instahyre.
        Uses a smart 72h window on Mondays (to capture weekend drops) and 48h Tue-Sun by default.
        """
        effective_max_days = (
            max_age_days if max_age_days is not None else (3.0 if datetime.datetime.utcnow().weekday() == 0 else 2.0)
        )
        all_portal_jobs: list[JobListing] = []
        portal_tel: dict[str, Any] = {
            "hirist_status": "OK",
            "hirist_count": 0,
            "instahyre_status": "OK",
            "instahyre_count": 0,
        }
        try:
            h_jobs = await asyncio.wait_for(
                self.hirist.fetch_jobs(
                    query="SDET", location="bangalore", filter_sdet=filter_sdet, max_age_days=effective_max_days
                ),
                timeout=45.0,
            )
            portal_tel["hirist_count"] = len(h_jobs)
            all_portal_jobs.extend(h_jobs)
        except Exception as e:
            portal_tel["hirist_status"] = f"WARN ({e})"
            print(f"⚠️ Hirist portal ingestion error: {e}")

        try:
            i_jobs = await asyncio.wait_for(
                self.instahyre.fetch_opportunities_via_browser(
                    headless=True, limit=25, filter_sdet=filter_sdet, max_age_days=effective_max_days
                ),
                timeout=45.0,
            )
            insta_err = getattr(self.instahyre, "last_status", "OK")
            if insta_err != "OK":
                portal_tel["instahyre_status"] = insta_err
            if not i_jobs:
                for slug in self.instahyre.CURATED_SLUGS[:2]:
                    feed_jobs = await asyncio.wait_for(
                        self.instahyre.fetch_feed_jobs(
                            slug=slug, filter_sdet=filter_sdet, max_age_days=effective_max_days
                        ),
                        timeout=20.0,
                    )
                    i_jobs.extend(feed_jobs)
            portal_tel["instahyre_count"] = len(i_jobs)
            all_portal_jobs.extend(i_jobs)
        except Exception as e:
            portal_tel["instahyre_status"] = f"WARN ({e})"
            print(f"⚠️ Instahyre portal ingestion error: {e}")

        self.last_portal_telemetry = portal_tel
        return all_portal_jobs

    @staticmethod
    def _extract_requirements_text(html_description: str) -> str:
        """Extracts clean plaintext from HTML job description for requirements display."""
        if not html_description:
            return ""
        # Strip HTML tags
        clean = re.sub(r"<[^>]+>", " ", html_description)
        # Decode common HTML entities
        clean = clean.replace("&amp;", "&").replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">")
        clean = clean.replace("&quot;", '"').replace("&#39;", "'")
        # Collapse whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        # Truncate to a reasonable length for display
        if len(clean) > 2000:
            clean = clean[:2000] + "..."
        return clean

    def save_listings_to_queue(self, listings: list[JobListing], tailor: bool = True) -> list[str]:
        """
        Deduplicates, optionally tailors, and saves JobListing objects to data/pending_queue/{job_id}.json.
        Registers newly discovered jobs into the master deduplication ledger (processed_jobs.json)
        and tracks them in SQLite with SHA-256 change detection.
        """
        os.makedirs(self.queue_dir, exist_ok=True)
        saved_paths: list[str] = []
        skipped_count = 0

        tailorer = None
        if tailor:
            try:
                from src.tailor.resume_tailorer import ResumeTailorer

                tailorer = ResumeTailorer(use_ai=self.use_ai)
            except Exception as e:
                print(f"⚠️ Could not initialize ResumeTailorer for ATS ingestion: {e}")

        proc_snapshot = self.load_processed_jobs()
        proc_ids = proc_snapshot.get("job_ids", {})
        proc_hashes = proc_snapshot.get("composite_hashes", {})

        pre_filter = None
        try:
            from src.filter.job_filter import LinkedInJobFilter

            pre_filter = LinkedInJobFilter(db_file=self.db_file)
        except Exception:
            pre_filter = None

        app_db = None
        try:
            from src.storage.database import ApplicationDatabase

            app_db = ApplicationDatabase()
        except Exception:
            app_db = None

        for item in listings:
            c_hash = self.generate_composite_hash(item.company_name, item.job_title)
            norm_c_hash = self.generate_normalized_composite_hash(item.company_name, item.job_title)
            prev_entry = proc_ids.get(item.id) or proc_hashes.get(c_hash) or proc_hashes.get(norm_c_hash)
            was_previously_seen = prev_entry is not None
            is_reopened_now = self._is_entry_reopened_within_24h(item.posted_at, prev_entry)

            # Cross-platform and applied reseed guard (allows genuinely re-opened <24h roles)
            if self.is_duplicate(item.id, item.company_name, item.job_title, posted_at=item.posted_at):
                if is_reopened_now and app_db is not None:
                    applied_details = app_db.get_applied_job_details(item.id, item.company_name, item.job_title)
                    if applied_details:
                        days_ago = float(applied_details.get("days_since_applied", 0.0) or 0.0)
                        if 2.0 <= days_ago < 30.0:
                            try:
                                from src.tailor.referral_generator import (
                                    ReferralNoteGenerator,
                                    resolve_direct_ats_portal_url,
                                )

                                existing_outreach = app_db.get_referral_outreach(job_id=item.id, limit=5)
                                if not any(r.get("outreach_type") == "REPOST_FOLLOWUP" for r in existing_outreach):
                                    direct_portal = resolve_direct_ats_portal_url(item.company_name) or (
                                        item.application_url or ""
                                    )
                                    followup_note = ReferralNoteGenerator.generate_repost_followup_note(
                                        {
                                            "job_id": item.id,
                                            "company_name": item.company_name,
                                            "job_title": item.job_title,
                                            "job_url": item.application_url or "",
                                        },
                                        days_since_applied=days_ago,
                                    )
                                    app_db.log_referral_outreach(
                                        job_id=str(applied_details.get("job_id") or item.id),
                                        company_name=item.company_name,
                                        job_title=item.job_title,
                                        outreach_type="REPOST_FOLLOWUP",
                                        note_content=followup_note,
                                        requisition_id=item.id,
                                        contact_name="Recruiter / Hiring Manager (Repost Follow-Up)",
                                        contact_title="Talent Acquisition / Engineering Leadership",
                                        contact_linkedin_url=direct_portal,
                                        status="REPOST_FOLLOWUP",
                                    )
                                self.mark_job_processed(
                                    item.id,
                                    item.company_name,
                                    item.job_title,
                                    status="APPLIED_REPOST_FOLLOWUP",
                                    posted_at=item.posted_at.isoformat() if item.posted_at else None,
                                )
                            except Exception:
                                pass
                skipped_count += 1
                continue

            filepath = os.path.join(self.queue_dir, f"{item.id}.json")
            requirements_text = self._extract_requirements_text(
                item.job_description_clean or item.job_description_raw or ""
            )

            # Fast (<1ms) Pre-Tailoring Experience Ceiling & Jurisdiction Check
            if pre_filter is not None:
                is_elig, elig_reason = pre_filter.evaluate_pre_tailoring_eligibility(
                    title=item.job_title,
                    location=item.location or "",
                    requirements=requirements_text,
                    description=item.job_description_clean or "",
                )
                if not is_elig:
                    print(
                        f"⏭️  Skipping ineligible ATS job pre-tailoring ({elig_reason}): {item.job_title} @ {item.company_name} (ID: {item.id})"
                    )
                    self.mark_job_processed(
                        item.id,
                        item.company_name,
                        item.job_title,
                        status="FILTERED_OUT",
                        posted_at=item.posted_at.isoformat() if item.posted_at else None,
                    )
                    skipped_count += 1
                    continue

            src_low = (item.source or "direct_ats").lower().strip()
            remote_sig = evaluate_global_remote_signal(
                title=item.job_title,
                location=item.location,
                description=item.job_description_clean or item.job_description_raw or "",
                compensation_str=item.salary_range or "",
            )
            is_track4_remote = src_low in GLOBAL_REMOTE_SOURCES or bool(remote_sig.get("is_usd_eor_remote"))
            track_name = "TRACK_4_GLOBAL_REMOTE" if is_track4_remote else "TRACK_1_DIRECT_ATS"
            app_type = f"GLOBAL_{src_low.upper()}" if src_low in GLOBAL_REMOTE_SOURCES else f"ATS_{item.source.upper()}"

            payload = {
                "job_id": item.id,
                "source": item.source,
                "discovery_track": track_name,
                "discovery_channel": src_low,
                "application_type": app_type,
                "is_dream_org": item.is_dream_org,
                "is_usd_eor_remote": is_track4_remote,
                "reopened_fresh": bool(was_previously_seen),
                "job_details": {
                    "title": item.job_title,
                    "company": item.company_name,
                    "location": item.location,
                    "description": item.job_description_clean,
                    "raw_description": item.job_description_raw,
                    "requirements": requirements_text,
                    "is_remote": item.is_remote,
                    "salary_range": item.salary_range,
                    "is_dream_org": item.is_dream_org,
                    "is_usd_eor_remote": is_track4_remote,
                    "reopened_fresh": bool(was_previously_seen),
                },
                "job_url": item.url,
                "url": item.url,
                "posted_at": item.posted_at.isoformat() if item.posted_at else None,
                "discovered_at": item.discovered_at.isoformat(),
            }

            if tailorer:
                try:
                    payload = tailorer.tailor_job_payload(payload)
                except Exception as e:
                    print(f"⚠️ Tailoring failed for {item.job_title} @ {item.company_name}: {e}")

            # 3-Tier Interview Routing Classification & Freshness Stamping
            try:
                from src.tailor.referral_generator import InterviewRouter

                routing = InterviewRouter.classify_job_strategy(payload)
                payload["routing_strategy"] = routing
                if was_previously_seen:
                    payload["freshness_badge"] = "🔄 REOPENED (<24h)"
                    routing["freshness_badge"] = "🔄 REOPENED (<24h)"
                else:
                    payload["freshness_badge"] = routing.get("freshness_badge", "📅 STANDARD")
            except Exception:
                pass

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

            self.mark_job_processed(
                item.id,
                item.company_name,
                item.job_title,
                status="PENDING",
                posted_at=item.posted_at.isoformat() if item.posted_at else None,
            )

            # Requisition State Engine: Sync to SQLite with SHA-256 change detection
            if app_db is not None:
                try:
                    app_db.sync_requisition(
                        requisition_id=item.id,
                        company_slug=item.company_name.lower().replace(" ", "_"),
                        ats_provider=item.source,
                        job_title=item.job_title,
                        location=item.location,
                        job_url=item.url,
                        description_clean=item.job_description_clean,
                        is_dream_org=item.is_dream_org,
                    )
                except Exception:
                    pass

            saved_paths.append(filepath)

        print(
            f"💾 Queued {len(saved_paths)} new ATS job(s) into data/pending_queue/ (skipped {skipped_count} duplicate/applied role(s))."
        )
        return saved_paths
