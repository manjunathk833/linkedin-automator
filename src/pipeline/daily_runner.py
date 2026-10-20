"""
Automated Daily Pipeline Orchestrator.
Coordinates:
1. Health & Regression Gate Verification (Tier 1 Core)
2. Unified Job Discovery & STAR Resume Tailoring (Track 1 ATS + Track 2 LinkedIn)
3. Zero-Cost Executive HTML Email Briefing via Gmail SMTP
4. Command Center Background Service Verification (Port 8000)
5. Structured JSONL & Operational Diagnostics Logging
"""

from __future__ import annotations

import datetime
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from src.notifier.daily_logger import DailyRunLogger
from src.notifier.email_reporter import EmailReporter
from src.pipeline.runner import JobSearchPipelineRunner

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class DailyPipelineRunner:
    """
    Executes automated morning workflow for job discovery, regression verification,
    executive alerting, and dashboard readiness.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.logger = DailyRunLogger()
        self.reporter = EmailReporter()
        self.pipeline_runner = JobSearchPipelineRunner(config)

    def is_port_in_use(self, port: int = 8000, host: str = "127.0.0.1") -> bool:
        """Checks if a TCP port is currently accepting connections."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            return s.connect_ex((host, port)) == 0

    def ensure_dashboard_running(self, port: int = 8000) -> bool:
        """
        Verifies if FastAPI dashboard is running. If not, spawns it as a detached background process.
        """
        if self.is_port_in_use(port):
            print(f"✅ Dashboard is already running on http://127.0.0.1:{port}.")
            return True

        print(f"🚀 Launching Command Center Dashboard in background on port {port}...")
        log_path = PROJECT_ROOT / "data" / "logs" / "dashboard.log"
        pid_path = PROJECT_ROOT / "data" / "dashboard.pid"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        python_bin = PROJECT_ROOT / "venv" / "bin" / "python"
        if not python_bin.exists():
            python_bin = Path(sys.executable)

        with open(log_path, "a", encoding="utf-8") as out:
            proc = subprocess.Popen(
                [str(python_bin), "main.py", "dashboard"],
                cwd=str(PROJECT_ROOT),
                stdout=out,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

        with open(pid_path, "w", encoding="utf-8") as f:
            f.write(str(proc.pid))

        # Give server a moment to bind
        time.sleep(2.0)
        is_active = self.is_port_in_use(port)
        if is_active:
            print(f"✅ Background Dashboard active at: http://127.0.0.1:{port} (PID: {proc.pid})")
        else:
            print(f"⚠️ Dashboard started (PID {proc.pid}) but port {port} not yet responding. Check {log_path}.")
        return is_active

    def run_health_checks(self) -> tuple[bool, str]:
        """Runs Tier 1 Core regression suite."""
        print("\n" + "=" * 60)
        print("  STEP 1: PRE-RUN HEALTH & REGRESSION GATE CHECK")
        print("=" * 60)

        python_bin = PROJECT_ROOT / "venv" / "bin" / "python"
        if not python_bin.exists():
            python_bin = Path(sys.executable)

        cmd = [str(python_bin), "main.py", "test", "--tier", "core"]
        try:
            res = subprocess.run(
                cmd,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=120.0,
            )
            passed = res.returncode == 0
            summary = "Core Regression Tests Passed (100%)" if passed else "Regression Failures Detected"
            for line in res.stdout.splitlines():
                if "Passed" in line and "Total Executed" in res.stdout:
                    summary = line.strip()
                    break
            print(f"   Health status: {summary}")
            return passed, summary
        except Exception as e:
            return False, f"Regression check error: {e}"

    async def run_naukri_refresh(self, headless: bool = True) -> dict[str, Any]:
        """
        Executes daily automated touch of candidate profile headline on Naukri.com
        to reset the 'Last Active' timestamp for top ranking in recruiter Resdex queries.
        Includes non-blocking fault isolation.
        """
        print("\n" + "=" * 60)
        print("  STEP 4: NAUKRI RESDEX DAILY PROFILE VISIBILITY REFRESH")
        print("=" * 60)
        try:
            from scripts.naukri_pinger import run_naukri_pinger

            res = await run_naukri_pinger(headless=headless, dry_run=False)
            status = res.get("status", "UNKNOWN")
            print(f"   Naukri Refresh Status: {status} ({res.get('message', '')})")
            return res
        except Exception as e:
            print(f"⚠️ Naukri refresh encountered non-blocking warning: {e}")
            return {"status": "WARNING", "error": str(e)}

    def get_staged_jobs(self) -> list[dict[str, Any]]:
        """Reads all JSON payloads currently waiting in data/pending_queue/."""
        import json

        queue_dir = PROJECT_ROOT / "data" / "pending_queue"
        queue_dir.mkdir(parents=True, exist_ok=True)
        jobs = []
        for f in queue_dir.glob("*.json"):
            if f.name.startswith("."):
                continue
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    jobs.append(json.load(fh))
            except Exception:  # noqa: S112
                continue
        return jobs

    async def execute_daily_run(
        self,
        headless: bool = True,
        send_email: bool = True,
        skip_tests: bool = False,
        launch_dashboard: bool = True,
    ) -> dict[str, Any]:
        """
        Executes complete morning workflow across all system capabilities:
        1. Regressions -> 2. Notes Sync -> 3. Unified Discovery (Tracks 1, 2, 3) ->
        4. Experience Filter -> 5. Naukri Refresh -> 6. Email Briefing -> 7. Dashboard Readiness.
        """
        run_id = f"daily_{datetime.date.today().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
        t0 = time.time()
        self.logger.log_run_start(run_id=run_id, trigger_source="daily_runner")

        print("\n" + "🌟 " + "=" * 58)
        print(f"  EXECUTING DAILY JOB SEARCH AUTOMATION RUN [{run_id}]")
        print("=" * 60)

        fatal_error: str | None = None
        staged_jobs: list[dict[str, Any]] = []
        dream_orgs: list[dict[str, Any]] = []
        discovered_posts: list[dict[str, Any]] = []
        naukri_res: dict[str, Any] = {"status": "SKIPPED"}
        reg_passed, reg_summary = True, "Skipped by flag"
        email_sent = False

        try:
            # 1. Regression Health Check
            if not skip_tests:
                reg_passed, reg_summary = self.run_health_checks()
                self.logger.log_phase(
                    run_id=run_id,
                    phase_name="HEALTH_CHECK",
                    status="SUCCESS" if reg_passed else "FAILED",
                    details={"summary": reg_summary, "passed": reg_passed},
                )
            else:
                self.logger.log_phase(
                    run_id=run_id,
                    phase_name="HEALTH_CHECK",
                    status="SKIPPED",
                    details={"reason": "skip_tests flag enabled"},
                )

            # 2. Candidate Notes -> Master Knowledge Bank Sync
            print("\n" + "=" * 60)
            print("  STEP 2: CANDIDATE NOTES TO STAR KNOWLEDGE SYNC")
            print("=" * 60)
            try:
                sync_res = self.pipeline_runner.run_sync_stage()
                self.logger.log_phase(
                    run_id=run_id,
                    phase_name="KNOWLEDGE_SYNC",
                    status="SUCCESS",
                    details={"added": sync_res.get("added", 0)},
                )
            except Exception as e:
                print(f"⚠️ Knowledge sync warning: {e}")
                self.logger.log_exception(run_id, e, phase="KNOWLEDGE_SYNC")
                self.logger.log_phase(
                    run_id=run_id,
                    phase_name="KNOWLEDGE_SYNC",
                    status="WARNING",
                    details={"warning": str(e)},
                )

            # 3. Unified Job Discovery & AI Tailoring (Tracks 1, 2 & 3)
            print("\n" + "=" * 60)
            print("  STEP 3: MULTI-TRACK JOB & LEAD DISCOVERY (Tracks 1, 2 & 3)")
            print("=" * 60)
            try:
                await self.pipeline_runner.run_search_stage(source="all", headless=headless)
                self.pipeline_runner.run_filter_stage()
                staged_jobs = self.get_staged_jobs()
                dream_orgs = [j for j in staged_jobs if j.get("is_dream_org")]
                discovered_posts = getattr(self.pipeline_runner, "last_posts_discovered", [])
                if not discovered_posts:
                    from src.storage.database import ApplicationDatabase

                    discovered_posts = ApplicationDatabase().get_hiring_posts(limit=10)

                print(
                    f"\n📊 Discovery Summary: {len(staged_jobs)} role(s) staged ({len(dream_orgs)} Dream Orgs) | {len(discovered_posts)} social lead(s) banked."
                )
                self.logger.log_phase(
                    run_id=run_id,
                    phase_name="DISCOVERY_AND_TAILORING",
                    status="SUCCESS",
                    details={
                        "staged_total": len(staged_jobs),
                        "dream_orgs": len(dream_orgs),
                        "social_leads": len(discovered_posts),
                    },
                )
            except Exception as e:
                print(f"⚠️ Search stage warning: {e}")
                self.logger.log_exception(run_id, e, phase="DISCOVERY_AND_TAILORING")
                self.logger.log_phase(
                    run_id=run_id,
                    phase_name="DISCOVERY_AND_TAILORING",
                    status="WARNING",
                    details={"warning": str(e)},
                )
                staged_jobs = self.get_staged_jobs()
                dream_orgs = [j for j in staged_jobs if j.get("is_dream_org")]

            # 4. Naukri Resdex Daily Profile Visibility Refresh (Non-blocking)
            try:
                naukri_res = await self.run_naukri_refresh(headless=headless)
                n_status = "SUCCESS" if naukri_res.get("status") in ("SUCCESS", "dry_run") else "WARNING"
                self.logger.log_phase(
                    run_id=run_id,
                    phase_name="NAUKRI_REFRESH",
                    status=n_status,
                    details=naukri_res,
                )
            except Exception as e:
                print(f"⚠️ Naukri refresh warning: {e}")
                self.logger.log_exception(run_id, e, phase="NAUKRI_REFRESH")
                self.logger.log_phase(
                    run_id=run_id,
                    phase_name="NAUKRI_REFRESH",
                    status="WARNING",
                    details={"error": str(e)},
                )

            # 5. Email Briefing
            if send_email:
                print("\n" + "=" * 60)
                print("  STEP 5: DISPATCHING MORNING EXECUTIVE EMAIL BRIEFING")
                print("=" * 60)
                duration_sec = time.time() - t0
                try:
                    email_sent = self.reporter.send_report(
                        staged_jobs=staged_jobs,
                        regression_passed=reg_passed,
                        regression_summary=reg_summary,
                        execution_duration_sec=duration_sec,
                        hiring_posts=discovered_posts,
                        naukri_status=naukri_res,
                    )
                    self.logger.log_phase(
                        run_id=run_id,
                        phase_name="EMAIL_BRIEFING",
                        status="SUCCESS" if email_sent else "WARNING",
                        details={"email_sent": email_sent, "mode": "smtp" if email_sent else "offline_archive"},
                    )
                except Exception as e:
                    self.logger.log_exception(run_id, e, phase="EMAIL_BRIEFING")
                    self.logger.log_phase(
                        run_id=run_id,
                        phase_name="EMAIL_BRIEFING",
                        status="WARNING",
                        details={"error": str(e)},
                    )
            else:
                self.logger.log_phase(
                    run_id=run_id,
                    phase_name="EMAIL_BRIEFING",
                    status="SKIPPED",
                    details={"reason": "send_email flag disabled"},
                )

            # 6. Dashboard Readiness
            if launch_dashboard:
                print("\n" + "=" * 60)
                print("  STEP 6: COMMAND CENTER DASHBOARD READINESS")
                print("=" * 60)
                is_db_ready = self.ensure_dashboard_running(port=8000)
                self.logger.log_phase(
                    run_id=run_id,
                    phase_name="DASHBOARD_READINESS",
                    status="SUCCESS" if is_db_ready else "WARNING",
                    details={"port": 8000, "running": is_db_ready},
                )

        except Exception as fatal_e:
            fatal_error = str(fatal_e)
            print(f"❌ Fatal error in daily run: {fatal_e}")
            self.logger.log_exception(run_id, fatal_e, phase="PIPELINE_FATAL")

        total_duration = time.time() - t0
        run_status = "FAILED" if fatal_error else ("SUCCESS" if reg_passed else "PARTIAL_REGRESSION_FAIL")

        self.logger.log_run_complete(
            run_id=run_id,
            status=run_status,
            staged_count=len(staged_jobs),
            dream_org_count=len(dream_orgs),
            social_leads_count=len(discovered_posts),
            naukri_status=naukri_res.get("status"),
            regression_passed=reg_passed,
            email_sent=email_sent,
            duration_sec=total_duration,
            error_message=fatal_error,
        )

        print("\n" + "=" * 60)
        print(f"🎉 DAILY RUN [{run_id}] COMPLETE: {run_status} in {total_duration:.1f}s")
        print("=" * 60 + "\n")

        return {
            "run_id": run_id,
            "status": run_status,
            "staged_count": len(staged_jobs),
            "dream_org_count": len(dream_orgs),
            "social_leads_count": len(discovered_posts),
            "naukri_status": naukri_res.get("status"),
            "regression_passed": reg_passed,
            "email_sent": email_sent,
            "duration_sec": total_duration,
            "error_message": fatal_error,
        }
