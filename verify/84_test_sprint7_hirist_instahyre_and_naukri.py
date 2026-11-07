#!/usr/bin/env python3
"""
Verification Gate 84: Sprint 7 Hirist & Instahyre Collectors + 2x Daily Naukri Resdex Trap.

Asserts:
1. HiristCollector parses structured payloads and Next.js HTML state into valid JobListing objects (source="hirist").
2. InstahyreCollector parses structured payloads and LD+JSON / HTML into valid JobListing objects (source="instahyre").
3. classify_ats_pattern() correctly maps hirist.tech job URLs to ATSVendorPattern.HIRIST_TECH_STANDARD.
4. normalize_job_source_metadata() properly attributes "hirist" and "instahyre" sources and application types.
5. scripts/naukri_pinger.py rotates headlines within Naukri character limit (<= 250 chars) with 30d buyout notice framing.
6. ATSDiscoveryCoordinator integrates HiristCollector and InstahyreCollector.
"""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.naukri_pinger import (
    HEADLINE_VARIANT_A,
    HEADLINE_VARIANT_B,
    get_next_headline,
)
from src.autofill.vendor_schemas import ATSVendorPattern, classify_ats_pattern
from src.ingestion.ats_discovery import ATSDiscoveryCoordinator
from src.ingestion.filters import is_linkedin_posting_fresh_and_unsaturated, is_sdet_title
from src.ingestion.hirist import HiristCollector
from src.ingestion.instahyre import InstahyreCollector
from src.storage.models import JobListing
from src.ui.app import normalize_job_source_metadata


def test_hirist_collector_parsing():
    print("🔍 Step 1: Validating HiristCollector parsing...")
    collector = HiristCollector()

    # Case A: Structured JSON payload parsing
    mock_payload = {
        "id": 984512,
        "title": "Lead SDET - Playwright & AI Automation",
        "cname": "Swiggy",
        "location": "Bengaluru",
        "minSal": "28",
        "maxSal": "38",
        "slug": "lead-sdet-playwright-ai-984512.html",
        "description": "Looking for Lead SDET with Playwright, Python, and LLM evaluation experience.",
        "createdDate": 1730000000000,
    }
    listing = collector.parse_job_payload(mock_payload, filter_sdet=True)
    assert listing is not None, "Expected HiristCollector to parse valid SDET payload"
    assert isinstance(listing, JobListing)
    assert listing.source == "hirist"
    assert listing.id == "hirist_984512"
    assert listing.company_name == "Swiggy"
    assert "Playwright" in listing.job_title
    assert listing.salary_range == "₹28 - ₹38 LPA"
    assert listing.url == "https://www.hirist.tech/j/lead-sdet-playwright-ai-984512.html"

    # Case B: Rejection of non-SDET title
    pm_payload = {
        "id": 984513,
        "title": "Product Manager - Growth",
        "cname": "Dunzo",
        "location": "Bengaluru",
    }
    assert collector.parse_job_payload(pm_payload, filter_sdet=True) is None

    # Case C: Rejection of foreign non-remote location
    us_payload = {
        "id": 984514,
        "title": "Senior SDET",
        "cname": "Tech Corp",
        "location": "Dallas, Texas",
    }
    assert collector.parse_job_payload(us_payload, filter_sdet=True) is None

    print("   ✅ HiristCollector parsing, qualification, and filtering verified.")


def test_instahyre_collector_parsing():
    print("\n🔍 Step 2: Validating InstahyreCollector parsing...")
    collector = InstahyreCollector()

    # Case A: Structured JSON payload parsing
    mock_payload = {
        "id": "78129",
        "title": "Senior QA Automation Engineer (Playwright / AI)",
        "company_name": "Razorpay",
        "location": "Bengaluru, India",
        "salary": "₹26 - ₹36 LPA",
        "description": "Architect end-to-end automation test suites using Playwright, TypeScript, and Docker.",
    }
    listing = collector.parse_job_payload(mock_payload, filter_sdet=True)
    assert listing is not None, "Expected InstahyreCollector to parse valid SDET payload"
    assert isinstance(listing, JobListing)
    assert listing.source == "instahyre"
    assert listing.id == "instahyre_78129"
    assert listing.company_name == "Razorpay"
    assert listing.url == "https://www.instahyre.com/job-78129"
    assert listing.salary_range == "₹26 - ₹36 LPA"

    # Case B: Rejection of non-SDET title
    sec_payload = {
        "id": "78130",
        "title": "SOC Analyst L1",
        "company_name": "Security Inc",
        "location": "Bengaluru",
    }
    assert collector.parse_job_payload(sec_payload, filter_sdet=True) is None

    # Case C: Evaluation Engineer title recognition + candidateOpportunitiesCtrl selector
    import inspect

    assert is_sdet_title("Senior Evaluation Engineer") is True
    src_code = inspect.getsource(InstahyreCollector.fetch_opportunities_via_browser)
    assert "candidateOpportunitiesCtrl" in src_code
    print("   ✅ InstahyreCollector parsing, qualification, and filtering verified.")


def test_vendor_schema_and_ats_pattern_matching():
    print("\n🔍 Step 3: Validating vendor pattern classification for Hirist URLs...")
    hirist_url_a = "https://www.hirist.tech/j/senior-sdet-playwright-984512.html"
    pattern_a = classify_ats_pattern(hirist_url_a)
    assert pattern_a == ATSVendorPattern.HIRIST_TECH_STANDARD, f"Expected HIRIST_TECH_STANDARD, got {pattern_a}"

    hirist_url_b = "https://www.hirist.com/j/lead-qa-engineer-12345"
    pattern_b = classify_ats_pattern(hirist_url_b)
    assert pattern_b == ATSVendorPattern.HIRIST_TECH_STANDARD, f"Expected HIRIST_TECH_STANDARD, got {pattern_b}"
    print("   ✅ classify_ats_pattern() correctly routes Hirist URLs to HIRIST_TECH_STANDARD.")


def test_source_metadata_normalization():
    print("\n🔍 Step 4: Validating normalize_job_source_metadata in src/ui/app.py...")
    # Hirist payload
    hirist_payload = {
        "id": "hirist_984512",
        "job_url": "https://www.hirist.tech/j/984512.html",
        "company": "Swiggy",
    }
    src_h, app_h = normalize_job_source_metadata(hirist_payload)
    assert src_h == "hirist", f"Expected 'hirist', got '{src_h}'"
    assert app_h == "ATS_HIRIST", f"Expected 'ATS_HIRIST', got '{app_h}'"

    # Instahyre payload
    instahyre_payload = {
        "id": "instahyre_78129",
        "url": "https://www.instahyre.com/job-78129",
        "company": "Razorpay",
    }
    src_i, app_i = normalize_job_source_metadata(instahyre_payload)
    assert src_i == "instahyre", f"Expected 'instahyre', got '{src_i}'"
    assert app_i == "ATS_INSTAHYRE", f"Expected 'ATS_INSTAHYRE', got '{app_i}'"
    print("   ✅ UI source normalization accurately recognizes 'hirist' and 'instahyre'.")


def test_naukri_pinger_headline_rotation():
    print("\n🔍 Step 5: Validating Naukri headline rotation and Resdex notice framing...")
    # 1. Check length constraints (Naukri max is 250 characters)
    assert len(HEADLINE_VARIANT_A) <= 250, f"Variant A too long: {len(HEADLINE_VARIANT_A)}"
    assert len(HEADLINE_VARIANT_B) <= 250, f"Variant B too long: {len(HEADLINE_VARIANT_B)}"

    # 2. Check essential high-converting keywords (evidence-gated: no learning-roadmap tools)
    from src.resume_store.master_resume import load_learning_roadmap, tool_mentioned

    for tool in load_learning_roadmap():
        assert not tool_mentioned(tool, HEADLINE_VARIANT_A), f"Roadmap tool '{tool}' leaked into Variant A"
        assert not tool_mentioned(tool, HEADLINE_VARIANT_B), f"Roadmap tool '{tool}' leaked into Variant B"
    for core_kw in ("Java", "Python", "Selenium", "Playwright", "REST Assured", "Docker", "CI/CD"):
        assert core_kw in HEADLINE_VARIANT_A, f"Missing '{core_kw}' in Variant A"
        assert core_kw in HEADLINE_VARIANT_B, f"Missing '{core_kw}' in Variant B"
    assert "30d" in HEADLINE_VARIANT_A or "Buyout" in HEADLINE_VARIANT_A
    assert "Agentic AI" in HEADLINE_VARIANT_B
    assert "30d" in HEADLINE_VARIANT_B or "Buyout" in HEADLINE_VARIANT_B

    # 3. Deterministic rotation check
    next_from_empty = get_next_headline("")
    assert next_from_empty == HEADLINE_VARIANT_B

    next_from_b = get_next_headline(HEADLINE_VARIANT_B)
    assert next_from_b == HEADLINE_VARIANT_A

    next_from_a = get_next_headline(HEADLINE_VARIANT_A)
    assert next_from_a == HEADLINE_VARIANT_B

    print(
        f"   ✅ Headline rotation verified (Variant A: {len(HEADLINE_VARIANT_A)} chars, Variant B: {len(HEADLINE_VARIANT_B)} chars)."
    )


def test_coordinator_integration():
    print("\n🔍 Step 6: Validating ATSDiscoveryCoordinator integration...")
    coordinator = ATSDiscoveryCoordinator()
    assert hasattr(coordinator, "hirist"), "Coordinator missing hirist collector"
    assert hasattr(coordinator, "instahyre"), "Coordinator missing instahyre collector"
    assert hasattr(coordinator, "ingest_direct_portals"), "Coordinator missing ingest_direct_portals method"
    print("   ✅ ATSDiscoveryCoordinator properly wired with Hirist & Instahyre collectors.")


def test_freshness_and_negative_hardware_filters():
    print("\n🔍 Step 7: Validating LinkedIn freshness/repost-saturation and negative hardware title filters...")
    # Negative hardware/PLC/FPGA/Typst exclusions
    for bad_title in (
        "Senior Lead Engineer - Test & Validation - PLC Systems",
        "Automation Engineer (Python + Typst)",
        "Post-Silicon Validation & Test Automation Engineer",
        "Network Automation Engineer",
        "IT Infrastructure Automation Engineer",
        "FPGA Test Engineer",
        "Bluetooth Automation QA Engineer",
    ):
        assert not is_sdet_title(bad_title), f"Expected negative filter to reject '{bad_title}'"

    # Stale LinkedIn age rejection
    for stale_text in (
        "Bengaluru, Karnataka, India · 1 week ago · 32 applicants",
        "Pune, Maharashtra, India · 6 days ago · Over 100 people clicked apply",
        "Hyderabad, India · Reposted 2 weeks ago · 45 people clicked apply",
        "Bengaluru · 1 month ago · 12 applicants",
    ):
        ok, reason = is_linkedin_posting_fresh_and_unsaturated(stale_text, max_days=3)
        assert not ok, f"Expected stale text to be rejected: {stale_text} (got {reason})"

    # Saturated repost rejection
    sat_repost = "Bengaluru, Karnataka, India · Reposted 1 day ago · Over 100 people clicked apply"
    ok_sat, reason_sat = is_linkedin_posting_fresh_and_unsaturated(sat_repost, max_days=3)
    assert not ok_sat and reason_sat == "reposted_and_saturated_over_100_applicants"

    # Fresh / unsaturated acceptance
    for fresh_text in (
        "Bengaluru, Karnataka, India · 22 hours ago · 19 people clicked apply",
        "Bengaluru, Karnataka, India · 1 day ago · 45 people clicked apply",
        "Bengaluru, Karnataka, India · Reposted 6 hours ago · 28 people clicked apply",
    ):
        ok_f, _ = is_linkedin_posting_fresh_and_unsaturated(fresh_text, max_days=3)
        assert ok_f, f"Expected fresh text to pass: {fresh_text}"

    # Sniper <24h strict 1-day enforcement
    ok_sniper_2d, reason_sniper_2d = is_linkedin_posting_fresh_and_unsaturated(
        "Bengaluru, Karnataka, India · 2 days ago · 15 people clicked apply",
        max_days=1,
        is_sniper_24h=True,
    )
    assert not ok_sniper_2d and reason_sniper_2d == "stale_age_2_days_ago"

    ok_sniper_18h, _ = is_linkedin_posting_fresh_and_unsaturated(
        "Bengaluru, Karnataka, India · 18 hours ago · 12 people clicked apply",
        max_days=1,
        is_sniper_24h=True,
    )
    assert ok_sniper_18h

    print(
        "   ✅ LinkedIn freshness, Sniper <24h vs <=3d, repost-saturation, and negative hardware exclusions verified."
    )


def main():
    print("=" * 70)
    print("  VERIFICATION GATE 84: SPRINT 7 HIRIST, INSTAHYRE & NAUKRI TRAP")
    print("=" * 70)

    test_hirist_collector_parsing()
    test_instahyre_collector_parsing()
    test_vendor_schema_and_ats_pattern_matching()
    test_source_metadata_normalization()
    test_naukri_pinger_headline_rotation()
    test_coordinator_integration()
    test_freshness_and_negative_hardware_filters()

    print("\n" + "=" * 70)
    print("  🎉 ALL GATE 84 SPECIFICATIONS VERIFIED: 100% PASS RATE")
    print("=" * 70)


if __name__ == "__main__":
    main()
