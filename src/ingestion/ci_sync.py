"""
Cloud-to-Local CI Drop Auto-Ingestor (CISyncIngestor).
Bridges GitHub Actions CI (`data/ci_inbox/latest_ci_drops.json` or remote `ci-job-drops` branch)
directly into the local SQLite database (`data/app_database.db`) and `data/pending_queue/`
so every `<24h` fresh drop appears automatically in the Command Center UI (`http://localhost:8000`).
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from src.ingestion.ats_discovery import ATSDiscoveryCoordinator
from src.storage.database import ApplicationDatabase

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_INBOX_DIR = os.path.join(PROJECT_ROOT, "data", "ci_inbox")
DEFAULT_PENDING_DIR = os.path.join(PROJECT_ROOT, "data", "pending_queue")
DEFAULT_PROCESSED_DB = os.path.join(PROJECT_ROOT, "data", "processed_jobs.json")
DEFAULT_SQLITE_DB = os.path.join(PROJECT_ROOT, "data", "app_database.db")


class CISyncIngestor:
    """Ingests `<24h` fresh drops from `data/ci_inbox/latest_ci_drops.json` into local SQLite and `pending_queue/`."""

    def __init__(
        self,
        inbox_dir: str = DEFAULT_INBOX_DIR,
        pending_dir: str = DEFAULT_PENDING_DIR,
        processed_db_file: str = DEFAULT_PROCESSED_DB,
        sqlite_db_path: str = DEFAULT_SQLITE_DB,
        use_ai: bool = False,
    ):
        self.inbox_dir = Path(inbox_dir)
        self.pending_dir = Path(pending_dir)
        self.processed_db_file = processed_db_file
        self.sqlite_db_path = sqlite_db_path
        self.use_ai = use_ai
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.coordinator = ATSDiscoveryCoordinator(
            queue_dir=str(self.pending_dir),
            db_file=self.processed_db_file,
            use_ai=self.use_ai,
        )

    def _pull_remote_ci_branch(self) -> bool:
        """
        Optionally fetches the latest `data/ci_inbox/latest_ci_drops.json` from `origin/ci-job-drops`
        if available on GitHub, without disturbing the current working branch.
        """
        try:
            res = subprocess.run(
                ["git", "fetch", "origin", "ci-job-drops"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0:
                show_res = subprocess.run(
                    ["git", "show", "origin/ci-job-drops:data/ci_inbox/latest_ci_drops.json"],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if show_res.returncode == 0 and show_res.stdout.strip():
                    self.inbox_dir.mkdir(parents=True, exist_ok=True)
                    local_file = self.inbox_dir / "latest_ci_drops.json"
                    if local_file.exists():
                        try:
                            local_gen = str(json.loads(local_file.read_text(encoding="utf-8")).get("generated_at", ""))
                            remote_gen = str(json.loads(show_res.stdout).get("generated_at", ""))
                            if local_gen and remote_gen and local_gen > remote_gen:
                                # Local bundle (e.g. from local portal-sniper fallback) is newer than remote CI branch
                                return False
                        except Exception:
                            pass
                    local_file.write_text(show_res.stdout, encoding="utf-8")
                    return True
        except Exception:
            pass
        return False

    @staticmethod
    def _is_bundle_fresh(bundle: dict[str, Any], max_age_hours: float = 6.0) -> bool:
        """Returns True if the CI drops bundle was generated within max_age_hours."""
        raw_gen = str(bundle.get("generated_at") or "").strip()
        if not raw_gen:
            return False
        try:
            dt = datetime.datetime.fromisoformat(raw_gen.removesuffix("Z"))
            if dt.tzinfo is not None:
                dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            age_h = (datetime.datetime.utcnow() - dt).total_seconds() / 3600.0
            return -1.0 <= age_h <= max_age_hours
        except Exception:
            return False

    def sync_latest_drops(self, fetch_remote: bool = False) -> dict[str, Any]:
        """
        Reads `data/ci_inbox/latest_ci_drops.json`, deduplicates against SQLite and `pending_queue/`,
        tailors new drops, stages them into `data/pending_queue/`, and records requisitions in SQLite.
        """
        pulled_remote = False
        if fetch_remote:
            pulled_remote = self._pull_remote_ci_branch()

        drops_file = self.inbox_dir / "latest_ci_drops.json"
        if not drops_file.exists():
            return {
                "status": "ok",
                "pulled_remote": pulled_remote,
                "ingested_count": 0,
                "skipped_duplicates": 0,
                "ingested_job_ids": [],
                "message": "No latest_ci_drops.json found in data/ci_inbox/ yet.",
            }

        try:
            bundle = json.loads(drops_file.read_text(encoding="utf-8"))
        except Exception as e:
            return {
                "status": "error",
                "pulled_remote": pulled_remote,
                "ingested_count": 0,
                "skipped_duplicates": 0,
                "ingested_job_ids": [],
                "message": f"Failed to parse latest_ci_drops.json: {e}",
            }

        drops = bundle.get("drops", [])
        ci_branch_fresh = self._is_bundle_fresh(bundle, max_age_hours=6.0)
        if not isinstance(drops, list) or not drops:
            return {
                "status": "ok",
                "pulled_remote": pulled_remote,
                "ci_branch_fresh": ci_branch_fresh,
                "ingested_count": 0,
                "skipped_duplicates": 0,
                "ingested_job_ids": [],
                "message": "0 fresh drops in bundle.",
            }

        tailorer = None
        try:
            from src.tailor.resume_tailorer import ResumeTailorer

            tailorer = ResumeTailorer(use_ai=self.use_ai)
        except Exception:
            tailorer = None

        pre_filter = None
        try:
            from src.filter.job_filter import LinkedInJobFilter

            pre_filter = LinkedInJobFilter(db_file=self.processed_db_file)
        except Exception:
            pre_filter = None

        db = ApplicationDatabase(db_path=self.sqlite_db_path)

        ingested_ids: list[str] = []
        repost_followup_ids: list[str] = []
        skipped_dups = 0

        for raw_drop in drops:
            job_id = str(raw_drop.get("job_id") or "").strip()
            if not job_id:
                continue
            jd = raw_drop.get("job_details") or {}
            company = str(jd.get("company") or raw_drop.get("company_name") or "Unknown").strip()
            title = str(jd.get("title") or raw_drop.get("job_title") or "SDET").strip()
            reopened_fresh = bool(raw_drop.get("reopened_fresh") or jd.get("reopened_fresh"))
            posted_at_str = raw_drop.get("posted_at") or jd.get("posted_at")

            # Check duplicate across SQLite, processed_jobs.json, and physical queues
            applied_details = db.get_applied_job_details(job_id, company, title)
            if applied_details is not None:
                if reopened_fresh and db.is_reapply_eligible(job_id, company, title, min_days=30.0):
                    pass  # Eligible for fresh re-application (>=30d on new ID)
                else:
                    days_ago = float(applied_details.get("days_since_applied") or 0.0)
                    if reopened_fresh and 2.0 <= days_ago < 30.0:
                        try:
                            from src.tailor.referral_generator import (
                                ReferralNoteGenerator,
                                resolve_direct_ats_portal_url,
                            )

                            existing_outreach = db.get_referral_outreach(job_id=job_id, limit=5)
                            if not any(r.get("outreach_type") == "REPOST_FOLLOWUP" for r in existing_outreach):
                                job_url = str(raw_drop.get("url") or raw_drop.get("job_url") or "")
                                direct_portal = resolve_direct_ats_portal_url(company) or job_url
                                followup_note = ReferralNoteGenerator.generate_repost_followup_note(
                                    {
                                        "job_id": job_id,
                                        "company_name": company,
                                        "job_title": title,
                                        "job_url": job_url,
                                    },
                                    days_since_applied=days_ago,
                                )
                                db.log_referral_outreach(
                                    job_id=job_id,
                                    company_name=company,
                                    job_title=title,
                                    outreach_type="REPOST_FOLLOWUP",
                                    note_content=followup_note,
                                    requisition_id=job_id,
                                    contact_name="Recruiter / Hiring Manager (Repost Follow-Up)",
                                    contact_title="Talent Acquisition / Engineering Leadership",
                                    contact_linkedin_url=direct_portal,
                                    status="REPOST_FOLLOWUP",
                                )
                                repost_followup_ids.append(job_id)
                        except Exception:
                            pass
                    skipped_dups += 1
                    continue

            if self.coordinator.is_duplicate(
                job_id,
                company,
                title,
                posted_at=posted_at_str,
                reopened_fresh=reopened_fresh,
            ):
                skipped_dups += 1
                continue

            if pre_filter is not None:
                is_elig, _reason = pre_filter.evaluate_pre_tailoring_eligibility(
                    title=title,
                    location=str(jd.get("location") or ""),
                    requirements=str(jd.get("requirements") or jd.get("description") or ""),
                    description=str(jd.get("description") or ""),
                )
                if not is_elig:
                    self.coordinator.mark_job_processed(
                        job_id,
                        company,
                        title,
                        status="FILTERED_OUT",
                        posted_at=str(posted_at_str) if posted_at_str else None,
                    )
                    skipped_dups += 1
                    continue

            payload = dict(raw_drop)
            payload["ci_onboarded"] = True
            if reopened_fresh:
                payload["reopened_fresh"] = True
                payload["freshness_badge"] = "🔄 REOPENED (<24h)"

            if tailorer and "tailored_resume" not in payload:
                try:
                    payload = tailorer.tailor_job_payload(payload)
                except Exception:
                    pass

            target_path = self.pending_dir / f"{job_id}.json"
            target_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            self.coordinator.mark_job_processed(
                job_id,
                company,
                title,
                status="PENDING",
                posted_at=str(posted_at_str) if posted_at_str else None,
            )

            try:
                db.sync_requisition(
                    requisition_id=job_id,
                    company_slug=company.lower().replace(" ", "_"),
                    ats_provider=str(payload.get("source") or "ats"),
                    job_title=title,
                    location=str(jd.get("location") or "India"),
                    job_url=str(payload.get("url") or payload.get("job_url") or ""),
                    description_clean=str(jd.get("description") or ""),
                    is_dream_org=bool(payload.get("is_dream_org")),
                )
            except Exception:
                pass

            ingested_ids.append(job_id)

        return {
            "status": "ok",
            "pulled_remote": pulled_remote,
            "ci_branch_fresh": ci_branch_fresh,
            "ingested_count": len(ingested_ids),
            "skipped_duplicates": skipped_dups,
            "ingested_job_ids": ingested_ids,
            "repost_followups_logged": len(repost_followup_ids),
            "repost_followup_ids": repost_followup_ids,
            "generated_at": bundle.get("generated_at"),
        }
