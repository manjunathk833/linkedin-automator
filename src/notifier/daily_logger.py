"""
Daily Run Structured Audit Logger.
Maintains persistent audit logs of automated daily pipeline executions in:
- data/logs/daily_runs.jsonl (machine-readable structured events)
- data/logs/daily_runs.log (human-readable operational diagnostics)
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import traceback
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class DailyRunLogger:
    """
    Manages structured diagnostic logs for daily scheduled background executions.
    """

    def __init__(self, log_dir: Path | None = None):
        self.log_dir = log_dir or (PROJECT_ROOT / "data" / "logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "daily_runs.log"
        self.jsonl_file = self.log_dir / "daily_runs.jsonl"

    def get_git_commit(self) -> str:
        """Retrieves short git commit hash of the executing codebase."""
        try:
            out = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(PROJECT_ROOT),
                text=True,
                stderr=subprocess.DEVNULL,
            )
            return out.strip()
        except Exception:
            return "unknown"

    def get_git_branch(self) -> str:
        """Retrieves active git branch name."""
        try:
            out = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(PROJECT_ROOT),
                text=True,
                stderr=subprocess.DEVNULL,
            )
            return out.strip()
        except Exception:
            return "unknown"

    def log_run_start(self, run_id: str, trigger_source: str = "manual") -> dict[str, Any]:
        """Logs the start of a daily automation run."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        entry = {
            "run_id": run_id,
            "timestamp": now,
            "event": "RUN_STARTED",
            "git_commit": self.get_git_commit(),
            "git_branch": self.get_git_branch(),
            "trigger": trigger_source,
        }
        self._append_jsonl(entry)
        self._append_log(
            f"[{now}] [RUN_STARTED] RunID={run_id} Branch={entry['git_branch']} Commit={entry['git_commit']} Trigger={trigger_source}"
        )
        return entry

    def log_phase(
        self,
        run_id: str,
        phase_name: str,
        status: str,  # SUCCESS, WARNING, FAILED
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Logs phase-level telemetry during a daily run."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        entry = {
            "run_id": run_id,
            "timestamp": now,
            "event": "PHASE_RESULT",
            "phase": phase_name,
            "status": status,
            "details": details or {},
        }
        self._append_jsonl(entry)
        det_str = f" | {details}" if details else ""
        icon = "✅" if status == "SUCCESS" else ("⚠️" if status == "WARNING" else "❌")
        self._append_log(f"[{now}] [PHASE] {icon} Phase={phase_name} Status={status}{det_str}")
        return entry

    def log_exception(
        self,
        run_id: str,
        exc: Exception,
        phase: str | None = None,
    ) -> dict[str, Any]:
        """Logs full exception stack trace to operational log and structured JSONL."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        tb_str = traceback.format_exc()
        entry = {
            "run_id": run_id,
            "timestamp": now,
            "event": "EXCEPTION",
            "phase": phase or "UNKNOWN",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "traceback": tb_str,
        }
        self._append_jsonl(entry)
        self._append_log(f"[{now}] [CRITICAL_EXCEPTION] RunID={run_id} Phase={phase or 'N/A'}")
        self._append_log(f"    Type: {type(exc).__name__}: {exc}")
        self._append_log("    --- Traceback ---")
        for tb_line in tb_str.splitlines():
            self._append_log(f"    {tb_line}")
        self._append_log("    -----------------")
        return entry

    def log_run_complete(
        self,
        run_id: str,
        status: str,  # SUCCESS, PARTIAL, FAILED
        staged_count: int,
        dream_org_count: int,
        regression_passed: bool,
        email_sent: bool,
        duration_sec: float,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        """Logs the completion of a daily automation run."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        entry = {
            "run_id": run_id,
            "timestamp": now,
            "event": "RUN_COMPLETED",
            "status": status,
            "git_commit": self.get_git_commit(),
            "staged_count": staged_count,
            "dream_org_count": dream_org_count,
            "regression_passed": regression_passed,
            "email_sent": email_sent,
            "duration_sec": round(duration_sec, 2),
            "error_message": error_message,
        }
        self._append_jsonl(entry)
        self._append_log(
            f"[{now}] [RUN_COMPLETED] RunID={run_id} Status={status} Staged={staged_count} "
            f"DreamOrgs={dream_org_count} Regressions={'PASS' if regression_passed else 'FAIL'} "
            f"Email={'SENT' if email_sent else 'SKIPPED'} Duration={duration_sec:.1f}s"
        )
        if error_message:
            self._append_log(f"    ⚠️ Error: {error_message}")
        return entry

    def get_recent_runs(self, limit: int = 5) -> list[dict[str, Any]]:
        """Reads recent run events from JSONL log."""
        if not self.jsonl_file.exists():
            return []
        runs = []
        with open(self.jsonl_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        runs.append(json.loads(line))
                    except Exception:  # noqa: S112
                        continue
        return runs[-limit:]

    def diagnose_system(self) -> dict[str, Any]:
        """
        Executes comprehensive diagnostic health audit:
        1. Session storageState & LinkedIn cookies
        2. Environment variables (.env credentials)
        3. macOS launchd daemon status
        4. Log file paths and latest execution status
        """
        from src.browser.session_manager import SessionManager

        # 1. Session check
        sess_mgr = SessionManager()
        sess_info = sess_mgr.get_session_status()

        # 2. Env check
        env_checks = {
            "GMAIL_USER": bool(os.getenv("GMAIL_USER")),
            "GMAIL_APP_PASSWORD": bool(os.getenv("GMAIL_APP_PASSWORD")),
            "REPORT_RECIPIENT": bool(os.getenv("REPORT_RECIPIENT")),
            "GEMINI_API_KEY": bool(os.getenv("GEMINI_API_KEY")),
        }

        # 3. macOS launchd check
        launchd_active = False
        launchd_info = "Not registered"
        try:
            out = subprocess.check_output(
                ["launchctl", "list"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            for line in out.splitlines():
                if "com.linkedin.automator.daily" in line:
                    launchd_active = True
                    launchd_info = line.strip()
                    break
        except Exception as e:
            launchd_info = f"launchctl check failed: {e}"

        # 4. Recent run summary
        recent = self.get_recent_runs(limit=1)
        last_run = recent[-1] if recent else None

        return {
            "session": sess_info,
            "environment": env_checks,
            "launchd": {
                "active": launchd_active,
                "info": launchd_info,
            },
            "last_run": last_run,
            "log_paths": {
                "jsonl": str(self.jsonl_file),
                "operational_log": str(self.log_file),
                "launchd_stdout": str(self.log_dir / "launchd_stdout.log"),
                "launchd_stderr": str(self.log_dir / "launchd_stderr.log"),
            },
        }

    def _append_jsonl(self, data: dict[str, Any]) -> None:
        with open(self.jsonl_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")

    def _append_log(self, text: str) -> None:
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(text + "\n")
