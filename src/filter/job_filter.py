from __future__ import annotations

import json
import os
import re
from typing import Any


class LinkedInJobFilter:
    def __init__(self, queue_dir: str = "data/pending_queue", db_file: str = "data/processed_jobs.json"):
        self.queue_dir = queue_dir
        self.db_file = db_file
        self.min_exp_years = 4
        self.max_exp_years = 10
        self.candidate_exp_years = 6.8  # Senior SDET candidate profile baseline

    def parse_required_years(self, text: str) -> list[int]:
        """
        Extracts experience year requirements (e.g., '5+ years experience', '8 years in SDET') using regex with context guards.
        Ignores false positives like '20+ years in business' or '15+ locations'.
        """
        context_keywords = [
            "exp",
            "experience",
            "testing",
            "sdet",
            "automation",
            "background",
            "working",
            "quality",
            "qa",
            "relevant",
            "required",
            "preferred",
            "qualification",
        ]
        years = []
        for m in re.finditer(r"(\d+)\+?\s*(?:-\s*\d+)?\s*years?", text, re.IGNORECASE):
            val_str = m.group(1)
            start_idx = max(0, m.start() - 40)
            end_idx = min(len(text), m.end() + 40)
            snippet = text[start_idx:end_idx].lower()

            if any(kw in snippet for kw in context_keywords):
                try:
                    val = int(val_str)
                    if 0 < val < 30:  # Sanity bound
                        years.append(val)
                except ValueError:
                    pass
        return years

    def update_processed_jobs_status(self, status_map: dict[str, str]):
        """Updates status field for job_ids in data/processed_jobs.json."""
        if not os.path.exists(self.db_file):
            return
        try:
            with open(self.db_file, "r") as f:
                data = json.load(f)
            job_ids = data.get("job_ids", {})
            updated = False
            for jid, new_status in status_map.items():
                if jid in job_ids:
                    job_ids[jid]["status"] = new_status
                    updated = True
            if updated:
                with open(self.db_file, "w") as f:
                    json.dump(data, f, indent=2)
                print(f"🔄 Synchronized {len(status_map)} status update(s) to {self.db_file}")
        except Exception as e:
            print(f"⚠️ Error updating processed_jobs.json status: {e}")

    def filter_pending_queue(self) -> dict[str, Any]:
        """
        Scans data/pending_queue/, evaluates experience, Easy Apply, and role alignment,
        removes unqualified jobs from queue, and updates processed_jobs.json status.
        """
        if not os.path.exists(self.queue_dir):
            print(f"⚠️ Pending queue directory {self.queue_dir} does not exist.")
            return {"retained": 0, "filtered": 0, "details": []}

        json_files = [f for f in os.listdir(self.queue_dir) if f.endswith(".json")]
        print("\n" + "=" * 50)
        print("  RUNNING STANDALONE JOB FILTER MODULE (filterjobs)")
        print(f"  Evaluating {len(json_files)} job(s) in {self.queue_dir}...")
        print("=" * 50)

        from src.storage.database import ApplicationDatabase

        applied_ids = ApplicationDatabase().get_applied_job_ids()

        retained = []
        filtered = []
        status_updates = {}

        for fname in json_files:
            filepath = os.path.join(self.queue_dir, fname)
            try:
                with open(filepath, "r") as f:
                    payload = json.load(f)
            except Exception as e:
                print(f"⚠️ Error reading {fname}: {e}")
                continue

            job_id = payload.get("job_id", fname.replace(".json", ""))
            details = payload.get("job_details", {})
            title = details.get("title", "")
            company = details.get("company", "")
            requirements = details.get("requirements", "")
            app_type = payload.get("application_type", "EASY_APPLY")

            rejection_reason = None

            # 0. Database Applied Filter
            if job_id in applied_ids:
                rejection_reason = "Already marked as APPLIED in application database"

            # 1. Easy Apply Filter
            elif app_type != "EASY_APPLY":
                rejection_reason = "Missing Easy Apply flag"

            # 2. Role Title Keyword Alignment
            title_lower = title.lower()
            valid_role_keywords = [
                "sdet",
                "qa",
                "automation",
                "test",
                "quality",
                "software",
                "engineer",
                "lead",
                "staff",
            ]
            if not any(kw in title_lower for kw in valid_role_keywords):
                rejection_reason = f"Title '{title}' does not align with QA/SDET automation role"

            # 3. Context-Aware Experience Requirements Matching
            years_found = self.parse_required_years(requirements)
            if years_found:
                req_max = max(years_found)
                if req_max > self.max_exp_years:
                    rejection_reason = (
                        f"Requires {req_max}+ years exp (exceeds max threshold of {self.max_exp_years} years)"
                    )
                elif req_max < self.min_exp_years:
                    rejection_reason = (
                        f"Requires {req_max} years exp (below min threshold of {self.min_exp_years} years)"
                    )

            if rejection_reason:
                print(f"❌ FILTERED OUT: {title} @ {company} (ID: {job_id}) -> Reason: {rejection_reason}")
                os.remove(filepath)
                filtered.append({"job_id": job_id, "title": title, "company": company, "reason": rejection_reason})
                status_updates[job_id] = "FILTERED_OUT"
            else:
                print(f"✅ RETAINED: {title} @ {company} (ID: {job_id})")
                retained.append({"job_id": job_id, "title": title, "company": company})
                status_updates[job_id] = "RETAINED"

        if status_updates:
            self.update_processed_jobs_status(status_updates)

        print("\n" + "=" * 50)
        print(f"🎉 FILTERING COMPLETE: Retained {len(retained)} job(s), Filtered out {len(filtered)} job(s).")
        print("=" * 50 + "\n")

        return {
            "retained": len(retained),
            "filtered": len(filtered),
            "retained_list": retained,
            "filtered_list": filtered,
        }
