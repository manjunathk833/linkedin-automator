"""
Verification script for Sprint 1: Humanized Kinematics & CDP Stealth Hardening.
Tests cubic Bézier trajectory generation, log-normal keystroke modeling,
and browser stealth environment integrity.
"""

from __future__ import annotations

import asyncio
import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.browser.cdp_stealth import launch_stealth_browser, verify_stealth_integrity
from src.browser.kinematics import (
    cubic_bezier_point,
    generate_bezier_trajectory,
    get_lognormal_keystroke_delay,
    human_mouse_move,
)


def test_kinematics_math():
    print("==================================================")
    print("  Testing Kinematics Engine Math & Distributions")
    print("==================================================")

    # 1. Test cubic bezier endpoints
    p0 = (0.0, 0.0)
    p1 = (25.0, 50.0)
    p2 = (75.0, 50.0)
    p3 = (100.0, 100.0)

    start_pt = cubic_bezier_point(p0, p1, p2, p3, 0.0)
    end_pt = cubic_bezier_point(p0, p1, p2, p3, 1.0)
    assert abs(start_pt[0] - 0.0) < 1e-5 and abs(start_pt[1] - 0.0) < 1e-5, f"Start point mismatch: {start_pt}"
    assert abs(end_pt[0] - 100.0) < 1e-5 and abs(end_pt[1] - 100.0) < 1e-5, f"End point mismatch: {end_pt}"
    print("✅ Cubic Bézier endpoints verified: B(0)=P0, B(1)=P3")

    # 2. Test trajectory generation
    start = (100.0, 200.0)
    end = (800.0, 600.0)
    steps = 30
    trajectory = generate_bezier_trajectory(start, end, num_steps=steps)
    assert len(trajectory) == steps + 1, f"Expected {steps + 1} points, got {len(trajectory)}"
    # Verify bounds approximately around bounding corridor
    for x, y in trajectory:
        assert -50 <= x <= 1200, f"Trajectory x out of bounds: {x}"
        assert -50 <= y <= 1200, f"Trajectory y out of bounds: {y}"
    print(f"✅ Generated {len(trajectory)} Bézier path coordinates with human tremor jitter.")

    # 3. Test log-normal keystroke distribution
    delays = [get_lognormal_keystroke_delay() for _ in range(500)]
    avg_delay_ms = (sum(delays) / len(delays)) * 1000.0
    min_delay_ms = min(delays) * 1000.0
    max_delay_ms = max(delays) * 1000.0

    assert 40.0 <= min_delay_ms, f"Min delay too low: {min_delay_ms}ms"
    assert max_delay_ms <= 245.0, f"Max delay too high: {max_delay_ms}ms"
    assert 70.0 <= avg_delay_ms <= 130.0, f"Average delay unexpected: {avg_delay_ms}ms"
    print(
        f"✅ Keystroke distribution verified across 500 samples: "
        f"avg={avg_delay_ms:.1f}ms, min={min_delay_ms:.1f}ms, max={max_delay_ms:.1f}ms"
    )


async def test_stealth_browser():
    print("\n==================================================")
    print("  Testing CDP Stealth Context & Detection Evasion")
    print("==================================================")

    pw, context, page = await launch_stealth_browser(
        user_data_dir=os.path.join(PROJECT_ROOT, ".browser_data_test"),
        headless=True,
    )

    try:
        # Navigate to a simple local data URL
        await page.goto(
            "data:text/html,<html><head><title>Stealth Test</title></head><body><h1>Anti-Bot Verification</h1></body></html>"
        )

        # Test mouse movement along Bézier curve
        new_pos = await human_mouse_move(
            page, target_x=350.0, target_y=250.0, current_x=50.0, current_y=50.0, num_steps=15
        )
        assert abs(new_pos[0] - 350.0) < 1e-3, f"Mouse final x mismatch: {new_pos}"
        print("✅ Mouse moved along Bézier curve to target coordinates smoothly.")

        # Check stealth integrity
        audit = await verify_stealth_integrity(page)
        print("\n🔍 Stealth Integrity Audit Report:")
        print(f"   • navigator.webdriver: {audit.get('webdriver')} (Must be None/False/undefined)")
        print(f"   • window.chrome present: {audit.get('hasChrome')} (Must be True)")
        print(f"   • window.chrome.runtime: {audit.get('hasChromeRuntime')} (Must be True)")
        print(f"   • Plugins count: {audit.get('pluginCount')} (Must be > 0)")
        print(f"   • Languages: {audit.get('languages')}")

        assert audit.get("webdriver") is None or audit.get("webdriver") is False, "navigator.webdriver leak detected!"
        assert audit.get("hasChrome") is True, "window.chrome is missing!"
        assert audit.get("hasChromeRuntime") is True, "window.chrome.runtime is missing!"
        assert audit.get("pluginCount", 0) > 0, "navigator.plugins is empty!"
        print("\n✅ ALL STEALTH INTEGRITY CRITERIA PASSED!")

    finally:
        await context.close()
        await pw.stop()


def main():
    test_kinematics_math()
    asyncio.run(test_stealth_browser())
    print("\n" + "=" * 50)
    print("✅ VERIFICATION SCRIPT 27 (KINEMATICS & STEALTH) PASSED!")
    print("=" * 50)


if __name__ == "__main__":
    main()
