#!/usr/bin/env python3
"""
Standardized Multi-Tier Regression Test Runner.

Tier 1: Core (Fast Unit, Schema, Logic, Database, APIs) -> default (runs in ~5-10s)
Tier 2: Autofill (Playwright Browser Simulation & Vendor Schemas) -> --tier autofill
Tier 3: Live (External Live Career Portals & Live Sessions) -> --live

Usage:
    python verify/run_regressions.py              # Runs Tier 1 Core
    python verify/run_regressions.py --tier all   # Runs Tier 1 + Tier 2
    python verify/run_regressions.py --tier autofill # Runs Tier 2
    python verify/run_regressions.py --live       # Runs Tier 3
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from typing import NamedTuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def ensure_regression_test_fixtures():
    """
    Ensures baseline fixtures exist for CI/headless environments where
    private candidate data is gitignored. Uses programmatic zero-secret generator.
    """
    from verify.synthetic_mock_fixtures import deploy_mock_fixtures_if_missing

    deploy_mock_fixtures_if_missing()

    # Initialize SQLite app_database.db schema
    try:
        from src.storage.database import ApplicationDatabase

        ApplicationDatabase()
    except Exception as e:
        print(f"   ⚠️ Database initialization warning: {e}")


# Test Classification Mapping
TIER_1_CORE = [
    "02_test_resume_store.py",
    "03_test_approval_gate.py",
    "04_test_playwright_cdp_connect.py",
    "05_test_pdf_generation.py",
    "06_audit_resume_accuracy.py",
    "08_test_job_finder_and_tailorer.py",
    "09_test_llm_integration.py",
    "11_test_main_orchestrator.py",
    "12_test_search_and_filter.py",
    "13_test_job_finder_optimization.py",
    "14_test_multi_channel_discovery.py",
    "15_test_scraper_bug_fixes.py",
    "16_test_scaled_search_profiles.py",
    "17_test_recommended_feed_pagination.py",
    "18_test_dynamic_pagination.py",
    "19_test_job_filter_status_sync.py",
    "20_test_easy_apply_resilience.py",
    "21_test_description_and_diff.py",
    "23_test_master_knowledge_tailoring.py",
    "24_test_knowledge_translation.py",
    "25_test_fabrication_detector.py",
    "28_test_ollama_local.py",
    "29_test_ats_ingestion.py",
    "30_test_tailoring_and_compilation.py",
    "32_test_governance_and_sqlite.py",
    "33_test_resume_and_knowledge_regeneration.py",
    "34_test_dashboard_data_flow.py",
    "35_test_approval_gate_coercion.py",
    "36_test_queue_status_flow.py",
    "37_test_approved_queue_ui_flow.py",
    "38_test_static_cache_headers.py",
    "42_test_safety_governor_cap_200.py",
    "44_test_resume_professional_naming.py",
    "45_test_staging_job_metadata_enrichment.py",
    "51_test_company_boundary_isolation.py",
    "52_audit_queue_zero_contamination.py",
    "53_test_resume_comparison_and_selection.py",
    "54_test_pdf_inline_preview_headers.py",
    "57_test_autofill_logger_and_learning_vault.py",
    "61_test_application_tracking_and_auto_purge.py",
    "62_test_user_driven_applied_and_approved_purge.py",
    "63_test_unified_job_search.py",
    "64_test_source_badge_accuracy.py",
    "65_test_sprint1_stack_and_inbound.py",
    "66_test_sprint2_workday_cxs_and_dream_orgs.py",
    "67_test_sprint2_enhanced_filtering_and_workday.py",
    "68_test_sprint3_dual_funnel_and_referral_generator.py",
    "69_test_sprint4_global_remote_and_compliance.py",
    "70_test_session_and_email_reporter.py",
    "71_test_referral_reconnaissance_pivot_and_job_links.py",
    "72_test_hiring_posts_tracker_and_classifier.py",
    "73_test_post_url_extraction_and_repair.py",
    "74_test_posts_links_and_dream_org_precision.py",
    "75_test_post_formatting_and_permalink_resilience.py",
    "76_test_posts_optimization_and_deduplication.py",
    "77_test_daily_pipeline_comprehensive_wiring.py",
    "79_test_autofill_logging_and_self_healing.py",
    "103_test_expanded_collections_and_keywords.py",
]


TIER_2_AUTOFILL = [
    "01_test_playwright_context.py",
    "07_test_easy_apply_flow.py",
    "26_test_pipeline_runner.py",
    "27_test_kinematics_and_stealth.py",
    "31_test_assisted_autofill.py",
    "39_test_ats_filler_resilience.py",
    "40_test_new_tab_ats_handling.py",
    "41_test_standardized_vendor_autofill.py",
    "43_test_coinbase_greenhouse_live_fill.py",
    "46_test_okta_autofill_heuristics.py",
    "47_test_databricks_autofill_heuristics.py",
    "48_test_coinbase_autofill_heuristics.py",
    "49_test_linkedin_external_ats_pivot.py",
    "55_test_oracle_hcm_autofill_heuristics.py",
    "56_test_workday_autofill_heuristics.py",
    "58_test_workday_dynamic_question_solver.py",
    "59_test_workday_live_dom_schema_precision.py",
    "60_test_manual_takeover_fallback.py",
]

TIER_3_LIVE = [
    "10_test_linkedin_live_flow.py",
    "46b_test_okta_live_page_autofill.py",
    "50_test_gemini_38_flash_pacer.py",
    "56b_test_workday_live_page_autofill.py",
]


class TestResult(NamedTuple):
    file_name: str
    status: str  # PASS, FAIL, TIMEOUT, SKIP
    duration_sec: float
    output: str


def run_single_test(file_name: str, timeout_sec: float = 30.0) -> TestResult:
    test_path = os.path.join(PROJECT_ROOT, "verify", file_name)
    if not os.path.exists(test_path):
        return TestResult(file_name, "SKIP", 0.0, "File not found")

    python_bin = os.path.join(PROJECT_ROOT, "venv", "bin", "python")
    if not os.path.exists(python_bin):
        python_bin = sys.executable

    t0 = time.time()
    try:
        proc = subprocess.run(
            [python_bin, test_path],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=PROJECT_ROOT,
        )
        duration = time.time() - t0
        if proc.returncode == 0:
            return TestResult(file_name, "PASS", duration, proc.stdout)
        else:
            err = proc.stderr or proc.stdout
            return TestResult(file_name, "FAIL", duration, err)
    except subprocess.TimeoutExpired:
        duration = time.time() - t0
        return TestResult(file_name, "TIMEOUT", duration, f"Timed out after {timeout_sec}s")
    except Exception as e:
        duration = time.time() - t0
        return TestResult(file_name, "FAIL", duration, str(e))


def main():
    parser = argparse.ArgumentParser(description="Standardized Regression Test Runner")
    parser.add_argument(
        "--tier",
        choices=["core", "autofill", "all"],
        default="core",
        help="Test tier to execute: 'core' (default, ~5-10s), 'autofill' (~30s), 'all'",
    )
    parser.add_argument("--live", action="store_true", help="Include live external smoke tests")
    parser.add_argument(
        "--timeout",
        type=float,
        default=25.0,
        help="Per-test timeout in seconds (default: 25.0s)",
    )
    args = parser.parse_args()
    ensure_regression_test_fixtures()

    tests_to_run: list[str] = []
    if args.tier in ("core", "all"):
        tests_to_run.extend(TIER_1_CORE)
    if args.tier in ("autofill", "all"):
        tests_to_run.extend(TIER_2_AUTOFILL)
    if args.live:
        tests_to_run.extend(TIER_3_LIVE)

    print("\n" + "=" * 65)
    print(f"  STANDARDIZED REGRESSION RUNNER — TIER: {args.tier.upper()}")
    print(f"  Target: {len(tests_to_run)} test file(s) | Timeout: {args.timeout}s")
    print("=" * 65 + "\n")

    results: list[TestResult] = []
    total_start = time.time()

    for idx, test_file in enumerate(tests_to_run, start=1):
        print(
            f"[{idx:02d}/{len(tests_to_run):02d}] Running {test_file:<45}",
            end="",
            flush=True,
        )
        res = run_single_test(test_file, timeout_sec=args.timeout)
        results.append(res)

        if res.status == "PASS":
            print(f"✅ PASS ({res.duration_sec:.2f}s)")
        elif res.status == "SKIP":
            print(f"⏭️ SKIP ({res.duration_sec:.2f}s)")
        elif res.status == "TIMEOUT":
            print(f"⏱️ TIMEOUT ({res.duration_sec:.2f}s)")
        else:
            print(f"❌ FAIL ({res.duration_sec:.2f}s)")

    total_time = time.time() - total_start

    # Summary
    passed_cnt = sum(1 for r in results if r.status == "PASS")
    failed_cnt = sum(1 for r in results if r.status == "FAIL")
    timeout_cnt = sum(1 for r in results if r.status == "TIMEOUT")
    skipped_cnt = sum(1 for r in results if r.status == "SKIP")

    print("\n" + "=" * 65)
    print("  REGRESSION TEST EXECUTION SUMMARY")
    print("=" * 65)
    print(f"  Total Executed : {len(results)}")
    print(f"  ✅ Passed      : {passed_cnt}")
    print(f"  ❌ Failed      : {failed_cnt}")
    print(f"  ⏱️ Timed Out   : {timeout_cnt}")
    print(f"  ⏭️ Skipped     : {skipped_cnt}")
    print(f"  Total Duration : {total_time:.2f} seconds")
    print("=" * 65)

    if failed_cnt > 0 or timeout_cnt > 0:
        print("\n🚨 FAILURES / TIMEOUTS DETECTED:")
        for r in results:
            if r.status in ("FAIL", "TIMEOUT"):
                print(f"\n--- {r.file_name} ({r.status}) ---")
                first_lines = "\n".join(r.output.strip().split("\n")[-10:])
                print(first_lines)
        print("\n" + "=" * 65)
        sys.exit(1)

    print("\n🎉 ALL TESTS IN SUITE PASSED (100% SUCCESS)!\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
