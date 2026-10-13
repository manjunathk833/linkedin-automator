#!/usr/bin/env python3
"""
Verification Gate 69: Sprint 4 Global Remote Pipeline, Tax Architecture & Interview Loops.
Validates:
1. Global Remote Location & Jurisdiction Restriction Filtering heuristics.
2. Independent Contractor Tax & Legal Compliance Guides (Section 44ADA, GST LUT, Form W-8BEN, FIRA).
3. Senior SDET System Design & Live Coding Architectural Patterns.
"""

from __future__ import annotations

import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ingestion.filters import (
    has_jurisdiction_restriction,
    is_global_remote_eligible,
    is_india_or_remote_location,
)


def test_global_remote_and_jurisdiction_filters():
    print("\n--- 1. Testing Global Remote & Jurisdiction Filtering ---")

    # Positive global / India locations
    assert is_india_or_remote_location("Worldwide"), "Worldwide should match global remote"
    assert is_india_or_remote_location("Remote (Global)"), "Remote (Global) should match"
    assert is_india_or_remote_location("Work from Anywhere"), "Work from Anywhere should match"
    assert is_india_or_remote_location("Remote - APAC"), "Remote - APAC should match"
    assert is_india_or_remote_location("Remote - India"), "Remote - India should match"
    assert is_india_or_remote_location("Bengaluru, Karnataka, India"), "Bengaluru should match"
    print("  ✅ Positive location assertions passed.")

    # Negative foreign resident locations
    assert not is_india_or_remote_location("Austin, Texas, United States"), "US location must be rejected"
    assert not is_india_or_remote_location("London, United Kingdom"), "UK location must be rejected"
    assert not is_india_or_remote_location("Toronto, Ontario, Canada"), "Canada location must be rejected"
    print("  ✅ Foreign location rejection assertions passed.")

    # Jurisdiction exclusivity checks
    assert has_jurisdiction_restriction("Must be US citizens only with active security clearance")
    assert has_jurisdiction_restriction("Candidate must reside in the United States and hold US residency")
    assert has_jurisdiction_restriction("Authorized to work in the US without sponsorship required")
    assert has_jurisdiction_restriction("Position is open to North America only. W2 only.")
    assert not has_jurisdiction_restriction("Looking for Senior SDET with TypeScript and Playwright experience")
    print("  ✅ Jurisdiction restriction detection assertions passed.")

    # Composite global contractor eligibility
    # 1. Global remote + No restrictions -> Eligible
    assert is_global_remote_eligible(
        "Remote - Global",
        "Seeking Senior SDET experienced in Kafka event validation and contract testing.",
    )
    # 2. Global remote + US citizen restriction -> Ineligible
    assert not is_global_remote_eligible(
        "Worldwide",
        "Role requires US citizens only with secret clearance.",
    )
    # 3. India location + No restrictions -> Eligible
    assert is_global_remote_eligible(
        "Bengaluru, India",
        "Playwright framework design and Docker test sharding.",
    )
    # 4. US Location + No restrictions -> Ineligible
    assert not is_global_remote_eligible(
        "San Francisco, CA, USA",
        "Senior Automation Architect.",
    )
    print("  ✅ Composite contractor eligibility assertions passed.")


def test_tax_and_compliance_framework_docs():
    print("\n--- 2. Validating Contractor Tax & Legal Compliance Guides ---")

    required_docs = [
        (
            "docs/tax_and_compliance/section_44ada_guide.md",
            ["Section 44ADA", "75,00,000", "50%", "ITR-4", "Section 211(1)(b)"],
        ),
        (
            "docs/tax_and_compliance/gst_lut_rfd11_guide.md",
            ["RFD-11", "Section 2(6)", "Rule 96A", "998314", "0%"],
        ),
        (
            "docs/tax_and_compliance/form_w8ben_guide.md",
            ["W-8BEN", "Article 12", "DTAA", "PAN", "0%"],
        ),
        (
            "docs/tax_and_compliance/fira_wise_checklist.md",
            ["FIRA", "Wise", "P0802", "Section 2(6)"],
        ),
    ]

    for doc_path, keywords in required_docs:
        assert os.path.exists(doc_path), f"File {doc_path} does not exist!"
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert len(content) > 500, f"Document {doc_path} is unexpectedly short!"
        for kw in keywords:
            assert kw in content, f"Keyword '{kw}' missing from {doc_path}!"
        print(f"  ✅ Verified {doc_path} ({len(content)} chars)")


def test_interview_prep_and_algorithmic_patterns():
    print("\n--- 3. Validating Senior SDET System Design & Coding Patterns ---")

    # 1. Document verification
    prep_docs = [
        (
            "docs/interview_prep/system_design_for_testability.md",
            ["Pact", "Kafka", "DLQ", "Testcontainers", "Docker"],
        ),
        (
            "docs/interview_prep/senior_sdet_coding_patterns.md",
            ["TokenBucketRateLimiter", "LRUCacheWithTTL", "execute_with_exponential_backoff", "diff_json_contract"],
        ),
    ]

    for doc_path, keywords in prep_docs:
        assert os.path.exists(doc_path), f"File {doc_path} does not exist!"
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert len(content) > 500, f"Document {doc_path} is unexpectedly short!"
        for kw in keywords:
            assert kw in content, f"Keyword '{kw}' missing from {doc_path}!"
        print(f"  ✅ Verified {doc_path} ({len(content)} chars)")

    # 2. Algorithmic Pattern Execution: diff_json_contract test
    from docs.interview_prep.code_patterns import LRUCacheWithTTL, diff_json_contract

    expected_schema = {
        "status": "success",
        "data": {
            "orderId": "123",
            "items": [{"id": 1, "price": 10.0}],
        },
    }
    actual_matching = {
        "status": "success",
        "data": {
            "orderId": "ord-456",
            "items": [{"id": 2, "price": 25.5}],
        },
    }
    actual_divergent = {
        "status": "error",
        "data": {
            "items": [{"id": "not-an-int", "price": 25.5}],
        },
    }

    diffs_none = diff_json_contract(expected_schema, actual_matching)
    assert len(diffs_none) == 0, f"Expected 0 diffs on matching schema, got: {diffs_none}"

    diffs_divergent = diff_json_contract(expected_schema, actual_divergent)
    assert len(diffs_divergent) >= 2, f"Expected divergence detection, got: {diffs_divergent}"
    print(f"  ✅ Executed diff_json_contract algorithm: correctly detected {len(diffs_divergent)} schema violations.")

    # 3. Algorithmic Pattern Execution: LRUCacheWithTTL test
    cache = LRUCacheWithTTL(max_capacity=2, default_ttl_sec=60.0)
    cache.put("k1", "v1")
    cache.put("k2", "v2")
    assert cache.get("k1") == "v1"
    # Adding k3 should evict k2 (since k1 was accessed most recently)
    cache.put("k3", "v3")
    assert cache.get("k1") == "v1"
    assert cache.get("k2") is None, "k2 should have been evicted by LRU policy"
    assert cache.get("k3") == "v3"
    print("  ✅ Executed LRUCacheWithTTL algorithm: verified capacity bounds and LRU eviction.")


if __name__ == "__main__":
    test_global_remote_and_jurisdiction_filters()
    test_tax_and_compliance_framework_docs()
    test_interview_prep_and_algorithmic_patterns()
    print("\n🎉 ALL VERIFICATION GATE 69 CHECKS PASSED (100% SUCCESS)!\n")
