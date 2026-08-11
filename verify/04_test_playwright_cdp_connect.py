"""
Playwright CDP Connection Test
Connects to a Chrome instance running with --remote-debugging-port=9222
and verifies we can control it programmatically.
"""

import asyncio
import os

from playwright.async_api import async_playwright


async def test_cdp_connection():
    async with async_playwright() as p:
        print("🔗 Connecting to Chrome via CDP on localhost:9222...")
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")

        contexts = browser.contexts
        print(f"✅ Connected! Found {len(contexts)} browser context(s).")

        # Use the default context (the one Chrome launched with)
        context = contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()

        # Navigate to a test page
        print("🌐 Navigating to https://www.linkedin.com/jobs...")
        await page.goto("https://www.linkedin.com/jobs", wait_until="networkidle")

        current_url = page.url
        title = await page.title()
        print(f"   URL: {current_url}")
        print(f"   Title: {title}")

        # Take a screenshot
        screenshot_path = os.path.join(os.path.dirname(__file__), "cdp_session_check.png")
        await page.screenshot(path=screenshot_path)
        print(f"📸 Screenshot saved to: {screenshot_path}")

        # Check login state
        if "login" in current_url or "signup" in current_url:
            print("⚠️  Status: NOT logged in — redirected to auth.")
        else:
            print("✅ Status: Active session or public page loaded.")

        # Don't close — we just disconnect (Chrome keeps running)
        print("🔌 Disconnecting from CDP (Chrome stays open)...")


if __name__ == "__main__":
    asyncio.run(test_cdp_connection())
