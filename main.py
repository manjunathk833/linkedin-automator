from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import subprocess
from typing import Any

import uvicorn
import yaml
from playwright.async_api import async_playwright

from src.automation.easy_apply import EasyApplyExecutor
from src.browser.cdp_connector import launch_persistent_browser
from src.filter.job_filter import LinkedInJobFilter
from src.scraper.job_finder import LinkedInJobFinder
from src.tailor.knowledge_translator import KnowledgeBankTranslator


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


async def handle_search(config: dict[str, Any]):
    """Reads search_profiles & discovery settings from config.yaml and runs 4-channel discovery + AI tailorer pipeline."""
    profiles = config.get("search_profiles", [])
    discovery_cfg = config.get("discovery", {})
    if not profiles:
        print("⚠️ No search_profiles found in config.yaml.")
        return

    print("\n" + "=" * 60)
    print("  RUNNING 10X MULTI-CHANNEL JOB DISCOVERY & AI TAILORING PIPELINE")
    print("=" * 60)

    use_ai = config.get("llm", {}).get("use_ai", True)
    finder = LinkedInJobFinder(use_ai=use_ai)
    jobs = await finder.search_all_channels(profiles, discovery_config=discovery_cfg)

    print("\n" + "=" * 60)
    print(f"🎉 MULTI-CHANNEL SEARCH PIPELINE COMPLETE: {len(jobs)} job(s) tailored & queued in data/pending_queue/")
    print("👉 Next Step: Run `python main.py filterjobs` or `python main.py dashboard` on localhost:8000")
    print("=" * 60 + "\n")


def handle_filterjobs():
    """Runs standalone job filter engine on pending queue."""
    job_filter = LinkedInJobFilter()
    job_filter.filter_pending_queue()


def handle_dashboard():
    """Launches FastAPI Approval Gate Dashboard on http://127.0.0.1:8000."""
    print("\n" + "=" * 50)
    print("  LAUNCHING APPROVAL GATE DASHBOARD")
    print("  Access UI at: http://127.0.0.1:8000")
    print("=" * 50 + "\n")
    uvicorn.run("src.ui.app:app", host="127.0.0.1", port=8000, reload=True)


def handle_sync_knowledge(config: dict[str, Any]):
    """Translates candidate_notes.md into master_knowledge_bank.json entries."""
    print("\n" + "=" * 50)
    print("  TRANSLATING CANDIDATE NOTES TO MASTER KNOWLEDGE BANK")
    print("=" * 50)
    use_ai = config.get("llm", {}).get("use_ai", True)
    translator = KnowledgeBankTranslator(use_ai=use_ai)
    res = translator.sync_notes_to_knowledge_bank()
    print("\n" + "=" * 50)
    print(f"✅ KNOWLEDGE SYNC COMPLETE: Added {res.get('added', 0)} new STAR achievement(s).")
    print("=" * 50 + "\n")


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


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Job Search & Application Automation Orchestrator")
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["search", "filterjobs", "dashboard", "lint", "sync-knowledge"],
        help="Pipeline execution mode (search, filterjobs, dashboard, lint, or sync-knowledge)",
    )
    parser.add_argument("--login", action="store_true", help="Launch Chrome for one-time manual LinkedIn login")
    parser.add_argument("--apply", action="store_true", help="Execute Easy Apply automation on approved jobs")
    parser.add_argument(
        "--dry-run", action="store_true", default=True, help="Run Easy Apply in Dry Run mode (default: True)"
    )
    parser.add_argument(
        "--no-dry-run", action="store_false", dest="dry_run", help="Disable Dry Run mode and submit real applications"
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml file")

    args = parser.parse_args()
    config = load_config(args.config)

    if args.login:
        asyncio.run(handle_login(config))
    elif args.mode == "search":
        asyncio.run(handle_search(config))
    elif args.mode == "filterjobs":
        handle_filterjobs()
    elif args.mode == "dashboard":
        handle_dashboard()
    elif args.mode == "sync-knowledge":
        handle_sync_knowledge(config)
    elif args.mode == "lint":
        handle_lint()
    elif args.apply:
        asyncio.run(handle_apply(config, dry_run=args.dry_run))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
