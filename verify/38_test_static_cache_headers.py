"""Verification script for static asset cache-busting and fresh delivery.

Tests:
1. GET / returns HTML with cache-busting query strings on styles.css and app.js.
2. GET /static/styles.css includes required selectors (.tab-btn, .approved-card, .btn-pdf, .btn-copilot).
3. GET /static/styles.css returns Cache-Control: no-cache / must-revalidate headers to prevent browser staleness.
"""

import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from fastapi.testclient import TestClient

from src.ui.app import app


def test_static_asset_delivery():
    print("Testing static asset delivery and cache-busting headers...")
    client = TestClient(app)

    # 1. Verify index.html contains cache-busting query parameters
    res_root = client.get("/")
    assert res_root.status_code == 200
    html_text = res_root.text

    assert 'href="/static/styles.css?v=' in html_text, "styles.css missing cache-busting query parameter"
    assert 'src="/static/app.js?v=' in html_text, "app.js missing cache-busting query parameter"
    print("   ✅ index.html has active cache-busting tags for styles.css and app.js")

    # 2. Verify styles.css contains all critical classes
    res_css = client.get("/static/styles.css")
    assert res_css.status_code == 200
    css_text = res_css.text

    critical_selectors = [
        ".tab-btn",
        ".approved-grid",
        ".approved-card",
        ".source-pill",
        ".btn-pdf",
        ".btn-copilot",
    ]
    for sel in critical_selectors:
        assert sel in css_text, f"Missing critical selector in styles.css: {sel}"
    print(f"   ✅ styles.css contains all {len(critical_selectors)} critical UI classes")

    # 3. Verify Cache-Control header prevents stale browser caching
    cache_control = res_css.headers.get("cache-control", "").lower()
    assert "no-cache" in cache_control or "must-revalidate" in cache_control or "max-age=0" in cache_control, (
        f"Cache-Control header '{cache_control}' does not enforce revalidation"
    )
    print(f"   ✅ /static/styles.css returns Cache-Control: {cache_control}")

    print("\n🎉 ALL STATIC ASSET CACHE VERIFICATIONS PASSED!")


if __name__ == "__main__":
    test_static_asset_delivery()
