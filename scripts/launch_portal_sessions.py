#!/usr/bin/env python3
"""
Portal Session Bootstrapper & Interactive Authenticator
======================================================
Launches headful Google Chrome with the persistent profile (.browser_data/)
using CDP stealth evasion (system Chrome channel, no automation flags).
Opens Hirist.tech and Instahyre.com so the candidate can complete login/OTP.
Monitors session state, verifies cookies, and saves authenticated sessions.

Usage:
    python scripts/launch_portal_sessions.py [--timeout 600] [--headless]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from typing import Any

from playwright.async_api import BrowserContext, Page

# Project Root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.browser.cdp_stealth import (
    DEFAULT_STEALTH_DIR,
    launch_stealth_browser,
)

BROWSER_DATA_DIR = DEFAULT_STEALTH_DIR
LOG_FILE = os.path.join(PROJECT_ROOT, "data", "logs", "portal_sessions.log")
SCREENSHOT_DIR = os.path.join(PROJECT_ROOT, "data", "logs", "screenshots")

HIRIST_URL = "https://www.hirist.tech/login"
INSTAHYRE_URL = "https://www.instahyre.com/candidate/opportunities/"


def log_event(status: str, message: str) -> None:
    """Logs timestamped event to stdout and log file."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    entry = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{status.upper()}] {message}"
    print(entry, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


async def check_hirist_authenticated(page: Page, context: BrowserContext) -> dict[str, Any]:
    """Inspects Hirist cookies and DOM elements for logged-in status."""
    try:
        cookies = await context.cookies()
        hirist_cookies = {c["name"]: c["value"] for c in cookies if "hirist" in c.get("domain", "")}

        # Auth cookie indicators
        has_auth_cookie = any(
            k in hirist_cookies
            for k in ("auth_token", "token", "hirist_token", "user_id", "accessToken", "hiristSession")
        )

        # DOM indicators: check if user avatar, candidate dashboard, or logout is visible
        has_profile_dom = False
        try:
            profile_el = await page.query_selector(
                ".user-profile, .profile-icon, .avatar, [href*='myprofile'], [href*='dashboard'], .userDropdown, [href*='jobfeed']"
            )
            has_profile_dom = profile_el is not None
        except Exception:
            pass

        # Check if URL redirected to an authenticated dashboard
        url_auth = (
            "/candidate/" in page.url or "/myprofile" in page.url or "/jobfeed" in page.url
        ) and "login" not in page.url

        is_auth = (has_auth_cookie and "login" not in page.url) or has_profile_dom or url_auth
        return {
            "authenticated": is_auth,
            "url": page.url,
            "cookies": list(hirist_cookies.keys()),
            "has_profile_dom": has_profile_dom,
        }
    except Exception as e:
        return {"authenticated": False, "error": str(e)}


async def check_instahyre_authenticated(page: Page, context: BrowserContext) -> dict[str, Any]:
    """Inspects Instahyre cookies and DOM elements for logged-in status."""
    try:
        cookies = await context.cookies()
        insta_cookies = {c["name"]: c["value"] for c in cookies if "instahyre" in c.get("domain", "")}

        # Instahyre candidate auth is governed by 'sessionid' and candidate URL
        has_session = "sessionid" in insta_cookies

        # DOM indicators: candidate opportunities feed or profile navigation
        has_cand_dom = False
        try:
            cand_el = await page.query_selector(
                ".candidate-nav, #candidate-profile, [href*='/candidate/'], .opportunity-row, #opportunities, [ng-controller*='Candidate']"
            )
            has_cand_dom = cand_el is not None
        except Exception:
            pass

        # Check URL
        url_auth = "candidate/opportunities" in page.url and "login" not in page.url and "google" not in page.url

        is_auth = (has_session and "login" not in page.url and "google" not in page.url) or has_cand_dom or url_auth
        return {
            "authenticated": is_auth,
            "url": page.url,
            "has_sessionid": has_session,
            "cookies": list(insta_cookies.keys()),
            "has_cand_dom": has_cand_dom,
        }
    except Exception as e:
        return {"authenticated": False, "error": str(e)}


async def main():
    parser = argparse.ArgumentParser(description="Launch stealth browser for Hirist & Instahyre login verification.")
    parser.add_argument("--timeout", type=int, default=600, help="Max wait time in seconds (default: 600s / 10m)")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode (default: headful)")
    args = parser.parse_args()

    os.makedirs(BROWSER_DATA_DIR, exist_ok=True)
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    log_event("START", f"Launching stealth Chrome session (headless={args.headless}, timeout={args.timeout}s)...")
    log_event("INFO", f"Browser Profile Directory: {BROWSER_DATA_DIR}")

    # Launch using native system Google Chrome with anti-detection bypass
    playwright_instance, context, page1 = await launch_stealth_browser(
        user_data_dir=BROWSER_DATA_DIR,
        headless=args.headless,
    )

    hirist_page = page1
    instahyre_page = await context.new_page()

    log_event("NAVIGATE", f"Tab 1 -> Hirist: {HIRIST_URL}")
    try:
        await hirist_page.goto(HIRIST_URL, timeout=30000, wait_until="domcontentloaded")
    except Exception as e:
        log_event("WARN", f"Hirist navigation warning: {e}")

    log_event("NAVIGATE", f"Tab 2 -> Instahyre: {INSTAHYRE_URL}")
    try:
        await instahyre_page.goto(INSTAHYRE_URL, timeout=30000, wait_until="domcontentloaded")
    except Exception as e:
        log_event("WARN", f"Instahyre navigation warning: {e}")

    start_time = time.time()
    log_event("WAIT", "Stealth Chrome window is open. Please complete login on Hirist (Tab 1) and Instahyre (Tab 2).")
    log_event("INFO", "Active monitoring running every 4 seconds. Session will persist automatically upon sign-in.")

    hirist_ok = False
    instahyre_ok = False

    while time.time() - start_time < args.timeout:
        # Check Hirist
        if not hirist_ok:
            h_stat = await check_hirist_authenticated(hirist_page, context)
            if h_stat.get("authenticated"):
                hirist_ok = True
                log_event(
                    "SUCCESS", f"✅ Hirist authenticated! URL: {h_stat.get('url')} | Cookies: {h_stat.get('cookies')}"
                )
                try:
                    await hirist_page.screenshot(path=os.path.join(SCREENSHOT_DIR, "hirist_authenticated.png"))
                except Exception:
                    pass

        # Check Instahyre
        if not instahyre_ok:
            i_stat = await check_instahyre_authenticated(instahyre_page, context)
            if i_stat.get("authenticated"):
                instahyre_ok = True
                log_event(
                    "SUCCESS",
                    f"✅ Instahyre authenticated! URL: {i_stat.get('url')} | Cookies: {i_stat.get('cookies')}",
                )
                try:
                    await instahyre_page.screenshot(path=os.path.join(SCREENSHOT_DIR, "instahyre_authenticated.png"))
                except Exception:
                    pass

        if hirist_ok and instahyre_ok:
            log_event("ALL_AUTHENTICATED", "🎉 BOTH Hirist and Instahyre authenticated successfully!")
            break

        remaining = int(args.timeout - (time.time() - start_time))
        if remaining % 20 == 0 or remaining <= 10:
            h_msg = "AUTHENTICATED" if hirist_ok else "Awaiting login..."
            i_msg = "AUTHENTICATED" if instahyre_ok else "Awaiting login..."
            log_event("POLL", f"Status [{remaining}s remaining] -> Hirist: {h_msg} | Instahyre: {i_msg}")

        await asyncio.sleep(4.0)

    # Final snapshot
    final_h = await check_hirist_authenticated(hirist_page, context)
    final_i = await check_instahyre_authenticated(instahyre_page, context)

    print("\n" + "=" * 60, flush=True)
    print("AUTHENTICATION AUDIT REPORT:", flush=True)
    print(
        f"Hirist Status:    {'✅ Logged In' if final_h.get('authenticated') else '❌ Not Logged In'} ({final_h.get('url')})",
        flush=True,
    )
    print(
        f"Instahyre Status: {'✅ Logged In' if final_i.get('authenticated') else '❌ Not Logged In'} ({final_i.get('url')})",
        flush=True,
    )
    print("=" * 60 + "\n", flush=True)

    await context.close()
    await playwright_instance.stop()


if __name__ == "__main__":
    asyncio.run(main())
