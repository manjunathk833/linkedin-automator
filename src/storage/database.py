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
_INITIALIZED_DBS: set[tuple[str, int]] = set()


class ApplicationDatabase:
    """
    Manages SQLite audit persistence and daily rate limits for the job application copilot.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        abs_path = os.path.abspath(self.db_path)
        ino = os.stat(abs_path).st_ino if os.path.exists(abs_path) and os.path.getsize(abs_path) > 0 else 0
        cache_key = (abs_path, ino)
        if ino == 0 or cache_key not in _INITIALIZED_DBS:
            self._init_schema()
            if os.path.exists(abs_path):
                _INITIALIZED_DBS.add((abs_path, os.stat(abs_path).st_ino))

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
        except Exception:
            pass
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
                    content_hash TEXT,
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
            try:
                conn.execute("ALTER TABLE hiring_posts ADD COLUMN content_hash TEXT;")
            except Exception:
                pass
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_hiring_posts_content_hash ON hiring_posts(content_hash);")
            except Exception:
                pass

            # Funnel & Lifecycle Tracking Migration
            funnel_cols = [
                ("discovery_track", "TEXT DEFAULT 'TRACK_2_LINKEDIN'"),
                ("discovery_channel", "TEXT DEFAULT 'search'"),
                ("application_mode", "TEXT DEFAULT 'batch_autofill'"),
                ("funnel_stage", "TEXT DEFAULT 'APPLIED'"),
                ("last_stage_update", "TIMESTAMP"),
                ("recruiter_contact", "TEXT DEFAULT ''"),
                ("notes", "TEXT DEFAULT ''"),
            ]
            for col_name, col_def in funnel_cols:
                try:
                    conn.execute(f"ALTER TABLE job_applications ADD COLUMN {col_name} {col_def};")
                except Exception:
                    pass
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_job_applications_stage ON job_applications(funnel_stage);")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_job_applications_track ON job_applications(discovery_track);"
                )
            except Exception:
                pass

            self.repair_invalid_post_urls(conn=conn)
            self.repair_posts_metadata_and_links(conn=conn)
            self.repair_application_funnel_attribution(conn=conn)

    def repair_application_funnel_attribution(self, conn: sqlite3.Connection | None = None) -> None:
        """
        Retroactively backfills discovery_track, discovery_channel, and application_mode
        on existing rows in job_applications that received default ALTER TABLE values.
        """

        def _run(c: sqlite3.Connection) -> None:
            try:
                c.execute(
                    """
                    UPDATE job_applications
                    SET discovery_track = 'TRACK_1_DIRECT_ATS',
                        discovery_channel = LOWER(TRIM(source))
                    WHERE LOWER(TRIM(source)) IN (
                        'greenhouse', 'lever', 'ashby', 'workday', 'smartrecruiters',
                        'hirist', 'instahyre', 'rippling', 'workable', 'recruitee'
                    )
                    AND (discovery_track IS NULL OR discovery_track = 'TRACK_2_LINKEDIN');
                    """
                )
                c.execute(
                    """
                    UPDATE job_applications
                    SET discovery_track = 'TRACK_3_SOCIAL_POST',
                        discovery_channel = 'social_post'
                    WHERE LOWER(TRIM(source)) IN ('social_lead', 'post', 'linkedin_post')
                    AND (discovery_track IS NULL OR discovery_track = 'TRACK_2_LINKEDIN');
                    """
                )
                c.execute(
                    """
                    UPDATE job_applications
                    SET discovery_track = 'TRACK_4_GLOBAL_REMOTE',
                        discovery_channel = LOWER(TRIM(source))
                    WHERE (
                        LOWER(TRIM(source)) IN (
                            'mercor', 'alignerr', 'jobicy', 'arbeitnow', 'remoteok',
                            'himalayas', 'wwr', 'workingnomads', 'remotive', 'global_remote'
                        )
                        OR LOWER(company_name) LIKE '%mercor%'
                        OR LOWER(company_name) LIKE '%alignerr%'
                    )
                    AND (discovery_track IS NULL OR discovery_track = 'TRACK_2_LINKEDIN');
                    """
                )
                c.execute(
                    """
                    UPDATE job_applications
                    SET application_mode = 'manual_takeover'
                    WHERE (LOWER(status) LIKE '%manual%' OR LOWER(source) LIKE '%manual%')
                    AND (application_mode IS NULL OR application_mode = 'batch_autofill');
                    """
                )
                c.commit()
            except Exception:
                pass

        if conn is not None:
            _run(conn)
        else:
            with self._get_connection() as new_conn:
                _run(new_conn)

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

    VALID_FUNNEL_STAGES = (
        "APPLIED",
        "ACKNOWLEDGED",
        "RECRUITER_SCREEN",
        "TECH_ASSESSMENT",
        "TECH_ROUND_1",
        "SYSTEM_DESIGN",
        "HIRING_MANAGER",
        "OFFER",
        "REJECTED",
        "GHOSTED",
    )

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
        discovery_track: str | None = None,
        discovery_channel: str | None = None,
        application_mode: str | None = None,
        funnel_stage: str = "APPLIED",
        recruiter_contact: str = "",
        notes: str = "",
    ) -> None:
        """Records an application event into the audit trail, initializes funnel stage, and updates daily quota."""
        tailored_payload = tailored_data if tailored_data is not None else {}
        tailored_json = tailored_payload if isinstance(tailored_payload, str) else json.dumps(tailored_payload)
        qa_json = screening_qa if isinstance(screening_qa, str) or screening_qa is None else json.dumps(screening_qa)

        # Automatically deduce discovery track & mode if not explicitly supplied
        norm_source = (source or "linkedin").lower().strip()
        if isinstance(discovery_track, dict):
            # Guard against callers passing the routing_strategy dict instead of a track string
            tier = str(discovery_track.get("routing_tier") or "")
            discovery_track = None if tier.startswith("TIER_") else (tier or None)

        global_remote_sources = (
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
        comp_low = (company_name or "").strip().lower()
        if not discovery_track or not isinstance(discovery_track, str):
            if norm_source in global_remote_sources or any(
                k in comp_low for k in ("mercor", "alignerr", "turing", "proxify", "toptal", "testgorilla")
            ):
                discovery_track = "TRACK_4_GLOBAL_REMOTE"
            elif norm_source in (
                "greenhouse",
                "lever",
                "ashby",
                "workday",
                "smartrecruiters",
                "hirist",
                "instahyre",
                "rippling",
                "workable",
                "recruitee",
                "amazon",
                "eightfold",
                "apple",
                "google",
                "comeet",
            ):
                discovery_track = "TRACK_1_DIRECT_ATS"
            elif norm_source in ("social_lead", "post", "linkedin_post"):
                discovery_track = "TRACK_3_SOCIAL_POST"
            elif "sniper" in norm_source:
                discovery_track = "PORTAL_SNIPER"
            else:
                discovery_track = "TRACK_2_LINKEDIN"

        if not discovery_channel or not isinstance(discovery_channel, str):
            discovery_channel = (
                norm_source
                if ("TRACK_1" in discovery_track or "TRACK_4" in discovery_track)
                else ("social_post" if "TRACK_3" in discovery_track else "search")
            )

        if not application_mode:
            if "manual" in status.lower():
                application_mode = "manual_takeover"
            elif "easy_apply" in norm_source:
                application_mode = "easy_apply"
            else:
                application_mode = "batch_autofill"

        stage = (funnel_stage or "APPLIED").upper().strip()
        if stage not in self.VALID_FUNNEL_STAGES:
            stage = "APPLIED"

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO job_applications (
                    id, source, company_name, job_title, job_url,
                    resume_path, tailored_data_json, screening_qa_json, status,
                    discovery_track, discovery_channel, application_mode, funnel_stage,
                    recruiter_contact, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    resume_path = excluded.resume_path,
                    tailored_data_json = excluded.tailored_data_json,
                    screening_qa_json = excluded.screening_qa_json,
                    discovery_track = COALESCE(job_applications.discovery_track, excluded.discovery_track),
                    discovery_channel = COALESCE(job_applications.discovery_channel, excluded.discovery_channel),
                    application_mode = COALESCE(job_applications.application_mode, excluded.application_mode),
                    funnel_stage = COALESCE(job_applications.funnel_stage, excluded.funnel_stage);
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
                    discovery_track,
                    discovery_channel,
                    application_mode,
                    stage,
                    recruiter_contact,
                    notes,
                ),
            )
            conn.commit()

        self.increment_today_submission_count()

    def update_funnel_stage(
        self,
        job_id: str,
        new_stage: str,
        notes: str | None = None,
        recruiter_contact: str | None = None,
    ) -> bool:
        """
        Updates the recruitment funnel lifecycle stage for an application.
        Valid stages: APPLIED, ACKNOWLEDGED, RECRUITER_SCREEN, TECH_ASSESSMENT,
        TECH_ROUND_1, SYSTEM_DESIGN, HIRING_MANAGER, OFFER, REJECTED, GHOSTED.
        """
        stage = (new_stage or "APPLIED").upper().strip()
        if stage not in self.VALID_FUNNEL_STAGES:
            stage = "APPLIED"

        updates = ["funnel_stage = ?", "last_stage_update = CURRENT_TIMESTAMP"]
        params: list[Any] = [stage]

        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        if recruiter_contact is not None:
            updates.append("recruiter_contact = ?")
            params.append(recruiter_contact)

        params.append(job_id)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE job_applications SET {', '.join(updates)} WHERE id = ?;",
                tuple(params),
            )
            conn.commit()
            return cursor.rowcount > 0

    INTERVIEW_STAGES = (
        "RECRUITER_SCREEN",
        "TECH_ASSESSMENT",
        "TECH_ROUND_1",
        "SYSTEM_DESIGN",
        "HIRING_MANAGER",
        "OFFER",
    )

    CANONICAL_SDET_TOPICS = (
        ("Playwright", r"\bplaywright\b"),
        ("Java", r"\bjava\b(?!\s*script)"),
        ("Python", r"\bpython\b|\bpytest\b"),
        ("TypeScript / JS", r"\btypescript\b|\bjavascript\b|\bnode\.?js\b"),
        ("API / REST Assured", r"\brest\s*assured\b|\bapi\s+automation\b|\bapi\s+testing\b|\bpostman\b|\bgraphql\b"),
        ("Selenium", r"\bselenium\b|\bwebdriver\b"),
        ("AI / LLM Evaluation", r"\bllm\b|\bgenai\b|\bai\s+qa\b|\bai\s+agent|\brag\b|\bred\s+team|\beval"),
        ("Docker / Kubernetes", r"\bdocker\b|\bkubernetes\b|\bk8s\b|\bhelm\b"),
        ("CI/CD (Jenkins/GHA)", r"\bjenkins\b|\bci/cd\b|\bgithub\s+actions\b|\bgitlab\b|\bharness\b"),
        ("Kafka / Distributed", r"\bkafka\b|\bmicroservices\b|\brabbitmq\b|\bevent[\s-]+driven\b"),
        ("Appium / Mobile", r"\bappium\b|\bmobile\s+automation\b|\bandroid\b|\bios\b"),
        ("Contract / WireMock", r"\bpact\b|\bwiremock\b|\bcontract\s+testing\b|\bmock"),
        ("SQL / Data QA", r"\bsql\b|\bpostgres|\bdatabase|\bsnowflake\b|\betl\b"),
        ("Performance / k6", r"\bjmeter\b|\bk6\b|\bgatling\b|\bperformance\s+testing\b|\bload\s+testing\b"),
    )

    @staticmethod
    def _parse_iso_utc(raw_ts: Any) -> datetime.datetime | None:
        if not raw_ts or not isinstance(raw_ts, str):
            return None
        clean = raw_ts.strip().replace("Z", "")
        try:
            dt = datetime.datetime.fromisoformat(clean)
            if dt.tzinfo is not None:
                dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            return None

    def _enrich_application_row(
        self,
        item: dict[str, Any],
        req_first_seen_map: dict[str, str] | None = None,
        dream_names: set[str] | None = None,
    ) -> dict[str, Any]:
        """Enriches an application row with posted_to_applied_hours, speed_bucket, topics, and dream/interview flags."""
        item["job_id"] = item.get("id")
        stage = (item.get("funnel_stage") or "APPLIED").upper().strip()
        item["funnel_stage"] = stage
        item["is_interviewed"] = stage in self.INTERVIEW_STAGES

        t_data: dict[str, Any] = {}
        raw_t = item.get("tailored_data_json")
        if raw_t and isinstance(raw_t, str):
            try:
                loaded = json.loads(raw_t)
                if isinstance(loaded, dict):
                    t_data = loaded
            except Exception:
                t_data = {}

        jd = t_data.get("job_details") if isinstance(t_data.get("job_details"), dict) else {}
        posted_raw = (
            t_data.get("posted_at")
            or jd.get("posted_at")
            or t_data.get("discovered_at")
            or (req_first_seen_map or {}).get(str(item.get("id") or ""))
        )
        applied_dt = self._parse_iso_utc(item.get("applied_at"))
        posted_dt = self._parse_iso_utc(posted_raw)

        hours_val: float | None = None
        if applied_dt and posted_dt:
            diff_h = (applied_dt - posted_dt).total_seconds() / 3600.0
            if -2.0 <= diff_h <= 720.0:
                hours_val = round(max(0.2, diff_h), 1)
        if hours_val is None and t_data.get("age_hours") is not None:
            try:
                hours_val = round(max(0.2, float(t_data["age_hours"])), 1)
            except Exception:
                hours_val = None
        if hours_val is None:
            ch = str(item.get("discovery_channel") or "").lower()
            tr = str(item.get("discovery_track") or "").upper()
            if ch in ("sniper_fresh_24h", "portal_sniper") or tr in ("PORTAL_SNIPER", "TRACK_4_GLOBAL_REMOTE"):
                hours_val = 4.5
            elif tr == "TRACK_1_DIRECT_ATS":
                hours_val = 14.0
            else:
                hours_val = 22.0

        item["posted_at"] = posted_raw or item.get("applied_at")
        item["posted_to_applied_hours"] = hours_val
        if hours_val <= 6.0:
            item["speed_bucket"] = "<6h"
            item["speed_label"] = f"⚡ {hours_val}h (<2% Early)"
        elif hours_val <= 24.0:
            item["speed_bucket"] = "6-24h"
            item["speed_label"] = f"🔥 {hours_val}h (<5% Sniper)"
        elif hours_val <= 72.0:
            item["speed_bucket"] = "24-72h"
            item["speed_label"] = f"🟢 {hours_val}h (<15% Optimal)"
        else:
            item["speed_bucket"] = ">72h"
            item["speed_label"] = f"🕒 {round(hours_val / 24.0, 1)}d"

        comp_low = str(item.get("company_name") or "").strip().lower()
        is_dream = bool(
            t_data.get("is_dream_org") or jd.get("is_dream_org") or (dream_names and comp_low in dream_names)
        )
        item["is_dream_org"] = is_dream

        # Extract canonical topics from job_title + notes + screening_qa + strictly tailored bullets (is_tailored=True)
        matched_kw = t_data.get("matched_keywords") if isinstance(t_data.get("matched_keywords"), list) else []
        tailored_bullets: list[str] = []
        for section in (t_data.get("experience_history") or []) + (t_data.get("projects") or []):
            if isinstance(section, dict):
                for diff_item in section.get("achievements_diff") or []:
                    if isinstance(diff_item, dict) and diff_item.get("is_tailored"):
                        tailored_bullets.append(str(diff_item.get("text") or ""))
        blob = " ".join(
            [
                str(item.get("job_title") or ""),
                str(item.get("notes") or ""),
                str(item.get("screening_qa_json") or ""),
                " ".join(str(k) for k in matched_kw),
                str(jd.get("requirements") or "")[:1200],
                " ".join(tailored_bullets),
            ]
        ).lower()
        topics: list[str] = []
        for topic_label, pattern in self.CANONICAL_SDET_TOPICS:
            if re.search(pattern, blob, re.IGNORECASE):
                topics.append(topic_label)
        item["extracted_topics"] = topics[:8]
        return item

    @staticmethod
    def _parse_iso_utc(raw_ts: Any) -> datetime.datetime | None:
        if not raw_ts or not isinstance(raw_ts, str):
            return None
        clean = raw_ts.strip().replace("Z", "")
        try:
            dt = datetime.datetime.fromisoformat(clean)
            if dt.tzinfo is not None:
                dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            return None

    def _enrich_application_row(
        self,
        item: dict[str, Any],
        req_first_seen_map: dict[str, str] | None = None,
        dream_names: set[str] | None = None,
    ) -> dict[str, Any]:
        """Enriches an application row with posted_to_applied_hours, speed_bucket, topics, and dream/interview flags."""
        item["job_id"] = item.get("id")
        stage = (item.get("funnel_stage") or "APPLIED").upper().strip()
        item["funnel_stage"] = stage
        item["is_interviewed"] = stage in self.INTERVIEW_STAGES

        t_data: dict[str, Any] = {}
        raw_t = item.get("tailored_data_json")
        if raw_t and isinstance(raw_t, str):
            try:
                loaded = json.loads(raw_t)
                if isinstance(loaded, dict):
                    t_data = loaded
            except Exception:
                t_data = {}

        jd = t_data.get("job_details") if isinstance(t_data.get("job_details"), dict) else {}
        posted_raw = (
            t_data.get("posted_at")
            or jd.get("posted_at")
            or t_data.get("discovered_at")
            or (req_first_seen_map or {}).get(str(item.get("id") or ""))
        )
        applied_dt = self._parse_iso_utc(item.get("applied_at"))
        posted_dt = self._parse_iso_utc(posted_raw)

        hours_val: float | None = None
        if applied_dt and posted_dt:
            diff_h = (applied_dt - posted_dt).total_seconds() / 3600.0
            if -2.0 <= diff_h <= 720.0:
                hours_val = round(max(0.2, diff_h), 1)
        if hours_val is None and t_data.get("age_hours") is not None:
            try:
                hours_val = round(max(0.2, float(t_data["age_hours"])), 1)
            except Exception:
                hours_val = None
        if hours_val is None:
            ch = str(item.get("discovery_channel") or "").lower()
            tr = str(item.get("discovery_track") or "").upper()
            if ch in ("sniper_fresh_24h", "portal_sniper") or tr in ("PORTAL_SNIPER", "TRACK_4_GLOBAL_REMOTE"):
                hours_val = 4.5
            elif tr == "TRACK_1_DIRECT_ATS":
                hours_val = 14.0
            else:
                hours_val = 22.0

        item["posted_at"] = posted_raw or item.get("applied_at")
        item["posted_to_applied_hours"] = hours_val
        if hours_val <= 6.0:
            item["speed_bucket"] = "<6h"
            item["speed_label"] = f"⚡ {hours_val}h (<2% Early)"
        elif hours_val <= 24.0:
            item["speed_bucket"] = "6-24h"
            item["speed_label"] = f"🔥 {hours_val}h (<5% Sniper)"
        elif hours_val <= 72.0:
            item["speed_bucket"] = "24-72h"
            item["speed_label"] = f"🟢 {hours_val}h (<15% Optimal)"
        else:
            item["speed_bucket"] = ">72h"
            item["speed_label"] = f"🕒 {round(hours_val / 24.0, 1)}d"

        comp_low = str(item.get("company_name") or "").strip().lower()
        is_dream = bool(
            t_data.get("is_dream_org") or jd.get("is_dream_org") or (dream_names and comp_low in dream_names)
        )
        item["is_dream_org"] = is_dream

        # Extract canonical topics from job_title + notes + screening_qa + strictly tailored bullets (is_tailored=True)
        matched_kw = t_data.get("matched_keywords") if isinstance(t_data.get("matched_keywords"), list) else []
        tailored_bullets: list[str] = []
        for section in (t_data.get("experience_history") or []) + (t_data.get("projects") or []):
            if isinstance(section, dict):
                for diff_item in section.get("achievements_diff") or []:
                    if isinstance(diff_item, dict) and diff_item.get("is_tailored"):
                        tailored_bullets.append(str(diff_item.get("text") or ""))
        blob = " ".join(
            [
                str(item.get("job_title") or ""),
                str(item.get("notes") or ""),
                str(item.get("screening_qa_json") or ""),
                " ".join(str(k) for k in matched_kw),
                str(jd.get("requirements") or "")[:1200],
                " ".join(tailored_bullets),
            ]
        ).lower()
        topics: list[str] = []
        for topic_label, pattern in self.CANONICAL_SDET_TOPICS:
            if re.search(pattern, blob, re.IGNORECASE):
                topics.append(topic_label)
        item["extracted_topics"] = topics[:8]
        return item

    def get_funnel_metrics(self) -> dict[str, Any]:
        """
        Calculates conversion funnel metrics & full inference telemetry:
        - Stage counts (Applied, Screens, Tech Rounds, Offers, Rejections)
        - Track & Source Interview Turnover rates (%)
        - Posted vs. Applied Speed Latency (<6h, 6-24h, 24-72h, >72h) & <5% early applicant share
        - Most sought-out SDET / AI-QA topics across all applied & interviewed orgs
        - Application frequency, portfolio value mix, and actionable strategic inferences
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total FROM job_applications;")
            total_apps = cursor.fetchone()["total"] or 0

            cursor.execute(
                "SELECT COALESCE(funnel_stage, 'APPLIED') AS stage, COUNT(*) AS cnt FROM job_applications GROUP BY stage;"
            )
            stage_counts = {row["stage"]: row["cnt"] for row in cursor.fetchall()}

            cursor.execute(
                "SELECT COALESCE(discovery_track, 'TRACK_2_LINKEDIN') AS track, COUNT(*) AS cnt FROM job_applications GROUP BY track;"
            )
            track_counts = {row["track"]: row["cnt"] for row in cursor.fetchall()}

            cursor.execute(
                "SELECT COALESCE(discovery_channel, 'search') AS channel, COUNT(*) AS cnt FROM job_applications GROUP BY channel;"
            )
            channel_counts = {row["channel"]: row["cnt"] for row in cursor.fetchall()}

            cursor.execute(
                "SELECT COALESCE(application_mode, 'batch_autofill') AS mode, COUNT(*) AS cnt FROM job_applications GROUP BY mode;"
            )
            mode_counts = {row["mode"]: row["cnt"] for row in cursor.fetchall()}

            cursor.execute("SELECT requisition_id, first_seen_at FROM tracked_requisitions;")
            req_map = {str(r["requisition_id"]): str(r["first_seen_at"] or "") for r in cursor.fetchall()}

            cursor.execute("SELECT * FROM job_applications ORDER BY applied_at DESC;")
            raw_rows = [dict(r) for r in cursor.fetchall()]

        dream_names: set[str] = set()
        cfg_path = os.path.join(PROJECT_ROOT, "data", "config", "target_companies.json")
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    for c in json.load(f):
                        if c.get("is_dream_org"):
                            dream_names.add(str(c.get("name", "")).strip().lower())
                            dream_names.add(str(c.get("slug", "")).strip().lower())
            except Exception:
                pass

        enriched_rows = [self._enrich_application_row(r, req_map, dream_names) for r in raw_rows]

        screens = sum(stage_counts.get(s, 0) for s in self.INTERVIEW_STAGES)
        screen_rate = round((screens / total_apps * 100), 1) if total_apps > 0 else 0.0
        offers = stage_counts.get("OFFER", 0)
        offer_rate = round((offers / total_apps * 100), 1) if total_apps > 0 else 0.0

        # 1. Interview Turnover & Interviewed Orgs
        interviewed_orgs = []
        by_track: dict[str, dict[str, Any]] = {}
        by_source: dict[str, dict[str, Any]] = {}
        dream_stats = {"dream_org": {"applied": 0, "interviewed": 0}, "standard": {"applied": 0, "interviewed": 0}}

        # 2. Speed Latency Buckets (<6h, 6-24h, 24-72h, >72h)
        speed_buckets: dict[str, dict[str, Any]] = {
            "<6h": {"label": "⚡ <6h (Top <2% Early)", "applied": 0, "interviewed": 0, "turnover_pct": 0.0},
            "6-24h": {"label": "🔥 6h–24h (Top <5% Sniper)", "applied": 0, "interviewed": 0, "turnover_pct": 0.0},
            "24-72h": {"label": "🟢 24h–72h (Optimal <15%)", "applied": 0, "interviewed": 0, "turnover_pct": 0.0},
            ">72h": {"label": "🕒 >72h (Standard)", "applied": 0, "interviewed": 0, "turnover_pct": 0.0},
        }
        all_hours: list[float] = []

        # 3. Topics & Company Frequency
        topic_counts: dict[str, dict[str, Any]] = {}
        company_Rollup: dict[str, dict[str, Any]] = {}
        daily_map: dict[str, int] = {}
        ai_qa_count = 0

        for row in enriched_rows:
            is_int = bool(row.get("is_interviewed"))
            trk = str(row.get("discovery_track") or "TRACK_2_LINKEDIN")
            src = str(row.get("source") or "linkedin").lower()
            comp = str(row.get("company_name") or "Unknown").strip()
            title = str(row.get("job_title") or "").strip()
            hrs = float(row.get("posted_to_applied_hours") or 22.0)
            sbucket = str(row.get("speed_bucket") or "6-24h")
            is_drm = bool(row.get("is_dream_org"))

            all_hours.append(hrs)
            if sbucket in speed_buckets:
                speed_buckets[sbucket]["applied"] += 1
                if is_int:
                    speed_buckets[sbucket]["interviewed"] += 1

            by_track.setdefault(trk, {"applied": 0, "interviewed": 0, "turnover_pct": 0.0})
            by_track[trk]["applied"] += 1
            if is_int:
                by_track[trk]["interviewed"] += 1

            by_source.setdefault(src, {"applied": 0, "interviewed": 0, "turnover_pct": 0.0})
            by_source[src]["applied"] += 1
            if is_int:
                by_source[src]["interviewed"] += 1

            d_key = "dream_org" if is_drm else "standard"
            dream_stats[d_key]["applied"] += 1
            if is_int:
                dream_stats[d_key]["interviewed"] += 1

            if is_int:
                interviewed_orgs.append(
                    {
                        "job_id": row.get("job_id"),
                        "company_name": comp,
                        "job_title": title,
                        "funnel_stage": row.get("funnel_stage"),
                        "source": src,
                        "discovery_track": trk,
                        "notes": row.get("notes") or "",
                        "recruiter_contact": row.get("recruiter_contact") or "",
                        "applied_at": row.get("applied_at"),
                        "posted_to_applied_hours": hrs,
                        "topics": row.get("extracted_topics", []),
                    }
                )

            topics_for_row = row.get("extracted_topics") or []
            if "AI / LLM Evaluation" in topics_for_row or re.search(r"\b(ai|llm|genai|agent)\b", title, re.IGNORECASE):
                ai_qa_count += 1
            for t_name in topics_for_row:
                entry = topic_counts.setdefault(t_name, {"topic": t_name, "count": 0, "interview_count": 0, "pct": 0.0})
                entry["count"] += 1
                if is_int:
                    entry["interview_count"] += 1

            c_entry = company_Rollup.setdefault(
                comp,
                {
                    "company": comp,
                    "count": 0,
                    "interviewed": 0,
                    "is_dream_org": is_drm,
                    "latest_stage": row.get("funnel_stage"),
                },
            )
            c_entry["count"] += 1
            if is_int:
                c_entry["interviewed"] += 1
                c_entry["latest_stage"] = row.get("funnel_stage")

            app_date = str(row.get("applied_at") or "")[:10]
            if app_date and len(app_date) == 10:
                daily_map[app_date] = daily_map.get(app_date, 0) + 1

        for d in (
            list(by_track.values())
            + list(by_source.values())
            + list(speed_buckets.values())
            + list(dream_stats.values())
        ):
            app_c = d.get("applied", 0)
            int_c = d.get("interviewed", 0)
            d["count"] = app_c
            d["pct_of_measured"] = round(app_c / total_apps * 100.0, 1) if total_apps > 0 else 0.0
            d["turnover_pct"] = round(int_c / app_c * 100.0, 1) if app_c > 0 else 0.0

        dream_stats["dream"] = dream_stats["dream_org"]

        for t_entry in topic_counts.values():
            pct_val = round(t_entry["count"] / total_apps * 100.0, 1) if total_apps > 0 else 0.0
            t_entry["pct"] = pct_val
            t_entry["pct_of_apps"] = pct_val

        sorted_topics = sorted(
            topic_counts.values(),
            key=lambda x: x["interview_count"] * 3 + x["count"],
            reverse=True,
        )[:12]

        sorted_companies = sorted(
            company_Rollup.values(),
            key=lambda x: (x["interviewed"], x["count"], x["is_dream_org"]),
            reverse=True,
        )[:15]

        sorted_hours = sorted(all_hours)
        median_hours = sorted_hours[len(sorted_hours) // 2] if sorted_hours else 0.0
        avg_hours = round(sum(all_hours) / len(all_hours), 1) if all_hours else 0.0
        under_24h_cnt = speed_buckets["<6h"]["applied"] + speed_buckets["6-24h"]["applied"]
        under_24h_pct = round(under_24h_cnt / total_apps * 100.0, 1) if total_apps > 0 else 0.0

        daily_velocity = [
            {"date": dt, "count": cnt} for dt, cnt in sorted(daily_map.items(), key=lambda x: x[0], reverse=True)[:10]
        ]
        dream_total = dream_stats["dream_org"]["applied"]
        dream_pct = round(dream_total / total_apps * 100.0, 1) if total_apps > 0 else 0.0
        ai_qa_pct = round(ai_qa_count / total_apps * 100.0, 1) if total_apps > 0 else 0.0
        direct_ats_cnt = by_track.get("TRACK_1_DIRECT_ATS", {}).get("applied", 0) + by_track.get(
            "PORTAL_SNIPER", {}
        ).get("applied", 0)
        direct_ats_pct = round(direct_ats_cnt / total_apps * 100.0, 1) if total_apps > 0 else 0.0
        global_remote_cnt = by_track.get("TRACK_4_GLOBAL_REMOTE", {}).get("applied", 0)
        global_remote_pct = round(global_remote_cnt / total_apps * 100.0, 1) if total_apps > 0 else 0.0

        top_3_topics = [t["topic"] for t in sorted_topics[:3]] or ["Playwright", "Java", "API / REST Assured"]
        best_track = (
            max(by_track.items(), key=lambda kv: (kv[1]["turnover_pct"], kv[1]["applied"]))[0]
            if by_track
            else "TRACK_1_DIRECT_ATS"
        )

        inferences = [
            f"⚡ Speed Advantage (<5% Applicant Pool): {under_24h_pct}% ({under_24h_cnt}/{total_apps}) of your applications were submitted within <24h of posting (median latency: {median_hours}h).",
            f"🎯 Channel ROI & Turnover: {best_track.replace('_', ' ')} leads your portfolio volume; Direct Enterprise ATS & Sniper roles account for {direct_ats_pct}% of all submissions.",
            f"🔥 Most Sought-Out Technical Topics: {', '.join(top_3_topics)} appear in the highest share of your applied & interviewed SDET requisitions — prioritize these in mock rounds.",
            f"⭐ Portfolio Quality Mix: {dream_pct}% ({dream_total} roles) target Tier-1 Dream Orgs / GCCs and {ai_qa_pct}% ({ai_qa_count} roles) feature AI / LLM QA & Agentic Automation mandates.",
        ]

        return {
            "total_applications": total_apps,
            "stages": stage_counts,
            "tracks": track_counts,
            "channels": channel_counts,
            "application_modes": mode_counts,
            "total_interviews_or_screens": screens,
            "application_to_screen_rate_pct": screen_rate,
            "offers": offers,
            "offer_rate_pct": offer_rate,
            "interview_turnover": {
                "interviewed_orgs": interviewed_orgs,
                "by_track": by_track,
                "by_source": by_source,
                "dream_vs_standard": dream_stats,
            },
            "speed_analytics": {
                "buckets": speed_buckets,
                "under_24h_count": under_24h_cnt,
                "under_24h_pct": under_24h_pct,
                "median_hours": median_hours,
                "avg_hours": avg_hours,
            },
            "topic_analytics": {
                "top_topics": sorted_topics,
            },
            "value_and_frequency": {
                "daily_velocity": daily_velocity,
                "top_companies": sorted_companies,
                "portfolio_value": {
                    "dream_org_count": dream_total,
                    "dream_org_pct": dream_pct,
                    "ai_qa_count": ai_qa_count,
                    "ai_qa_pct": ai_qa_pct,
                    "ai_role_count": ai_qa_count,
                    "ai_role_pct": ai_qa_pct,
                    "direct_ats_count": direct_ats_cnt,
                    "direct_ats_pct": direct_ats_pct,
                    "global_remote_count": global_remote_cnt,
                    "global_remote_pct": global_remote_pct,
                },
                "inferences": inferences,
            },
        }

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

    def get_applied_job_details(
        self,
        job_id: str,
        company_name: str = "",
        job_title: str = "",
    ) -> dict[str, Any] | None:
        """
        Returns metadata for the most recent applied record matching either `job_id` or
        `(company_name, job_title)`, including `days_since_applied` and `is_exact_id_match`.
        """
        clean_id = (job_id or "").strip()
        clean_company = (company_name or "").strip().lower()
        clean_title = (job_title or "").strip().lower()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            row = None
            if clean_id:
                cursor.execute(
                    """
                    SELECT id, source, company_name, job_title, job_url, applied_at
                    FROM job_applications
                    WHERE id = ? AND status = 'applied'
                    ORDER BY applied_at DESC
                    LIMIT 1;
                    """,
                    (clean_id,),
                )
                row = cursor.fetchone()
            if row is None and clean_company and clean_title:
                cursor.execute(
                    """
                    SELECT id, source, company_name, job_title, job_url, applied_at
                    FROM job_applications
                    WHERE LOWER(TRIM(company_name)) = ?
                      AND LOWER(TRIM(job_title)) = ?
                      AND status = 'applied'
                    ORDER BY applied_at DESC
                    LIMIT 1;
                    """,
                    (clean_company, clean_title),
                )
                row = cursor.fetchone()

        if not row:
            return None

        applied_at_raw = str(row["applied_at"] or "").strip()
        days_since = 0.0
        if applied_at_raw:
            try:
                norm_ts = applied_at_raw.replace("Z", "")
                applied_dt = datetime.datetime.fromisoformat(norm_ts)
                if applied_dt.tzinfo is not None:
                    applied_dt = applied_dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                delta_sec = (datetime.datetime.utcnow() - applied_dt).total_seconds()
                days_since = max(0.0, round(delta_sec / 86400.0, 2))
            except Exception:
                days_since = 0.0

        return {
            "id": str(row["id"]),
            "source": str(row["source"] or ""),
            "company_name": str(row["company_name"] or ""),
            "job_title": str(row["job_title"] or ""),
            "job_url": str(row["job_url"] or ""),
            "applied_at": applied_at_raw,
            "days_since_applied": days_since,
            "is_exact_id_match": bool(clean_id and str(row["id"]) == clean_id),
        }

    def is_reapply_eligible(
        self,
        job_id: str,
        company_name: str = "",
        job_title: str = "",
        min_days: float = 30.0,
    ) -> bool:
        """
        Determines whether a previously applied role is eligible for a fresh re-application:
        - Returns True if never applied.
        - Returns False if it is the exact same LinkedIn job ID (LinkedIn locks same jobId forever).
        - Returns True if `days_since_applied >= min_days` (default 30 days) on a new requisition ID
          or direct ATS portal.
        """
        details = self.get_applied_job_details(job_id, company_name, job_title)
        if details is None:
            return True
        if details["is_exact_id_match"] and "linkedin" in details["source"].lower():
            return False
        return float(details["days_since_applied"]) >= min_days

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
        """Retrieves all application records ordered by applied_at DESC for tracking, enriched with latency and topics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT requisition_id, first_seen_at FROM tracked_requisitions;")
            req_map = {str(r["requisition_id"]): str(r["first_seen_at"] or "") for r in cursor.fetchall()}

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

        dream_names: set[str] = set()
        cfg_path = os.path.join(PROJECT_ROOT, "data", "config", "target_companies.json")
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    for c in json.load(f):
                        if c.get("is_dream_org"):
                            dream_names.add(str(c.get("name", "")).strip().lower())
                            dream_names.add(str(c.get("slug", "")).strip().lower())
            except Exception:
                pass

        return [self._enrich_application_row(dict(row), req_map, dream_names) for row in rows]

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
                "funnel": self.get_funnel_metrics(),
            }

    def delete_application(self, job_id: str) -> bool:
        """Deletes an application record by job_id and cleans up processed_jobs.json & daily_submission_limits."""
        comp_name = ""
        title_name = ""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT company_name, job_title FROM job_applications WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if row:
                comp_name = (row["company_name"] or "").strip()
                title_name = (row["job_title"] or "").strip()
            cursor.execute("DELETE FROM job_applications WHERE id = ?", (job_id,))
            deleted = cursor.rowcount > 0
            if deleted and os.path.abspath(self.db_path) == os.path.abspath(DEFAULT_DB_PATH):
                bucket = self._get_today_bucket()
                cursor.execute(
                    "SELECT COUNT(*) AS cnt FROM job_applications WHERE DATE(applied_at) = ?",
                    (bucket,),
                )
                cnt = int(cursor.fetchone()["cnt"])
                cursor.execute(
                    "UPDATE daily_submission_limits SET submission_count = ? WHERE date_bucket = ?",
                    (cnt, bucket),
                )
            conn.commit()

        if deleted and os.path.abspath(self.db_path) == os.path.abspath(DEFAULT_DB_PATH):
            proc_path = os.path.join(PROJECT_ROOT, "data", "processed_jobs.json")
            if os.path.exists(proc_path):
                try:
                    with open(proc_path, "r", encoding="utf-8") as f:
                        proc_data = json.load(f)
                    modified = False
                    job_ids_map = proc_data.get("job_ids", {})
                    if job_id in job_ids_map:
                        del job_ids_map[job_id]
                        modified = True
                    if comp_name and title_name:
                        norm = f"{comp_name.lower()}_{title_name.lower()}"
                        c_hash = hashlib.md5(norm.encode("utf-8")).hexdigest()
                        comp_hashes = proc_data.get("composite_hashes", {})
                        if c_hash in comp_hashes:
                            del comp_hashes[c_hash]
                            modified = True
                    if modified:
                        with open(proc_path, "w", encoding="utf-8") as f:
                            json.dump(proc_data, f, indent=2)
                except Exception:
                    pass
        return deleted

    def prune_synthetic_and_polluted_records(self) -> dict[str, int]:
        """
        Surgically purges synthetic test records, early non-SDET/intern filter leaks,
        polluted Hirist title-as-company requisitions, and synthetic processed_jobs.json keys
        while preserving all authentic SDET applications.
        """
        summary = {
            "deleted_applications": 0,
            "deleted_requisitions": 0,
            "resynced_limit_buckets": 0,
            "pruned_processed_ids": 0,
            "pruned_composite_hashes": 0,
        }
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM job_applications
                WHERE id LIKE 'mark_endpoint_test_%'
                   OR id LIKE 'test_%'
                   OR id LIKE 'scraper_guard_%'
                   OR id LIKE 'purge_test_%'
                   OR id LIKE 'GATE60_%'
                   OR id IN (
                       'TEST-GATE60-CONFIRM',
                       'p1_job_3',
                       'p1_job_6',
                       'postman_frontend_sdet',
                       'greenhouse_coinbase_8031208',
                       'greenhouse_instacart_8077510',
                       'greenhouse_scopely_5448999008',
                       '4467845446'
                   );
                """
            )
            summary["deleted_applications"] = cursor.rowcount

            cursor.execute(
                """
                DELETE FROM tracked_requisitions
                WHERE ats_provider = 'hirist'
                  AND company_slug IN (
                      'ai_test_architect',
                      'qa_engineer',
                      'quality_assurance_automation_engineer',
                      'quality_assurance_automation_tester',
                      'hirist_enterprise'
                  );
                """
            )
            summary["deleted_requisitions"] = cursor.rowcount

            # Resync daily_submission_limits to authentic application counts per date_bucket
            cursor.execute("SELECT date_bucket FROM daily_submission_limits;")
            buckets = [r["date_bucket"] for r in cursor.fetchall()]
            for b in buckets:
                cursor.execute(
                    "SELECT COUNT(*) AS cnt FROM job_applications WHERE DATE(applied_at) = ?",
                    (b,),
                )
                true_cnt = int(cursor.fetchone()["cnt"])
                cursor.execute(
                    "UPDATE daily_submission_limits SET submission_count = ? WHERE date_bucket = ?",
                    (true_cnt, b),
                )
                summary["resynced_limit_buckets"] += 1

            conn.commit()

        proc_path = os.path.join(PROJECT_ROOT, "data", "processed_jobs.json")
        if os.path.exists(proc_path) and os.path.abspath(self.db_path) == os.path.abspath(DEFAULT_DB_PATH):
            try:
                with open(proc_path, "r", encoding="utf-8") as f:
                    proc_data = json.load(f)
                job_ids = proc_data.get("job_ids", {})
                synthetic_prefixes = (
                    "mark_endpoint_test_",
                    "test_",
                    "scraper_guard_",
                    "purge_test_",
                    "GATE60_",
                    "TEST-GATE60",
                    "p1_job_",
                )
                synthetic_exact = {
                    "postman_frontend_sdet",
                    "greenhouse_coinbase_8031208",
                    "greenhouse_instacart_8077510",
                    "greenhouse_scopely_5448999008",
                    "4467845446",
                    "hirist_1682386",
                }
                keys_to_drop = [k for k in job_ids if k.startswith(synthetic_prefixes) or k in synthetic_exact]
                for k in keys_to_drop:
                    del job_ids[k]
                summary["pruned_processed_ids"] = len(keys_to_drop)

                comp_hashes = proc_data.get("composite_hashes", {})
                synthetic_company_tokens = (
                    "tracking metrics corp_",
                    "triggertest technologies_",
                    "defense corp_",
                    "autopurge inc_",
                    "unit test tech_",
                    "swiggy test_",
                    "ai test architect_",
                )
                hashes_to_drop = [
                    h
                    for h, meta in comp_hashes.items()
                    if isinstance(meta, dict)
                    and str(meta.get("normalized", "")).lower().startswith(synthetic_company_tokens)
                ]
                for h in hashes_to_drop:
                    del comp_hashes[h]
                summary["pruned_composite_hashes"] = len(hashes_to_drop)

                with open(proc_path, "w", encoding="utf-8") as f:
                    json.dump(proc_data, f, indent=2)
            except Exception:
                pass

        return summary

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
        outreach_id = f"ref_{job_id}_{hashlib.md5(f'{outreach_type}:{contact_linkedin_url or contact_name}:{datetime.datetime.utcnow()}'.encode()).hexdigest()[:8]}"
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
        """Saves or updates a discovered hiring / referral post with content deduplication."""
        post_id = post_data.get("post_id")
        if not post_id:
            return False

        content_hash = post_data.get("content_hash") or ""
        if not content_hash:
            norm_text = re.sub(r"\s+", " ", (post_data.get("post_text") or "").lower()).strip()
            content_hash = hashlib.sha256(norm_text.encode("utf-8")).hexdigest()[:16]

        emails = json.dumps(post_data.get("extracted_emails", []))
        links = json.dumps(post_data.get("extracted_links", []))
        job_codes = json.dumps(post_data.get("extracted_job_codes", []))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # If a post with identical content_hash already exists under a different post_id, skip saving
            if content_hash:
                cursor.execute(
                    "SELECT 1 FROM hiring_posts WHERE content_hash = ? AND post_id != ? LIMIT 1",
                    (content_hash, post_id),
                )
                if cursor.fetchone():
                    return False

            cursor.execute(
                """
                INSERT INTO hiring_posts (
                    post_id, content_hash, author_name, author_headline, author_profile_url,
                    company_name, is_dream_org, post_url, post_text,
                    posted_at_relative, extracted_emails, extracted_links,
                    extracted_job_codes, quality_score, author_role_category,
                    outreach_status, custom_dm_draft, custom_inmail_draft, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(post_id) DO UPDATE SET
                    content_hash = excluded.content_hash,
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
                    content_hash,
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

    def is_hiring_post_saved(self, post_id: str, content_hash: str | None = None) -> bool:
        """Checks if a hiring post has already been discovered and saved by post_id or content_hash."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if content_hash:
                cursor.execute(
                    "SELECT 1 FROM hiring_posts WHERE post_id = ? OR (content_hash = ? AND content_hash != '') LIMIT 1",
                    (post_id, content_hash),
                )
            else:
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
            # Ensure content_hash column exists
            try:
                active_conn.execute("ALTER TABLE hiring_posts ADD COLUMN content_hash TEXT;")
                active_conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_hiring_posts_content_hash ON hiring_posts(content_hash);"
                )
            except Exception:
                pass

            cursor = active_conn.cursor()
            cursor.execute("SELECT * FROM hiring_posts")
            rows = cursor.fetchall()
            updated_count = 0
            seen_content_hashes: set[str] = set()

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
                    # Purge job seeker, non-SDET CAD, overseas W2, or disclaimer post that slipped in
                    cursor.execute("DELETE FROM hiring_posts WHERE post_id = ?", (post_id,))
                    updated_count += 1
                    continue

                # Purge stale (>72h) uncontacted posts (e.g. 4d-9d, 1w+, 1mo+, or discovered >3 days ago)
                outreach_st = (r["outreach_status"] or "NEW").upper()
                rel_t = (r["posted_at_relative"] or "").strip().lower()
                if outreach_st in ("NEW", "UNCONTACTED"):
                    from src.posts.post_tracker import LinkedInPostTracker

                    if (
                        rel_t
                        and rel_t != "recent"
                        and not LinkedInPostTracker.is_post_within_age_limit(rel_t, "past-72h")
                    ):
                        cursor.execute("DELETE FROM hiring_posts WHERE post_id = ?", (post_id,))
                        updated_count += 1
                        continue
                    disc_raw = str(r["discovered_at"] or "").strip()
                    if disc_raw:
                        try:
                            disc_dt = datetime.datetime.fromisoformat(disc_raw.replace("Z", ""))
                            if (datetime.datetime.utcnow() - disc_dt).total_seconds() > 3 * 86400:
                                cursor.execute("DELETE FROM hiring_posts WHERE post_id = ?", (post_id,))
                                updated_count += 1
                                continue
                        except Exception:
                            pass

                # Purge stale (>72h) uncontacted posts (e.g. 4d-9d, 1w+, 1mo+, or discovered >3 days ago)
                outreach_st = (r["outreach_status"] or "NEW").upper()
                rel_t = (r["posted_at_relative"] or "").strip().lower()
                if outreach_st in ("NEW", "UNCONTACTED"):
                    from src.posts.post_tracker import LinkedInPostTracker

                    if (
                        rel_t
                        and rel_t != "recent"
                        and not LinkedInPostTracker.is_post_within_age_limit(rel_t, "past-72h")
                    ):
                        cursor.execute("DELETE FROM hiring_posts WHERE post_id = ?", (post_id,))
                        updated_count += 1
                        continue
                    disc_raw = str(r["discovered_at"] or "").strip()
                    if disc_raw:
                        try:
                            disc_dt = datetime.datetime.fromisoformat(disc_raw.replace("Z", ""))
                            if (datetime.datetime.utcnow() - disc_dt).total_seconds() > 3 * 86400:
                                cursor.execute("DELETE FROM hiring_posts WHERE post_id = ?", (post_id,))
                                updated_count += 1
                                continue
                        except Exception:
                            pass

                norm_text = re.sub(r"\s+", " ", clean_text.lower()).strip()
                c_hash = hashlib.sha256(norm_text.encode("utf-8")).hexdigest()[:16]

                if c_hash in seen_content_hashes:
                    # Duplicate post from syndicated agency bot account
                    cursor.execute("DELETE FROM hiring_posts WHERE post_id = ?", (post_id,))
                    updated_count += 1
                    continue
                seen_content_hashes.add(c_hash)

                # Clean links
                clean_links = classifier.extract_links(clean_text, additional_links=raw_links)
                # Re-extract company and dream flag
                company, is_dream = classifier.extract_company_name(headline, clean_text)
                role_cat = r["author_role_category"] or classifier.classify_author_role(headline, clean_text)
                emails = _safe_json_list(r["extracted_emails"])
                job_codes = _safe_json_list(r["extracted_job_codes"])
                posted_time = r["posted_at_relative"] or "recent"

                score = classifier.compute_quality_score(
                    is_dream, emails, clean_links, job_codes, posted_time, role_cat, post_text=clean_text
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
                        content_hash = ?,
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
                        c_hash,
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
