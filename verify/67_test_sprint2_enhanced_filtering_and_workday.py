#!/usr/bin/env python3
"""
Verification Gate 67: Enhanced Filtering & Workday Multi-Term Ingestion Precision.
Validates:
1. Title Filter: Rejects non-SDET false positives (PMs, EM, IT Automation, Search Quality).
2. Title Filter: Accepts authentic SDET / QA / Test roles.
3. Location Filter: Rejects US/Canada/UK remote and blind 'Hybrid' roles.
4. Location Filter: Accepts Indian tech hubs (Bengaluru, Pune, IND, Hyderabad) and Global Remote.
5. Workday Ingestion: Ingests verified Indian engineering roles across active Workday tenants.
"""

import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ingestion.filters import (
    is_india_or_remote_location,
    is_sdet_title,
)
from src.ingestion.workday import WorkdayCollector


def test_title_filter():
    print("\n--- 1. Testing Title Filter Precision ---")

    # Titles from output.md that must be REJECTED
    false_positive_titles = [
        "Group Product Manager, Compliance Automation",
        "Senior Engineering Manager, Core AI Automation (Platform)",
        "Senior IT Automation Engineer",
        "DCSC Automation Specialist",
        "Software Engineer, Revenue and Financial Automation",
        "Staff Backend Engineer, Database Automation (Go)",
        "Senior Staff Software Engineer- Search Quality",
        "People Analytics, India Leader",
        "Customer Success Account Manager",
        "Senior Manager, Fusion Sales - India",
    ]

    for title in false_positive_titles:
        result = is_sdet_title(title)
        assert not result, f"Expected REJECT for '{title}', but got {result}"
        print(f"  ✅ Correctly rejected: '{title}'")

    # Authentic SDET / QA titles that must be ACCEPTED
    valid_titles = [
        "Principal Software Engineer in Test",
        "Senior SDET",
        "Staff Software Engineer in Test",
        "Senior Software Engineer, Mobile QA",
        "Staff Software Engineer, Developer Infrastructure (Test Infrastructure)",
        "Lead QA Automation Engineer",
        "Senior Quality Assurance Engineer",
        "Software Development Engineer in Test II",
        "Senior Test Automation Engineer",
        "SDET - Performance and Automation",
    ]

    for title in valid_titles:
        result = is_sdet_title(title)
        assert result, f"Expected ACCEPT for '{title}', but got {result}"
        print(f"  ✅ Correctly accepted: '{title}'")


def test_location_filter():
    print("\n--- 2. Testing Location Filter Precision ---")

    # Non-India / Overseas locations that must be REJECTED
    rejected_locations = [
        "Remote - USA",
        "Remote, Canada; Remote, United States",
        "San Francisco, New York City, Seattle, Chicago, US-Remote",
        "Remote, United States",
        "Remote - UK",
        "London, United Kingdom",
        "Hybrid",  # Ambiguous without country
        "Berlin, Germany",
        "Sydney, Australia",
    ]

    for loc in rejected_locations:
        result = is_india_or_remote_location(loc)
        assert not result, f"Expected REJECT for location '{loc}', but got {result}"
        print(f"  ✅ Correctly rejected location: '{loc}'")

    # Valid Indian and Global Remote locations that must be ACCEPTED
    accepted_locations = [
        "Bengaluru, India",
        "Bangalore, India",
        "Remote - India",
        "India - Remote",
        "Pune, IND",
        "APAC - India - Bengaluru - Sunriver",
        "Hyderabad, Telangana, India",
        "Gurugram, Haryana",
        "Noida, India",
        "India - Bangalore",
        "Remote",
        "Remote (Worldwide)",
        "Global Remote",
    ]

    for loc in accepted_locations:
        result = is_india_or_remote_location(loc)
        assert result, f"Expected ACCEPT for location '{loc}', but got {result}"
        print(f"  ✅ Correctly accepted location: '{loc}'")


async def test_live_workday_ingestion():
    print("\n--- 3. Testing Workday Multi-Term Collector on Live Tenants ---")
    collector = WorkdayCollector(timeout_seconds=15.0)

    # Test Adobe (wd5, external_experienced)
    adobe_jobs = await collector.fetch_board_jobs(
        company_name="Adobe",
        slug="adobe",
        site="external_experienced",
        datacenter="wd5",
        search_terms=["SDET India", "QA India", "Software Engineer in Test India"],
        filter_sdet=False,  # Test raw location filtering on CXS results
        filter_india=True,
    )
    print(f"  Found {len(adobe_jobs)} Indian roles at Adobe")
    assert len(adobe_jobs) > 0, "Expected at least 1 Indian role from Adobe"
    for j in adobe_jobs[:3]:
        print(f"    • {j.job_title} | {j.location} | {j.url}")

    # Test Autodesk (wd1, Ext)
    autodesk_jobs = await collector.fetch_board_jobs(
        company_name="Autodesk",
        slug="autodesk",
        site="Ext",
        datacenter="wd1",
        search_terms=["SDET India", "QA India"],
        filter_sdet=False,
        filter_india=True,
    )
    print(f"  Found {len(autodesk_jobs)} Indian roles at Autodesk")
    assert len(autodesk_jobs) > 0, "Expected at least 1 Indian role from Autodesk"
    for j in autodesk_jobs[:3]:
        print(f"    • {j.job_title} | {j.location} | {j.url}")


async def main():
    test_title_filter()
    test_location_filter()
    await test_live_workday_ingestion()
    print("\n🎉 ALL VERIFICATION GATE 67 CHECKS PASSED!")


if __name__ == "__main__":
    asyncio.run(main())
