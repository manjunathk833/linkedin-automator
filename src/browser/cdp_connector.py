"""
Shared Chrome CDP connection utility.

Uses launch_persistent_context with channel="chrome" to reuse your
existing Chrome profile (cookies, LinkedIn session) while giving
Playwright full browser control — avoiding the Browser.setDownloadBehavior
protocol error that connect_over_cdp triggers on Chrome 151+.
"""

import json
import os
import urllib.request

# Default directory for persistent Playwright session data
DEFAULT_PROFILE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".browser_data"
)


async def connect_cdp(playwright, cdp_url: str = "http://localhost:9222") -> tuple:
    """
    Connect to a running Chrome instance via CDP using the direct WebSocket URL.

    This is a fallback method. It fetches the WebSocket debugger URL from
    Chrome's /json/version endpoint and connects directly, but may still
    hit setDownloadBehavior issues depending on the Chrome version.

    Returns:
        tuple: (browser, page)
    """
    version_url = f"{cdp_url}/json/version"
    try:
        with urllib.request.urlopen(version_url, timeout=5) as resp:
            info = json.loads(resp.read().decode())
    except Exception as e:
        raise ConnectionError(
            f"Cannot reach Chrome on {cdp_url}. "
            f"Launch Chrome with: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222"
        ) from e

    ws_url = info.get("webSocketDebuggerUrl", "")
    if not ws_url:
        raise ConnectionError(f"No webSocketDebuggerUrl found at {version_url}")

    browser_version = info.get("Browser", "unknown")
    print(f"🔗 Chrome CDP connected — {browser_version}")
    print(f"   WebSocket: {ws_url[:60]}...")

    browser = await playwright.chromium.connect_over_cdp(ws_url)
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    page = context.pages[0] if context.pages else await context.new_page()
    return browser, page


async def launch_persistent_browser(
    playwright, profile_dir: str = DEFAULT_PROFILE_DIR, headless: bool = False
) -> tuple:
    """
    Launch Chrome with a persistent profile directory.

    On first run, a real Chrome window opens — log into LinkedIn manually.
    On subsequent runs, the saved cookies/session are reused automatically.

    This method gives Playwright full browser ownership, avoiding all
    CDP protocol errors (setDownloadBehavior, etc).

    Returns:
        tuple: (context, page)
    """
    os.makedirs(profile_dir, exist_ok=True)

    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        channel="chrome",  # Use installed system Chrome
        headless=headless,
        args=["--start-maximized"],
        no_viewport=True,
        accept_downloads=True,
    )

    page = context.pages[0] if context.pages else await context.new_page()
    print(f"🔗 Playwright launched with persistent profile: {profile_dir}")
    return context, page
