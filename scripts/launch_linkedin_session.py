#!/usr/bin/env python3
"""
LinkedIn Stealth Interactive Session Authenticator
==================================================
Launches headful Google Chrome with persistent profile (.browser_data/)
using CDP stealth evasion (system Chrome channel, no automation flags).
Navigates to https://www.linkedin.com/login for user authentication.
Monitors session state, verifies `li_at` and `JSESSIONID` cookies,
and automatically exports `.browser_data/storage_state.json` upon successful login.

Usage:
    python scripts/launch_linkedin_session.py [--timeout 600]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from typing import Any

from playwright.async_api import BrowserContext, Page

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.browser.cdp_stealth import (
    DEFAULT_STEALTH_DIR,
    launch_stealth_browser,
)

BROWSER_DATA_DIR = DEFAULT_STEALTH_DIR
LOG_FILE = os.path.join(PROJECT_ROOT, "data", "logs", "portal_sessions.log")
SCREENSHOT_DIR = os.path.join(PROJECT_ROOT, "data", "logs", "screenshots")
LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"


def log_event(status: str, message: str) -> None:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    entry = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{status.upper()}] {message}"
    print(entry, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


async def check_linkedin_authenticated(page: Page, context: BrowserContext) -> dict[str, Any]:
    """Inspects LinkedIn cookies and DOM elements for authenticated status."""
    try:
        cookies = await context.cookies()
        li_cookies = {c["name"]: c["value"] for c in cookies if "linkedin" in c.get("domain", "")}

        has_li_at = "li_at" in li_cookies
        has_jsession = "JSESSIONID" in li_cookies
        url = page.url.lower()

        # Check DOM indicators
        has_nav = False
        try:
            nav_el = await page.query_selector(
                "#global-nav, .global-nav__me, .feed-identity-module, [data-control-name='nav.settings']"
            )
            has_nav = nav_el is not None
        except Exception:
            pass

        is_feed = "/feed" in url or "/in/" in url or "/mynetwork" in url or "/jobs" in url
        authenticated = has_li_at and (is_feed or has_nav)

        return {
            "authenticated": authenticated,
            "has_li_at": has_li_at,
            "has_jsession": has_jsession,
            "is_feed": is_feed,
            "has_nav": has_nav,
            "url": page.url,
        }
    except Exception as e:
        return {"authenticated": False, "error": str(e)}


async def main():
    parser = argparse.ArgumentParser(description="Launch stealth Chrome for manual LinkedIn login.")
    parser.add_argument("--timeout", type=int, default=600, help="Max wait time in seconds (default: 600s / 10m)")
    args = parser.parse_args()

    os.makedirs(BROWSER_DATA_DIR, exist_ok=True)
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    log_event("START", f"Launching headful stealth Chrome for LinkedIn login (timeout={args.timeout}s)...")
    log_event("INFO", f"Persistent Profile Directory: {BROWSER_DATA_DIR}")

    playwright_instance, context, page = await launch_stealth_browser(
        user_data_dir=BROWSER_DATA_DIR,
        headless=False,
    )

    log_event("NAVIGATE", f"Navigating to {LINKEDIN_LOGIN_URL}...")
    try:
        await page.goto(LINKEDIN_LOGIN_URL, timeout=30000, wait_until="domcontentloaded")
    except Exception as e:
        log_event("WARN", f"Navigation warning: {e}")

    log_event("WAIT", "Chrome window is open. Please log into your LinkedIn account.")
    log_event("INFO", "Monitoring session status every 3 seconds. Session will save automatically upon sign-in.")

    start_time = time.time()
    logged_in = False

    try:
        while time.time() - start_time < args.timeout:
            stat = await check_linkedin_authenticated(page, context)
            if stat.get("authenticated"):
                logged_in = True
                log_event("SUCCESS", f"✅ LinkedIn authenticated! Feed URL: {stat.get('url')}")
                try:
                    await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "linkedin_authenticated.png"))
                except Exception:
                    pass

                # Export portable storage_state.json
                state_path = os.path.join(BROWSER_DATA_DIR, "storage_state.json")
                try:
                    await context.storage_state(path=state_path)
                    log_event("SAVED", f"Exported persistent storage state: {state_path}")
                except Exception as save_err:
                    log_event("WARN", f"Could not export storage state: {save_err}")

                # Wait 3 seconds for cookies to finalize
                await asyncio.sleep(3)
                break

            await asyncio.sleep(3)

        if not logged_in:
            log_event("TIMEOUT", f"Login window closed or timed out after {args.timeout}s.")

    finally:
        try:
            await context.close()
        except Exception:
            pass
        try:
            await playwright_instance.stop()
        except Exception:
            pass
        log_event("FINISH", "Browser context closed cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
