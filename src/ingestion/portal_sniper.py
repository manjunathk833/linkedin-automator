"""
Cycle 2: Official Career Portal <24h Delta Sniper Engine.
Polls all explicit organizations in target_companies.json, cross-references native publish
timestamps (<24h) against a persistent portal_seen_ledger.json to prevent recycled ghost jobs
from triggering false alerts, classifies winners via InterviewRouter, and writes
data/ci_inbox/latest_ci_drops.json + data/ci_inbox/latest_daily_report.md.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ingestion.ats_discovery import ATSDiscoveryCoordinator
from src.storage.models import JobListing
from src.tailor.referral_generator import InterviewRouter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_INBOX_DIR = os.path.join(PROJECT_ROOT, "data", "ci_inbox")


class PortalSniperEngine:
    """Executes the <24h Freshness Delta Scan across the explicit organization watchlist."""

    def __init__(
        self,
        inbox_dir: str = DEFAULT_INBOX_DIR,
        max_age_hours: float = 24.0,
        config_path: str | None = None,
    ):
        self.inbox_dir = Path(inbox_dir)
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_hours = max_age_hours
        self.ledger_path = self.inbox_dir / "portal_seen_ledger.json"
        self.drops_path = self.inbox_dir / "latest_ci_drops.json"
        self.report_path = self.inbox_dir / "latest_daily_report.md"
        self.coordinator = (
            ATSDiscoveryCoordinator(config_path=config_path, use_ai=False)
            if config_path
            else ATSDiscoveryCoordinator(use_ai=False)
        )

    def load_seen_ledger(self) -> dict[str, dict[str, Any]]:
        """Loads persistent job_id -> first_seen_at ledger."""
        if not self.ledger_path.exists():
            return {}
        try:
            data = json.loads(self.ledger_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def save_seen_ledger(self, ledger: dict[str, dict[str, Any]]) -> None:
        """Writes updated job_id -> first_seen_at ledger to disk."""
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")

    @staticmethod
    def compute_listing_age_hours(listing: JobListing, now_utc: datetime | None = None) -> float | None:
        """Calculates age in hours from listing.posted_at (naive UTC)."""
        if listing.posted_at is None:
            return None
        now = now_utc or datetime.utcnow()
        dt = listing.posted_at
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        delta_sec = (now - dt).total_seconds()
        return max(0.0, round(delta_sec / 3600.0, 2))

    def filter_and_package_drops(
        self,
        listings: list[JobListing],
        total_orgs_polled: int = 0,
    ) -> dict[str, Any]:
        """
        Cross-references discovered SDET/QA listings against:
        1. Stateful portal_seen_ledger.json (must not have been seen in a prior scan).
        2. Post timestamp <= max_age_hours (or newly appeared in ledger if provider omits timestamp).
        Writes latest_ci_drops.json, portal_seen_ledger.json, and latest_daily_report.md.
        """
        now = datetime.utcnow()
        now_iso = now.isoformat() + "Z"
        ledger = self.load_seen_ledger()

        fresh_drops: list[dict[str, Any]] = []
        skipped_seen = 0
        skipped_stale = 0

        for item in listings:
            age_hours = self.compute_listing_age_hours(item, now_utc=now)

            # 1. Check stateful seen ledger first (prevents typo edits on old jobs from re-triggering)
            if item.id in ledger:
                skipped_seen += 1
                continue

            # Record in ledger so future runs know when we first saw this requisition ID
            ledger[item.id] = {
                "company": item.company_name,
                "title": item.job_title,
                "source": item.source,
                "first_seen_at": now_iso,
                "posted_at": item.posted_at.isoformat() if item.posted_at else None,
            }

            # 2. Enforce <24h freshness window if portal provides posted_at timestamp
            if age_hours is not None and age_hours > self.max_age_hours:
                skipped_stale += 1
                continue

            requirements_text = ATSDiscoveryCoordinator._extract_requirements_text(
                item.job_description_clean or item.job_description_raw or ""
            )
            payload: dict[str, Any] = {
                "job_id": item.id,
                "source": item.source,
                "application_type": f"ATS_{item.source.upper()}",
                "is_dream_org": item.is_dream_org,
                "posted_at": item.posted_at.isoformat() if item.posted_at else now_iso,
                "age_hours": age_hours if age_hours is not None else 0.5,
                "discovered_at": now_iso,
                "job_url": item.url,
                "url": item.url,
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
                    "posted_at": item.posted_at.isoformat() if item.posted_at else now_iso,
                },
            }
            routing = InterviewRouter.classify_job_strategy(payload)
            payload["routing_strategy"] = routing
            payload["freshness_badge"] = routing.get("freshness_badge", "⚡ EARLY (<24h old)")
            fresh_drops.append(payload)

        # Sort fresh drops: Dream Orgs & lowest age_hours first
        fresh_drops.sort(
            key=lambda d: (
                0 if d.get("is_dream_org") else 1,
                float(d.get("age_hours") if d.get("age_hours") is not None else 12.0),
            )
        )

        self.save_seen_ledger(ledger)

        report_bundle = {
            "generated_at": now_iso,
            "max_age_hours": self.max_age_hours,
            "total_orgs_polled": total_orgs_polled,
            "total_sdet_matches_scanned": len(listings),
            "fresh_drops_count": len(fresh_drops),
            "skipped_already_seen": skipped_seen,
            "skipped_older_than_window": skipped_stale,
            "drops": fresh_drops,
        }

        self.drops_path.write_text(json.dumps(report_bundle, indent=2), encoding="utf-8")
        self._write_markdown_report(report_bundle)
        return report_bundle

    def _write_markdown_report(self, bundle: dict[str, Any]) -> None:
        """Generates a human-readable Markdown matching report for CI summaries and local inspection."""
        lines = [
            "# 🎯 Daily Career Portal Sniper Report (`<24h` Fresh Drops)",
            "",
            f"- **Generated At (UTC):** `{bundle['generated_at']}`",
            f"- **Explicit Orgs Monitored:** `{bundle['total_orgs_polled']}`",
            f"- **Total SDET/QA Roles Found:** `{bundle['total_sdet_matches_scanned']}`",
            f"- **Verified Fresh Drops (`<={int(bundle['max_age_hours'])}h`):** `{bundle['fresh_drops_count']}`",
            f"- **Filtered Out:** `{bundle['skipped_already_seen']}` previously seen | `{bundle['skipped_older_than_window']}` older than {int(bundle['max_age_hours'])}h",
            "",
            "---",
            "",
            "## 🔥 Verified `<24h` Fresh QA / SDET Openings",
            "",
        ]

        drops = bundle.get("drops", [])
        if not drops:
            lines.append(
                "_No new `<24h` drops detected in this scan window. All previously seen roles are banked in `portal_seen_ledger.json`._"
            )
        else:
            lines.append("| # | Badge | Company | Role | Location | Age | Strategy | Direct Link |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            for idx, d in enumerate(drops, 1):
                jd = d.get("job_details", {})
                comp = jd.get("company", "Unknown")
                if d.get("is_dream_org"):
                    comp = f"⭐ **{comp}**"
                title = jd.get("title", "SDET")
                loc = jd.get("location", "India")
                age = f"{d.get('age_hours', 0.0):.1f}h"
                badge = d.get("freshness_badge", "⚡ EARLY")
                tier = d.get("routing_strategy", {}).get("routing_tier", "TIER_1_SNIPER_APPLY")
                url = d.get("url", "")
                lines.append(f"| {idx} | {badge} | {comp} | {title} | {loc} | `{age}` | `{tier}` | [Apply ↗]({url}) |")

        lines.append("")
        self.report_path.write_text("\n".join(lines), encoding="utf-8")

    async def execute_scan(self) -> dict[str, Any]:
        """Polls all active target companies concurrently and packages `<24h` fresh drops."""
        companies = self.coordinator.load_target_companies()
        listings = await self.coordinator.ingest_all_sources(filter_sdet=True)
        return self.filter_and_package_drops(listings, total_orgs_polled=len(companies))
