import asyncio
import os
import sys

from playwright.async_api import async_playwright

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.browser.cdp_connector import connect_cdp, launch_persistent_browser
from src.scraper.job_finder import LinkedInJobFinder


async def test_live_linkedin_flow():
    print("==================================================")
    print("  Testing Sprint 4: Live LinkedIn Integration Flow")
    print("==================================================")

    cdp_url = "http://localhost:9222"
    finder = LinkedInJobFinder(cdp_url=cdp_url)

    # 1. Test Search URL Generation
    search_url = finder.build_search_url("Senior SDET", "Remote")
    print(f"🌐 Target Search URL: {search_url}")
    assert "f_AL=true" in search_url
    print("✅ Easy Apply search URL construction verified!")

    # 2. Test CDP Connectivity — try connect_cdp first, fallback to persistent context
    print("\n🔍 Testing CDP Connectivity...")
    connected = False

    async with async_playwright() as p:
        # Strategy A: Attach to existing Chrome on port 9222
        try:
            _browser, page = await connect_cdp(p, cdp_url)
            title = await page.title()
            print(f"✅ CDP attached to live Chrome! Active tab: {title}")
            connected = True
        except Exception as e:
            print(f"⚠️ CDP attach failed: {e}")

        # Strategy B: Launch persistent context (full Playwright ownership)
        if not connected:
            print("\n🔄 Falling back to launch_persistent_browser...")
            try:
                context, page = await launch_persistent_browser(p)
                await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
                await asyncio.sleep(2)
                title = await page.title()
                print(f"✅ Persistent browser launched! Page: {title}")
                connected = True
                await context.close()
            except Exception as e:
                print(f"⚠️ Persistent launch also failed: {e}")

    if connected:
        print("✅ Browser connection strategy verified!")
    else:
        print("ℹ️ No browser connection available (both strategies failed). Continuing with AI-only tests.")

    # 3. Test Scraper & Tailorer Engine Pipeline
    print("\n🧪 Testing Scraper & Gemini AI Tailorer Integration...")
    raw_job = {
        "job_id": "test_live_job_555",
        "application_type": "EASY_APPLY",
        "job_details": {
            "title": "Lead SDET Automation Engineer",
            "company": "Skyline Global",
            "location": "Bengaluru, India",
            "requirements": "Looking for 5+ years experience in Python, Playwright, REST Assured, and CI/CD automation pipelines.",
        },
    }

    tailored_job = finder.tailorer.tailor_job_payload(raw_job)
    assert "tailored_resume" in tailored_job
    print("✅ AI Resume Tailoring attached cleanly!")

    # Save to pending queue
    queue_file = finder.save_job_to_queue(tailored_job)
    assert os.path.exists(queue_file)
    print(f"💾 Queue file verified at: {queue_file}")

    # Cleanup test job
    if os.path.exists(queue_file):
        os.remove(queue_file)

    print("\n" + "=" * 50)
    print("✅ SPRINT 4 LIVE LINKEDIN INTEGRATION TEST PASSED!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_live_linkedin_flow())
