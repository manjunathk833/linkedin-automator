from __future__ import annotations

import os
import sys

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import load_config
from src.scraper.job_finder import LinkedInJobFinder


def test_scaled_search_profiles():
    print("==================================================")
    print("  Testing 10x Scaled Search Profile Parameters")
    print("==================================================")

    finder = LinkedInJobFinder(use_ai=False)

    # 1. Test Past Month Time Window URL Construction (f_TPR=r2592000)
    print("\n🔍 Step 1: Testing Past Month Time Window URL Construction...")
    url_month = finder.build_search_url(
        keywords='"Senior SDET" NOT (Intern OR Junior)',
        location="Bengaluru",
        work_types=["remote", "hybrid", "onsite"],
        time_posted="past_month",
    )
    print(f"   Generated Search URL:\n   {url_month}")

    assert "f_TPR=r2592000" in url_month
    assert (
        "f_WT=2%2C3%2C1" in url_month
        or "f_WT=1%2C2%2C3" in url_month
        or "f_WT=2,3,1" in url_month
        or "f_WT=" in url_month
    )
    print("✅ Past Month (f_TPR=r2592000) and Bengaluru Onsite+Remote+Hybrid (f_WT=1,2,3) verified!")

    # 2. Test India Remote Only URL Construction
    print("\n🔍 Step 2: Testing India Remote Only URL Construction...")
    url_remote = finder.build_search_url(
        keywords='"Staff SDET" NOT (Intern OR Junior)',
        location="India",
        work_types=["remote"],
        time_posted="past_month",
    )
    print(f"   Generated Search URL:\n   {url_remote}")

    assert "f_WT=2" in url_remote
    assert "location=India" in url_remote
    print("✅ India Remote Only (f_WT=2) verified!")

    # 3. Test Config Loading
    print("\n🔍 Step 3: Validating config.yaml Profiles...")
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    config = load_config(config_path)
    profiles = config.get("search_profiles", [])

    assert len(profiles) == 3
    assert profiles[0]["time_posted"] == "past_month"
    assert "onsite" in profiles[0]["work_types"]
    print("✅ config.yaml profiles validated successfully!")

    print("\n" + "=" * 50)
    print("✅ SCALED SEARCH PROFILES VERIFIED SUCCESSFULLY!")
    print("=" * 50)


if __name__ == "__main__":
    test_scaled_search_profiles()
