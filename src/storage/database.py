"""
Persistent SQLite Audit Repository for Applications and Submission Budgets.
Tracks every staged listing, generated resume artifact, and completed submission
while enforcing daily quota governance (≤15 applications/24 hours).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sqlite3
from typing import Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "app_database.db")


class ApplicationDatabase:
    """
    Manages SQLite audit persistence and daily rate limits for the job application copilot.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Initializes database tables if they do not already exist."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS job_applications (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    job_title TEXT NOT NULL,
                    job_url TEXT NOT NULL,
                    resume_path TEXT NOT NULL,
                    tailored_data_json TEXT NOT NULL,
                    screening_qa_json TEXT,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_job_applications_status ON job_applications(status);
                CREATE INDEX IF NOT EXISTS idx_job_applications_applied_at ON job_applications(applied_at DESC);

                CREATE TABLE IF NOT EXISTS daily_submission_limits (
                    date_bucket TEXT PRIMARY KEY,
                    submission_count INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS tracked_requisitions (
                    requisition_id TEXT PRIMARY KEY,
                    company_slug TEXT NOT NULL,
                    ats_provider TEXT NOT NULL,
                    job_title TEXT NOT NULL,
                    location TEXT NOT NULL,
                    job_url TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    is_dream_org INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'ACTIVE',
                    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_tracked_req_company ON tracked_requisitions(company_slug);
                CREATE INDEX IF NOT EXISTS idx_tracked_req_dream ON tracked_requisitions(is_dream_org);
                CREATE INDEX IF NOT EXISTS idx_tracked_req_status ON tracked_requisitions(status);
                """
            )

    def _get_today_bucket(self) -> str:
        """Returns date string bucket in YYYY-MM-DD format."""
        return datetime.date.today().isoformat()

    def get_today_submission_count(self) -> int:
        """Returns the number of applications completed today."""
        bucket = self._get_today_bucket()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT submission_count FROM daily_submission_limits WHERE date_bucket = ?",
                (bucket,),
            )
            row = cursor.fetchone()
            return int(row["submission_count"]) if row else 0

    def increment_today_submission_count(self) -> int:
        """Increments today's submission counter and returns the new count."""
        bucket = self._get_today_bucket()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO daily_submission_limits (date_bucket, submission_count)
                VALUES (?, 1)
                ON CONFLICT(date_bucket) DO UPDATE SET submission_count = submission_count + 1
                RETURNING submission_count;
                """,
                (bucket,),
            )
            row = cursor.fetchone()
            conn.commit()
            return int(row[0]) if row else 1

    def record_application(
        self,
        job_id: str,
        source: str,
        company_name: str,
        job_title: str,
        job_url: str,
        resume_path: str = "",
        tailored_data: dict[str, Any] | str | None = None,
        screening_qa: dict[str, Any] | str | None = None,
        status: str = "applied",
    ) -> None:
        """Records an application event into the audit trail and updates daily submission counter."""
        tailored_payload = tailored_data if tailored_data is not None else {}
        tailored_json = tailored_payload if isinstance(tailored_payload, str) else json.dumps(tailored_payload)
        qa_json = screening_qa if isinstance(screening_qa, str) or screening_qa is None else json.dumps(screening_qa)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO job_applications (
                    id, source, company_name, job_title, job_url,
                    resume_path, tailored_data_json, screening_qa_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    resume_path = excluded.resume_path,
                    tailored_data_json = excluded.tailored_data_json,
                    screening_qa_json = excluded.screening_qa_json;
                """,
                (
                    job_id,
                    source,
                    company_name,
                    job_title,
                    job_url,
                    resume_path,
                    tailored_json,
                    qa_json,
                    status,
                ),
            )
            conn.commit()

        self.increment_today_submission_count()

    def get_application(self, job_id: str) -> dict[str, Any] | None:
        """Retrieves an application audit record by job_id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM job_applications WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)

    def is_job_applied(self, job_id: str) -> bool:
        """Returns True if job_id has been explicitly marked as applied in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM job_applications WHERE id = ? AND status = 'applied' LIMIT 1;",
                (job_id,),
            )
            return cursor.fetchone() is not None

    def is_company_role_applied(self, company_name: str, job_title: str) -> bool:
        """
        Returns True if a job for the given company and title has already been applied.
        Normalizes company and title case-insensitively and whitespace-trimmed to prevent cross-source reseeding.
        """
        if not company_name or not job_title:
            return False
        clean_company = company_name.strip().lower()
        clean_title = job_title.strip().lower()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1 FROM job_applications
                WHERE LOWER(TRIM(company_name)) = ?
                  AND LOWER(TRIM(job_title)) = ?
                  AND status = 'applied'
                LIMIT 1;
                """,
                (clean_company, clean_title),
            )
            return cursor.fetchone() is not None

    def get_applied_composite_hashes(self) -> set[str]:
        """Returns set of md5(company_title) composite hashes for all applied jobs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT company_name, job_title FROM job_applications WHERE status = 'applied';")
            hashes = set()
            for row in cursor.fetchall():
                comp = (row["company_name"] or "").strip().lower()
                tit = (row["job_title"] or "").strip().lower()
                if comp and tit:
                    norm = f"{comp}_{tit}"
                    hashes.add(hashlib.md5(norm.encode("utf-8")).hexdigest())
            return hashes

    def get_applied_job_ids(self) -> set[str]:
        """Returns the set of all job IDs that have been explicitly marked as applied."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM job_applications WHERE status = 'applied';")
            return {row["id"] for row in cursor.fetchall()}

    def get_all_applications(self, limit: int = 200, status_filter: str | None = None) -> list[dict[str, Any]]:
        """Retrieves all application records ordered by applied_at DESC for tracking."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status_filter:
                cursor.execute(
                    "SELECT * FROM job_applications WHERE status = ? ORDER BY applied_at DESC LIMIT ?",
                    (status_filter, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM job_applications ORDER BY applied_at DESC LIMIT ?",
                    (limit,),
                )
            rows = cursor.fetchall()
            applications = []
            for row in rows:
                item = dict(row)
                item["job_id"] = item.get("id")
                applications.append(item)
            return applications

    def get_application_stats(self) -> dict[str, Any]:
        """Returns summary statistics for the tracking dashboard."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total FROM job_applications;")
            total = cursor.fetchone()["total"]

            today_count = self.get_today_submission_count()

            cursor.execute("SELECT source, COUNT(*) AS cnt FROM job_applications GROUP BY source ORDER BY cnt DESC;")
            sources = {row["source"]: row["cnt"] for row in cursor.fetchall()}

            cursor.execute("SELECT status, COUNT(*) AS cnt FROM job_applications GROUP BY status ORDER BY cnt DESC;")
            statuses = {row["status"]: row["cnt"] for row in cursor.fetchall()}

            return {
                "total_applied": total,
                "today_applied": today_count,
                "applied_today": today_count,
                "sources": sources,
                "source_breakdown": sources,
                "statuses": statuses,
                "status_breakdown": statuses,
            }

    def delete_application(self, job_id: str) -> bool:
        """Deletes an application record by job_id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM job_applications WHERE id = ?", (job_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def compute_requisition_hash(job_title: str, location: str, description_clean: str) -> str:
        """Computes deterministic SHA-256 hash for requisition change detection."""
        norm_title = (job_title or "").strip().lower()
        norm_loc = (location or "").strip().lower()
        norm_desc = (description_clean or "").strip()
        payload = f"{norm_title}|{norm_loc}|{norm_desc}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def sync_requisition(
        self,
        requisition_id: str,
        company_slug: str,
        ats_provider: str,
        job_title: str,
        location: str,
        job_url: str,
        description_clean: str,
        is_dream_org: bool = False,
    ) -> dict[str, Any]:
        """
        Synchronizes a requisition into tracked_requisitions using SHA-256 change detection.
        Returns state dict: status ('NEW' | 'ACTIVE' | 'UPDATED'), is_changed flag, and content_hash.
        """
        content_hash = self.compute_requisition_hash(job_title, location, description_clean)
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        dream_flag = 1 if is_dream_org else 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT requisition_id, content_hash, status FROM tracked_requisitions WHERE requisition_id = ?",
                (requisition_id,),
            )
            row = cursor.fetchone()

            if not row:
                # Newly published requisition
                cursor.execute(
                    """
                    INSERT INTO tracked_requisitions (
                        requisition_id, company_slug, ats_provider, job_title,
                        location, job_url, content_hash, is_dream_org, status,
                        first_seen_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'NEW', ?, ?)
                    """,
                    (
                        requisition_id,
                        company_slug,
                        ats_provider,
                        job_title,
                        location,
                        job_url,
                        content_hash,
                        dream_flag,
                        now_ts,
                        now_ts,
                    ),
                )
                conn.commit()
                return {
                    "requisition_id": requisition_id,
                    "status": "NEW",
                    "is_changed": True,
                    "content_hash": content_hash,
                }

            prev_hash = row["content_hash"]
            if prev_hash == content_hash:
                # Unchanged active requisition
                cursor.execute(
                    """
                    UPDATE tracked_requisitions
                    SET last_seen_at = ?, status = 'ACTIVE'
                    WHERE requisition_id = ?
                    """,
                    (now_ts, requisition_id),
                )
                conn.commit()
                return {
                    "requisition_id": requisition_id,
                    "status": "ACTIVE",
                    "is_changed": False,
                    "content_hash": content_hash,
                }
            else:
                # Content changed (e.g. updated job description/requirements)
                cursor.execute(
                    """
                    UPDATE tracked_requisitions
                    SET content_hash = ?, last_seen_at = ?, status = 'UPDATED'
                    WHERE requisition_id = ?
                    """,
                    (content_hash, now_ts, requisition_id),
                )
                conn.commit()
                return {
                    "requisition_id": requisition_id,
                    "status": "UPDATED",
                    "is_changed": True,
                    "content_hash": content_hash,
                }

    def get_tracked_requisitions(
        self,
        is_dream_only: bool = False,
        status_filter: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Retrieves tracked requisitions filtered by dream status or lifecycle state."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM tracked_requisitions"
            conditions = []
            params: list[Any] = []

            if is_dream_only:
                conditions.append("is_dream_org = 1")
            if status_filter:
                conditions.append("status = ?")
                params.append(status_filter)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY last_seen_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, tuple(params))
            return [dict(r) for r in cursor.fetchall()]

    def is_dream_company(self, company_name_or_slug: str) -> bool:
        """Checks if a company is categorized as an elite Dream Org."""
        target = company_name_or_slug.strip().lower()
        # 1. Check tracked_requisitions in SQLite
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM tracked_requisitions WHERE (LOWER(company_slug) = ? OR LOWER(job_title) LIKE ?) AND is_dream_org = 1 LIMIT 1",
                (target, f"%{target}%"),
            )
            if cursor.fetchone():
                return True

        # 2. Check target_companies.json
        cfg_path = os.path.join(PROJECT_ROOT, "data", "config", "target_companies.json")
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    companies = json.load(f)
                for c in companies:
                    if (c.get("slug", "").lower() == target or c.get("name", "").lower() == target) and c.get(
                        "is_dream_org"
                    ):
                        return True
            except Exception:
                pass
        return False
