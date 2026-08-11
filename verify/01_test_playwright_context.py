import asyncio
import os

from playwright.async_api import async_playwright


async def run_playwright():
    user_data_dir = os.path.join(os.getcwd(), ".browser_data")
    print(f"Using browser profile directory: {user_data_dir}")

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(user_data_dir=user_data_dir, headless=False)

        pages = browser.pages
        page = pages[0] if pages else await browser.new_page()

        print("Navigating to https://www.linkedin.com/jobs")
        await page.goto("https://www.linkedin.com/jobs", wait_until="networkidle")

        await page.wait_for_timeout(3000)

        current_url = page.url
        print(f"Current URL: {current_url}")

        if "login" in current_url or "signup" in current_url:
            print("Status: User is NOT logged in. Redirected to authentication flow.")
        else:
            print("Status: User appears to be in an active session or on a public page.")

        screenshot_path = os.path.join(os.getcwd(), "verify", "session_check.png")
        await page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to: {screenshot_path}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(run_playwright())
