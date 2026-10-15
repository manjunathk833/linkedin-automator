"""
Portable Browser Session & StorageState Manager.
Enables exporting and importing Playwright authentication snapshots (cookies, localStorage)
to avoid SingletonLock crashes when running background automations alongside active Chrome sessions.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

from src.browser.cdp_connector import launch_persistent_browser

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_STATE_PATH = PROJECT_ROOT / ".browser_data" / "storage_state.json"
DEFAULT_PROFILE_DIR = PROJECT_ROOT / ".browser_data"


class SessionManager:
    """
    Manages Playwright portable storage state snapshots (cookies, origins).
    """

    def __init__(self, state_path: Path | str | None = None, profile_dir: Path | str | None = None):
        self.state_path = Path(state_path or DEFAULT_STATE_PATH)
        self.profile_dir = Path(profile_dir or DEFAULT_PROFILE_DIR)

    async def export_storage_state(self, output_path: Path | str | None = None) -> str:
        """
        Launches persistent context briefly to snapshot cookies & storage into a portable JSON file.
        """
        dest = Path(output_path or self.state_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            context, _ = await launch_persistent_browser(
                p,
                profile_dir=str(self.profile_dir),
                headless=True,
            )
            await context.storage_state(path=str(dest))
            await context.close()

        print(f"💾 Exported Playwright storage state to: {dest}")
        return str(dest)

    def get_session_status(self) -> dict[str, Any]:
        """
        Inspects stored storage_state.json for LinkedIn authentication cookies (li_at).
        """
        if not self.state_path.exists():
            return {
                "exists": False,
                "path": str(self.state_path),
                "is_authenticated": False,
                "has_li_at": False,
                "cookie_count": 0,
                "message": f"Storage state file not found at {self.state_path}. Run `python main.py session export`.",
            }

        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            cookies = data.get("cookies", [])
            li_at = next((c for c in cookies if c.get("name") == "li_at"), None)
            jsessionid = next((c for c in cookies if c.get("name") == "JSESSIONID"), None)

            expires_str = "N/A"
            is_expired = False
            if li_at and li_at.get("expires"):
                exp_ts = li_at["expires"]
                exp_dt = datetime.datetime.fromtimestamp(exp_ts, datetime.timezone.utc)
                expires_str = exp_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                is_expired = exp_dt < datetime.datetime.now(datetime.timezone.utc)

            is_valid = bool(li_at and not is_expired)

            return {
                "exists": True,
                "path": str(self.state_path),
                "is_authenticated": is_valid,
                "has_li_at": bool(li_at),
                "has_jsessionid": bool(jsessionid),
                "li_at_expires": expires_str,
                "is_expired": is_expired,
                "cookie_count": len(cookies),
                "message": "Valid authenticated LinkedIn session." if is_valid else "Session missing or expired.",
            }
        except Exception as e:
            return {
                "exists": True,
                "path": str(self.state_path),
                "is_authenticated": False,
                "error": str(e),
                "message": f"Failed to parse storage state: {e}",
            }
