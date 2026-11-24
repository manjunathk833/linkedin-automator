"""
Verification Gate 117: Fortress Top-30 Keyless ATS Collectors & Watchlist Repair.
Validates:
1. OracleCloudHCMCollector payload parsing (JPMorgan Chase / Texas Instruments).
2. AtlassianCareersCollector JSON array parsing & India/Remote location filtering.
3. TalentBrewCollector SSR HTML parsing & strict India filtering (Synopsys / Intuit).
4. target_companies.json Fortress GCC configuration health (0 broken duplicates,
   repaired Palo Alto Networks, Target India, Synopsys, Intuit, Atlassian, TI, JPMC).
5. ATSDiscoveryCoordinator.ingest_all_sources(fortress_only=True) restriction.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ingestion.ats_discovery import ATSDiscoveryCoordinator
from src.ingestion.extended_providers import (
    AtlassianCareersCollector,
    OracleCloudHCMCollector,
    TalentBrewCollector,
)
from src.tailor.referral_generator import classify_fortress_company


def test_oracle_cloud_hcm_collector():
    collector = OracleCloudHCMCollector()
    sample_payload = {
        "items": [
            {
                "TotalJobsCount": 3,
                "requisitionList": [
                    {
                        "Id": "25020422",
                        "Title": "Senior Test Automation Engineer",
                        "PrimaryLocation": "Bengaluru, Karnataka, India",
                        "PrimaryLocationCountry": "IN",
                        "PostedDate": "2026-11-20",
                        "WorkplaceTypeCode": "HYBRID",
                        "ShortDescriptionStr": "<p>Build Python & Playwright automation suites.</p>",
                        "secondaryLocations": [],
                    },
                    {
                        "Id": "25020999",
                        "Title": "Senior SDET",
                        "PrimaryLocation": "Dallas, Texas, United States",
                        "PrimaryLocationCountry": "US",
                        "PostedDate": "2026-11-20",
                        "secondaryLocations": [],
                    },
                    {
                        "Id": "25020888",
                        "Title": "Account Executive",
                        "PrimaryLocation": "Bengaluru, Karnataka, India",
                        "PrimaryLocationCountry": "IN",
                        "PostedDate": "2026-11-20",
                        "secondaryLocations": [],
                    },
                ],
            }
        ]
    }
    listings = collector.parse_response(
        company_name="Texas Instruments India",
        slug="ti",
        base_url="https://edbz.fa.us2.oraclecloud.com",
        site_number="CX",
        data=sample_payload,
        filter_sdet=True,
    )
    assert len(listings) == 1, f"Expected 1 India SDET listing, got {len(listings)}"
    item = listings[0]
    assert item.id == "oracle_hcm_ti_25020422"
    assert item.source == "oracle_hcm"
    assert item.url == "https://edbz.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX/job/25020422"
    assert "Bengaluru" in item.location
    assert item.posted_at is not None and item.posted_at.year == 2026
    print("✅ Test 1 Passed: OracleCloudHCMCollector parses India SDET & rejects US/non-SDET roles.")


def test_atlassian_careers_collector():
    collector = AtlassianCareersCollector()
    sample_payload = [
        {
            "id": 99001,
            "title": "Senior Quality Engineer - Cloud Platform",
            "locations": ["Bengaluru, India", "Remote - India"],
            "overview": "<p>Own quality engineering for Jira Cloud microservices.</p>",
            "responsibilities": "<p>Build Playwright and API test pipelines.</p>",
            "qualifications": "<p>5+ years QA automation.</p>",
            "applyUrl": "https://www.atlassian.com/company/careers/details/99001",
        },
        {
            "id": 99002,
            "title": "Senior SDET",
            "locations": ["Sydney, Australia"],
            "overview": "Australia only",
        },
        {
            "id": 99003,
            "title": "Product Marketing Manager",
            "locations": ["Bengaluru, India"],
            "overview": "Marketing role",
        },
    ]
    listings = collector.parse_response("Atlassian", "atlassian", sample_payload, filter_sdet=True)
    assert len(listings) == 1, f"Expected 1 India QA role, got {len(listings)}"
    item = listings[0]
    assert item.id == "atlassian_atlassian_99001"
    assert item.source == "atlassian"
    assert item.is_remote is True
    assert "Jira Cloud" in item.job_description_clean
    print("✅ Test 2 Passed: AtlassianCareersCollector filters India QA roles cleanly.")


def test_talentbrew_collector():
    collector = TalentBrewCollector()
    sample_html = """
    <ul>
      <li>
        <a href="/job/bengaluru/senior-qa-automation-engineer/44408/88112233">
          <h2>Senior QA Automation Engineer</h2>
          <span class="job-location">Bengaluru, Karnataka, India</span>
          <span class="job-date-posted">11/22/2026</span>
        </a>
      </li>
      <li>
        <a href="/job/san-diego/staff-quality-engineer/27595/88112244">
          <h2>Staff Quality Engineer</h2>
          <span class="job-location">San Diego, California, United States</span>
        </a>
      </li>
      <li>
        <a href="/job/bengaluru/principal-partner-manager/27595/88112255">
          <h2>Principal Partner Manager</h2>
          <span class="job-location">Bengaluru, Karnataka, India</span>
        </a>
      </li>
    </ul>
    """
    listings = collector.parse_search_html(
        company_name="Synopsys India",
        slug="synopsys",
        base_url="https://careers.synopsys.com",
        html_text=sample_html,
        filter_sdet=True,
    )
    assert len(listings) == 1, f"Expected 1 India QA role, got {len(listings)}"
    item = listings[0]
    assert item.id == "talentbrew_synopsys_88112233"
    assert item.source == "talentbrew"
    assert item.url == "https://careers.synopsys.com/job/bengaluru/senior-qa-automation-engineer/44408/88112233"
    assert item.posted_at is not None and item.posted_at.month == 11 and item.posted_at.day == 22
    print("✅ Test 3 Passed: TalentBrewCollector extracts India QA cards & rejects US/non-QA noise.")


def test_target_companies_fortress_repairs():
    cfg_path = os.path.join(PROJECT_ROOT, "data", "config", "target_companies.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    by_name = {item["name"]: item for item in data if item.get("active", True)}
    expected = {
        "Palo Alto Networks": ("workday", "paloaltonetworks", "wd5", "panwexternalcareers"),
        "Target India": ("workday", "target", "wd5", "targetcareers"),
        "Atlassian": ("atlassian", "atlassian", None, None),
        "Texas Instruments India": ("oracle_hcm", "ti", None, "CX"),
        "JPMorgan Chase": ("oracle_hcm", "jpmorganchase", None, "CX_1001"),
        "Synopsys India": ("talentbrew", "synopsys", None, None),
        "Intuit": ("talentbrew", "intuit", None, None),
    }
    for name, (prov, slug, dc, site) in expected.items():
        assert name in by_name, f"Missing active Fortress org: {name}"
        entry = by_name[name]
        assert entry["ats_provider"] == prov, f"{name}: expected {prov}, got {entry['ats_provider']}"
        assert entry["slug"] == slug, f"{name}: expected slug {slug}, got {entry['slug']}"
        if dc is not None:
            assert entry.get("datacenter") == dc, f"{name}: expected dc {dc}, got {entry.get('datacenter')}"
        if site is not None:
            assert entry.get("site") == site, f"{name}: expected site {site}, got {entry.get('site')}"

    # Ensure broken Qualcomm Workday duplicate is inactive while Qualcomm Eightfold stays active
    q_wd = [x for x in data if x.get("name") == "Qualcomm" and x.get("ats_provider") == "workday"]
    assert all(not x.get("active", True) for x in q_wd), "Broken Qualcomm Workday duplicate must be inactive"
    assert "Qualcomm India (Careers)" in by_name, "Qualcomm Eightfold must remain active"

    # Verify zero duplicate active (ats_provider, slug) pairs
    seen = set()
    for item in data:
        if not item.get("active", True):
            continue
        key = (item["ats_provider"].lower(), item["slug"].lower())
        assert key not in seen, f"Duplicate active target_companies key: {key}"
        seen.add(key)

    print("✅ Test 4 Passed: All 8 Fortress GCC entries repaired with 0 duplicate active boards.")


def test_fortress_only_coordinator_filter():
    coord = ATSDiscoveryCoordinator(use_ai=False)
    polled_names: list[str] = []

    async def fake_fetch(company):
        polled_names.append(company.name)
        return []

    coord._fetch_company_jobs = fake_fetch  # type: ignore[method-assign]
    asyncio.run(coord.ingest_all_sources(filter_sdet=True, max_age_days=None, fortress_only=True))
    assert 30 <= len(polled_names) <= 35, f"Expected ~32 Fortress orgs polled, got {len(polled_names)}"
    for name in polled_names:
        assert classify_fortress_company(name).get("is_fortress_org"), f"Non-fortress org leaked: {name}"
    print(f"✅ Test 5 Passed: fortress_only=True strictly polled {len(polled_names)} Top-30 Fortress GCCs.")


if __name__ == "__main__":
    test_oracle_cloud_hcm_collector()
    test_atlassian_careers_collector()
    test_talentbrew_collector()
    test_target_companies_fortress_repairs()
    test_fortress_only_coordinator_filter()
    print("\n🎉 ALL GATE 117 FORTRESS ATS COLLECTOR TESTS PASSED!")
