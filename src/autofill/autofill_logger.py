"""Centralized Structured Diagnostics, Event Logger & Learning Vault for ATS Autofill.

Provides persistent human-readable logging, structured JSONL event tracking,
full-page failure screenshot captures, DOM element dumps, and self-learning
incident banking to eliminate repetitive automation debugging cycles.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

LOGS_DIR = Path("data/logs")
SCREENSHOTS_DIR = LOGS_DIR / "screenshots"
DIAGNOSTICS_LOG_FILE = LOGS_DIR / "autofill_diagnostics.log"
EVENTS_JSONL_FILE = LOGS_DIR / "autofill_events.jsonl"
LEARNING_VAULT_FILE = LOGS_DIR / "autofill_learning_vault.json"
BENCHMARKS_JSONL_FILE = LOGS_DIR / "autofill_benchmarks.jsonl"
UNMAPPED_BACKLOG_JSONL_FILE = LOGS_DIR / "unmapped_fields_backlog.jsonl"
LEARNED_MAPPINGS_FILE = LOGS_DIR / "learned_field_mappings.json"
FLIGHT_RECORDER_JSONL_FILE = LOGS_DIR / "application_flight_recorder.jsonl"


def normalize_field_label_key(label: str) -> str:
    """Normalizes a form field label into a canonical lookup key for learned mappings."""
    cleaned = re.sub(r"[\*\:\?\(\)\[\]]", " ", (label or "").lower())
    cleaned = re.sub(r"\b(required|optional|please|enter|select|specify|your)\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def mask_pii(value: str, field_name: str = "") -> str:
    """Masks sensitive credentials and contact tokens for diagnostic audit trails."""
    if not value:
        return ""
    lower_field = field_name.lower()
    if any(k in lower_field for k in ("password", "pwd", "secret", "token")):
        return "********"
    if any(k in lower_field for k in ("phone", "tel", "mobile")):
        clean_num = re.sub(r"[^\d+]", "", value)
        if len(clean_num) > 6:
            return clean_num[:4] + "****" + clean_num[-2:]
        return "******"
    return value


@dataclass
class AutofillEvent:
    """Structured event capturing atomic autofill and self-healing telemetry."""

    event_id: str
    timestamp: str
    event_type: str
    vendor: str
    stage: str
    action_type: str
    locator: str
    field_name: str
    value_preview: str
    duration_ms: float
    status: str
    error: str | None = None
    diagnostics: dict[str, Any] | None = None


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
        self._listeners: list[Callable[[dict[str, Any]], None]] = []

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

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Subscribes an async or sync callback to receive live autofill events (e.g. for SSE streams)."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Unsubscribes a listener callback."""
        if callback in self._listeners:
            self._listeners.remove(callback)

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

    def _notify_listeners(self, data: dict[str, Any]) -> None:
        for cb in list(self._listeners):
            try:
                cb(data)
            except Exception:
                pass

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

        self._notify_listeners(event_data)

    def log_field_action(
        self,
        event_type: str,
        vendor: str,
        stage: str,
        action_type: str,
        locator: str,
        field_name: str,
        value: str,
        duration_ms: float,
        status: str = "SUCCESS",
        error: str | None = None,
        diagnostics: dict[str, Any] | None = None,
    ) -> AutofillEvent:
        """Records a granular field action with PII masking and broadcasts to listeners."""
        masked_val = mask_pii(value, field_name)
        now_iso = datetime.now(timezone.utc).isoformat()
        evt = AutofillEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            timestamp=now_iso,
            event_type=event_type,
            vendor=vendor,
            stage=stage,
            action_type=action_type,
            locator=locator,
            field_name=field_name,
            value_preview=masked_val,
            duration_ms=round(duration_ms, 2),
            status=status,
            error=error,
            diagnostics=diagnostics,
        )
        evt_dict = asdict(evt)
        self.logger.info(
            f"[{vendor}] [{stage}] {event_type}: {action_type} '{field_name}' -> status={status} ({duration_ms:.1f}ms)"
        )
        try:
            with open(EVENTS_JSONL_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(evt_dict) + "\n")
        except Exception as e:
            self.logger.warning(f"Failed to append to {EVENTS_JSONL_FILE}: {e}")

        self._notify_listeners(evt_dict)
        return evt

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

    def record_batch_run_metrics(
        self,
        url: str,
        vendor: str,
        total_controls: int,
        auto_filled_count: int,
        unmapped_count: int,
        failed_count: int,
        duration_ms: float,
    ) -> dict[str, Any]:
        """Appends per-page Phase A speed & coverage metrics to autofill_benchmarks.jsonl."""
        _ensure_directories()
        coverage_pct = round((auto_filled_count / max(total_controls, 1)) * 100.0, 1)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "url": url,
            "vendor": vendor or "GENERIC",
            "total_controls": total_controls,
            "auto_filled_count": auto_filled_count,
            "unmapped_count": unmapped_count,
            "failed_count": failed_count,
            "coverage_pct": coverage_pct,
            "duration_ms": round(duration_ms, 2),
        }
        try:
            with open(BENCHMARKS_JSONL_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            self.logger.warning(f"Failed to append to {BENCHMARKS_JSONL_FILE}: {e}")
        return record

    def record_unmapped_fields(
        self,
        url: str,
        vendor: str,
        unmapped_fields: list[dict[str, Any]],
    ) -> int:
        """Appends unmapped custom fields from Phase A to unmapped_fields_backlog.jsonl."""
        if not unmapped_fields:
            return 0
        _ensure_directories()
        now_iso = datetime.now(timezone.utc).isoformat()
        written = 0
        try:
            with open(UNMAPPED_BACKLOG_JSONL_FILE, "a", encoding="utf-8") as f:
                for fld in unmapped_fields:
                    label = (fld.get("label") or "").strip()
                    if not label:
                        continue
                    entry = {
                        "timestamp": now_iso,
                        "url": url,
                        "vendor": vendor or "GENERIC",
                        "field_id": fld.get("field_id", ""),
                        "label": label,
                        "normalized_key": normalize_field_label_key(label),
                        "control_type": fld.get("control_type", "text"),
                        "required": bool(fld.get("required", False)),
                        "options_preview": [
                            opt.get("text", "") if isinstance(opt, dict) else str(opt)
                            for opt in (fld.get("options") or [])[:10]
                        ],
                    }
                    f.write(json.dumps(entry) + "\n")
                    written += 1
        except Exception as e:
            self.logger.warning(f"Failed to append to {UNMAPPED_BACKLOG_JSONL_FILE}: {e}")
        return written

    def get_learned_field_mappings(self) -> dict[str, dict[str, Any]]:
        """Loads previously learned custom field label->value mappings from disk."""
        if not LEARNED_MAPPINGS_FILE.exists():
            return {}
        try:
            with open(LEARNED_MAPPINGS_FILE, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data.get("mappings", data)
        except Exception:
            pass
        return {}

    def record_learned_field_mapping(
        self,
        label: str,
        value: str,
        control_type: str = "text",
        source: str = "phase_b_custom",
    ) -> dict[str, Any]:
        """Banks a custom field question + answer into learned_field_mappings.json for automatic Phase A reuse."""
        _ensure_directories()
        norm_key = normalize_field_label_key(label)
        if not norm_key or value is None or str(value).strip() == "":
            return {}

        # Never bank sensitive passwords or one-off tokens
        if any(k in norm_key for k in ("password", "otp", "verification code", "security code", "captcha")):
            return {}

        mappings = self.get_learned_field_mappings()
        existing = mappings.get(norm_key, {})
        hit_count = int(existing.get("use_count", 0)) + 1

        entry = {
            "label": label.strip(),
            "normalized_key": norm_key,
            "value": str(value).strip(),
            "control_type": control_type,
            "source": source,
            "use_count": hit_count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        mappings[norm_key] = entry

        try:
            with open(LEARNED_MAPPINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "version": "1.0",
                        "description": "Closed-loop learned custom form field answers automatically reused by Phase A UniversalBatchFormFiller.",
                        "mappings": mappings,
                    },
                    f,
                    indent=2,
                )
            self.logger.info(f"🧠 Auto-learned custom field mapping: '{norm_key}' -> '{mask_pii(str(value), label)}'")
        except Exception as e:
            self.logger.warning(f"Failed to save {LEARNED_MAPPINGS_FILE}: {e}")
        return entry

    def get_audit_summary(self, limit: int = 10) -> dict[str, Any]:
        """Returns the most recent autofill events, telemetry benchmarks, unmapped backlog, and learning vault lessons."""
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

        benchmarks = []
        if BENCHMARKS_JSONL_FILE.exists():
            try:
                with open(BENCHMARKS_JSONL_FILE, encoding="utf-8") as f:
                    for ln in f:
                        if ln.strip():
                            benchmarks.append(json.loads(ln))
            except Exception:
                pass

        avg_coverage_pct = 0.0
        avg_duration_ms = 0.0
        if benchmarks:
            avg_coverage_pct = round(
                sum(float(b.get("coverage_pct", 0.0)) for b in benchmarks) / len(benchmarks),
                1,
            )
            avg_duration_ms = round(
                sum(float(b.get("duration_ms", 0.0)) for b in benchmarks) / len(benchmarks),
                1,
            )

        unmapped_counts: dict[str, dict[str, Any]] = {}
        if UNMAPPED_BACKLOG_JSONL_FILE.exists():
            try:
                with open(UNMAPPED_BACKLOG_JSONL_FILE, encoding="utf-8") as f:
                    for ln in f:
                        if not ln.strip():
                            continue
                        item = json.loads(ln)
                        nkey = item.get("normalized_key") or item.get("label", "")
                        if not nkey:
                            continue
                        rec = unmapped_counts.setdefault(
                            nkey,
                            {
                                "label": item.get("label", nkey),
                                "normalized_key": nkey,
                                "control_type": item.get("control_type", "text"),
                                "count": 0,
                                "last_vendor": item.get("vendor", "GENERIC"),
                            },
                        )
                        rec["count"] += 1
            except Exception:
                pass

        top_unmapped = sorted(
            unmapped_counts.values(),
            key=lambda x: x["count"],
            reverse=True,
        )[:limit]

        learned_mappings = self.get_learned_field_mappings()

        flight_records = []
        if FLIGHT_RECORDER_JSONL_FILE.exists():
            try:
                with open(FLIGHT_RECORDER_JSONL_FILE, encoding="utf-8") as f:
                    lines = [ln.strip() for ln in f if ln.strip()]
                    for ln in lines[-limit:]:
                        try:
                            flight_records.append(json.loads(ln))
                        except Exception:
                            pass
            except Exception:
                pass

        return {
            "recent_events": events,
            "recent_flight_records": flight_records,
            "total_lessons_banked": len(lessons),
            "lessons": lessons,
            "recent_screenshots": screenshots,
            "telemetry": {
                "total_batch_runs": len(benchmarks),
                "avg_coverage_pct": avg_coverage_pct,
                "avg_duration_ms": avg_duration_ms,
                "recent_benchmarks": benchmarks[-limit:],
                "top_unmapped_fields": top_unmapped,
                "total_learned_mappings": len(learned_mappings),
                "learned_mappings": list(learned_mappings.values())[:limit],
            },
        }

    def attach_network_flight_recorder(self, page: Any) -> None:
        """
        Attaches a lightweight HTTP response listener to `page` that captures failed API calls
        (`status >= 400`) or ATS submission/validation payloads into `page._agy_net_errors`.
        """
        if not page or getattr(page, "_agy_flight_recorder_attached", False):
            return
        try:
            page._agy_net_errors = []
            page._agy_flight_recorder_attached = True

            async def _on_response(resp: Any) -> None:
                try:
                    status = int(resp.status)
                    r_url = str(resp.url or "")
                    if any(
                        ext in r_url.lower()
                        for ext in (".png", ".jpg", ".svg", ".woff", ".css", "google-analytics", "doubleclick")
                    ):
                        return
                    is_error = status >= 400
                    is_ats_submit = any(
                        k in r_url.lower() for k in ("/apply", "/submit", "/jobtasks", "/candidate", "/application")
                    ) and resp.request.method in ("POST", "PUT", "PATCH")
                    if not (is_error or is_ats_submit):
                        return
                    body_preview = ""
                    ctype = (resp.headers.get("content-type") or "").lower()
                    if "json" in ctype or "text" in ctype or is_error:
                        try:
                            txt = await resp.text()
                            if (
                                is_ats_submit
                                and status < 400
                                and not any(
                                    err_k in txt.lower()
                                    for err_k in ("error", "invalid", "required", "captcha", "fail")
                                )
                            ):
                                return
                            body_preview = re.sub(r"\s+", " ", txt).strip()[:350]
                        except Exception:
                            body_preview = ""
                    bucket: list[dict[str, Any]] = getattr(page, "_agy_net_errors", [])
                    if len(bucket) < 15:
                        bucket.append(
                            {
                                "status": status,
                                "method": resp.request.method,
                                "url": r_url[:180],
                                "response_preview": body_preview,
                            }
                        )
                except Exception:
                    pass

            page.on("response", _on_response)
        except Exception:
            pass

    async def record_flight_snapshot(
        self,
        page: Any,
        job_id: str,
        company: str,
        vendor: str,
        status: str,
        reason: str = "",
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Captures an Action-Scoped Application Flight Recorder entry (<15 KB JSONL) containing
        all visible interactive form controls (with resolved labels & data-automation-id),
        visible validation error banners, and failed XHR/HTTP responses into
        `data/logs/application_flight_recorder.jsonl`.
        """
        _ensure_directories()
        cur_url = getattr(page, "url", "") if page else ""
        dom_snapshot: dict[str, Any] = {
            "visible_controls": [],
            "validation_banners": [],
            "visible_buttons": [],
        }

        if page and hasattr(page, "evaluate"):
            try:
                dom_snapshot = await page.evaluate(
                    """() => {
                        const controls = [];
                        const els = Array.from(document.querySelectorAll(
                            'input:not([type="hidden"]):not([type="submit"]):not([type="button"]), select, textarea, [role="combobox"], [data-automation-id*="selectWidget"]'
                        ));
                        for (const el of els) {
                            const r = el.getBoundingClientRect();
                            if (r.width === 0 || r.height === 0) continue;
                            let lbl = '';
                            if (el.labels && el.labels.length > 0) {
                                lbl = Array.from(el.labels).map(l => l.innerText).join(' ');
                            }
                            if (!lbl && el.id) {
                                const byFor = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
                                if (byFor) lbl = byFor.innerText;
                            }
                            if (!lbl) {
                                lbl = el.getAttribute('aria-label') || el.getAttribute('placeholder') || '';
                            }
                            if (!lbl) {
                                const container = el.closest('[data-automation-id*="formField"], .application-question, .field, fieldset, label');
                                if (container) {
                                    const lEl = container.querySelector('label, legend, .text, [data-automation-id*="formLabel"]');
                                    if (lEl) lbl = lEl.innerText;
                                }
                            }
                            lbl = (lbl || '').replace(/\\s+/g, ' ').trim().slice(0, 120);
                            const tag = (el.tagName || '').toLowerCase();
                            const itype = (el.getAttribute('type') || tag).toLowerCase();
                            const rawVal = itype === 'password' ? '********' : (el.value || (el.innerText || '').trim()).slice(0, 80);
                            controls.push({
                                tag: tag,
                                type: itype,
                                id: (el.id || '').slice(0, 80),
                                name: (el.getAttribute('name') || '').slice(0, 80),
                                data_automation_id: (el.getAttribute('data-automation-id') || '').slice(0, 80),
                                label: lbl,
                                required: !!(el.required || el.getAttribute('aria-required') === 'true' || /\\*/.test(lbl)),
                                value: rawVal
                            });
                            if (controls.length >= 35) break;
                        }

                        const banners = [];
                        const seenBanners = new Set();
                        const alertEls = Array.from(document.querySelectorAll(
                            '[role="alert"], [data-automation-id*="error" i], .error-message, .field-error, .invalid-feedback, .g-recaptcha, .h-captcha, iframe[src*="hcaptcha"], iframe[src*="recaptcha"]'
                        ));
                        for (const a of alertEls) {
                            const r = a.getBoundingClientRect();
                            if (r.width === 0 || r.height === 0) continue;
                            const txt = (a.tagName === 'IFRAME' ? ('CAPTCHA_IFRAME:' + (a.getAttribute('src') || '').slice(0, 80)) : (a.innerText || '')).replace(/\\s+/g, ' ').trim().slice(0, 160);
                            if (txt && !seenBanners.has(txt.toLowerCase())) {
                                seenBanners.add(txt.toLowerCase());
                                banners.push(txt);
                            }
                            if (banners.length >= 10) break;
                        }

                        const buttons = [];
                        const seenBtns = new Set();
                        const btnEls = Array.from(document.querySelectorAll('button, a[role="button"], input[type="submit"], a.postings-btn'));
                        for (const b of btnEls) {
                            const r = b.getBoundingClientRect();
                            if (r.width === 0 || r.height === 0) continue;
                            const btxt = (b.innerText || b.value || b.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim().slice(0, 50);
                            if (btxt && !seenBtns.has(btxt.toLowerCase())) {
                                seenBtns.add(btxt.toLowerCase());
                                buttons.push(btxt);
                            }
                            if (buttons.length >= 12) break;
                        }

                        return {
                            visible_controls: controls,
                            validation_banners: banners,
                            visible_buttons: buttons
                        };
                    }"""
                )
            except Exception:
                pass

        net_errors = list(getattr(page, "_agy_net_errors", [])) if page else []
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "job_id": str(job_id),
            "company": company,
            "vendor": vendor or "GENERIC",
            "status": status,
            "reason": reason,
            "url": cur_url,
            "visible_controls_count": len(dom_snapshot.get("visible_controls", [])),
            "visible_controls": dom_snapshot.get("visible_controls", []),
            "validation_banners": dom_snapshot.get("validation_banners", []),
            "visible_buttons": dom_snapshot.get("visible_buttons", []),
            "network_errors": net_errors,
            "extra": extra or {},
        }

        try:
            with open(FLIGHT_RECORDER_JSONL_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            self.logger.warning(f"Failed to append to {FLIGHT_RECORDER_JSONL_FILE}: {e}")

        return record
