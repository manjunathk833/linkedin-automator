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
import re
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

                CREATE TABLE IF NOT EXISTS referral_outreach (
                    outreach_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    job_title TEXT NOT NULL,
                    requisition_id TEXT,
                    contact_name TEXT,
                    contact_title TEXT,
                    contact_linkedin_url TEXT,
                    outreach_type TEXT NOT NULL,
                    note_content TEXT NOT NULL,
                    status TEXT DEFAULT 'GENERATED',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_referral_outreach_job ON referral_outreach(job_id);
                CREATE INDEX IF NOT EXISTS idx_referral_outreach_company ON referral_outreach(company_name);
                CREATE INDEX IF NOT EXISTS idx_referral_outreach_status ON referral_outreach(status);

                CREATE TABLE IF NOT EXISTS hiring_posts (
                    post_id TEXT PRIMARY KEY,
                    author_name TEXT NOT NULL,
                    author_headline TEXT,
                    author_profile_url TEXT,
                    company_name TEXT,
                    is_dream_org INTEGER DEFAULT 0,
                    post_url TEXT NOT NULL,
                    post_text TEXT NOT NULL,
                    posted_at_relative TEXT,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    extracted_emails TEXT DEFAULT '[]',
                    extracted_links TEXT DEFAULT '[]',
                    extracted_job_codes TEXT DEFAULT '[]',
                    quality_score INTEGER DEFAULT 0,
                    author_role_category TEXT DEFAULT 'ENGINEER',
                    outreach_status TEXT DEFAULT 'NEW',
                    custom_dm_draft TEXT,
                    custom_inmail_draft TEXT,
                    notes TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_hiring_posts_company ON hiring_posts(company_name);
                CREATE INDEX IF NOT EXISTS idx_hiring_posts_status ON hiring_posts(outreach_status);
                CREATE INDEX IF NOT EXISTS idx_hiring_posts_discovered ON hiring_posts(discovered_at DESC);
                CREATE INDEX IF NOT EXISTS idx_hiring_posts_dream ON hiring_posts(is_dream_org);
                """
            )
            self.repair_invalid_post_urls(conn=conn)
            self.repair_posts_metadata_and_links(conn=conn)

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

    def log_referral_outreach(
        self,
        job_id: str,
        company_name: str,
        job_title: str,
        outreach_type: str,
        note_content: str,
        requisition_id: str | None = None,
        contact_name: str | None = None,
        contact_title: str | None = None,
        contact_linkedin_url: str | None = None,
        status: str = "GENERATED",
    ) -> str:
        """Logs a generated referral connection note or InMail into SQLite."""
        outreach_id = (
            f"ref_{job_id}_{hashlib.md5(f'{outreach_type}:{datetime.datetime.utcnow()}'.encode()).hexdigest()[:8]}"
        )
        now = datetime.datetime.utcnow().isoformat() + "Z"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO referral_outreach (
                    outreach_id, job_id, company_name, job_title, requisition_id,
                    contact_name, contact_title, contact_linkedin_url, outreach_type,
                    note_content, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    outreach_id,
                    job_id,
                    company_name,
                    job_title,
                    requisition_id,
                    contact_name,
                    contact_title,
                    contact_linkedin_url,
                    outreach_type,
                    note_content,
                    status,
                    now,
                    now,
                ),
            )
            conn.commit()
        return outreach_id

    def get_referral_outreach(
        self,
        outreach_id: str | None = None,
        job_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Retrieves logged referral outreach records with optional filtering."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM referral_outreach"
            conditions = []
            params: list[Any] = []

            if outreach_id:
                conditions.append("outreach_id = ?")
                params.append(outreach_id)
            if job_id:
                conditions.append("job_id = ?")
                params.append(job_id)
            if status:
                conditions.append("status = ?")
                params.append(status)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, tuple(params))
            return [dict(r) for r in cursor.fetchall()]

    def update_referral_status(
        self,
        outreach_id: str,
        status: str,
        contact_name: str | None = None,
        contact_title: str | None = None,
        contact_linkedin_url: str | None = None,
    ) -> bool:
        """Updates the status and optional contact metadata of an existing referral outreach."""
        now = datetime.datetime.utcnow().isoformat() + "Z"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            updates = ["status = ?", "updated_at = ?"]
            params: list[Any] = [status, now]

            if contact_name is not None:
                updates.append("contact_name = ?")
                params.append(contact_name)
            if contact_title is not None:
                updates.append("contact_title = ?")
                params.append(contact_title)
            if contact_linkedin_url is not None:
                updates.append("contact_linkedin_url = ?")
                params.append(contact_linkedin_url)

            params.append(outreach_id)
            query = f"UPDATE referral_outreach SET {', '.join(updates)} WHERE outreach_id = ?"
            cursor.execute(query, tuple(params))
            conn.commit()
            return cursor.rowcount > 0

    def save_hiring_post(self, post_data: dict[str, Any]) -> bool:
        """Saves or updates a discovered hiring / referral post."""
        post_id = post_data.get("post_id")
        if not post_id:
            return False

        emails = json.dumps(post_data.get("extracted_emails", []))
        links = json.dumps(post_data.get("extracted_links", []))
        job_codes = json.dumps(post_data.get("extracted_job_codes", []))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO hiring_posts (
                    post_id, author_name, author_headline, author_profile_url,
                    company_name, is_dream_org, post_url, post_text,
                    posted_at_relative, extracted_emails, extracted_links,
                    extracted_job_codes, quality_score, author_role_category,
                    outreach_status, custom_dm_draft, custom_inmail_draft, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(post_id) DO UPDATE SET
                    author_headline = excluded.author_headline,
                    company_name = excluded.company_name,
                    is_dream_org = excluded.is_dream_org,
                    post_text = excluded.post_text,
                    posted_at_relative = excluded.posted_at_relative,
                    extracted_emails = excluded.extracted_emails,
                    extracted_links = excluded.extracted_links,
                    extracted_job_codes = excluded.extracted_job_codes,
                    quality_score = excluded.quality_score,
                    author_role_category = excluded.author_role_category,
                    custom_dm_draft = COALESCE(excluded.custom_dm_draft, hiring_posts.custom_dm_draft),
                    custom_inmail_draft = COALESCE(excluded.custom_inmail_draft, hiring_posts.custom_inmail_draft)
                """,
                (
                    post_id,
                    post_data.get("author_name", "Unknown"),
                    post_data.get("author_headline", ""),
                    post_data.get("author_profile_url", ""),
                    post_data.get("company_name", ""),
                    1 if post_data.get("is_dream_org") else 0,
                    post_data.get("post_url", ""),
                    post_data.get("post_text", ""),
                    post_data.get("posted_at_relative", ""),
                    emails,
                    links,
                    job_codes,
                    post_data.get("quality_score", 0),
                    post_data.get("author_role_category", "ENGINEER"),
                    post_data.get("outreach_status", "NEW"),
                    post_data.get("custom_dm_draft", ""),
                    post_data.get("custom_inmail_draft", ""),
                    post_data.get("notes", ""),
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def is_hiring_post_saved(self, post_id: str) -> bool:
        """Checks if a hiring post has already been discovered and saved."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM hiring_posts WHERE post_id = ? LIMIT 1", (post_id,))
            return cursor.fetchone() is not None

    def get_hiring_post(self, post_id: str) -> dict[str, Any] | None:
        """Retrieves a single hiring post by its post_id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hiring_posts WHERE post_id = ? LIMIT 1", (post_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["is_dream_org"] = bool(d.get("is_dream_org"))
            try:
                d["extracted_emails"] = json.loads(d.get("extracted_emails") or "[]")
            except Exception:
                d["extracted_emails"] = []
            try:
                d["extracted_links"] = json.loads(d.get("extracted_links") or "[]")
            except Exception:
                d["extracted_links"] = []
            try:
                d["extracted_job_codes"] = json.loads(d.get("extracted_job_codes") or "[]")
            except Exception:
                d["extracted_job_codes"] = []
            return d

    def get_hiring_posts(
        self,
        limit: int = 50,
        status: str | None = None,
        dream_only: bool = False,
        fresh_only: bool = False,
        role_category: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieves hiring posts with rich multi-parameter filtering."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM hiring_posts"
            conditions: list[str] = []
            params: list[Any] = []

            if status:
                conditions.append("outreach_status = ?")
                params.append(status)
            if dream_only:
                conditions.append("is_dream_org = 1")
            if fresh_only:
                conditions.append(
                    "(posted_at_relative LIKE '%h%' OR posted_at_relative LIKE '%1d%' OR posted_at_relative LIKE '%2d%' OR posted_at_relative LIKE '%m%')"
                )
            if role_category:
                conditions.append("author_role_category = ?")
                params.append(role_category)
            if search:
                pattern = f"%{search.strip()}%"
                conditions.append(
                    "(post_id LIKE ? OR author_name LIKE ? OR company_name LIKE ? OR author_headline LIKE ? OR post_text LIKE ?)"
                )
                params.extend([pattern, pattern, pattern, pattern, pattern])

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY is_dream_org DESC, quality_score DESC, discovered_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, tuple(params))
            results = []
            for row in cursor.fetchall():
                d = dict(row)
                d["is_dream_org"] = bool(d.get("is_dream_org"))
                try:
                    d["extracted_emails"] = json.loads(d.get("extracted_emails") or "[]")
                except Exception:
                    d["extracted_emails"] = []
                try:
                    d["extracted_links"] = json.loads(d.get("extracted_links") or "[]")
                except Exception:
                    d["extracted_links"] = []
                try:
                    d["extracted_job_codes"] = json.loads(d.get("extracted_job_codes") or "[]")
                except Exception:
                    d["extracted_job_codes"] = []
                results.append(d)
            return results

    def update_hiring_post_status(self, post_id: str, status: str, notes: str | None = None) -> bool:
        """Updates the outreach status of a post (e.g. DM_SENT, EMAIL_SENT, DISMISSED)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if notes is not None:
                cursor.execute(
                    "UPDATE hiring_posts SET outreach_status = ?, notes = ? WHERE post_id = ?",
                    (status, notes, post_id),
                )
            else:
                cursor.execute(
                    "UPDATE hiring_posts SET outreach_status = ? WHERE post_id = ?",
                    (status, post_id),
                )
            conn.commit()
            return cursor.rowcount > 0

    def get_hiring_posts_stats(self) -> dict[str, int]:
        """Calculates KPI statistics across discovered hiring posts."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM hiring_posts")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM hiring_posts WHERE is_dream_org = 1")
            dream_orgs = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM hiring_posts WHERE (posted_at_relative LIKE '%h%' OR posted_at_relative LIKE '%1d%' OR posted_at_relative LIKE '%m%')"
            )
            fresh_24h = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM hiring_posts WHERE extracted_emails != '[]' AND extracted_emails IS NOT NULL"
            )
            has_email = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM hiring_posts WHERE outreach_status IN ('DM_SENT', 'EMAIL_SENT', 'REFERRED', 'CONTACTED')"
            )
            contacted = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM hiring_posts WHERE outreach_status = 'NEW'")
            new_leads = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM hiring_posts WHERE author_role_category = 'ENGINEER'")
            engineer_posts = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM hiring_posts WHERE author_role_category = 'RECRUITER'")
            recruiter_posts = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM hiring_posts WHERE author_role_category = 'LEADER'")
            leader_posts = cursor.fetchone()[0]

            return {
                "total_posts": total,
                "dream_orgs": dream_orgs,
                "fresh_24h": fresh_24h,
                "has_email": has_email,
                "contacted": contacted,
                "new_leads": new_leads,
                "engineer_posts": engineer_posts,
                "recruiter_posts": recruiter_posts,
                "leader_posts": leader_posts,
            }

    def delete_hiring_post(self, post_id: str) -> bool:
        """Deletes a hiring post by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM hiring_posts WHERE post_id = ?", (post_id,))
            conn.commit()
            return cursor.rowcount > 0

    def repair_invalid_post_urls(self, conn: sqlite3.Connection | None = None) -> int:
        """
        Repairs legacy hiring post URLs that were populated with synthetic MD5 update hashes
        (e.g., https://www.linkedin.com/feed/update/{hash}), transforming them into authentic
        author activity/post feeds that load with HTTP 200.
        """

        def _do_repair(active_conn: sqlite3.Connection) -> int:
            cursor = active_conn.cursor()
            cursor.execute(
                "SELECT post_id, author_profile_url, post_url FROM hiring_posts "
                "WHERE post_url LIKE 'https://www.linkedin.com/feed/update/%' "
                "AND post_url NOT LIKE '%urn:li:activity%'"
            )
            rows = cursor.fetchall()
            updated_count = 0
            for r in rows:
                post_id = r["post_id"]
                author_url = (r["author_profile_url"] or "").strip().rstrip("/")
                post_url = (r["post_url"] or "").strip()
                # Check for 8-32 character hex hash
                if re.search(r"/feed/update/[0-9a-fA-F]{8,32}/?$", post_url):
                    if "/in/" in author_url:
                        new_url = f"{author_url}/recent-activity/all/"
                    elif "/company/" in author_url:
                        new_url = f"{author_url}/posts/"
                    elif author_url:
                        new_url = author_url
                    else:
                        continue
                    cursor.execute(
                        "UPDATE hiring_posts SET post_url = ? WHERE post_id = ?",
                        (new_url, post_id),
                    )
                    updated_count += 1
            if updated_count > 0:
                active_conn.commit()
            return updated_count

        if conn is not None:
            return _do_repair(conn)
        with self._get_connection() as active_conn:
            return _do_repair(active_conn)

    def repair_posts_metadata_and_links(self, conn: sqlite3.Connection | None = None) -> int:
        """
        Re-evaluates existing hiring posts in SQLite to:
        1. Sanitize corrupted lnkd.in and external URLs (stripping trailing words/emojis).
        2. Disambiguate technical skills from company names, removing false dream org flags.
        3. Recalculate quality score and regenerate custom outreach drafts.
        """
        from src.posts.outreach_composer import PostOutreachComposer
        from src.posts.post_classifier import PostClassifier
        from src.posts.post_tracker import sanitize_post_text

        classifier = PostClassifier()
        composer = PostOutreachComposer()

        def _do_repair(active_conn: sqlite3.Connection) -> int:
            cursor = active_conn.cursor()
            cursor.execute("SELECT * FROM hiring_posts")
            rows = cursor.fetchall()
            updated_count = 0

            def _safe_json_list(val: Any) -> list[str]:
                if not val:
                    return []
                if isinstance(val, list):
                    return val
                try:
                    loaded = json.loads(val)
                    return loaded if isinstance(loaded, list) else []
                except Exception:
                    return []

            for r in rows:
                post_id = r["post_id"]
                author_name = r["author_name"] or ""
                headline = r["author_headline"] or ""
                text = r["post_text"] or ""
                clean_text = sanitize_post_text(text, author_name=author_name)
                raw_links = _safe_json_list(r["extracted_links"])

                # Validate whether post is an authentic hiring/referral lead
                is_valid, _reason = classifier.is_hiring_post(headline, clean_text)
                if not is_valid:
                    # Purge job seeker post that slipped in
                    cursor.execute("DELETE FROM hiring_posts WHERE post_id = ?", (post_id,))
                    updated_count += 1
                    continue

                # Clean links
                clean_links = classifier.extract_links(clean_text, additional_links=raw_links)
                # Re-extract company and dream flag
                company, is_dream = classifier.extract_company_name(headline, clean_text)
                role_cat = r["author_role_category"] or classifier.classify_author_role(headline, clean_text)
                emails = _safe_json_list(r["extracted_emails"])
                job_codes = _safe_json_list(r["extracted_job_codes"])
                posted_time = r["posted_at_relative"] or "recent"

                score = classifier.compute_quality_score(
                    is_dream, emails, clean_links, job_codes, posted_time, role_cat
                )

                post_data = {
                    "author_name": author_name,
                    "company_name": company,
                    "author_role_category": role_cat,
                    "extracted_job_codes": job_codes,
                }
                new_dm = composer.generate_connection_note(post_data)
                new_inmail = composer.generate_inmail_pitch(post_data)

                cursor.execute(
                    """
                    UPDATE hiring_posts SET
                        post_text = ?,
                        company_name = ?,
                        is_dream_org = ?,
                        extracted_links = ?,
                        quality_score = ?,
                        custom_dm_draft = ?,
                        custom_inmail_draft = ?
                    WHERE post_id = ?
                    """,
                    (
                        clean_text,
                        company,
                        1 if is_dream else 0,
                        json.dumps(clean_links),
                        score,
                        new_dm,
                        new_inmail,
                        post_id,
                    ),
                )
                updated_count += 1
            if updated_count > 0:
                active_conn.commit()
            return updated_count

        if conn is not None:
            return _do_repair(conn)
        with self._get_connection() as active_conn:
            return _do_repair(active_conn)
