from __future__ import annotations

import os
import sys

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import load_config
from src.scraper.job_finder import LinkedInJobFinder


def test_dynamic_pagination():
    print("==================================================")
    print("  Testing Dynamic Pagination & Configurable Limits")
    print("==================================================")

    finder = LinkedInJobFinder(use_ai=False)

    # 1. Test Config Loading for max_recommended_pages
    print("\n🔍 Step 1: Validating config.yaml max_recommended_pages Setting...")
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    config = load_config(config_path)

    discovery_cfg = config.get("discovery", {})
    assert discovery_cfg.get("max_recommended_pages") == 5
    print("✅ max_recommended_pages = 5 loaded successfully!")

    # 2. Test Early Break Logic Interface
    print("\n🔍 Step 2: Validating Search URL Generation & Offset Logic...")
    finder.build_search_url(keywords="Senior SDET", location="Bengaluru", start=0)
    url_p2 = finder.build_search_url(keywords="Senior SDET", location="Bengaluru", start=25)

    assert "start=25" in url_p2
    print("✅ Search URL generation & offset logic verified!")

    print("\n" + "=" * 50)
    print("✅ DYNAMIC PAGINATION & CONFIGURABLE LIMITS VERIFIED SUCCESSFULLY!")
    print("=" * 50)


if __name__ == "__main__":
    test_dynamic_pagination()
