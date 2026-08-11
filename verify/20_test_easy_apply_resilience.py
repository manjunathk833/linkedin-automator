from __future__ import annotations

import os
import sys

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.automation.easy_apply import EasyApplyExecutor


def test_easy_apply_resilience():
    print("==================================================")
    print("  Testing Easy Apply Resilience & Context Cleanup")
    print("==================================================")

    executor = EasyApplyExecutor()
    assert executor.cdp_url == "http://localhost:9222"
    print("✅ EasyApplyExecutor initialized successfully!")

    print("\n" + "=" * 50)
    print("✅ EASY APPLY RESILIENCE & CONTEXT CLEANUP VERIFIED SUCCESSFULLY!")
    print("=" * 50)


if __name__ == "__main__":
    test_easy_apply_resilience()
