"""Headful Playwright dry-run verification for Mobile Hamburger Navigation Drawer."""

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
            page = await browser.new_page(viewport={"width": 390, "height": 844})
            await page.goto("http://127.0.0.1:5173/", wait_until="networkidle")
            await page.wait_for_timeout(500)

            # 1. Click mobile hamburger menu button
            trigger = page.locator('[data-testid="mobile-menu-trigger"]')
            assert await trigger.is_visible(), "Mobile hamburger button is not visible!"
            await trigger.click()
            await page.wait_for_timeout(500)

            # 2. Verify drawer and all 7 navigation options are visible inside viewport
            drawer = page.locator('[data-testid="mobile-menu-drawer"]')
            assert await drawer.is_visible(), "Mobile menu drawer did not open!"
            drawer_box = await drawer.bounding_box()
            print("1. Mobile Drawer BoundingBox:", drawer_box)
            assert drawer_box is not None and drawer_box["x"] >= 0 and drawer_box["y"] == 0

            expected_links = [
                "Home",
                "Projects",
                "Automation",
                "Blog",
                "Videos",
                "Resume",
                "Contact",
            ]
            for label in expected_links:
                link_el = drawer.locator(f'a:has-text("{label}")')
                assert await link_el.is_visible(), f"Mobile nav option '{label}' not visible!"
                lbox = await link_el.bounding_box()
                assert lbox is not None and lbox["x"] > drawer_box["x"] + 16, (
                    f"Option '{label}' lacks horizontal padding!"
                )
            print("2. Verified all 7 mobile navigation options visible with proper padding!")

            await page.screenshot(path=str(ARTIFACT_DIR / "portfolio_mobile_menu_verified.png"))

            # 3. Click 'Projects' in mobile drawer -> verify navigation & drawer auto-close
            await drawer.locator('a:has-text("Projects")').click()
            await page.wait_for_timeout(500)
            assert page.url.endswith("/projects"), f"Expected /projects URL, got {page.url}"
            assert not await drawer.is_visible(), "Drawer did not auto-close after link click!"
            print("3. Verified clicking 'Projects' navigated to /projects and closed the drawer!")

            await browser.close()
            print("ALL MOBILE HAMBURGER MENU CHECKS PASSED!")
    finally:
        server.terminate()
        await server.wait()


if __name__ == "__main__":
    asyncio.run(run_verification())
