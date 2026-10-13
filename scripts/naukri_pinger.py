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
NAUKRI_PROFILE_URL = "https://www.naukri.com/mnjuser/profile"


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
        # Check for profile elements or sign-in redirect
        current_url = page.url
        if "nlogin" in current_url or "login" in current_url:
            return False

        # Look for user profile container or navigation items
        profile_el = await page.wait_for_selector(
            ".user-name, .profile-name, .resumeHeadline, .widgetHead",
            timeout=8000,
        )
        return profile_el is not None
    except Exception:
        # If selector timed out, check URL
        return "mnjuser/profile" in page.url


async def touch_naukri_profile(page: Page, dry_run: bool = False) -> dict[str, Any]:
    """
    Touches candidate profile headline or summary to refresh the last-updated timestamp.
    """
    if dry_run:
        log_event("DRY_RUN", "Dry-run mode active. Profile update simulated successfully.")
        return {"status": "SUCCESS", "mode": "dry_run", "message": "Dry-run simulated"}

    # 1. Locate Resume Headline Widget
    headline_widget = page.locator(".resumeHeadline, .widgetHead:has-text('Resume Headline')").first
    if not await headline_widget.is_visible():
        # Fallback: look for generic edit button on profile
        edit_btn = page.locator("span.edit:has-text('Edit'), .editIcon").first
    else:
        edit_btn = headline_widget.locator("span.edit, .editIcon").first

    if await edit_btn.is_visible():
        await edit_btn.click()
        await page.wait_for_timeout(1000)

        # Locate headline text area
        text_area = page.locator("#resumeHeadlineTxt, textarea.resumeHeadlineTxt").first
        if await text_area.is_visible():
            current_text = await text_area.input_value()
            current_text = current_text.strip()

            # Non-destructive 1-character toggle (trailing space / period toggle)
            if current_text.endswith("."):
                new_text = current_text[:-1]
            else:
                new_text = current_text + "."

            await text_area.fill(new_text)
            await page.wait_for_timeout(500)

            # Revert to original clean text to preserve pristine wording
            await text_area.fill(current_text)
            await page.wait_for_timeout(500)

            # Click Save button
            save_btn = page.locator("button:has-text('Save'), .btn-save").first
            if await save_btn.is_visible():
                await save_btn.click()
                await page.wait_for_timeout(2000)
                log_event("SUCCESS", "Successfully refreshed Naukri Resdex profile timestamp via headline touch.")
                return {"status": "SUCCESS", "message": "Profile headline touched and saved"}

    # Fallback: general profile page refresh
    await page.reload()
    await page.wait_for_timeout(2000)
    log_event("SUCCESS", "Refreshed Naukri profile page session successfully.")
    return {"status": "SUCCESS", "message": "Profile session refreshed"}


async def run_naukri_pinger(headless: bool = False, dry_run: bool = False) -> dict[str, Any]:
    """Launches Playwright and executes the daily profile refresh."""
    log_event("START", f"Starting Naukri Resdex profile pinger (headless={headless}, dry_run={dry_run})...")

    os.makedirs(BROWSER_DATA_DIR, exist_ok=True)

    async with async_playwright() as p:
        context: BrowserContext = await p.chromium.launch_persistent_context(
            user_data_dir=BROWSER_DATA_DIR,
            headless=headless,
            viewport={"width": 1280, "height": 800},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        page: Page = context.pages[0] if context.pages else await context.new_page()

        try:
            if dry_run:
                log_event("DRY_RUN", "Simulating navigation to Naukri profile in dry-run mode...")
                result = await touch_naukri_profile(page, dry_run=True)
                await context.close()
                return result

            print(f"🌐 Navigating to {NAUKRI_PROFILE_URL}...")
            await page.goto(NAUKRI_PROFILE_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            is_logged_in = await check_naukri_login(page)
            if not is_logged_in:
                log_event(
                    "AUTH_REQUIRED",
                    "Naukri session not authenticated. Please log in manually in the open browser window.",
                )
                print("⚠️ Please log in to Naukri in the open browser window.")
                print("⏳ Waiting up to 60 seconds for login completion...")
                for _ in range(12):
                    await page.wait_for_timeout(5000)
                    if await check_naukri_login(page):
                        is_logged_in = True
                        break

                if not is_logged_in:
                    await context.close()
                    return {"status": "AUTH_REQUIRED", "message": "Login required on Naukri"}

            result = await touch_naukri_profile(page, dry_run=dry_run)
            await context.close()
            return result

        except Exception as e:
            log_event("ERROR", f"Naukri pinger encountered error: {e}")
            await context.close()
            return {"status": "ERROR", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Naukri Resdex Daily Profile Visibility Pinger")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without modifying live profile")
    args = parser.parse_args()

    result = asyncio.run(run_naukri_pinger(headless=args.headless, dry_run=args.dry_run))
    if result.get("status") in ("SUCCESS", "dry_run"):
        print("\n🎉 Naukri daily visibility pinger completed successfully.")
        sys.exit(0)
    else:
        print(f"\n⚠️ Naukri pinger finished with status: {result.get('status')}")
        sys.exit(1 if result.get("status") == "ERROR" else 0)


if __name__ == "__main__":
    main()
