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
    RecruiteeCollector,
    RipplingCollector,
    SmartRecruitersCollector,
    WorkableCollector,
)
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
        max_concurrency: int = 10,
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
        self.hirist = HiristCollector()
        self.instahyre = InstahyreCollector()

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

    def generate_composite_hash(self, company: str, title: str) -> str:
        """Generates a composite hash md5(company_title) for cross-platform duplicate detection."""
        norm = f"{company.strip().lower()}_{title.strip().lower()}"
        return hashlib.md5(norm.encode("utf-8")).hexdigest()

    def is_duplicate(self, job_id: str, company: str, title: str) -> bool:
        """
        Checks if a job_id or (company + title) has already been applied or processed across
        SQLite persistent database, processed_jobs.json, and physical file queues.
        """
        # 0. Check SQLite persistent database for completed applications (exact ID & company+role)
        try:
            from src.storage.database import ApplicationDatabase

            db = ApplicationDatabase()
            if db.is_job_applied(job_id) or db.is_company_role_applied(company, title):
                return True
        except Exception:
            pass

        data = self.load_processed_jobs()
        job_ids = data.get("job_ids", {})
        composite_hashes = data.get("composite_hashes", {})

        # 1. Check primary job_id
        if job_id in job_ids:
            return True

        # 2. Check composite hash (cross-source duplicate protection)
        c_hash = self.generate_composite_hash(company, title)
        if c_hash in composite_hashes:
            return True

        # 3. Check physical file queues
        for qdir in [
            self.queue_dir,
            os.path.join(PROJECT_ROOT, "data", "approved_queue"),
            os.path.join(PROJECT_ROOT, "data", "applied_queue"),
        ]:
            if os.path.exists(qdir) and f"{job_id}.json" in os.listdir(qdir):
                return True

        return False

    def mark_job_processed(self, job_id: str, company: str, title: str, status: str = "PENDING"):
        """Registers an ATS job into the master deduplication index."""
        data = self.load_processed_jobs()
        now = datetime.datetime.utcnow().isoformat() + "Z"
        c_hash = self.generate_composite_hash(company, title)

        data.setdefault("job_ids", {})[job_id] = {
            "title": title,
            "company": company,
            "first_seen": now,
            "status": status,
        }
        data.setdefault("composite_hashes", {})[c_hash] = {"job_id": job_id, "first_seen": now}
        self.save_processed_jobs(data)

    def load_target_companies(self) -> list[TargetCompany]:
        """Loads and parses configured target companies."""
        if not os.path.exists(self.config_path):
            return []
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [TargetCompany(**item) for item in data if item.get("active", True)]

    async def _fetch_company_jobs(self, company: TargetCompany) -> list[JobListing]:
        """Fetches jobs for a single target company using its respective ATS collector."""
        if self.semaphore is None:
            self.semaphore = asyncio.Semaphore(self.max_concurrency)
        async with self.semaphore:
            provider = company.ats_provider.lower()
            listings: list[JobListing] = []
            if provider == "greenhouse":
                listings = await self.greenhouse.fetch_board_jobs(company.name, company.slug)
            elif provider == "lever":
                listings = await self.lever.fetch_board_jobs(company.name, company.slug)
            elif provider == "ashby":
                listings = await self.ashby.fetch_board_jobs(company.name, company.slug)
            elif provider == "workday":
                listings = await self.workday.fetch_board_jobs(
                    company_name=company.name,
                    slug=company.slug,
                    site=company.site or company.slug,
                    datacenter=company.datacenter or "wd3",
                    is_dream_org=company.is_dream_org,
                )
            elif provider == "smartrecruiters":
                listings = await self.smartrecruiters.fetch_board_jobs(company.name, company.slug)
            elif provider == "rippling":
                listings = await self.rippling.fetch_board_jobs(company.name, company.slug)
            elif provider == "workable":
                listings = await self.workable.fetch_board_jobs(company.name, company.slug)
            elif provider == "recruitee":
                listings = await self.recruitee.fetch_board_jobs(company.name, company.slug)
            elif provider == "hirist":
                listings = await self.hirist.fetch_board_jobs(company.name, company.slug)
            elif provider == "instahyre":
                listings = await self.instahyre.fetch_board_jobs(company.name, company.slug)
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
        for res in results:
            if isinstance(res, list):
                for item in res:
                    if self.is_listing_within_age_limit(item, max_age_days=max_age_days):
                        all_listings.append(item)
                    else:
                        skipped_stale += 1
            elif isinstance(res, Exception):
                print(f"⚠️ Ingestion error: {res}")

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
        try:
            h_jobs = await self.hirist.fetch_jobs(
                query="SDET", location="bangalore", filter_sdet=filter_sdet, max_age_days=effective_max_days
            )
            all_portal_jobs.extend(h_jobs)
        except Exception as e:
            print(f"⚠️ Hirist portal ingestion error: {e}")

        try:
            i_jobs = await self.instahyre.fetch_opportunities_via_browser(
                headless=True, limit=25, filter_sdet=filter_sdet, max_age_days=effective_max_days
            )
            if not i_jobs:
                for slug in self.instahyre.CURATED_SLUGS[:2]:
                    feed_jobs = await self.instahyre.fetch_feed_jobs(
                        slug=slug, filter_sdet=filter_sdet, max_age_days=effective_max_days
                    )
                    i_jobs.extend(feed_jobs)
            all_portal_jobs.extend(i_jobs)
        except Exception as e:
            print(f"⚠️ Instahyre portal ingestion error: {e}")

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

        for item in listings:
            # Cross-platform and applied reseed guard
            if self.is_duplicate(item.id, item.company_name, item.job_title):
                skipped_count += 1
                continue

            filepath = os.path.join(self.queue_dir, f"{item.id}.json")
            requirements_text = self._extract_requirements_text(
                item.job_description_clean or item.job_description_raw or ""
            )
            payload = {
                "job_id": item.id,
                "source": item.source,
                "discovery_track": "TRACK_1_DIRECT_ATS",
                "discovery_channel": (item.source or "direct_ats").lower().strip(),
                "application_type": f"ATS_{item.source.upper()}",
                "is_dream_org": item.is_dream_org,
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
                payload["freshness_badge"] = routing.get("freshness_badge", "📅 STANDARD")
            except Exception:
                pass

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

            self.mark_job_processed(item.id, item.company_name, item.job_title, status="PENDING")

            # Requisition State Engine: Sync to SQLite with SHA-256 change detection
            try:
                from src.storage.database import ApplicationDatabase

                db = ApplicationDatabase()
                db.sync_requisition(
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
