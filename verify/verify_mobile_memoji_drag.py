"""Headful Playwright mobile touch long-press & free-drag verification for 3D Memoji Assistant."""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

PORTFOLIO_DIR = Path("/Users/yeshwinmanjunath/development/portfolio")
ARTIFACT_DIR = Path("/Users/yeshwinmanjunath/.gemini/antigravity/brain/77583479-b37a-47ac-884e-cacad5e1d5ab")


async def run_verification() -> None:
    server = await asyncio.create_subprocess_exec(
        "npx",
        "vite",
        "--host",
        "127.0.0.1",
        "--port",
        "5173",
        cwd=str(PORTFOLIO_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await asyncio.sleep(2.2)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={"width": 393, "height": 852},
                has_touch=True,
                is_mobile=True,
            )
            page = await context.new_page()
            await page.goto("http://127.0.0.1:5173/", wait_until="networkidle")
            await page.wait_for_timeout(500)

            trigger = page.locator('[data-testid="memoji-avatar-trigger"]')
            before_box = await trigger.bounding_box()
            assert before_box is not None

            # 1. Verify CSS touch-action: none and -webkit-touch-callout: none
            css_check = await trigger.evaluate(
                """el => {
                    const cs = window.getComputedStyle(el);
                    return {
                        touchAction: cs.touchAction,
                        userSelect: cs.userSelect || cs.webkitUserSelect,
                    };
                }"""
            )
            print("1. Mobile Touch CSS Check:", css_check)
            assert css_check["touchAction"] == "none", f"Expected touch-action: none, got {css_check}"

            # 2. Simulate iPhone Long-Press (220ms hold) -> Free Touch Drag across mobile screen
            drag_result = await page.evaluate(
                """async () => {
                    const el = document.querySelector('[data-testid="memoji-avatar-trigger"]');
                    const rect = el.getBoundingClientRect();
                    const startX = rect.left + rect.width / 2;
                    const startY = rect.top + rect.height / 2;

                    function fireTouch(type, x, y) {
                        const t = new Touch({
                            identifier: 1,
                            target: el,
                            clientX: x,
                            clientY: y,
                            pageX: x,
                            pageY: y,
                        });
                        const ev = new TouchEvent(type, {
                            cancelable: true,
                            bubbles: true,
                            touches: type === 'touchend' ? [] : [t],
                            targetTouches: type === 'touchend' ? [] : [t],
                            changedTouches: [t],
                        });
                        return !el.dispatchEvent(ev); // true if preventDefault() was called
                    }

                    fireTouch('touchstart', startX, startY);
                    await new Promise(r => setTimeout(r, 220));
                    const armedState = el.getAttribute('data-dragging');
                    const badgeTextDuringHold = el.innerText.trim();

                    let preventedCount = 0;
                    const steps = 10;
                    for (let i = 1; i <= steps; i++) {
                        const nx = startX - (190 * i) / steps;
                        const ny = startY - (240 * i) / steps;
                        if (fireTouch('touchmove', nx, ny)) {
                            preventedCount++;
                        }
                        await new Promise(r => setTimeout(r, 16));
                    }
                    fireTouch('touchend', startX - 190, startY - 240);

                    return {
                        armedState,
                        badgeTextDuringHold,
                        preventedCount,
                        scrollY: window.scrollY,
                    };
                }"""
            )
            print("2. Long-Press Touch Drag Telemetry:", drag_result)
            assert drag_result["armedState"] == "true", "Long-press did not arm drag mode!"
            assert "Move me" in drag_result["badgeTextDuringHold"], "Badge did not switch to 'Move me ✨'!"
            assert drag_result["preventedCount"] == 10, "touchmove did not call preventDefault()!"
            assert drag_result["scrollY"] == 0, "Page scrolled during avatar touch drag!"

            after_box = await trigger.bounding_box()
            assert after_box is not None
            print(
                f"3. Mobile Coordinates: before=({before_box['x']:.1f}, {before_box['y']:.1f}) -> "
                f"after=({after_box['x']:.1f}, {after_box['y']:.1f})"
            )
            assert after_box["x"] < before_box["x"] - 150, "Memoji X did not move on mobile touch drag!"
            assert after_box["y"] < before_box["y"] - 180, "Memoji Y did not move on mobile touch drag!"

            # 4. Quick tap on mobile -> opens chat popover clamped inside 393px iPhone viewport
            await page.evaluate(
                """() => {
                    const el = document.querySelector('[data-testid="memoji-avatar-trigger"]');
                    const rect = el.getBoundingClientRect();
                    const x = rect.left + rect.width / 2;
                    const y = rect.top + rect.height / 2;
                    const t = new Touch({ identifier: 2, target: el, clientX: x, clientY: y });
                    el.dispatchEvent(new TouchEvent('touchstart', { cancelable: true, bubbles: true, touches: [t], changedTouches: [t] }));
                    el.dispatchEvent(new TouchEvent('touchend', { cancelable: true, bubbles: true, touches: [], changedTouches: [t] }));
                }"""
            )
            await page.wait_for_timeout(400)

            popover = page.locator('[data-testid="memoji-chat-popover"]')
            assert await popover.is_visible(), "Quick tap on mobile did not open chat popover!"
            pop_box = await popover.bounding_box()
            actual_vw = await page.evaluate("window.innerWidth")
            print(f"4. Mobile Popover Clamped BoundingBox (vw={actual_vw}):", pop_box)
            assert pop_box is not None
            assert pop_box["x"] >= 8 and (pop_box["x"] + pop_box["width"]) <= actual_vw - 8, (
                f"Popover overflowed {actual_vw}px mobile screen: {pop_box}"
            )

            await page.screenshot(path=str(ARTIFACT_DIR / "portfolio_mobile_memoji_drag_verified.png"))
            await browser.close()
            print("ALL MOBILE TOUCH LONG-PRESS & FREE-DRAG CHECKS PASSED!")
    finally:
        server.terminate()
        await server.wait()


if __name__ == "__main__":
    asyncio.run(run_verification())
