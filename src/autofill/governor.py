"""
Application Rate Limiter and Daily Quota Governor.
Guards candidate LinkedIn and ATS accounts by strictly enforcing an application budget cap (≤15/day).
"""

from __future__ import annotations

from typing import Any

from src.storage.database import ApplicationDatabase

DEFAULT_DAILY_LIMIT = 15


class ApplicationGovernor:
    """
    Enforces daily budget governance and safety limits for automated and assisted applications.
    """

    def __init__(self, db: ApplicationDatabase | None = None, daily_limit: int = DEFAULT_DAILY_LIMIT):
        self.db = db or ApplicationDatabase()
        self.daily_limit = daily_limit

    def check_budget(self) -> dict[str, Any]:
        """
        Audits current submission count against the daily safety budget threshold.
        """
        current_count = self.db.get_today_submission_count()
        remaining = max(0, self.daily_limit - current_count)
        allowed = current_count < self.daily_limit

        if not allowed:
            message = (
                f"🛑 Daily budget reached ({current_count}/{self.daily_limit}). "
                "Applications are locked for today to maintain account safety. Quota resets at midnight."
            )
        else:
            message = f"✅ Budget available: {current_count}/{self.daily_limit} used ({remaining} remaining today)."

        return {
            "allowed": allowed,
            "current_count": current_count,
            "daily_limit": self.daily_limit,
            "remaining": remaining,
            "message": message,
        }

    def can_proceed(self) -> bool:
        """Returns True if at least 1 application slot remains today."""
        return self.check_budget()["allowed"]
