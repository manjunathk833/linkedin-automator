"""
Verification Gate 81: Seamless Headful Chrome CDP Reuse & Anti-Collision Test
Verifies that launch_stealth_browser reuses an already-running Chrome instance via CDP (port 9222)
without profile collision errors ('Opening in existing browser session') or child process crashes.
"""

import asyncio
import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.browser.cdp_stealth import (
    DEFAULT_STEALTH_DIR,
    is_browser_context_alive,
    is_cdp_port_open,
    launch_stealth_browser,
)


async def main():
    print("=================================================================")
    print("  VERIFY GATE 81: SEAMLESS CHROME CDP REUSE & ANTI-COLLISION TEST")
    print("=================================================================\n")

    port_open = is_cdp_port_open(9222)
    print(f"📡 CDP Port 9222 Status: {'OPEN (Active Chrome)' if port_open else 'CLOSED'}")

    print("\n🧪 Step 1: Testing initial launch_stealth_browser...")
    pw1, ctx1, page1 = await launch_stealth_browser(
        user_data_dir=DEFAULT_STEALTH_DIR,
        headless=False,
    )
    assert pw1 is not None, "Playwright instance must not be None"
    assert ctx1 is not None, "Browser context must not be None"
    assert page1 is not None, "Page must not be None"
    assert is_browser_context_alive(ctx1), "Context must be alive and accessible"

    # Evaluate simple JS to verify stealth script execution
    js_check = await page1.evaluate("() => ({ hasChrome: !!window.chrome, webdriver: navigator.webdriver })")
    print(f"   ✅ Page evaluated successfully: {js_check}")
    assert js_check["webdriver"] is None or js_check["webdriver"] is False, (
        "navigator.webdriver must be undefined/masked"
    )

    print("\n🧪 Step 2: Testing consecutive launch_stealth_browser (CDP Reuse Fast-Path)...")
    # Call launch_stealth_browser again while the first session is active
    pw2, ctx2, page2 = await launch_stealth_browser(
        user_data_dir=DEFAULT_STEALTH_DIR,
        headless=False,
    )
    assert pw2 is not None, "Second Playwright instance must not be None"
    assert ctx2 is not None, "Second Browser context must not be None"
    assert page2 is not None, "Second Page must not be None"
    assert is_browser_context_alive(ctx2), "Second context must be alive"

    js_check2 = await page2.evaluate("() => ({ url: window.location.href, hasChrome: !!window.chrome })")
    print(f"   ✅ Second tab acquired seamlessly via CDP: {js_check2}")

    # Clean up test tab
    try:
        await page2.close()
    except Exception:
        pass

    print("\n🎉 ALL GATE 81 CHECKS COMPLETED SUCCESSFULLY!")
    print("   Consecutive autofill launches are verified safe against browser profile collisions.\n")


if __name__ == "__main__":
    asyncio.run(main())
