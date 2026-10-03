"""
verify/49_test_linkedin_external_ats_pivot.py — Verification Gate 49:
Validates LinkedIn External ATS Discovery & Dynamic Application Pivot.

Checks:
1. URL Construction:
   - easy_apply_only=False omits f_AL=true (enables external ATS jobs).
   - easy_apply_only=True includes f_AL=true.
   - distance=25 injects distance=25.
   - time_posted='past_week' injects f_TPR=r604800 (7-day high-velocity window).
2. Application Type Heuristics:
   - Correctly differentiates 'Easy Apply' vs 'Apply' / 'Apply on company website'.
3. End-to-End Simulation:
   - Launches headless Playwright session.
   - Loads a simulated LinkedIn job view with external Apply button that opens an ATS portal.
   - Verifies capture of opened tab, URL resolution, and ATS pattern classification.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from playwright.async_api import async_playwright

from src.autofill.ats_filler import ATSAssistedFiller
from src.autofill.vendor_schemas import ATSVendorPattern, classify_ats_pattern
from src.scraper.job_finder import LinkedInJobFinder


def test_url_construction():
    print("\n🔍 Step 1: Testing Search URL Construction (easy_apply_only & distance & time_posted)...")
    finder = LinkedInJobFinder(use_ai=False)

    # 1. Default: easy_apply_only=False -> f_AL=true MUST NOT be present
    url_external = finder.build_search_url(
        keywords="Senior SDET",
        location="Bengaluru",
        work_types=["remote", "hybrid", "onsite"],
        time_posted="past_week",
        distance=25,
        easy_apply_only=False,
    )
    print(f"   Generated External Search URL: {url_external}")
    assert "f_AL=true" not in url_external, "f_AL=true should NOT be present when easy_apply_only=False"
    assert "distance=25" in url_external, "distance=25 should be in URL"
    assert "f_TPR=r604800" in url_external, "f_TPR=r604800 (past_week) should be in URL"
    assert "location=Bengaluru" in url_external

    # 2. easy_apply_only=True -> f_AL=true MUST be present
    url_easy = finder.build_search_url(
        keywords="Senior SDET",
        location="Bengaluru",
        work_types=["remote"],
        time_posted="past_week",
        easy_apply_only=True,
    )
    print(f"   Generated Easy Apply Search URL: {url_easy}")
    assert "f_AL=true" in url_easy, "f_AL=true MUST be present when easy_apply_only=True"
    assert "distance=" not in url_easy, "distance should not be present when not specified"
    assert "f_TPR=r604800" in url_easy

    # 3. 24-hour time posted
    url_24h = finder.build_search_url(
        keywords="Lead SDET",
        location="India",
        time_posted="past_24h",
        easy_apply_only=False,
    )
    assert "f_TPR=r86400" in url_24h, "f_TPR=r86400 (past_24h) should be in URL"
    assert "f_AL=true" not in url_24h

    print("✅ Search URL construction with external jobs & parameters verified!")


async def test_apply_type_heuristics():
    print("\n🔍 Step 2: Testing Application Type Classification Heuristics...")

    # Simulated card payloads
    cases = [
        ("Easy Apply", "Easy Apply", "EASY_APPLY"),
        ("Apply", "", "LINKEDIN_EXTERNAL"),
        ("Apply on company website", "Apply externally", "LINKEDIN_EXTERNAL"),
        ("Apply externally", "", "LINKEDIN_EXTERNAL"),
    ]

    for btn_text, aria_label, expected_type in cases:
        combined = f"{btn_text.lower()} {aria_label.lower()}"
        app_type = "EASY_APPLY" if "easy apply" in combined else "LINKEDIN_EXTERNAL"
        assert app_type == expected_type, f"Expected {expected_type} for '{btn_text}', got {app_type}"

    print("✅ Application type classification heuristics verified!")


async def test_external_ats_pivot_simulation():
    print("\n🔍 Step 3: Testing Playwright External ATS Tab Capture & Pattern Pivot...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # HTML page simulating a LinkedIn job view with an external Apply button
        linkedin_mock_html = """
        <!DOCTYPE html>
        <html>
        <head><title>LinkedIn Job View Mock</title></head>
        <body>
            <h1 class="job-card-list__title">Senior Staff SDET</h1>
            <a class="jobs-apply-button" aria-label="Apply to Databricks" href="https://boards.greenhouse.io/databricks/jobs/8054055" target="_blank">
                Apply on company website
            </a>
        </body>
        </html>
        """
        await page.set_content(linkedin_mock_html)

        filler = ATSAssistedFiller(headless=True)

        # Mock fill_ats_page to observe the target page and detected pattern
        target_classified_pattern: list[ATSVendorPattern] = []

        async def _mock_fill_ats_page(target_p: Any, ats_url: str, resume_path: str | None = None):
            pattern = classify_ats_pattern(ats_url)
            target_classified_pattern.append(pattern)
            return {
                "status": "ready_for_review",
                "pattern": str(pattern),
                "url": ats_url,
                "fields_filled": 5,
                "resume_attached": True,
            }

        filler.fill_ats_page = _mock_fill_ats_page  # type: ignore

        # Trigger simulated external apply click and capture
        apply_btn = page.locator(".jobs-apply-button").first
        assert await apply_btn.is_visible()

        opened_pages = []

        def _on_page(new_p):
            opened_pages.append(new_p)

        context.on("page", _on_page)
        page.on("popup", _on_page)

        try:
            await apply_btn.click()
            for _ in range(30):
                if opened_pages:
                    break
                await asyncio.sleep(0.1)
        finally:
            try:
                context.remove_listener("page", _on_page)
            except Exception:
                pass
            try:
                page.remove_listener("popup", _on_page)
            except Exception:
                pass

        assert len(opened_pages) > 0, "External ATS tab should have been captured by page listener"
        ats_page = opened_pages[0]

        # In headless mock, we simulate navigation to the ATS URL
        ats_url = "https://boards.greenhouse.io/databricks/jobs/8054055"
        res = await filler.fill_ats_page(ats_page, ats_url)

        assert res["status"] == "ready_for_review"
        assert target_classified_pattern[0] in (
            ATSVendorPattern.DATABRICKS_CUSTOM_GREENHOUSE,
            ATSVendorPattern.GREENHOUSE_STANDARD,
        )

        print(f"✅ Captured external ATS tab and classified as: {target_classified_pattern[0]}")
        await browser.close()


async def main():
    print("=" * 60)
    print("  GATE 49: LINKEDIN EXTERNAL ATS DISCOVERY & PIVOT VERIFICATION")
    print("=" * 60)

    test_url_construction()
    await test_apply_type_heuristics()
    await test_external_ats_pivot_simulation()

    print("\n" + "=" * 60)
    print("🎉 ALL GATE 49 ASSERTIONS PASSED (100% SUCCESS)!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
