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
        state_file = os.path.join(profile_dir, "storage_state.json")
        await context.storage_state(path=state_file)
        await context.close()
        print(f"✅ LinkedIn session & cookies saved to {state_file} successfully!\n")


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
    """Prints a diagnostics audit report of recent autofill events, telemetry benchmarks, and learning vault lessons."""
    from src.autofill.autofill_logger import AutofillLogger

    logger = AutofillLogger.get_logger()
    summary = logger.get_audit_summary(limit=10)
    telemetry = summary.get("telemetry", {})

    print("\n" + "=" * 72)
    print("  ATS AUTOFILL CONTINUOUS TELEMETRY & LEARNING VAULT AUDIT")
    print("=" * 72)

    print("\n⚡ Phase A Batch Form Telemetry (data/logs/autofill_benchmarks.jsonl):")
    print(f"  • Total Batch Runs Logged : {telemetry.get('total_batch_runs', 0)}")
    print(f"  • Avg Phase A Coverage    : {telemetry.get('avg_coverage_pct', 0.0)}%")
    print(f"  • Avg Phase A Speed       : {telemetry.get('avg_duration_ms', 0.0)} ms")
    print(f"  • Auto-Learned Mappings   : {telemetry.get('total_learned_mappings', 0)} custom questions banked")

    learned_list = telemetry.get("learned_mappings", [])
    if learned_list:
        print("\n🔁 Recently Auto-Learned Custom Mappings (data/logs/learned_field_mappings.json):")
        for lm in learned_list[:5]:
            print(
                f"  • [{lm.get('control_type', 'text')}] '{lm.get('label')}' -> '{lm.get('value')}' (used {lm.get('use_count', 1)}x)"
            )

    top_unmapped = telemetry.get("top_unmapped_fields", [])
    if top_unmapped:
        print("\n📋 Top Recurring Unmapped Custom Questions (data/logs/unmapped_fields_backlog.jsonl):")
        for uf in top_unmapped[:5]:
            print(
                f"  • ({uf.get('count', 1)}x) [{uf.get('last_vendor', 'GENERIC')}] {uf.get('label')} ({uf.get('control_type')})"
            )

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

    print("\n" + "=" * 72 + "\n")


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
                social = r.get("social_leads_count", 0)
                naukri = r.get("naukri_status", "N/A")
                print(f"     • Jobs Staged: {staged} ({dream} Dream Orgs) | Social Leads: {social}")
                print(f"     • Naukri Touch: {naukri} | Regressions: {reg} | Email: {em} | Duration: {dur}s")
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


def handle_posts(
    action: str = "list",
    date_filter: str = "past-24h",
    limit: int = 15,
    headless: bool = True,
):
    """Handles LinkedIn Hiring Posts Tracker CLI subcommands."""
    from src.storage.database import ApplicationDatabase

    db = ApplicationDatabase()

    if action == "discover":
        from src.posts.post_tracker import LinkedInPostTracker

        print("\n" + "=" * 65)
        print("  LINKEDIN HIRING POSTS DISCOVERY ENGINE (Track 3)")
        print(f"  Date Filter: {date_filter} | Headless: {headless}")
        print("=" * 65 + "\n")
        tracker = LinkedInPostTracker(db=db)
        discovered = asyncio.run(tracker.discover_posts(date_filter=date_filter, headless=headless))
        print(f"\n🎉 Finished! Discovered and banked {len(discovered)} new lead(s).")
    elif action == "stats":
        stats = db.get_hiring_posts_stats()
        print("\n" + "=" * 60)
        print("  LINKEDIN HIRING POSTS & INBOUND LEADS METRICS")
        print("=" * 60)
        for k, v in stats.items():
            print(f"  • {k.replace('_', ' ').title():24s}: {v}")
        print("=" * 60 + "\n")
    else:  # list
        posts = db.get_hiring_posts(limit=limit)
        print("\n" + "=" * 75)
        print(f"  SAVED HIRING POSTS & INBOUND OUTREACH LEADS (Top {len(posts)})")
        print("=" * 75)
        if not posts:
            print("  No hiring posts saved yet. Run `python main.py posts discover` to fetch leads.")
        for p in posts:
            author = p.get("author_name", "Unknown")
            role_cat = p.get("author_role_category", "PEER")
            company = p.get("company_name", "Enterprise")
            score = p.get("quality_score", 0)
            status = p.get("outreach_status", "NEW")
            rel_time = p.get("posted_at_relative", "")
            emails = ", ".join(p.get("extracted_emails", [])) or "None"
            dream_flag = "⭐ " if p.get("is_dream_org") else ""
            print(f"  [{status}] {dream_flag}{author} ({role_cat}) @ {company}")
            print(f"       Score: {score}/100 | Time: {rel_time} | Emails: {emails}")
            post_url = p.get("post_url", "")
            if post_url:
                print(f"       Link: {post_url}")
            print("-" * 75)
        print("\n")


def _ensure_cdp_page_target(cdp_url: str = "http://127.0.0.1:9222") -> None:
    """Ensures at least one browser window/page target exists on macOS Chrome before connect_over_cdp."""
    import urllib.request

    try:
        with urllib.request.urlopen(f"{cdp_url}/json/list", timeout=2) as resp:
            targets = json.loads(resp.read().decode("utf-8"))
        page_targets = [t for t in targets if t.get("type") == "page"]
        if not page_targets:
            req = urllib.request.Request(f"{cdp_url}/json/new?about:blank", method="PUT")
            urllib.request.urlopen(req, timeout=3).read()
    except Exception:
        pass


async def _run_form_batch_async(
    action: str = "inspect",
    job_id: str = "",
    url: str = "",
    resume_path: str = "",
    actions_json: str = "{}",
    cdp_url: str = "http://127.0.0.1:9222",
) -> None:
    """Connects to persistent Chrome over CDP and runs 2-phase batch form inspection or custom action fill."""
    from src.autofill.batch_form_engine import UniversalBatchFormFiller

    _ensure_cdp_page_target(cdp_url)

    # Resolve job_id from data/approved_queue if provided
    if job_id and not (url and resume_path):
        approved_file = os.path.join("data", "approved_queue", f"{job_id}.json")
        if os.path.exists(approved_file):
            with open(approved_file, encoding="utf-8") as f:
                payload = json.load(f)
            if not url:
                url = (
                    payload.get("url")
                    or payload.get("job_url")
                    or payload.get("direct_link")
                    or payload.get("job_details", {}).get("url", "")
                )
            if not resume_path:
                cand_pdf = payload.get("resume_pdf_path") or os.path.join(
                    "data", "approved_queue", f"resume_{job_id}.pdf"
                )
                if cand_pdf and os.path.exists(cand_pdf):
                    resume_path = os.path.abspath(cand_pdf)
                else:
                    import glob
                    import re as _re

                    comp = (payload.get("job_details", {}).get("company") or payload.get("company_name") or "").strip()
                    num_id = "".join(_re.findall(r"\d+", job_id))[:8]
                    for pdf_f in glob.glob(os.path.join("data", "approved_queue", "*.pdf")):
                        base_f = os.path.basename(pdf_f).lower()
                        if (num_id and num_id in base_f) or (comp and comp.lower().split()[0] in base_f):
                            resume_path = os.path.abspath(pdf_f)
                            break

    filler = UniversalBatchFormFiller()
    async with async_playwright() as p:
        _ensure_cdp_page_target(cdp_url)
        browser = await p.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        pages = context.pages
        page = None

        if url:
            for pg in pages:
                if url in (pg.url or ""):
                    page = pg
                    break
            if page is None:
                page = pages[-1] if pages else await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(1.5)
        else:
            # Find the tab with the most visible interactive form fields (penalizing LinkedIn browse tabs without Easy Apply modal)
            best_score = -1000
            for pg in reversed(pages):
                try:
                    score = await pg.evaluate(
                        """() => {
                            const els = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), select, textarea'));
                            const visCnt = els.filter(el => {
                                const r = el.getBoundingClientRect();
                                return r.width > 0 && r.height > 0;
                            }).length;
                            if (visCnt === 0) return -1000;
                            const isLiBrowse = location.hostname.includes('linkedin.com') && !document.querySelector('.jobs-easy-apply-modal, .jobs-easy-apply-content');
                            return (visCnt * 10) - (isLiBrowse ? 500 : 0);
                        }"""
                    )
                    if score > best_score:
                        best_score = score
                        page = pg
                except Exception:
                    pass
            if page is None:
                page = pages[-1] if pages else await context.new_page()

        if action == "apply":
            parsed_actions = json.loads(actions_json) if actions_json else {}
            res = await filler.apply_custom_actions(page, parsed_actions)
            print(json.dumps(res, indent=2))
        else:
            res = await filler.inspect_and_autofill_step(page, resume_pdf_path=resume_path or None)
            print(json.dumps(res, indent=2))


async def _run_referral_scout_async(
    company_filter: str = "",
    cdp_url: str = "http://127.0.0.1:9222",
) -> None:
    """Dynamically scouts low-key verified SDET/EM referral contacts on LinkedIn for approved/target jobs."""
    import re
    from pathlib import Path

    from src.tailor.referral_generator import ReferralNoteGenerator, score_referral_candidate

    targets: list[dict[str, str]] = []
    q_dir = Path("data/approved_queue")
    if q_dir.exists():
        for jf in sorted(q_dir.glob("*.json")):
            try:
                payload = json.loads(jf.read_text(encoding="utf-8"))
                jd = payload.get("job_details", payload)
                comp = (jd.get("company") or jd.get("company_name") or "").strip()
                if not comp:
                    continue
                if company_filter and company_filter.lower() not in comp.lower():
                    continue
                targets.append(
                    {
                        "company": comp,
                        "role": jd.get("title") or jd.get("job_title") or "Senior SDET",
                        "req_id": str(jd.get("job_id") or jf.stem),
                        "job_url": (
                            payload.get("url") or payload.get("job_url") or jd.get("url") or jd.get("job_url") or ""
                        ),
                    }
                )
            except Exception:
                pass

    if not targets and company_filter:
        targets.append(
            {
                "company": company_filter,
                "role": "Senior SDET",
                "req_id": "N/A",
                "job_url": "",
            }
        )

    if not targets:
        print("ℹ️ No target jobs found in data/approved_queue/. Pass --company <Name> or stage a job first.")
        return

    recon_path = Path("data/logs/referral_reconnaissance.json")
    recon_path.parent.mkdir(parents=True, exist_ok=True)
    recon_data: dict[str, Any] = {}
    if recon_path.exists():
        try:
            recon_data = json.loads(recon_path.read_text(encoding="utf-8"))
        except Exception:
            recon_data = {}

    async with async_playwright() as p:
        _ensure_cdp_page_target(cdp_url)
        browser = await p.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        page = context.pages[0]

        for t in targets:
            comp = t["company"]
            urls = ReferralNoteGenerator.build_linkedin_people_search_urls(comp)
            people_url = urls["company_people_sdet"]
            print(f"🔍 Scouting verified SDET/QE peers for {comp} -> {people_url}")
            await page.goto(people_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3.5)
            await page.evaluate("() => window.scrollTo(0, 900)")
            await asyncio.sleep(1.5)

            raw_cards = await page.evaluate(
                """() => {
                    const cards = Array.from(document.querySelectorAll('.org-people-profile-card__profile-info, li.org-people-profiles-module__profile-item'));
                    return cards.map(c => {
                        const a = c.querySelector('a[href*="/in/"]');
                        return {
                            text: c.innerText.trim(),
                            href: a ? a.href.split('?')[0] : ''
                        };
                    }).filter(x => x.href);
                }"""
            )

            scored_leads = []
            seen = set()
            for item in raw_cards:
                href = item["href"]
                if href in seen:
                    continue
                seen.add(href)
                lines = [ln.strip() for ln in item["text"].split("\n") if ln.strip()]
                if len(lines) < 2:
                    continue
                name = re.sub(r"\s*(1st|2nd|3rd\+?|\bdegree connection\b).*", "", lines[0], flags=re.IGNORECASE).strip()
                deg = "1st" if "1st" in item["text"] else ("2nd" if "2nd" in item["text"] else "3rd")
                headline = next(
                    (
                        ln
                        for ln in lines[1:]
                        if not re.search(
                            r"(degree connection|mutual connection|^Connect$|^Message$|^Follow$)", ln, re.IGNORECASE
                        )
                    ),
                    lines[1],
                )
                mutual_m = re.search(r"(\d+)\s+other\s+mutual", item["text"], re.IGNORECASE)
                mutual_cnt = (
                    (int(mutual_m.group(1)) + 1)
                    if mutual_m
                    else (1 if "mutual connection" in item["text"].lower() else 0)
                )

                score_info = score_referral_candidate(
                    {
                        "name": name,
                        "headline": headline,
                        "connection_degree": deg,
                        "mutual_count": mutual_cnt,
                        "from_company_people_tab": True,
                    },
                    target_company=comp,
                )
                if score_info["excluded"]:
                    continue

                payload = {
                    "company_name": comp,
                    "job_title": t["role"],
                    "requisition_id": t["req_id"],
                    "job_url": t["job_url"],
                }
                fname = name.split()[0] if name else "there"
                scored_leads.append(
                    {
                        "name": name,
                        "first_name": fname,
                        "url": href,
                        "connection_degree": deg,
                        "headline": headline,
                        "reply_score": score_info["score"],
                        "tier": score_info["tier"],
                        "reasons": score_info["reasons"],
                        "connection_note": ReferralNoteGenerator.generate_connection_note(
                            payload, recipient_name=fname
                        ),
                        "post_acceptance_dm": ReferralNoteGenerator.generate_post_acceptance_dm(
                            payload, recipient_name=fname
                        ),
                        "inmail_pitch": ReferralNoteGenerator.generate_inmail_pitch(payload, recipient_name=fname),
                    }
                )

            scored_leads.sort(key=lambda x: x["reply_score"], reverse=True)
            recon_data[comp] = {
                "target_role": t["role"],
                "target_req_id": t["req_id"],
                "job_url": t["job_url"],
                "leads": scored_leads[:5],
            }
            print(f"✅ Discovered {len(scored_leads)} high-probability contacts for {comp} (saved top 5).")

    recon_path.write_text(json.dumps(recon_data, indent=2), encoding="utf-8")
    print(f"\n📂 Updated local referral reconnaissance pack: {recon_path}")


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

    # 13. posts (Track 3: Recruiter, Lead & Peer Hiring Posts Tracker)
    parser_posts = subparsers.add_parser(
        "posts", help="Track 3: Discover, classify, and track hiring posts from engineers, leads, and recruiters"
    )
    parser_posts.add_argument(
        "action",
        choices=["discover", "list", "stats"],
        nargs="?",
        default="list",
        help="Action: 'list' (default), 'discover' (search LinkedIn feed/content), or 'stats'",
    )
    parser_posts.add_argument(
        "--date-filter",
        choices=["past-24h", "past-week"],
        default="past-week",
        help="Date filter for LinkedIn content search: 'past-week' (default) or 'past-24h'",
    )
    parser_posts.add_argument(
        "--limit",
        type=int,
        default=15,
        help="Limit number of posts to list (default: 15)",
    )
    parser_posts.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run browser in headless mode (default: False, runs headful visible)",
    )

    # 14. form-batch (2-Phase Extract-Map-BatchExecute high-speed form engine)
    parser_batch = subparsers.add_parser(
        "form-batch", help="High-speed 2-phase DOM schema extractor & deterministic batch form filler"
    )
    parser_batch.add_argument(
        "action",
        choices=["inspect", "apply"],
        nargs="?",
        default="inspect",
        help="Action: 'inspect' (extract schema & batch-fill known fields) or 'apply' (apply custom field JSON)",
    )
    parser_batch.add_argument("--job-id", default="", help="Job ID from data/approved_queue/")
    parser_batch.add_argument("--url", default="", help="Optional target URL to open/inspect")
    parser_batch.add_argument("--resume", default="", help="Optional path to tailored resume PDF")
    parser_batch.add_argument("--actions", default="{}", help="JSON mapping of {field_id_or_label: value} for 'apply'")

    # 15. referral-scout (Dynamic LinkedIn low-key referral contact scout)
    parser_scout = subparsers.add_parser(
        "referral-scout", help="Dynamically scout & score low-key SDET/EM referral contacts on LinkedIn via Chrome CDP"
    )
    parser_scout.add_argument(
        "--company", default="", help="Optional company name filter (defaults to all jobs in data/approved_queue/)"
    )

    # 16. portal-sniper (Cycle 2: <24h Official Career Portal Delta Scanner for CI/CD & Local)
    parser_sniper = subparsers.add_parser(
        "portal-sniper",
        help="Cycle 2: Poll all 100+ explicit org portals & package <24h fresh SDET/QA drops into data/ci_inbox/",
    )
    parser_sniper.add_argument(
        "--hours",
        type=float,
        default=24.0,
        help="Maximum job age in hours to qualify as a fresh drop (default: 24.0)",
    )
    parser_sniper.add_argument(
        "--ci-mode",
        action="store_true",
        default=False,
        help="Run in headless CI mode (outputs data/ci_inbox/latest_ci_drops.json + latest_daily_report.md)",
    )
    parser_sniper.add_argument(
        "--auto-ingest",
        action="store_true",
        default=False,
        help="Immediately onboard discovered fresh drops into local SQLite and data/pending_queue/",
    )

    # 17. sync-ci (Cloud-to-Local CI Drop Auto-Ingestor)
    parser_syncci = subparsers.add_parser(
        "sync-ci",
        help="Onboard <24h fresh drops from data/ci_inbox/latest_ci_drops.json (or origin/ci-job-drops) into SQLite & pending_queue/",
    )
    parser_syncci.add_argument(
        "--fetch-remote",
        action="store_true",
        default=False,
        help="Fetch latest data/ci_inbox/latest_ci_drops.json from origin/ci-job-drops git branch first",
    )

    # 18. org-research (Cycle 1: Explicit Organization Watchlist Auditor & Endpoint Fingerprinter)
    parser_orgres = subparsers.add_parser(
        "org-research",
        help="Cycle 1: Audit explicit organization watchlist coverage or probe a company slug across ATS providers",
    )
    parser_orgres.add_argument("--probe", default="", help="Optional company slug to probe across all ATS providers")
    parser_orgres.add_argument("--audit", action="store_true", help="Audit live endpoint responsiveness for watchlist")
    parser_orgres.add_argument("--limit", type=int, default=15, help="Number of watchlist orgs to live-probe in audit")

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
    elif cmd == "posts":
        handle_posts(
            action=args.action,
            date_filter=getattr(args, "date_filter", "past-24h"),
            limit=getattr(args, "limit", 15),
            headless=getattr(args, "headless", True),
        )
    elif cmd == "form-batch":
        asyncio.run(
            _run_form_batch_async(
                action=args.action,
                job_id=getattr(args, "job_id", ""),
                url=getattr(args, "url", ""),
                resume_path=getattr(args, "resume", ""),
                actions_json=getattr(args, "actions", "{}"),
            )
        )
    elif cmd == "referral-scout":
        asyncio.run(
            _run_referral_scout_async(
                company_filter=getattr(args, "company", ""),
            )
        )
    elif cmd == "portal-sniper":
        from src.ingestion.ci_sync import CISyncIngestor
        from src.ingestion.portal_sniper import PortalSniperEngine

        sniper = PortalSniperEngine(max_age_hours=getattr(args, "hours", 24.0))
        bundle = asyncio.run(sniper.execute_scan())
        print("\n" + "=" * 70)
        print("  🎯 PORTAL SNIPER (<24H FRESH DROPS) SCAN SUMMARY")
        print("=" * 70)
        print(f"  • Explicit Orgs Polled    : {bundle['total_orgs_polled']}")
        print(f"  • Total SDET/QA Matches   : {bundle['total_sdet_matches_scanned']}")
        print(f"  • Verified Fresh Drops    : {bundle['fresh_drops_count']} (<= {bundle['max_age_hours']}h)")
        print(f"  • Filtered (Already Seen) : {bundle['skipped_already_seen']}")
        print(f"  • Filtered (Older Window) : {bundle['skipped_older_than_window']}")
        print(f"  • Output JSON             : {sniper.drops_path}")
        print(f"  • Output Markdown Report  : {sniper.report_path}")
        print("=" * 70 + "\n")
        if getattr(args, "auto_ingest", False):
            ing = CISyncIngestor(use_ai=runner.use_ai).sync_latest_drops(fetch_remote=False)
            print(f"📥 Auto-Ingested {ing['ingested_count']} fresh drop(s) into local pending_queue/ & SQLite!")
    elif cmd == "sync-ci":
        from src.ingestion.ci_sync import CISyncIngestor

        ing = CISyncIngestor(use_ai=False).sync_latest_drops(fetch_remote=getattr(args, "fetch_remote", False))
        print("\n" + "=" * 65)
        print("  📥 CLOUD-TO-LOCAL CI DROP SYNC SUMMARY")
        print("=" * 65)
        print(f"  • Remote Branch Pulled : {ing.get('pulled_remote')}")
        print(f"  • New Jobs Ingested    : {ing.get('ingested_count')}")
        print(f"  • Duplicates Skipped   : {ing.get('skipped_duplicates')}")
        if ing.get("ingested_job_ids"):
            for jid in ing["ingested_job_ids"][:15]:
                print(f"    + {jid}")
        print("=" * 65 + "\n")
    elif cmd == "org-research":
        from src.ingestion.org_researcher import OrgResearcher

        researcher = OrgResearcher()
        probe_slug = getattr(args, "probe", "").strip()
        if probe_slug:
            res = asyncio.run(researcher.probe_company_slug(probe_slug, probe_slug))
            print(json.dumps(res, indent=2))
        elif getattr(args, "audit", False):
            audit_res = asyncio.run(researcher.audit_watchlist_health(limit=getattr(args, "limit", 15)))
            print(json.dumps(audit_res, indent=2))
        else:
            summary = researcher.get_watchlist_Breakdown()
            print("\n" + "=" * 65)
            print("  🔭 EXPLICIT ORGANIZATION WATCHLIST BREAKDOWN (Cycle 1)")
            print("=" * 65)
            print(f"  • Total Explicit Orgs : {summary['total_companies']}")
            print(f"  • Active Monitored    : {summary['active_companies']}")
            print(f"  • Dream Organizations : {summary['dream_orgs']}")
            print("  • Adapter Distribution:")
            for prov, cnt in sorted(summary["by_provider"].items(), key=lambda x: x[1], reverse=True):
                print(f"    - {prov:18s}: {cnt}")
            print("=" * 65 + "\n")
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
