"""
LinkedIn Authentication Preflight & Zero-Yield Guard.

The daily pipeline previously reported SUCCESS even when the shared `.browser_data` profile was
logged out of LinkedIn: auth-only surfaces (job collections, company job pages, content/post search)
silently rendered 0 cards and no alert was raised. This module provides:

1. `check_profile_session()`  - offline check for a non-expired `li_at` cookie in the Chrome profile
                                 (Cookies SQLite, read immutably) with `storage_state.json` fallback.
2. `verify_live_session()`    - live check: navigates to /feed/ and detects authwall/login redirects.
3. `capture_zero_yield_evidence()` - screenshot + URL/title dump when an auth-only surface yields 0.
"""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PROFILE_DIR = PROJECT_ROOT / ".browser_data"
SCREENSHOT_DIR = PROJECT_ROOT / "data" / "logs" / "screenshots"

# URL fragments LinkedIn uses when an unauthenticated visitor hits a member-only surface.
AUTH_REDIRECT_MARKERS = ("/authwall", "/login", "/uas/login", "/checkpoint", "/signup", "/start/join")

# Chrome stores expires_utc as microseconds since 1601-01-01.
_CHROME_EPOCH_OFFSET_S = 11644473600


def is_auth_redirect(url: str) -> bool:
    """Returns True if the URL is a LinkedIn login / authwall / checkpoint page."""
    u = (url or "").lower()
    return "linkedin.com" in u and any(m in u for m in AUTH_REDIRECT_MARKERS)


def _li_at_from_cookie_db(profile_dir: Path) -> dict[str, Any] | None:
    cookie_db = profile_dir / "Default" / "Cookies"
    if not cookie_db.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{cookie_db}?immutable=1", uri=True)
        try:
            row = conn.execute(
                "SELECT expires_utc FROM cookies WHERE host_key LIKE '%linkedin.com' AND name = 'li_at' "
                "ORDER BY expires_utc DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
    except Exception:
        return None
    if not row:
        return {"source": "profile_cookie_db", "has_li_at": False, "expires": None}
    expires_utc = int(row[0] or 0)
    expires_dt = (
        datetime.datetime.fromtimestamp(expires_utc / 1_000_000 - _CHROME_EPOCH_OFFSET_S, datetime.timezone.utc)
        if expires_utc
        else None
    )
    return {"source": "profile_cookie_db", "has_li_at": True, "expires": expires_dt}


def _li_at_from_storage_state(profile_dir: Path) -> dict[str, Any] | None:
    state_file = profile_dir / "storage_state.json"
    if not state_file.exists():
        return None
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    li_at = next((c for c in data.get("cookies", []) if c.get("name") == "li_at"), None)
    if not li_at:
        return {"source": "storage_state", "has_li_at": False, "expires": None}
    exp = li_at.get("expires")
    expires_dt = (
        datetime.datetime.fromtimestamp(exp, datetime.timezone.utc)
        if isinstance(exp, (int, float)) and exp > 0
        else None
    )
    return {"source": "storage_state", "has_li_at": True, "expires": expires_dt}


def check_profile_session(profile_dir: str | Path | None = None) -> dict[str, Any]:
    """
    Offline preflight: is there a non-expired LinkedIn `li_at` cookie available to the browser?
    The profile Cookies DB is authoritative; storage_state.json (injected at launch by
    `cdp_connector.launch_persistent_browser`) is accepted as a fallback.
    """
    pdir = Path(profile_dir or DEFAULT_PROFILE_DIR).resolve()
    now = datetime.datetime.now(datetime.timezone.utc)
    sources = [s for s in (_li_at_from_cookie_db(pdir), _li_at_from_storage_state(pdir)) if s]

    for s in sources:
        if s["has_li_at"] and (s["expires"] is None or s["expires"] > now):
            exp = s["expires"]
            return {
                "is_authenticated": True,
                "status": "AUTHENTICATED",
                "source": s["source"],
                "li_at_expires": exp.strftime("%Y-%m-%d %H:%M UTC") if exp else "session",
                "days_remaining": (exp - now).days if exp else None,
                "profile_dir": str(pdir),
                "message": f"LinkedIn session valid (li_at via {s['source']}).",
            }

    expired = any(s["has_li_at"] for s in sources)
    return {
        "is_authenticated": False,
        "status": "EXPIRED" if expired else "LOGGED_OUT",
        "source": ",".join(s["source"] for s in sources) or "none",
        "li_at_expires": None,
        "days_remaining": None,
        "profile_dir": str(pdir),
        "message": (
            "LinkedIn li_at cookie expired. Run `python main.py login` to re-authenticate."
            if expired
            else "No LinkedIn li_at cookie in browser profile. Run `python main.py login` to re-authenticate."
        ),
    }


async def verify_live_session(page: Any, timeout_ms: int = 30000) -> dict[str, Any]:
    """
    Live preflight: loads https://www.linkedin.com/feed/ and checks for authwall/login redirects.
    Returns {"is_authenticated": bool, "status": ..., "final_url": ...}.
    """
    try:
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=timeout_ms)
        final_url = page.url
    except Exception as e:
        return {"is_authenticated": False, "status": "NAV_ERROR", "final_url": "", "message": str(e)}

    if is_auth_redirect(final_url):
        return {
            "is_authenticated": False,
            "status": "AUTHWALL",
            "final_url": final_url,
            "message": "LinkedIn redirected /feed/ to login/authwall. Run `python main.py login`.",
        }
    # Persist fresh authenticated storage_state.json so fallback state never goes stale
    try:
        state_path = DEFAULT_PROFILE_DIR / "storage_state.json"
        if hasattr(page, "context") and hasattr(page.context, "storage_state"):
            await page.context.storage_state(path=str(state_path))
    except Exception:
        pass
    return {
        "is_authenticated": True,
        "status": "AUTHENTICATED",
        "final_url": final_url,
        "message": "Live feed reachable.",
    }


async def capture_zero_yield_evidence(page: Any, surface: str) -> str:
    """Captures a screenshot of an auth-only surface that returned 0 cards. Returns the path or ''."""
    try:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe = "".join(ch if ch.isalnum() else "_" for ch in surface)[:40]
        path = SCREENSHOT_DIR / f"zero_yield_{safe}_{stamp}.png"
        await page.screenshot(path=str(path), full_page=False)
        print(f"   📸 Zero-yield evidence for [{surface}] saved: {path} (url={page.url})")
        return str(path)
    except Exception as e:
        print(f"   ⚠️ Could not capture zero-yield evidence for [{surface}]: {e}")
        return ""


def summarize_yield(channel_yield: dict[str, int], auth_only: tuple[str, ...]) -> str:
    """
    Classifies a LinkedIn run:
    - "OK"                 at least one auth-only surface produced cards
    - "ZERO_YIELD_SUSPECT" authenticated but every auth-only surface returned 0 cards
    """
    visited = [k for k in auth_only if k in channel_yield]
    if visited and all(channel_yield.get(k, 0) == 0 for k in visited):
        return "ZERO_YIELD_SUSPECT"
    return "OK"


__all__ = [
    "AUTH_REDIRECT_MARKERS",
    "capture_zero_yield_evidence",
    "check_profile_session",
    "is_auth_redirect",
    "summarize_yield",
    "verify_live_session",
]

if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(check_profile_session(os.environ.get("PROFILE_DIR")), indent=2))
