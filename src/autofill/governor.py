"""
Application Rate Limiter and Daily Quota Governor.
Guards candidate LinkedIn and ATS accounts with an assisted copilot application budget cap (default ≤200/day).
"""

from __future__ import annotations

import os
from typing import Any

import yaml

from src.storage.database import ApplicationDatabase

DEFAULT_DAILY_LIMIT = 200


class ApplicationGovernor:
    """
    Enforces daily budget governance and safety limits for automated and assisted applications.
    """

    def __init__(self, db: ApplicationDatabase | None = None, daily_limit: int | None = None):
        self.db = db or ApplicationDatabase()
        if daily_limit is not None:
            self.daily_limit = daily_limit
        else:
            self.daily_limit = self._load_limit_from_config()

    def _load_limit_from_config(self) -> int:
        """Reads daily_limit from config.yaml if defined, otherwise falls back to DEFAULT_DAILY_LIMIT."""
        config_path = os.path.join(os.getcwd(), "config.yaml")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                val = cfg.get("safety_governor", {}).get("daily_limit")
                if val is not None:
                    return int(val)
            except Exception:
                pass
        return DEFAULT_DAILY_LIMIT

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
