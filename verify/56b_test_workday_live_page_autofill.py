"""Verification Gate 56b: Live JioStar Workday Portal Autofill & Hydration Probing.

Validates:
1. Live network navigation to https://jiostar.wd102.myworkdayjobs.com/JioStar/...
2. Workday SPA client hydration barrier detection
3. Live 'Apply' trigger click with post-condition verification
4. Live 'Start Your Application' modal traversal to 'Apply Manually'
5. Live Auth Gate detection (Create Account / Sign In inputs)
6. Assertion of element visibility and interactability without live submission
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.autofill.ats_filler import ATSAssistedFiller
from src.autofill.vendor_schemas import load_candidate_master_data
from src.browser.cdp_stealth import launch_stealth_browser


async def test_live_jiostar_workday_flow():
    print("\n🚀 ========================================================")
    print("🚀 Running Verification Gate 56b: Live JioStar Workday Probing")
    print("🚀 ========================================================\n")

    live_url = (
        "https://jiostar.wd102.myworkdayjobs.com/JioStar/job/Bengaluru--We-Work/"
        "Senior-Software-Development-Engineer-Test-II_JR10381?source=LinkedIn"
    )

    master_data = load_candidate_master_data()
    filler = ATSAssistedFiller(headless=False, master_data=master_data)

    print(f"🌐 Launching stealth browser and navigating to live Workday portal: {live_url}")
    _pw, _context, page = await launch_stealth_browser(headless=False)

    try:
        try:
            await page.bring_to_front()
        except Exception:
            pass

        await page.goto(live_url, wait_until="domcontentloaded", timeout=45000)

        # 1. Hydration Barrier Check
        initial_state = await filler._wait_for_workday_ready(page, timeout=15.0)
        print(f"🎯 Live Hydration Barrier detected state = [{initial_state}]")
        assert initial_state in ("overview", "modal", "auth"), f"Unexpected initial state: {initial_state}"

        # 2. If overview, trigger Apply button
        if initial_state == "overview":
            apply_btn = page.locator(
                "[data-automation-id='applyButton'], a[role='button']:has-text('Apply'), button:has-text('Apply'), a:has-text('Apply'), [data-automation-id='adventureButton']"
            ).first
            await apply_btn.wait_for(state="visible", timeout=10000)
            print("🖱️ Clicking live 'Apply' button...")
            await apply_btn.scroll_into_view_if_needed()
            await apply_btn.click()

            # Wait for modal
            modal_el = page.locator(
                "[data-automation-id='applyManually'], a[href*='/apply/applyManually'], button:has-text('Apply Manually')"
            ).first
            await modal_el.wait_for(state="visible", timeout=8000)
            print("✅ Live 'Start Your Application' modal confirmed visible.")

        # 3. Select 'Apply Manually'
        apply_manually = page.locator(
            "[data-automation-id='applyManually'], a[href*='/apply/applyManually'], button:has-text('Apply Manually'), a:has-text('Apply Manually')"
        ).first
        if await apply_manually.is_visible():
            print("📝 Clicking live 'Apply Manually'...")
            await apply_manually.scroll_into_view_if_needed()
            await apply_manually.click()

        # 4. Verify Auth Gate mounts
        email_inp = page.locator("input[data-automation-id='email'], input#email").first
        await email_inp.wait_for(state="visible", timeout=10000)
        print("✅ Live Auth Gate confirmed visible with email field.")

        pwd_inp = page.locator("input[data-automation-id='password'], input#password").first
        assert await pwd_inp.is_visible(), "Password input should be visible on live auth gate"
        print("✅ Live Password input confirmed visible.")

        # Check if Create Account or Sign In is active
        verify_pwd = page.locator("input[data-automation-id='verifyPassword'], input#verifyPassword").first
        is_create_account = await verify_pwd.is_visible()
        mode = "Create Account" if is_create_account else "Sign In"
        print(f"📋 Live Workday Auth Screen Mode: [{mode}]")

        print("\n🎉 ========================================================")
        print("🎉 Verification Gate 56b PASSED: Live Workday Hydration & Navigation Verified!")
        print("🎉 ========================================================\n")

    finally:
        await page.close()
        await _context.close()
        await _pw.stop()


if __name__ == "__main__":
    asyncio.run(test_live_jiostar_workday_flow())
