"""
Hardened CDP Stealth Browser Context Manager for LinkedIn & ATS Ingestion.
Patches CDP inspection leaks, masks webdriver flags, and emulates authentic macOS Chrome fingerprints.
Supports dynamic drop-in of rebrowser-playwright or standard Playwright.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from typing import Any

# Default directory for persistent stealth session data
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_STEALTH_DIR = os.path.join(PROJECT_ROOT, ".browser_data")

STEALTH_EVASION_JS = """
(() => {
    // 1. Remove navigator.webdriver artifact
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
        configurable: true
    });

    // 2. Mock authentic Chrome object if missing or incomplete
    if (!window.chrome) {
        window.chrome = {};
    }
    if (!window.chrome.runtime) {
        window.chrome.runtime = {
            OnInstalledReason: { CHROME_UPDATE: "chrome_update", INSTALL: "install", SHARED_MODULE_UPDATE: "shared_module_update", UPDATE: "update" },
            OnRestartRequiredReason: { APP_UPDATE: "app_update", OS_UPDATE: "os_update", PERIODIC: "periodic" },
            PlatformArch: { ARM: "arm", ARM64: "arm64", MIPS: "mips", MIPS64: "mips64", X86_32: "x86-32", X86_64: "x86-64" },
            PlatformNaclArch: { ARM: "arm", MIPS: "mips", MIPS64: "mips64", X86_32: "x86-32", X86_64: "x86-64" },
            PlatformOs: { ANDROID: "android", CROS: "cros", LINUX: "linux", MAC: "mac", OPENBSD: "openbsd", WIN: "win" },
            RequestUpdateCheckStatus: { NO_UPDATE: "no_update", THROTTLED: "throttled", UPDATE_AVAILABLE: "update_available" }
        };
    }
    if (!window.chrome.loadTimes) {
        window.chrome.loadTimes = function() {
            return {
                commitLoadTime: Date.now() / 1000 - 0.5,
                connectionInfo: "h2",
                finishDocumentLoadTime: Date.now() / 1000 - 0.1,
                finishLoadTime: Date.now() / 1000,
                firstPaintAfterLoadTime: 0,
                firstPaintTime: Date.now() / 1000 - 0.4,
                navigationType: "Other",
                npnNegotiatedProtocol: "h2",
                requestTime: Date.now() / 1000 - 0.6,
                startLoadTime: Date.now() / 1000 - 0.6,
                wasAlternateProtocolAvailable: false,
                wasFetchedViaSpdy: true,
                wasNpnNegotiated: true
            };
        };
    }
    if (!window.chrome.csi) {
        window.chrome.csi = function() {
            return {
                onloadT: Date.now(),
                pageT: 1200.0,
                startE: Date.now() - 1200,
                tran: 15
            };
        };
    }

    // 3. Emulate authentic macOS Chrome plugins
    if (!navigator.plugins || navigator.plugins.length === 0) {
        const mockPlugins = [
            { name: "PDF Viewer", filename: "internal-pdf-viewer", description: "Portable Document Format" },
            { name: "Chrome PDF Viewer", filename: "internal-pdf-viewer", description: "Portable Document Format" },
            { name: "Chromium PDF Viewer", filename: "internal-pdf-viewer", description: "Portable Document Format" },
            { name: "Microsoft Edge PDF Viewer", filename: "internal-pdf-viewer", description: "Portable Document Format" },
            { name: "WebKit built-in PDF", filename: "internal-pdf-viewer", description: "Portable Document Format" }
        ];
        Object.defineProperty(navigator, 'plugins', {
            get: () => mockPlugins,
            configurable: true
        });
    }

    // 4. Emulate authentic notification permissions query
    const originalQuery = window.navigator.permissions ? window.navigator.permissions.query : null;
    if (originalQuery) {
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    }

    // 5. Ensure languages reflect natural English browser
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en'],
        configurable: true
    });
})();
"""


def get_playwright_module():
    """
    Returns rebrowser_playwright.async_api if available, otherwise falls back to standard playwright.async_api.
    """
    try:
        import rebrowser_playwright.async_api as pw_api

        print("🛡️ Anti-Detection Engine: rebrowser-playwright (CDP runtime patch active)")
        return pw_api
    except ImportError:
        import playwright.async_api as pw_api

        print("🛡️ Anti-Detection Engine: standard Playwright (Stealth JS & Chrome flags active)")
        return pw_api


def clean_stale_browser_processes(user_data_dir: str, force: bool = False) -> int:
    """
    Finds and cleanly terminates orphaned Chrome or Chromium processes that are bound
    to the target user_data_dir, preventing profile lock collisions and renderer crashes.
    Safely removes Singleton lock files only after processes are dead.
    """
    norm_dir = os.path.abspath(user_data_dir)
    try:
        res = subprocess.run(["ps", "-A", "-o", "pid,ppid,command"], capture_output=True, text=True, check=False)
        pids = []
        current_pid = os.getpid()
        for line in res.stdout.splitlines():
            if norm_dir in line and ("Google Chrome" in line or "chromium" in line or "chrome" in line.lower()):
                parts = line.strip().split(None, 2)
                if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                    pid = int(parts[0])
                    ppid = int(parts[1])
                    if pid != current_pid and (force or ppid == 1):
                        pids.append(pid)

        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass

        if pids:
            time.sleep(0.4)
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass

        # Clean lock files only if no active Chrome process is currently bound
        active_bound = False
        res_check = subprocess.run(["ps", "-A", "-o", "pid,command"], capture_output=True, text=True, check=False)
        for line in res_check.stdout.splitlines():
            if norm_dir in line and ("Google Chrome" in line or "chromium" in line or "chrome" in line.lower()):
                parts = line.strip().split(None, 1)
                if parts and parts[0].isdigit() and int(parts[0]) != current_pid:
                    active_bound = True
                    break

        if not active_bound:
            for lock_file in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
                lock_path = os.path.join(norm_dir, lock_file)
                if os.path.lexists(lock_path):
                    try:
                        os.remove(lock_path)
                    except Exception:
                        pass

        return len(pids)
    except Exception:
        return 0


def is_browser_context_alive(context: Any) -> bool:
    """Verifies whether the Playwright browser context and at least one page are alive and accessible."""
    if not context:
        return False
    try:
        pages = getattr(context, "pages", [])
        return len(pages) > 0 and not pages[0].is_closed()
    except Exception:
        return False


async def launch_stealth_browser(
    user_data_dir: str = DEFAULT_STEALTH_DIR,
    headless: bool = False,
    extra_args: list[str] | None = None,
) -> tuple[Any, Any, Any]:
    """
    Launches an anti-detection hardened persistent browser context using system Google Chrome.
    Ensures stale processes are terminated and locks cleaned to prevent concurrent profile collisions.

    Returns:
        tuple: (playwright_instance, context, page)
    """
    os.makedirs(user_data_dir, exist_ok=True)
    clean_stale_browser_processes(user_data_dir)

    pw_api = get_playwright_module()
    playwright_instance = await pw_api.async_playwright().start()

    chrome_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-gpu-shader-disk-cache",
        "--disable-dev-shm-usage",
        "--no-zygote",
        "--remote-debugging-port=9222",
        "--start-maximized",
    ]

    if extra_args:
        chrome_args.extend(extra_args)

    # Launch persistent Chrome context
    try:
        context = await playwright_instance.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="chrome",  # Uses native system Google Chrome on macOS
            headless=headless,
            args=chrome_args,
            no_viewport=True,
            accept_downloads=True,
            ignore_default_args=["--enable-automation"],
        )
    except Exception as e:
        # Fallback to default chromium if native Chrome channel is unavailable
        print(f"⚠️ System Chrome launch warning: {e}. Falling back to Chromium binary...")
        context = await playwright_instance.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            args=chrome_args,
            no_viewport=True,
            accept_downloads=True,
            ignore_default_args=["--enable-automation"],
        )

    # Inject stealth scripts before any page navigation occurs
    await context.add_init_script(STEALTH_EVASION_JS)

    page = context.pages[0] if context.pages else await context.new_page()
    return playwright_instance, context, page


async def verify_stealth_integrity(page: Any) -> dict[str, Any]:
    """
    Audits the current page environment for common bot detection artifacts.
    """
    results = await page.evaluate(
        """() => {
        return {
            webdriver: navigator.webdriver,
            hasChrome: !!window.chrome,
            hasChromeRuntime: !!(window.chrome && window.chrome.runtime),
            pluginCount: navigator.plugins.length,
            languages: navigator.languages,
            userAgent: navigator.userAgent
        };
    }"""
    )
    return results
