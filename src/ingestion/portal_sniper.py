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
from src.ingestion.filters import evaluate_global_remote_signal
from src.ingestion.global_remote_providers import GLOBAL_REMOTE_SOURCES
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

    @staticmethod
    def _parse_iso_utc(raw_ts: str | None) -> datetime | None:
        """Parses an ISO-8601 timestamp string into naive UTC datetime."""
        if not raw_ts or not isinstance(raw_ts, str):
            return None
        cleaned = raw_ts.strip()
        cleaned = cleaned.removesuffix("Z")
        try:
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            return None

    @classmethod
    def is_reopened_fresh(
        cls,
        listing: JobListing,
        ledger_entry: dict[str, Any],
        age_hours: float | None,
        max_age_hours: float = 24.0,
        min_refresh_gap_hours: float = 24.0,
    ) -> bool:
        """
        Determines whether a previously seen requisition was genuinely re-opened or refreshed
        within the <24h window.
        Requires:
        1. listing.posted_at is present and age_hours <= max_age_hours (<=24h old right now).
        2. listing.posted_at is at least `min_refresh_gap_hours` (24h) newer than the previously
           recorded `posted_at` or `first_seen_at` in `portal_seen_ledger.json`.
        """
        if listing.posted_at is None or age_hours is None or age_hours > max_age_hours:
            return False
        item_dt = listing.posted_at
        if item_dt.tzinfo is not None:
            item_dt = item_dt.astimezone(timezone.utc).replace(tzinfo=None)

        prev_ts_str = ledger_entry.get("posted_at") or ledger_entry.get("first_seen_at")
        prev_dt = cls._parse_iso_utc(prev_ts_str)
        if prev_dt is None:
            return False

        refresh_delta_hours = (item_dt - prev_dt).total_seconds() / 3600.0
        return refresh_delta_hours >= min_refresh_gap_hours

    def filter_and_package_drops(
        self,
        listings: list[JobListing],
        total_orgs_polled: int = 0,
    ) -> dict[str, Any]:
        """
        Cross-references discovered SDET/QA listings against:
        1. Stateful portal_seen_ledger.json (must not have been seen in a prior scan, UNLESS
           its native posted_at/updated_at timestamp was refreshed within <24h after >=24h gap).
        2. Post timestamp <= max_age_hours (or newly appeared in ledger if provider omits timestamp).
        Writes latest_ci_drops.json, portal_seen_ledger.json, and latest_daily_report.md.
        """
        now = datetime.utcnow()
        now_iso = now.isoformat() + "Z"
        ledger = self.load_seen_ledger()

        fresh_drops: list[dict[str, Any]] = []
        skipped_seen = 0
        skipped_stale = 0
        reopened_count = 0

        for item in listings:
            age_hours = self.compute_listing_age_hours(item, now_utc=now)
            reopened_fresh = False
            previous_first_seen_at: str | None = None

            # 1. Check stateful seen ledger first (prevents typo edits on old jobs from re-triggering,
            #    while allowing genuinely re-opened / <24h refreshed requisitions through)
            if item.id in ledger:
                existing_entry = ledger[item.id]
                if self.is_reopened_fresh(item, existing_entry, age_hours, max_age_hours=self.max_age_hours):
                    reopened_fresh = True
                    reopened_count += 1
                    previous_first_seen_at = existing_entry.get("first_seen_at")
                    ledger[item.id] = {
                        **existing_entry,
                        "company": item.company_name,
                        "title": item.job_title,
                        "source": item.source,
                        "posted_at": item.posted_at.isoformat() if item.posted_at else existing_entry.get("posted_at"),
                        "last_reopened_at": now_iso,
                        "reopen_count": int(existing_entry.get("reopen_count", 0)) + 1,
                    }
                else:
                    skipped_seen += 1
                    continue
            else:
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
            src_low = (item.source or "direct_ats").lower().strip()
            remote_sig = evaluate_global_remote_signal(
                title=item.job_title,
                location=item.location,
                description=item.job_description_clean or item.job_description_raw or "",
                compensation_str=item.salary_range or "",
            )
            is_track4_remote = src_low in GLOBAL_REMOTE_SOURCES or bool(remote_sig.get("is_usd_eor_remote"))
            track_name = "TRACK_4_GLOBAL_REMOTE" if is_track4_remote else "PORTAL_SNIPER"
            app_type = f"GLOBAL_{src_low.upper()}" if src_low in GLOBAL_REMOTE_SOURCES else f"ATS_{item.source.upper()}"

            payload: dict[str, Any] = {
                "job_id": item.id,
                "source": item.source,
                "discovery_track": track_name,
                "discovery_channel": src_low,
                "application_type": app_type,
                "is_dream_org": item.is_dream_org,
                "is_usd_eor_remote": is_track4_remote,
                "posted_at": item.posted_at.isoformat() if item.posted_at else now_iso,
                "age_hours": age_hours if age_hours is not None else 0.5,
                "discovered_at": now_iso,
                "reopened_fresh": reopened_fresh,
                "previous_first_seen_at": previous_first_seen_at,
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
                    "is_usd_eor_remote": is_track4_remote,
                    "posted_at": item.posted_at.isoformat() if item.posted_at else now_iso,
                    "reopened_fresh": reopened_fresh,
                },
            }
            routing = InterviewRouter.classify_job_strategy(payload)
            payload["routing_strategy"] = routing
            if reopened_fresh:
                payload["freshness_badge"] = "🔄 REOPENED (<24h)"
                routing["freshness_badge"] = "🔄 REOPENED (<24h)"
            else:
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
            "reopened_fresh_count": reopened_count,
            "skipped_already_seen": skipped_seen,
            "skipped_older_than_window": skipped_stale,
            "provider_telemetry": getattr(self.coordinator, "last_ingestion_telemetry", {}),
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
        ]

        prov_tel = bundle.get("provider_telemetry") or {}
        if prov_tel:
            lines.extend(
                [
                    "## 📊 Per-Provider Ingestion Telemetry (`13` Keyless Providers)",
                    "",
                    "| Provider | Orgs Polled | Orgs w/ SDET Matches | Total SDET/QA Roles Retrieved | Sample Matched Orgs |",
                    "| :--- | :---: | :---: | :---: | :--- |",
                ]
            )
            for prov_name, st in sorted(
                prov_tel.items(), key=lambda kv: (-kv[1].get("sdet_matches_found", 0), -kv[1].get("orgs_polled", 0))
            ):
                orgs_str = ", ".join(st.get("matched_orgs", [])[:5]) or "—"
                lines.append(
                    f"| `{prov_name}` | `{st.get('orgs_polled', 0)}` | `{st.get('orgs_with_matches', 0)}` | "
                    f"**`{st.get('sdet_matches_found', 0)}`** | {orgs_str} |"
                )
            lines.append("")

        lines.extend(
            [
                "---",
                "",
                "## 🔥 Verified `<24h` Fresh QA / SDET Openings",
                "",
            ]
        )

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
        listings = await self.coordinator.ingest_all_sources(filter_sdet=True, max_age_days=None)
        return self.filter_and_package_drops(listings, total_orgs_polled=len(companies))
