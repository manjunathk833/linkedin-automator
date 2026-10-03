"""
Unified ATS Ingestion Coordinator.
Dispatches parallel asynchronous collectors across Greenhouse, Lever, and Ashby boards,
normalizes payloads, and queues them for tailoring and human-in-the-loop review.
"""

from __future__ import annotations

import asyncio
import json
import os
import re

from src.ingestion.ashby import AshbyCollector
from src.ingestion.greenhouse import GreenhouseCollector
from src.ingestion.lever import LeverCollector
from src.storage.models import JobListing, TargetCompany

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "data", "config", "target_companies.json")
DEFAULT_QUEUE_DIR = os.path.join(PROJECT_ROOT, "data", "pending_queue")


class ATSDiscoveryCoordinator:
    """Coordinates multi-source keyless ATS ingestion across target enterprises."""

    def __init__(
        self,
        config_path: str = DEFAULT_CONFIG_PATH,
        queue_dir: str = DEFAULT_QUEUE_DIR,
        max_concurrency: int = 10,
    ):
        self.config_path = config_path
        self.queue_dir = queue_dir
        self.semaphore = asyncio.Semaphore(max_concurrency)

        self.greenhouse = GreenhouseCollector()
        self.lever = LeverCollector()
        self.ashby = AshbyCollector()

    def load_target_companies(self) -> list[TargetCompany]:
        """Loads and parses configured target companies."""
        if not os.path.exists(self.config_path):
            return []
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [TargetCompany(**item) for item in data if item.get("active", True)]

    async def _fetch_company_jobs(self, company: TargetCompany) -> list[JobListing]:
        """Fetches jobs for a single target company using its respective ATS collector."""
        async with self.semaphore:
            provider = company.ats_provider.lower()
            if provider == "greenhouse":
                return await self.greenhouse.fetch_board_jobs(company.name, company.slug)
            elif provider == "lever":
                return await self.lever.fetch_board_jobs(company.name, company.slug)
            elif provider == "ashby":
                return await self.ashby.fetch_board_jobs(company.name, company.slug)
            else:
                return []

    async def ingest_all_sources(self, filter_sdet: bool = True) -> list[JobListing]:
        """
        Ingests public job boards across all target companies concurrently.
        """
        companies = self.load_target_companies()
        if not companies:
            print(f"⚠️ No target companies found in {self.config_path}")
            return []

        print(f"🌐 Ingesting ATS boards across {len(companies)} target enterprises...")
        tasks = [self._fetch_company_jobs(c) for c in companies]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_listings: list[JobListing] = []
        for res in results:
            if isinstance(res, list):
                all_listings.extend(res)
            elif isinstance(res, Exception):
                print(f"⚠️ Ingestion error: {res}")

        print(f"✅ Ingestion complete: {len(all_listings)} relevant SDET/QA role(s) discovered.")
        return all_listings

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

    def save_listings_to_queue(self, listings: list[JobListing]) -> list[str]:
        """
        Saves JobListing objects to data/pending_queue/{job_id}.json
        compatible with the approval gate dashboard and filter engine.
        """
        os.makedirs(self.queue_dir, exist_ok=True)
        saved_paths: list[str] = []

        for item in listings:
            filepath = os.path.join(self.queue_dir, f"{item.id}.json")
            requirements_text = self._extract_requirements_text(
                item.job_description_clean or item.job_description_raw or ""
            )
            payload = {
                "job_id": item.id,
                "source": item.source,
                "application_type": f"ATS_{item.source.upper()}",
                "job_details": {
                    "title": item.job_title,
                    "company": item.company_name,
                    "location": item.location,
                    "description": item.job_description_clean,
                    "raw_description": item.job_description_raw,
                    "requirements": requirements_text,
                    "is_remote": item.is_remote,
                    "salary_range": item.salary_range,
                },
                "job_url": item.url,
                "url": item.url,
                "discovered_at": item.discovered_at.isoformat(),
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            saved_paths.append(filepath)

        return saved_paths
