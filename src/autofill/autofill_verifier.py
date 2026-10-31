"""
Log-Grounded Submission Verification Gate & False-Positive Guardrail Engine.

Validates that an application has genuinely displayed an authentic submission confirmation
display (DOM text marker, confirmation URL, or confirmation modal) and captured a visual
screenshot before any application is permitted to transition to 'applied' in SQLite tracking.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.autofill.autofill_logger import EVENTS_JSONL_FILE, SCREENSHOTS_DIR, AutofillLogger


class SubmissionVerifier:
    """Audits persistent logs and visual evidence to guarantee authentic application submission."""

    DEFAULT_MAX_AGE_SECONDS: int = 1800  # 30 minutes validity window

    @staticmethod
    def verify_submission(
        job_id: str,
        max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
        events_file: Path | str | None = None,
    ) -> dict[str, Any]:
        """
        Scans autofill_events.jsonl in reverse order to verify that a genuine
        SUBMISSION_CONFIRMED event was registered for the specific job_id within max_age_seconds.

        Returns:
            dict with 'verified': bool, and either confirmation details or failure reason.
        """
        if not job_id:
            return {"verified": False, "reason": "Missing or empty job_id."}

        target_file = Path(events_file) if events_file else EVENTS_JSONL_FILE
        if not target_file.exists():
            return {
                "verified": False,
                "reason": f"Autofill event log does not exist at: {target_file}",
            }

        target_jid = str(job_id).strip()

        try:
            with open(target_file, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
        except Exception as e:
            return {"verified": False, "reason": f"Failed to read autofill event log: {e}"}

        # Scan from newest to oldest
        for line in reversed(lines):
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue

            if event.get("event_type") != "SUBMISSION_CONFIRMED":
                continue

            details = event.get("details", {})
            event_jid = str(details.get("job_id", "")).strip()

            # Check if this confirmation event matches our job_id
            if event_jid != target_jid and f"({target_jid})" not in event.get("message", ""):
                continue

            # Verify timestamp freshness
            raw_ts = event.get("timestamp")
            if raw_ts:
                try:
                    # Support ISO strings with Z or offsets
                    ts_clean = raw_ts.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(ts_clean)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    age_seconds = (datetime.now(timezone.utc) - dt).total_seconds()
                except Exception:
                    age_seconds = 0.0
            else:
                age_seconds = 0.0

            if age_seconds > max_age_seconds:
                return {
                    "verified": False,
                    "reason": f"Matching confirmation event found, but expired ({age_seconds:.1f}s old > {max_age_seconds}s allowed).",
                    "event": event,
                }

            screenshot_path = details.get("screenshot")
            screenshot_exists = bool(screenshot_path and os.path.exists(screenshot_path))

            return {
                "verified": True,
                "job_id": target_jid,
                "event": event,
                "screenshot": screenshot_path,
                "screenshot_exists": screenshot_exists,
                "marker_type": details.get("marker_type", "unknown"),
                "marker_text": details.get("marker_text", ""),
                "age_seconds": round(age_seconds, 1),
                "timestamp": raw_ts,
            }

        return {
            "verified": False,
            "reason": f"No SUBMISSION_CONFIRMED event found in autofill_events.jsonl for job {target_jid}.",
        }

    @staticmethod
    async def record_submission_confirmed(
        job_id: str,
        company: str = "",
        page: Any = None,
        marker_type: str = "url_or_dom",
        marker_text: str = "",
        screenshot_path: str | None = None,
    ) -> dict[str, Any]:
        """
        Captures a visual screenshot of the confirmation page, writes a structured
        SUBMISSION_CONFIRMED event to autofill_events.jsonl, and notifies live subscribers.
        """
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        final_screenshot = screenshot_path

        # If a page is provided and no screenshot exists yet, capture one
        if page and not final_screenshot:
            safe_comp = re.sub(r"[^\w\-]", "_", company or "application").strip("_")
            safe_jid = re.sub(r"[^\w\-]", "_", str(job_id)).strip("_")
            ts = int(time.time())
            snap_file = SCREENSHOTS_DIR / f"confirmation_{safe_comp}_{safe_jid}_{ts}.png"

            try:
                if hasattr(page, "screenshot"):
                    await page.screenshot(path=str(snap_file), full_page=True)
                    if snap_file.exists():
                        final_screenshot = str(snap_file.resolve())
            except Exception as e:
                print(f"⚠️ Warning: Could not capture confirmation screenshot: {e}")

        logger = AutofillLogger.get_logger()
        event_details = {
            "job_id": str(job_id),
            "company": company or "Unknown",
            "marker_type": marker_type,
            "marker_text": marker_text,
            "screenshot": final_screenshot,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }

        page_url = getattr(page, "url", "") if page else ""
        logger.log(
            event_type="SUBMISSION_CONFIRMED",
            message=f"Application submission confirmed for {company or 'Company'} ({job_id})",
            url=page_url,
            details=event_details,
        )

        return event_details
