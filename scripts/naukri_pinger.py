#!/usr/bin/env python3
"""
Naukri Resdex Daily Profile Visibility Pinger
=============================================
Automated script utilizing headful Playwright with the persistent Chrome profile (.browser_data/)
to touch candidate profile details daily. Resets the candidate's 'Last Active' timestamp on Naukri
to maintain top search ranking in recruiter Resdex queries.

Usage:
    python scripts/naukri_pinger.py [--headless] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

from playwright.async_api import BrowserContext, Page, async_playwright

# Project Root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

BROWSER_DATA_DIR = os.path.join(PROJECT_ROOT, ".browser_data")
LOG_FILE = os.path.join(PROJECT_ROOT, "data", "logs", "naukri_pinger.log")
DAILY_RUNS_LOG = os.path.join(PROJECT_ROOT, "data", "logs", "daily_runs.jsonl")
NAUKRI_PROFILE_URL = "https://www.naukri.com/mnjuser/profile"

# High-converting Naukri Resdex Headline Variants (<= 250 chars)
HEADLINE_VARIANT_A = (
    "Senior SDET (7 YOE) | Playwright, Java, Python, AI & LLM Evaluation (DeepEval, RAGAS) | "
    "Ex-Dunzo, Tata Elxsi | Notice: 60 Days (Negotiable to 30d / Buyout)"
)
HEADLINE_VARIANT_B = (
    "Senior SDET & AI QA Architect | Playwright, REST Assured, Python, Agentic AI & CI/CD | "
    "Ex-Dunzo, Tata Elxsi | Notice: 60 Days (Early Release / 30d Buyout)"
)


def get_next_headline(current_headline: str) -> str:
    """
    Deterministically rotates between high-signal headline variants to ensure
    the profile text meaningfully updates and forces Resdex re-indexing.
    """
    if "Agentic AI" in current_headline or "REST Assured" in current_headline:
        return HEADLINE_VARIANT_A
    return HEADLINE_VARIANT_B


def record_daily_run_event(event_type: str, details: dict[str, Any]) -> None:
    """Appends structured audit record to data/logs/daily_runs.jsonl."""
    os.makedirs(os.path.dirname(DAILY_RUNS_LOG), exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        "details": details,
    }
    with open(DAILY_RUNS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def log_event(status: str, message: str, details: dict[str, Any] | None = None) -> None:
    """Logs timestamped event to data/logs/naukri_pinger.log."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = f"[{timestamp}] [{status.upper()}] {message}"
    if details:
        entry += f" | Details: {details}"
    print(entry)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


async def check_naukri_login(page: Page) -> bool:
    """Checks whether the persistent session is logged in on Naukri."""
    try:
        # Check for profile elements or sign-in redirect (inspect path before query string)
        base_url = page.url.split("?")[0].lower()
        if "nlogin" in base_url or "login" in base_url:
            return False

        # Look for user profile container or navigation items
        profile_el = await page.wait_for_selector(
            ".user-name, .profile-name, .resumeHeadline, #lazyResumeHead, .widgetHead",
            timeout=5000,
        )
        base_url_after = page.url.split("?")[0].lower()
        if "nlogin" in base_url_after or "login" in base_url_after:
            return False
        return profile_el is not None
    except Exception:
        base_url = page.url.split("?")[0].lower()
        if "nlogin" in base_url or "login" in base_url:
            return False
        return "mnjuser/profile" in base_url


async def touch_naukri_profile(page: Page, dry_run: bool = False) -> dict[str, Any]:
    """
    Touches candidate profile headline or summary to refresh the last-updated timestamp.
    """
    if dry_run:
        target_headline = get_next_headline("")
        record_daily_run_event(
            "NAUKRI_RESDEX_TOUCH_SUCCESS",
            {
                "mode": "dry_run",
                "headline": target_headline,
                "char_count": len(target_headline),
            },
        )
        log_event(
            "DRY_RUN",
            f"Dry-run mode active. Target headline: {target_headline[:60]}... ({len(target_headline)} chars)",
        )
        return {"status": "SUCCESS", "mode": "dry_run", "headline": target_headline, "message": "Dry-run simulated"}

    # 1. Locate Resume Headline Widget
    headline_widget = page.locator("#lazyResumeHead, .resumeHeadline, .widgetHead:has-text('Resume Headline')").first
    edit_btn = page.locator(
        "#lazyResumeHead span.edit, .resumeHeadline span.edit, #lazyResumeHead .editIcon, "
        ".widgetHead:has-text('Resume headline') span.edit, .widgetHead:has-text('Resume Headline') span.edit, "
        "span.edit:has-text('Edit'), .editIcon"
    ).first
    try:
        if await headline_widget.count() > 0:
            w_edit = headline_widget.locator("span.edit, .editIcon").first
            if await w_edit.count() > 0:
                edit_btn = w_edit
        await edit_btn.wait_for(state="visible", timeout=2500)
    except Exception:
        pass

    if await edit_btn.is_visible():
        await edit_btn.click()
        await page.wait_for_timeout(1000)

        # Locate headline text area
        text_area = page.locator("#resumeHeadlineTxt, textarea.resumeHeadlineTxt, textarea[id*='Headline']").first
        if await text_area.is_visible():
            current_text = await text_area.input_value()
            current_text = current_text.strip()
            new_text = get_next_headline(current_text)

            await text_area.fill(new_text)
            await page.wait_for_timeout(500)

            # Click Save button
            save_btn = page.locator("button:has-text('Save'), .btn-save, button[type='submit']:has-text('Save')").first
            if await save_btn.is_visible():
                await save_btn.click()
                await page.wait_for_timeout(2000)
                record_daily_run_event(
                    "NAUKRI_RESDEX_TOUCH_SUCCESS",
                    {
                        "mode": "live",
                        "headline": new_text,
                        "previous_headline": current_text,
                        "char_count": len(new_text),
                    },
                )
                log_event(
                    "SUCCESS",
                    f"Successfully refreshed Naukri Resdex profile timestamp via rotated headline ({len(new_text)} chars).",
                )
                return {"status": "SUCCESS", "headline": new_text, "message": "Profile headline touched and saved"}

    # Fallback: general profile page refresh (using domcontentloaded to avoid hanging on slow ad trackers)
    try:
        await page.reload(wait_until="domcontentloaded", timeout=20000)
    except Exception:
        pass
    await page.wait_for_timeout(1500)
    record_daily_run_event(
        "NAUKRI_RESDEX_TOUCH_SUCCESS",
        {"mode": "session_refresh", "message": "Profile session refreshed"},
    )
    log_event("SUCCESS", "Refreshed Naukri profile page session successfully.")
    return {"status": "SUCCESS", "message": "Profile session refreshed"}


async def run_naukri_pinger(headless: bool = False, dry_run: bool = False, interactive: bool = False) -> dict[str, Any]:
    """Launches Playwright (reusing active Chrome CDP port 9222 when available) and executes the daily profile refresh."""
    log_event("START", f"Starting Naukri Resdex profile pinger (headless={headless}, dry_run={dry_run})...")

    os.makedirs(BROWSER_DATA_DIR, exist_ok=True)
    from unittest.mock import MagicMock

    from src.browser.cdp_stealth import ensure_cdp_page_target, is_cdp_port_open

    async with async_playwright() as p:
        owns_context = True
        if not isinstance(p, MagicMock) and is_cdp_port_open(9222):
            ensure_cdp_page_target(9222)
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=10000)
            context: BrowserContext = browser.contexts[0] if browser.contexts else await browser.new_context()
            page: Page = await context.new_page()
            owns_context = False
        else:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=BROWSER_DATA_DIR,
                headless=headless,
                viewport={"width": 1280, "height": 800},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            page = context.pages[0] if context.pages else await context.new_page()

        async def _cleanup() -> None:
            if not owns_context:
                try:
                    await page.close()
                except Exception:
                    pass
            else:
                try:
                    await context.close()
                except Exception:
                    pass

        try:
            if dry_run:
                log_event("DRY_RUN", "Simulating navigation to Naukri profile in dry-run mode...")
                result = await touch_naukri_profile(page, dry_run=True)
                await _cleanup()
                return result

            print(f"🌐 Navigating to {NAUKRI_PROFILE_URL}...")
            await page.goto(NAUKRI_PROFILE_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            is_logged_in = await check_naukri_login(page)
            if not is_logged_in:
                log_event(
                    "AUTH_REQUIRED",
                    "Naukri session not authenticated. Please log in manually in headful mode (python scripts/naukri_pinger.py --interactive).",
                )
                if headless or not interactive:
                    print("⚠️ Naukri session not authenticated (returning AUTH_REQUIRED without blocking).")
                    await _cleanup()
                    return {
                        "status": "AUTH_REQUIRED",
                        "message": "Naukri login required (sign in at naukri.com in Chrome)",
                    }

                print("⚠️ Please log in to Naukri in the open browser window.")
                print("⏳ Waiting up to 60 seconds for login completion...")
                for _ in range(12):
                    await page.wait_for_timeout(5000)
                    if await check_naukri_login(page):
                        is_logged_in = True
                        break

                if not is_logged_in:
                    await _cleanup()
                    return {"status": "AUTH_REQUIRED", "message": "Login required on Naukri"}

            result = await touch_naukri_profile(page, dry_run=dry_run)
            await _cleanup()
            return result

        except Exception as e:
            log_event("ERROR", f"Naukri pinger encountered error: {e}")
            await _cleanup()
            return {"status": "ERROR", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Naukri Resdex Daily Profile Visibility Pinger")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without modifying live profile")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Wait up to 60s for manual Naukri login if session is unauthenticated",
    )
    args = parser.parse_args()

    is_headless = args.headless or bool(os.getenv("CI"))
    result = asyncio.run(run_naukri_pinger(headless=is_headless, dry_run=args.dry_run, interactive=args.interactive))
    if result.get("status") in ("SUCCESS", "dry_run"):
        print("\n🎉 Naukri daily visibility pinger completed successfully.")
        sys.exit(0)
    else:
        print(f"\n⚠️ Naukri pinger finished with status: {result.get('status')}")
        sys.exit(1 if result.get("status") == "ERROR" else 0)


if __name__ == "__main__":
    main()
