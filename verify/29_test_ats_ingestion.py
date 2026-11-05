"""
Verification script for Sprint 2: Multi-Source ATS Keyless Ingestion.
Tests unauthenticated public API fetching for Greenhouse, Lever, and Ashby,
verifying normalized JobListing schemas.
"""

from __future__ import annotations

import asyncio
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ingestion.ashby import AshbyCollector
from src.ingestion.ats_discovery import ATSDiscoveryCoordinator
from src.ingestion.greenhouse import GreenhouseCollector
from src.ingestion.lever import LeverCollector
from src.storage.models import JobListing


async def test_ats_collectors():
    print("==================================================")
    print("  Testing Sprint 2: ATS Keyless REST Collectors")
    print("==================================================")
    from unittest.mock import AsyncMock, MagicMock, patch

    if os.environ.get("RUN_LIVE_TESTS") != "1" and "--live" not in sys.argv:
        gh = GreenhouseCollector(timeout_seconds=5.0)
        lever = LeverCollector(timeout_seconds=5.0)
        ashby = AshbyCollector(timeout_seconds=5.0)

        def _mock_get(url: str, *args, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if "greenhouse" in url:
                resp.json.return_value = {
                    "jobs": [
                        {
                            "id": 101,
                            "title": "Senior SDET",
                            "location": {"name": "Bengaluru, India"},
                            "content": "<p>Playwright & Java</p>",
                            "absolute_url": "https://boards.greenhouse.io/postman/jobs/101",
                            "first_published": "2026-11-05T06:00:00Z",
                        }
                    ]
                }
            elif "lever" in url:
                resp.json.return_value = [
                    {
                        "id": "lev-202",
                        "text": "Staff QA Automation Engineer",
                        "categories": {"location": "Bangalore, India"},
                        "workplaceType": "remote",
                        "description": "<p>API Testing</p>",
                        "descriptionPlain": "API Testing",
                        "hostedUrl": "https://jobs.lever.co/docker/lev-202",
                        "createdAt": 1762320000000,
                    }
                ]
            else:
                resp.json.return_value = {
                    "jobs": [
                        {
                            "id": "ash-303",
                            "title": "Software Engineer in Test",
                            "locationName": "Remote - India",
                            "isRemote": True,
                            "descriptionHtml": "<p>TypeScript Playwright</p>",
                            "descriptionPlain": "TypeScript Playwright",
                            "jobUrl": "https://jobs.ashbyhq.com/linear/ash-303",
                            "publishedAt": "2026-11-05T07:00:00Z",
                        }
                    ]
                }
            return resp

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.get = AsyncMock(side_effect=_mock_get)
        with patch("httpx.AsyncClient", return_value=mock_client):
            gh_jobs = await gh.fetch_board_jobs("Postman", "postman", filter_sdet=True)
            assert len(gh_jobs) == 1 and gh_jobs[0].source == "greenhouse"
            lever_jobs = await lever.fetch_board_jobs("Docker", "docker", filter_sdet=True)
            assert len(lever_jobs) == 1 and lever_jobs[0].source == "lever"
            ashby_jobs = await ashby.fetch_board_jobs("Linear", "linear", filter_sdet=True)
            assert len(ashby_jobs) == 1 and ashby_jobs[0].source == "ashby"

            coordinator = ATSDiscoveryCoordinator()
            companies = coordinator.load_target_companies()
            assert len(companies) >= 20
            subset_companies = [c for c in companies if c.ats_provider in ("greenhouse", "lever", "ashby")][:5]
            results = await asyncio.gather(*[coordinator._fetch_company_jobs(c) for c in subset_companies])
            assert sum(len(r) for r in results) == 5
        print("✅ VERIFICATION SCRIPT 29 (ATS INGESTION FAST MOCK) PASSED!")
        return

    # 1. Test Greenhouse Collector (Postman / Cloudflare / BrowserStack)
    gh = GreenhouseCollector(timeout_seconds=8.0)
    gh_jobs = await gh.fetch_board_jobs("Postman", "postman", filter_sdet=False)
    print(f"📦 Greenhouse (Postman): Fetched {len(gh_jobs)} total job(s)")
    if gh_jobs:
        sample = gh_jobs[0]
        assert isinstance(sample, JobListing)
        assert sample.source == "greenhouse"
        assert sample.company_name == "Postman"
        assert sample.url.startswith("http")
        print(f"   Sample: '{sample.job_title}' ({sample.location}) ✅")

    # 2. Test Lever Collector (Docker / Canva / Spotify)
    lever = LeverCollector(timeout_seconds=8.0)
    lever_jobs = await lever.fetch_board_jobs("Docker", "docker", filter_sdet=False)
    print(f"📦 Lever (Docker): Fetched {len(lever_jobs)} total job(s)")
    if lever_jobs:
        sample = lever_jobs[0]
        assert isinstance(sample, JobListing)
        assert sample.source == "lever"
        assert sample.company_name == "Docker"
        assert sample.url.startswith("http")
        print(f"   Sample: '{sample.job_title}' ({sample.location}) ✅")

    # 3. Test Ashby Collector (Linear / Ramp / Retool)
    ashby = AshbyCollector(timeout_seconds=8.0)
    ashby_jobs = await ashby.fetch_board_jobs("Linear", "linear", filter_sdet=False)
    print(f"📦 Ashby (Linear): Fetched {len(ashby_jobs)} total job(s)")
    if ashby_jobs:
        sample = ashby_jobs[0]
        assert isinstance(sample, JobListing)
        assert sample.source == "ashby"
        assert sample.company_name == "Linear"
        assert sample.url.startswith("http")
        print(f"   Sample: '{sample.job_title}' ({sample.location}) ✅")

    # 4. Test Unified ATS Discovery Coordinator
    coordinator = ATSDiscoveryCoordinator()
    companies = coordinator.load_target_companies()
    assert len(companies) >= 20, f"Expected at least 20 companies, got {len(companies)}"
    print(f"\n🏢 Coordinator loaded {len(companies)} configured enterprise target boards ✅")

    # Ingest a subset to verify concurrent execution
    subset_companies = companies[:5]
    tasks = [coordinator._fetch_company_jobs(c) for c in subset_companies]
    results = await asyncio.gather(*tasks)
    total_found = sum(len(r) for r in results)
    print(f"⚡ Ingested 5 target boards concurrently: {total_found} role(s) parsed without browser overhead.")

    print("\n" + "=" * 50)
    print("✅ VERIFICATION SCRIPT 29 (ATS INGESTION) PASSED!")
    print("=" * 50)


def main():
    asyncio.run(test_ats_collectors())


if __name__ == "__main__":
    main()
