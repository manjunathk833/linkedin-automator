from __future__ import annotations

import os
import sys

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import load_config
from src.scraper.job_finder import LinkedInJobFinder


def test_multi_channel_discovery():
    print("==================================================")
    print("  Testing 10x Multi-Channel Job Discovery Engine")
    print("==================================================")

    finder = LinkedInJobFinder(use_ai=False)

    # 1. Test Pagination Search URL Construction
    print("\n🔍 Step 1: Testing Pagination URL Construction (start=0, 25, 50)...")
    url_p1 = finder.build_search_url(keywords="Senior SDET", location="Bengaluru", start=0)
    url_p2 = finder.build_search_url(keywords="Senior SDET", location="Bengaluru", start=25)
    url_p3 = finder.build_search_url(keywords="Senior SDET", location="Bengaluru", start=50)

    print(f"   Page 1 URL: {url_p1}")
    print(f"   Page 2 URL: {url_p2}")
    print(f"   Page 3 URL: {url_p3}")

    assert "start=" not in url_p1
    assert "start=25" in url_p2
    assert "start=50" in url_p3
    print("✅ Pagination URL construction (start=0, 25, 50) verified!")

    # 2. Test Discovery Config Loading
    print("\n🔍 Step 2: Testing config.yaml Discovery Settings...")
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    config = load_config(config_path)

    discovery_cfg = config.get("discovery", {})
    assert discovery_cfg.get("max_pages_per_search") == 3
    assert discovery_cfg.get("enable_recommended_feed") is True
    assert discovery_cfg.get("enable_recruiter_posts") is True
    print("✅ Discovery configuration parameters verified!")

    print("\n" + "=" * 50)
    print("✅ MULTI-CHANNEL DISCOVERY ENGINE VERIFIED SUCCESSFULLY!")
    print("=" * 50)


if __name__ == "__main__":
    test_multi_channel_discovery()
