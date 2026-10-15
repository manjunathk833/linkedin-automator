from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import subprocess
import sys
from typing import Any

import yaml
from playwright.async_api import async_playwright

from src.automation.easy_apply import EasyApplyExecutor
from src.browser.cdp_connector import launch_persistent_browser
from src.pipeline.runner import JobSearchPipelineRunner


def load_config(config_path: str = "config.yaml") -> dict[str, Any]:
    """Loads settings from config.yaml."""
    if not os.path.exists(config_path):
        print(f"⚠️ Config file {config_path} not found. Creating default...")
        return {
            "search_profiles": [{"keywords": "Senior SDET", "location": "Remote", "max_jobs": 5}],
            "resume_path": "data/resume_profile.json",
            "browser_profile_dir": ".browser_data",
            "llm": {"use_ai": True, "primary_model": "gemini-3.6-flash"},
        }
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


async def handle_login(config: dict[str, Any]):
    """Opens Chrome persistent profile for one-time manual LinkedIn login."""
    profile_dir = config.get("browser_profile_dir", ".browser_data")
    print("\n" + "=" * 50)
    print("  ONE-TIME LINKEDIN LOGIN MODE")
    print("=" * 50)
    print(f"🌐 Opening Chrome using persistent profile: {profile_dir}")
    print("👉 Please log into your LinkedIn account in the opened Chrome window.")

    async with async_playwright() as p:
        context, page = await launch_persistent_browser(p, profile_dir=profile_dir, headless=False)
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        print("\n⏳ Browser is open and waiting...")
        print("💡 Once you are logged in, press [ENTER] in this terminal to save session and close.")
        input(">>> Press ENTER when finished logging in: ")
        await context.close()
        print("✅ LinkedIn session saved to .browser_data/ successfully!\n")


async def handle_apply(config: dict[str, Any], dry_run: bool = True):
    """Reads approved jobs from data/approved_queue/ and executes Easy Apply automation."""
    approved_dir = os.path.join("data", "approved_queue")
    history_file = os.path.join("data", "application_history.json")
    os.makedirs(approved_dir, exist_ok=True)

    json_files = [f for f in os.listdir(approved_dir) if f.endswith(".json")]
    if not json_files:
        print("\n" + "=" * 50)
        print("⚠️ No approved jobs found in data/approved_queue/.")
        print("👉 Run `python main.py dashboard` to approve pending jobs first.")
        print("=" * 50 + "\n")
        return

    print("\n" + "=" * 50)
    print(f"  EXECUTING EASY APPLY AUTOMATION (Dry Run: {dry_run})")
    print(f"  Found {len(json_files)} approved job payload(s).")
    print("=" * 50 + "\n")

    executor = EasyApplyExecutor()
    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r") as f:
                history = json.load(f)
        except Exception:
            history = []

    for fname in json_files:
        filepath = os.path.join(approved_dir, fname)
        with open(filepath, "r") as f:
            payload = json.load(f)

        job_id = payload.get("job_id", fname.replace(".json", ""))
        title = payload.get("job_details", {}).get("title", "Unknown Title")
        company = payload.get("job_details", {}).get("company", "Unknown Company")

        print(f"\n🚀 Applying for: {title} @ {company} (ID: {job_id})")
        result = await executor.execute_application(payload, dry_run=dry_run)

        # Log history entry
        log_entry = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "job_id": job_id,
            "company": company,
            "title": title,
            "status": result.get("status", "UNKNOWN"),
            "dry_run": dry_run,
            "details": result.get("reason", "Execution completed"),
        }
        history.append(log_entry)

        # Write log back
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)

        print(f"✅ Result logged for {job_id}: Status={log_entry['status']}")

    print("\n" + "=" * 50)
    print("🎉 EASY APPLY AUTOMATION COMPLETE!")
    print(f"💾 Updated application history in: {history_file}")
    print("=" * 50 + "\n")


def handle_lint():
    """Runs Ruff auto-fix linter and code formatter across all project files."""
    print("\n" + "=" * 50)
    print("  RUNNING RUFF AUTO-FIX LINTER & FORMATTER")
    print("=" * 50 + "\n")
    script = os.path.join(os.path.dirname(__file__), "verify", "autofix_lint.sh")
    subprocess.run(["bash", script])


def handle_test(tier: str = "core", live: bool = False):
    """Runs the standardized regression test suite across specified tiers."""
    script = os.path.join(os.path.dirname(__file__), "verify", "run_regressions.py")
    python_bin = os.path.join(os.path.dirname(__file__), "venv", "bin", "python")
    if not os.path.exists(python_bin):
        python_bin = sys.executable
    cmd = [python_bin, script, "--tier", tier]
    if live:
        cmd.append("--live")
    ret = subprocess.run(cmd)
    sys.exit(ret.returncode)


def handle_autofill_audit():
    """Prints a diagnostics audit report of recent autofill events and learning vault lessons."""
    from src.autofill.autofill_logger import AutofillLogger

    logger = AutofillLogger.get_logger()
    summary = logger.get_audit_summary(limit=10)

    print("\n" + "=" * 65)
    print("  ATS AUTOFILL DIAGNOSTICS & LEARNING VAULT AUDIT")
    print("=" * 65)

    print(f"\n🧠 Banked Lessons in Learning Vault ({summary['total_lessons_banked']} total):")
    for lesson in summary["lessons"]:
        print(f"  [{lesson['id']}] [{lesson['vendor']}]")
        print(f"     • Symptom:    {lesson['symptom']}")
        print(f"     • Root Cause: {lesson['root_cause']}")
        print(f"     • Fix Rule:   {lesson['fix_rule']}")
        print()

    recent_events = summary["recent_events"]
    print(f"📜 Recent Autofill Events ({len(recent_events)} captured):")
    if not recent_events:
        print("  (No recent events recorded in data/logs/autofill_events.jsonl)")
    else:
        for ev in recent_events[-5:]:
            ts = ev.get("timestamp", "")[:19]
            ev_type = ev.get("event_type", "INFO")
            vendor = ev.get("vendor", "UNKNOWN")
            st = ev.get("state", "N/A")
            msg = ev.get("message", "")
            print(f"  [{ts}] [{ev_type}] [{vendor}] [{st}]: {msg}")

    recent_screenshots = summary["recent_screenshots"]
    if recent_screenshots:
        print(f"\n📸 Recent Diagnostic Screenshots ({len(recent_screenshots)} captured):")
        for sc in recent_screenshots[:5]:
            print(f"  • {sc}")

    print("\n" + "=" * 65 + "\n")


def handle_session(action: str = "status", output: str | None = None):
    """Manages portable Playwright storageState sessions."""
    from src.browser.session_manager import SessionManager

    mgr = SessionManager()
    if action == "export":
        print("\n" + "=" * 50)
        print("  EXPORTING PLAYWRIGHT SESSION STORAGE STATE")
        print("=" * 50)
        asyncio.run(mgr.export_storage_state(output_path=output))
    else:
        print("\n" + "=" * 50)
        print("  LINKEDIN SESSION AUTHENTICATION STATUS")
        print("=" * 50)
        status = mgr.get_session_status()
        print(f"📁 State Path:    {status['path']}")
        print(f"🔑 Authenticated: {status['is_authenticated']}")
        print(f"🍪 Cookie Count:  {status.get('cookie_count', 0)}")
        print(f"⏳ li_at Expiry:  {status.get('li_at_expires', 'N/A')}")
        print(f"💬 Message:       {status['message']}")
        print("=" * 50 + "\n")


def handle_daily(
    config: dict[str, Any],
    headless: bool = True,
    send_email: bool = True,
    skip_tests: bool = False,
    launch_dashboard: bool = True,
):
    """Executes the automated morning daily run."""
    from src.pipeline.daily_runner import DailyPipelineRunner

    runner = DailyPipelineRunner(config)
    asyncio.run(
        runner.execute_daily_run(
            headless=headless,
            send_email=send_email,
            skip_tests=skip_tests,
            launch_dashboard=launch_dashboard,
        )
    )


def handle_daily_audit(limit: int = 5):
    """Prints diagnostic logs of recent daily runs."""
    from src.notifier.daily_logger import DailyRunLogger

    logger = DailyRunLogger()
    runs = logger.get_recent_runs(limit=limit)

    print("\n" + "=" * 65)
    print(f"  AUTOMATED DAILY RUNS AUDIT LOG (Last {len(runs)} events)")
    print("=" * 65)

    if not runs:
        print("  (No daily runs logged yet in data/logs/daily_runs.jsonl)")
    else:
        for r in runs:
            ts = r.get("timestamp", "")[:19]
            ev = r.get("event", "UNKNOWN")
            st = r.get("status", "N/A")
            rid = r.get("run_id", "N/A")
            staged = r.get("staged_count", 0)
            dream = r.get("dream_org_count", 0)
            reg = "PASS" if r.get("regression_passed") else "FAIL"
            em = "SENT" if r.get("email_sent") else "NO"
            dur = r.get("duration_sec", 0.0)
            err = r.get("error_message")

            print(f"  [{ts}] [{ev}] [{st}] RunID: {rid}")
            if ev == "RUN_COMPLETED":
                print(f"     • Jobs Staged: {staged} ({dream} Dream Orgs)")
                print(f"     • Regressions: {reg} | Email: {em} | Duration: {dur}s")
            if err:
                print(f"     • Error: {err}")
            print()

    print("=" * 65 + "\n")


def handle_daily_diagnose():
    """Runs end-to-end system and environment diagnostics."""
    from src.notifier.daily_logger import DailyRunLogger

    logger = DailyRunLogger()
    diag = logger.diagnose_system()

    print("\n" + "=" * 65)
    print("  AUTOMATED DAILY PIPELINE SYSTEM DIAGNOSTICS")
    print("=" * 65)

    # 1. Session Health
    sess = diag.get("session", {})
    sess_auth = "AUTHENTICATED ✅" if sess.get("is_authenticated") else "NOT AUTHENTICATED ❌"
    print("\n🔑 1. Playwright StorageState & Session Health:")
    print(f"   • Status: {sess_auth}")
    print(f"   • Path: {sess.get('path')}")
    print(
        f"   • Cookies: {sess.get('cookie_count', 0)} total (li_at: {sess.get('has_li_at')}, JSESSIONID: {sess.get('has_jsessionid')})"
    )
    if not sess.get("is_authenticated"):
        print("   👉 TIP: Run `python main.py login` or `python main.py session export` to refresh cookies.")

    # 2. Environment Credentials
    env = diag.get("environment", {})
    print("\n📬 2. Zero-Cost Email & API Environment (.env):")
    for k, v in env.items():
        icon = "CONFIGURED ✅" if v else "MISSING ⚠️ (Will use offline archive)"
        print(f"   • {k}: {icon}")

    # 3. macOS launchd Daemon
    ld = diag.get("launchd", {})
    ld_icon = "ACTIVE & REGISTERED ✅" if ld.get("active") else "NOT REGISTERED ⚠️"
    print("\n⏰ 3. macOS launchd Scheduled Service:")
    print(f"   • Status: {ld_icon}")
    print(f"   • Details: {ld.get('info')}")
    if not ld.get("active"):
        print("   👉 TIP: Run `bash scripts/setup_daily_runner.sh` to register 8:00 AM daily job.")

    # 4. Latest Run Status
    last = diag.get("last_run")
    print("\n📊 4. Most Recent Pipeline Execution:")
    if not last:
        print("   • No past runs recorded.")
    else:
        print(f"   • Run ID: {last.get('run_id')} ({last.get('timestamp', '')[:19]})")
        print(f"   • Status: {last.get('status')} | Git: {last.get('git_commit')}")
        if last.get("error_message"):
            print(f"   • Error: {last.get('error_message')}")

    # 5. Diagnostic Log Paths
    paths = diag.get("log_paths", {})
    print("\n📂 5. Diagnostic Log Artifact Paths:")
    for name, p in paths.items():
        exists = "Exists" if os.path.exists(p) else "Pending"
        print(f"   • {name}: {p} [{exists}]")

    print("\n" + "=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="LinkedIn Job Search & Application Automation Orchestrator",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--config", default="config.yaml", help="Path to configuration file (default: config.yaml)")

    subparsers = parser.add_subparsers(dest="command", title="Subcommands", help="Available automation commands")

    # 1. run / pipeline (One-shot automated runner)
    parser_run = subparsers.add_parser(
        "run",
        aliases=["pipeline"],
        help="One-shot automated execution (sync notes -> unified search -> filter -> launch dashboard)",
    )
    parser_run.add_argument(
        "--skip-sync", action="store_true", help="Skip translating candidate notes to knowledge bank"
    )
    parser_run.add_argument(
        "--no-dashboard", action="store_false", dest="launch_ui", help="Do not auto-launch web dashboard server"
    )
    parser_run.add_argument(
        "--source",
        choices=["all", "linkedin", "ats"],
        default="all",
        help="Job discovery source: 'all' (Direct ATS + LinkedIn), 'linkedin', or 'ats' (default: all)",
    )
    parser_run.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode (ideal for CI/CD and daily scheduled runs)",
    )

    # 2. search
    parser_search = subparsers.add_parser(
        "search", help="Discover jobs across all sources (Direct ATS + LinkedIn) & tailor resumes"
    )
    parser_search.add_argument(
        "--source",
        choices=["all", "linkedin", "ats"],
        default="all",
        help="Job discovery source: 'all' (Direct ATS + LinkedIn), 'linkedin', or 'ats' (default: all)",
    )
    parser_search.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode (ideal for CI/CD and daily scheduled runs)",
    )

    # 3. sync / sync-knowledge
    subparsers.add_parser(
        "sync",
        aliases=["sync-knowledge"],
        help="Translate candidate_notes.md into master_knowledge_bank.json entries",
    )

    # 4. filter / filterjobs
    subparsers.add_parser(
        "filter", aliases=["filterjobs"], help="Run experience-level threshold filter on pending queue"
    )

    # 5. dashboard
    subparsers.add_parser("dashboard", help="Launch FastAPI Approval Gate Dashboard on http://127.0.0.1:8000")

    # 6. apply
    parser_apply = subparsers.add_parser("apply", help="Execute Easy Apply automation on approved queue jobs")
    parser_apply.add_argument(
        "--dry-run", action="store_true", default=True, help="Run Easy Apply in Dry Run mode (default: True)"
    )
    parser_apply.add_argument(
        "--no-dry-run", action="store_false", dest="dry_run", help="Disable Dry Run mode and submit real applications"
    )

    # 7. login
    subparsers.add_parser("login", help="Launch Chrome headful browser for one-time manual LinkedIn login")

    # 8. lint
    subparsers.add_parser("lint", help="Run Ruff auto-fix linter and code formatter")

    # 9. autofill (diagnostics and learning vault audit)
    parser_autofill = subparsers.add_parser("autofill", help="Inspect ATS autofill diagnostic logs and learning vault")
    parser_autofill.add_argument(
        "--audit", action="store_true", default=True, help="Display recent events and banked lessons"
    )

    # 10. test (standardized regression test suite)
    parser_test = subparsers.add_parser("test", help="Run standardized regression test runner")
    parser_test.add_argument(
        "--tier",
        choices=["core", "autofill", "all"],
        default="core",
        help="Test tier to execute: core (fast ~5-10s), autofill (~30s), or all",
    )
    parser_test.add_argument(
        "--live",
        action="store_true",
        help="Run live browser and remote career portal tests",
    )

    # 11. session (portable Playwright storageState)
    parser_session = subparsers.add_parser(
        "session", help="Manage portable Playwright storageState sessions without SingletonLock"
    )
    parser_session.add_argument(
        "action",
        choices=["status", "export"],
        nargs="?",
        default="status",
        help="Session action: 'status' (default) or 'export'",
    )
    parser_session.add_argument("--output", help="Optional output path for exported storage_state.json")

    # 12. daily (automated morning workflow + email briefing)
    parser_daily = subparsers.add_parser(
        "daily", help="Run automated morning workflow (regressions -> search -> email -> dashboard)"
    )
    parser_daily.add_argument(
        "action",
        choices=["run", "audit", "diagnose"],
        nargs="?",
        default="run",
        help="Action: 'run' (default), 'audit' (view history), or 'diagnose' (system health)",
    )
    parser_daily.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode (default: True)",
    )
    parser_daily.add_argument(
        "--no-email",
        action="store_false",
        dest="send_email",
        help="Skip sending executive email briefing",
    )
    parser_daily.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip pre-run regression health checks",
    )
    parser_daily.add_argument(
        "--no-dashboard",
        action="store_false",
        dest="launch_dashboard",
        help="Do not auto-ensure dashboard on port 8000",
    )
    parser_daily.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Limit number of runs to show in audit (default: 5)",
    )

    args = parser.parse_args()
    config = load_config(args.config)
    runner = JobSearchPipelineRunner(config)

    cmd = args.command
    if cmd in ["run", "pipeline"]:
        asyncio.run(
            runner.run_full_pipeline(
                skip_sync=args.skip_sync,
                launch_ui=args.launch_ui,
                source=args.source,
                headless=args.headless,
            )
        )
    elif cmd == "search":
        asyncio.run(runner.run_search_stage(source=args.source, headless=args.headless))
    elif cmd in ["sync", "sync-knowledge"]:
        runner.run_sync_stage()
    elif cmd in ["filter", "filterjobs"]:
        runner.run_filter_stage()
    elif cmd == "dashboard":
        runner.run_dashboard_stage()
    elif cmd == "apply":
        asyncio.run(handle_apply(config, dry_run=args.dry_run))
    elif cmd == "login":
        asyncio.run(handle_login(config))
    elif cmd == "lint":
        handle_lint()
    elif cmd == "autofill":
        handle_autofill_audit()
    elif cmd == "test":
        handle_test(tier=args.tier, live=args.live)
    elif cmd == "session":
        handle_session(action=args.action, output=getattr(args, "output", None))
    elif cmd == "daily":
        if args.action == "audit":
            handle_daily_audit(limit=args.limit)
        elif args.action == "diagnose":
            handle_daily_diagnose()
        else:
            handle_daily(
                config,
                headless=args.headless,
                send_email=args.send_email,
                skip_tests=args.skip_tests,
                launch_dashboard=args.launch_dashboard,
            )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
