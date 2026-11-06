"""
Hardened CDP Stealth Browser Context Manager for LinkedIn & ATS Ingestion.
Patches CDP inspection leaks, masks webdriver flags, and emulates authentic macOS Chrome fingerprints.
Supports dynamic drop-in of rebrowser-playwright or standard Playwright.
"""

from __future__ import annotations

import asyncio
import os
import signal
import socket
import subprocess
import time
from typing import Any

# Default directory for persistent stealth session data
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_STEALTH_DIR = os.path.join(PROJECT_ROOT, ".browser_data")

STEALTH_EVASION_JS = """
(() => {
    // 0. Never tamper with cross-origin CAPTCHA / anti-bot challenge iframes (hCaptcha, reCAPTCHA, Turnstile)
    try {
        const href = (window.location && window.location.href) || '';
        if (window !== window.top && /hcaptcha|recaptcha|cloudflare|turnstile|arkoselabs/i.test(href)) {
            return;
        }
    } catch (e) {
        return;
    }

    // 1. Mask navigator.webdriver on Navigator.prototype ONLY if true (headless fallback).
    // Never define an own-property on navigator instance (which hCaptcha flags via getOwnPropertyDescriptor).
    if (navigator.webdriver === true) {
        try {
            Object.defineProperty(Object.getPrototypeOf(navigator), 'webdriver', {
                get: () => false,
                configurable: true
            });
        } catch (e) {}
    }

    // 2. Mock authentic Chrome object ONLY if missing (headless Chromium fallback)
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

    // 3. Emulate authentic macOS Chrome plugins ONLY if empty (headless fallback)
    if (!navigator.plugins || navigator.plugins.length === 0) {
        const mockPlugins = [
            { name: "PDF Viewer", filename: "internal-pdf-viewer", description: "Portable Document Format" },
            { name: "Chrome PDF Viewer", filename: "internal-pdf-viewer", description: "Portable Document Format" },
            { name: "Chromium PDF Viewer", filename: "internal-pdf-viewer", description: "Portable Document Format" },
            { name: "Microsoft Edge PDF Viewer", filename: "internal-pdf-viewer", description: "Portable Document Format" },
            { name: "WebKit built-in PDF", filename: "internal-pdf-viewer", description: "Portable Document Format" }
        ];
        Object.defineProperty(Object.getPrototypeOf(navigator), 'plugins', {
            get: () => mockPlugins,
            configurable: true
        });
    }

    // 4. Ensure languages reflect natural English browser if missing
    if (!navigator.languages || navigator.languages.length === 0) {
        Object.defineProperty(Object.getPrototypeOf(navigator), 'languages', {
            get: () => ['en-US', 'en'],
            configurable: true
        });
    }
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


def is_cdp_port_open(port: int = 9222) -> bool:
    """Checks whether Chrome is actively listening on the target CDP remote debugging port."""
    for host in ("127.0.0.1", "localhost"):
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            continue
    return False


async def _connect_existing_cdp(
    playwright_instance: Any,
    port: int = 9222,
    inject_stealth_js: bool = False,
) -> tuple[Any, Any, Any] | None:
    """Attempts to attach to an active Chrome instance on the given CDP port."""
    for endpoint in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
        try:
            browser = await playwright_instance.chromium.connect_over_cdp(endpoint, timeout=5000)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            if inject_stealth_js and not getattr(context, "_agy_stealth_injected", False):
                await context.add_init_script(STEALTH_EVASION_JS)
                context._agy_stealth_injected = True
            page = context.pages[0] if context.pages else await context.new_page()
            print("✅ Seamlessly attached to active headful Chrome session via CDP!")
            return playwright_instance, context, page
        except Exception as cdp_err:
            print(f"⚠️ CDP endpoint {endpoint} warning: {cdp_err}")
    return None


def is_browser_context_alive(context: Any) -> bool:
    """Verifies whether the Playwright browser context and at least one page are alive and accessible."""
    if not context:
        return False
    try:
        pages = getattr(context, "pages", [])
        return len(pages) > 0 and not pages[0].is_closed()
    except Exception:
        return False


_ACTIVE_BROWSER_REFS: list[Any] = []
MACOS_CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def _spawn_native_macos_chrome(user_data_dir: str, extra_args: list[str] | None = None) -> None:
    """
    Spawns native macOS Google Chrome in a detached OS session with zero automation flags.
    Because `--enable-automation` is never passed, `navigator.webdriver` is natively `false`
    without needing `--disable-blink-features=AutomationControlled` (which triggers Chrome's
    unsupported-flag warning banner and hCaptcha Enterprise command-line flag detection).
    """
    native_cmd = [
        MACOS_CHROME_BIN,
        "--remote-debugging-port=9222",
        f"--user-data-dir={os.path.abspath(user_data_dir)}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if extra_args:
        native_cmd.extend(extra_args)
    subprocess.Popen(
        native_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


async def launch_stealth_browser(
    user_data_dir: str = DEFAULT_STEALTH_DIR,
    headless: bool = False,
    extra_args: list[str] | None = None,
) -> tuple[Any, Any, Any]:
    """
    Launches an anti-detection hardened browser context using system Google Chrome.
    If an existing Chrome instance is already running with remote debugging port 9222,
    seamlessly connects over CDP to prevent profile lock collisions and reuse session.
    In headful macOS mode, spawns native Google Chrome directly with minimal clean flags
    and attaches via CDP without injecting Page.addScriptToEvaluateOnNewDocument, preserving
    100% authentic hCaptcha / Cloudflare Turnstile iframe integrity.

    Returns:
        tuple: (playwright_instance, context, page)
    """
    os.makedirs(user_data_dir, exist_ok=True)
    pw_api = get_playwright_module()
    playwright_instance = await pw_api.async_playwright().start()

    # Auto-fallback to headless on Linux when DISPLAY is unset (e.g. CI environments)
    import sys

    if not headless and sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        headless = True

    # Fast-Path: Reuse existing active Chrome session via CDP if available
    if is_cdp_port_open(9222):
        print("🔗 Active Chrome detected on CDP port 9222. Connecting over CDP...")
        cdp_tuple = await _connect_existing_cdp(playwright_instance, 9222, inject_stealth_js=headless)
        if cdp_tuple is not None:
            return cdp_tuple
        print("⚠️ CDP connection attempt warning. Falling back to persistent launch...")

    clean_stale_browser_processes(user_data_dir)

    # Headful macOS Native Chrome Launch (Preserves 100% genuine hCaptcha/Turnstile fingerprint)
    if not headless and sys.platform == "darwin" and os.path.exists(MACOS_CHROME_BIN):
        try:
            _spawn_native_macos_chrome(user_data_dir=user_data_dir, extra_args=extra_args)
            for _ in range(25):
                if is_cdp_port_open(9222):
                    break
                await asyncio.sleep(0.25)
            if is_cdp_port_open(9222):
                cdp_tuple = await _connect_existing_cdp(playwright_instance, 9222, inject_stealth_js=False)
                if cdp_tuple is not None:
                    _ACTIVE_BROWSER_REFS.append((playwright_instance, cdp_tuple[1]))
                    return cdp_tuple
        except Exception as native_err:
            print(f"⚠️ Native Chrome spawn warning: {native_err}. Falling back to Playwright launch...")

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

    # Launch persistent Chrome context (Headless / Fallback)
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
        # If Chrome delegated to an existing session ('Opening in existing browser session'), attach via CDP
        await asyncio.sleep(0.5)
        if is_cdp_port_open(9222):
            cdp_tuple = await _connect_existing_cdp(playwright_instance, 9222, inject_stealth_js=headless)
            if cdp_tuple is not None:
                return cdp_tuple

        # Fallback to bundled Chromium with a deterministic isolated profile dir if user_data_dir is locked (EPERM)
        import tempfile

        fallback_dir = os.path.join(tempfile.gettempdir(), "agy_stealth_fallback_profile")
        os.makedirs(fallback_dir, exist_ok=True)
        clean_stale_browser_processes(fallback_dir)
        print(f"⚠️ System Chrome launch warning: {e}. Falling back to isolated Chromium ({fallback_dir})...")
        context = await playwright_instance.chromium.launch_persistent_context(
            user_data_dir=fallback_dir,
            headless=headless,
            args=chrome_args,
            no_viewport=True,
            accept_downloads=True,
            ignore_default_args=["--enable-automation"],
        )

    # Inject stealth scripts when running headless or via launch_persistent_context
    await context.add_init_script(STEALTH_EVASION_JS)

    _ACTIVE_BROWSER_REFS.append((playwright_instance, context))
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
            webdriverOwnProperty: Object.getOwnPropertyDescriptor(navigator, 'webdriver') !== undefined,
            hasChrome: !!window.chrome,
            hasChromeRuntime: !!(window.chrome && window.chrome.runtime),
            pluginCount: navigator.plugins.length,
            languages: navigator.languages,
            userAgent: navigator.userAgent
        };
    }"""
    )
    return results
