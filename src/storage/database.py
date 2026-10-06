"""
Persistent SQLite Audit Repository for Applications and Submission Budgets.
Tracks every staged listing, generated resume artifact, and completed submission
while enforcing daily quota governance (≤15 applications/24 hours).
"""

from __future__ import annotations

import datetime
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
