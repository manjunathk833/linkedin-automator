"""Centralized Structured Diagnostics, Event Logger & Learning Vault for ATS Autofill.

Provides persistent human-readable logging, structured JSONL event tracking,
full-page failure screenshot captures, DOM element dumps, and self-learning
incident banking to eliminate repetitive automation debugging cycles.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOGS_DIR = Path("data/logs")
SCREENSHOTS_DIR = LOGS_DIR / "screenshots"
DIAGNOSTICS_LOG_FILE = LOGS_DIR / "autofill_diagnostics.log"
EVENTS_JSONL_FILE = LOGS_DIR / "autofill_events.jsonl"
LEARNING_VAULT_FILE = LOGS_DIR / "autofill_learning_vault.json"


def _ensure_directories() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


class AutofillLogger:
    """Manages persistent structured logging, error snapshots, and learning banking for ATS autofill."""

    _instance: AutofillLogger | None = None

    def __init__(self) -> None:
        _ensure_directories()
        self.logger = logging.getLogger("autofill_diagnostics")
        self.logger.setLevel(logging.INFO)

        # Avoid duplicate handlers on re-instantiation
        if not self.logger.handlers:
            fh = logging.FileHandler(DIAGNOSTICS_LOG_FILE, encoding="utf-8")
            fmt = logging.Formatter(
                "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            fh.setFormatter(fmt)
            self.logger.addHandler(fh)

        self._init_learning_vault_if_missing()

    @classmethod
    def get_logger(cls) -> AutofillLogger:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_learning_vault_if_missing(self) -> None:
        """Initializes the Learning Vault with established lessons if not present."""
        if not LEARNING_VAULT_FILE.exists():
            initial_vault = {
                "version": "1.0",
                "description": "Persistent repository of ATS autofill failure patterns, root causes, and verified fixes.",
                "lessons": [
                    {
                        "id": "LESSON-001",
                        "vendor": "WORKDAY_STANDARD",
                        "symptom": "State machine stuck on Overview or misclassifying Job Overview page as auth_sign_in.",
                        "root_cause": "Broad 'button:has-text(Sign In)' selector matched the global navbar 'Sign In' header button on the job overview page before checking for applyButton.",
                        "fix_rule": "Prioritize applyButton for 'overview' when password input is absent; strictly target button[data-automation-id='signInSubmitButton'] inside auth container.",
                        "date_banked": "2026-10-05T17:30:00Z",
                    },
                    {
                        "id": "LESSON-002",
                        "vendor": "GREENHOUSE_STANDARD",
                        "symptom": "Combobox selecting transient loading spinner instead of real option.",
                        "root_cause": "Async React-Select combobox displays .select__menu-notice--loading while fetching suggestions.",
                        "fix_rule": "Filter out .select__menu-notice using .select__option:not(.select__menu-notice).",
                        "date_banked": "2026-10-03T10:00:00Z",
                    },
                    {
                        "id": "LESSON-003",
                        "vendor": "WORKDAY_STANDARD",
                        "symptom": "Autofill halts after credential entry on Workday.",
                        "root_cause": "Workday post-auth redirect lands back on /job/... overview page, requiring an authenticated 'Apply' click before Stage 3 mounts.",
                        "fix_rule": "Use state machine loop (max 20 transitions) that handles overview -> modal -> auth -> overview -> info dynamically.",
                        "date_banked": "2026-10-05T16:00:00Z",
                    },
                    {
                        "id": "LESSON-004",
                        "vendor": "COMMON",
                        "symptom": "Red validation outlines persist after filling inputs.",
                        "root_cause": "Setting input value without synthetic event dispatch leaves internal React/Angular state uncommitted.",
                        "fix_rule": "Always dispatch 'input', 'change', and 'blur' events on modified form elements.",
                        "date_banked": "2026-10-03T12:00:00Z",
                    },
                    {
                        "id": "LESSON-005",
                        "vendor": "COMMON",
                        "symptom": "Phone dial code matches British Indian Ocean Territory (+246) instead of India (+91).",
                        "root_cause": "Substring search for 'India' matches territory name before country name.",
                        "fix_rule": "Search and match exact dial code string '+91' before fallback to country name.",
                        "date_banked": "2026-10-02T18:00:00Z",
                    },
                ],
            }
            with open(LEARNING_VAULT_FILE, "w", encoding="utf-8") as f:
                json.dump(initial_vault, f, indent=2)

    def log(
        self,
        event_type: str,
        message: str,
        vendor: str = "UNKNOWN",
        url: str = "",
        state: str = "",
        details: dict[str, Any] | None = None,
        level: int = logging.INFO,
    ) -> None:
        """Logs a human-readable message and appends a structured event to JSONL."""
        now_iso = datetime.now(timezone.utc).isoformat()

        # Human-readable log
        log_msg = f"[{vendor}] [{state or 'N/A'}] {message}"
        self.logger.log(level, log_msg)

        # Structured JSONL event
        event_data = {
            "timestamp": now_iso,
            "event_type": event_type,
            "vendor": vendor,
            "state": state,
            "url": url,
            "message": message,
            "details": details or {},
        }

        try:
            with open(EVENTS_JSONL_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(event_data) + "\n")
        except Exception as e:
            self.logger.warning(f"Failed to append to {EVENTS_JSONL_FILE}: {e}")

    async def capture_diagnostic(
        self,
        target: Any,
        reason: str,
        vendor: str = "UNKNOWN",
        state: str = "",
        extra_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Captures a full-page diagnostic screenshot and DOM element dump upon error or stuck threshold."""
        _ensure_directories()
        timestamp = int(time.time())
        sanitized_reason = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in reason)
        screenshot_filename = f"autofill_failure_{sanitized_reason}_{timestamp}.png"
        dom_dump_filename = f"autofill_dom_{sanitized_reason}_{timestamp}.json"

        screenshot_path = SCREENSHOTS_DIR / screenshot_filename
        dom_path = SCREENSHOTS_DIR / dom_dump_filename

        page = getattr(target, "page", target)
        cur_url = getattr(page, "url", "")
        title = ""
        dom_elements: dict[str, Any] = {"inputs": [], "buttons": [], "alerts": []}

        try:
            title = await page.title()
        except Exception:
            pass

        # 1. Capture Full-Page Screenshot
        try:
            await page.screenshot(path=str(screenshot_path), full_page=True)
            self.logger.info(f"📸 Full-page diagnostic screenshot saved: {screenshot_path}")
        except Exception as e:
            self.logger.error(f"Failed to capture screenshot: {e}")

        # 2. Extract Visible DOM Elements Dump
        try:
            # Inputs
            inputs = await target.locator("input, textarea, select").all()
            for inp in inputs[:30]:
                try:
                    if await inp.is_visible():
                        tag = await inp.evaluate("e => e.tagName.toLowerCase()")
                        itype = await inp.get_attribute("type") or "text"
                        iid = await inp.get_attribute("id") or ""
                        iname = await inp.get_attribute("name") or ""
                        iauto = await inp.get_attribute("data-automation-id") or ""
                        aria = await inp.get_attribute("aria-label") or ""
                        val = await inp.input_value() if tag == "input" and itype != "password" else "..."
                        dom_elements["inputs"].append(
                            {
                                "tag": tag,
                                "type": itype,
                                "id": iid,
                                "name": iname,
                                "data_automation_id": iauto,
                                "aria_label": aria,
                                "value": val,
                            }
                        )
                except Exception:
                    pass

            # Buttons / Actionable links
            buttons = await target.locator("button, a[role='button'], [data-automation-id*='button' i]").all()
            for btn in buttons[:30]:
                try:
                    if await btn.is_visible():
                        txt = (await btn.text_content() or "").strip()
                        bid = await btn.get_attribute("id") or ""
                        bauto = await btn.get_attribute("data-automation-id") or ""
                        baria = await btn.get_attribute("aria-label") or ""
                        dom_elements["buttons"].append(
                            {
                                "text": txt[:40],
                                "id": bid,
                                "data_automation_id": bauto,
                                "aria_label": baria,
                            }
                        )
                except Exception:
                    pass

            # Visible Alerts / Error Messages
            alerts = await target.locator("[role='alert'], [data-automation-id*='error' i], .alert").all()
            for alt in alerts[:5]:
                try:
                    if await alt.is_visible():
                        dom_elements["alerts"].append((await alt.text_content() or "").strip()[:100])
                except Exception:
                    pass

            with open(dom_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "url": cur_url,
                        "title": title,
                        "reason": reason,
                        "vendor": vendor,
                        "state": state,
                        "dom_elements": dom_elements,
                        "extra": extra_meta or {},
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            self.logger.warning(f"Failed to dump DOM elements: {e}")

        # 3. Log event
        self.log(
            event_type="DIAGNOSTIC_FAILURE_DUMP",
            message=f"Autofill diagnostic dump created for reason: {reason}",
            vendor=vendor,
            url=cur_url,
            state=state,
            details={
                "screenshot": str(screenshot_path),
                "dom_dump": str(dom_path),
                "reason": reason,
                "visible_buttons": len(dom_elements["buttons"]),
                "visible_inputs": len(dom_elements["inputs"]),
            },
            level=logging.ERROR,
        )

        return {
            "screenshot": str(screenshot_path),
            "dom_dump": str(dom_path),
            "url": cur_url,
            "title": title,
        }

    def record_learning_incident(
        self,
        vendor: str,
        symptom: str,
        root_cause: str,
        fix_rule: str,
    ) -> dict[str, Any]:
        """Banks a newly discovered failure pattern and fix rule into the persistent Learning Vault."""
        self._init_learning_vault_if_missing()
        try:
            with open(LEARNING_VAULT_FILE, encoding="utf-8") as f:
                vault = json.load(f)
        except Exception:
            vault = {"version": "1.0", "lessons": []}

        lesson_count = len(vault.get("lessons", [])) + 1
        new_lesson = {
            "id": f"LESSON-{lesson_count:03d}",
            "vendor": vendor,
            "symptom": symptom,
            "root_cause": root_cause,
            "fix_rule": fix_rule,
            "date_banked": datetime.now(timezone.utc).isoformat(),
        }
        vault.setdefault("lessons", []).append(new_lesson)

        with open(LEARNING_VAULT_FILE, "w", encoding="utf-8") as f:
            json.dump(vault, f, indent=2)

        self.logger.info(f"🧠 Banked new lesson in Learning Vault: {new_lesson['id']} - {symptom}")
        return new_lesson

    def get_audit_summary(self, limit: int = 10) -> dict[str, Any]:
        """Returns the most recent autofill events and learning vault lessons for CLI reports."""
        events = []
        if EVENTS_JSONL_FILE.exists():
            try:
                with open(EVENTS_JSONL_FILE, encoding="utf-8") as f:
                    lines = [ln.strip() for ln in f if ln.strip()]
                    for ln in lines[-limit:]:
                        try:
                            events.append(json.loads(ln))
                        except Exception:
                            pass
            except Exception:
                pass

        lessons = []
        if LEARNING_VAULT_FILE.exists():
            try:
                with open(LEARNING_VAULT_FILE, encoding="utf-8") as f:
                    v = json.load(f)
                    lessons = v.get("lessons", [])
            except Exception:
                pass

        screenshots = []
        if SCREENSHOTS_DIR.exists():
            try:
                screenshots = sorted(
                    [str(p) for p in SCREENSHOTS_DIR.glob("*.png")],
                    key=os.path.getmtime,
                    reverse=True,
                )[:limit]
            except Exception:
                pass

        return {
            "recent_events": events,
            "total_lessons_banked": len(lessons),
            "lessons": lessons,
            "recent_screenshots": screenshots,
        }
