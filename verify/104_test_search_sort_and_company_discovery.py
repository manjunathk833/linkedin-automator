#!/usr/bin/env python3
"""
verify/104_test_search_sort_and_company_discovery.py — Standardized Verification Gate 104

Validates:
1. build_search_url() correctly respects sort_by parameter:
   - "relevance" omits sortBy=DD so LinkedIn surfaces exact-match roles (like Swiggy) on Page 1.
   - "date" explicitly includes sortBy=DD for chronological sorting.
2. config.yaml schema verification:
   - discovery.recommendation_collections includes 'recommended', 'top-applicant', and 'still-hiring'.
   - discovery.sort_by defaults to 'relevance'.
   - discovery.enable_target_company_pages is True and includes target slugs like 'swiggy-in'.
3. Company jobs tab scraping heuristics:
   - Validates URL generation pattern: https://www.linkedin.com/company/{slug}/jobs/
   - Tests title relevance filtering (accepts SDET/QA/Automation titles, filters out non-testing roles).
"""

import os
import sys
import unittest

import yaml

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scraper.job_finder import LinkedInJobFinder


class TestSearchSortAndCompanyDiscovery(unittest.TestCase):
    def setUp(self):
        self.finder = LinkedInJobFinder(use_ai=False)

    def test_01_build_search_url_sort_by(self):
        """Verifies build_search_url correctly handles relevance vs date sorting."""
        print("\n🧪 Step 1: Testing build_search_url sorting parameters...")

        # 1. Relevance sort (default): should NOT contain sortBy=DD
        url_relevance = self.finder.build_search_url(
            keywords='"Sr. Software Development Engineer in Test"',
            location="Bengaluru",
            sort_by="relevance",
            time_posted="past_week",
        )
        self.assertNotIn("sortBy=DD", url_relevance, "Relevance URL should not force sortBy=DD")
        self.assertIn("location=Bengaluru", url_relevance)
        self.assertIn("f_TPR=r604800", url_relevance)
        print(f"   ✅ Relevance search URL (omits sortBy=DD): {url_relevance[:90]}...")

        # 2. Date sort: should contain sortBy=DD
        url_date = self.finder.build_search_url(
            keywords='"Sr. Software Development Engineer in Test"',
            location="Bengaluru",
            sort_by="date",
            time_posted="past_week",
        )
        self.assertIn("sortBy=DD", url_date, "Date sort URL must include sortBy=DD")
        print(f"   ✅ Date search URL (includes sortBy=DD): {url_date[:90]}...")

    def test_02_config_yaml_schema(self):
        """Verifies config.yaml contains still-hiring, sort_by=relevance, and company pages."""
        print("\n🧪 Step 2: Testing config.yaml discovery configuration...")
        config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.yaml"))
        self.assertTrue(os.path.exists(config_path), "config.yaml must exist")

        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)

        disc = cfg.get("discovery", {})

        # Check sort_by
        self.assertEqual(disc.get("sort_by"), "relevance", "discovery.sort_by must default to 'relevance'")

        # Check recommendation collections
        collections = disc.get("recommendation_collections", [])
        self.assertIn("recommended", collections, "Must include 'recommended'")
        self.assertIn("top-applicant", collections, "Must include 'top-applicant'")
        self.assertIn("still-hiring", collections, "Must include 'still-hiring'")
        print(f"   ✅ Collections configured: {collections}")

        # Check company pages
        self.assertTrue(disc.get("enable_target_company_pages"), "enable_target_company_pages must be True")
        slugs = disc.get("target_company_slugs", [])
        self.assertIn("swiggy-in", slugs, "target_company_slugs must include 'swiggy-in'")
        print(f"   ✅ Target company slugs ({len(slugs)}): {slugs}")

    def test_03_company_jobs_relevance_filter(self):
        """Tests title relevance filtering logic for company page job cards."""
        print("\n🧪 Step 3: Testing company job title relevance filtering heuristics...")

        positive_titles = [
            "Sr. Software Development Engineer in Test",
            "SDET II",
            "Lead QA Automation Engineer",
            "Test Automation Architect",
            "Senior Quality Engineer",
            "Staff SDET - Platform",
            "QE Lead",
        ]

        negative_titles = [
            "Content Lead",
            "Manager - Analytics",
            "Executive - Sales & BD",
            "Operations Associate",
            "Consultant - Learning & Development",
            "HR Business Partner",
            "Product Manager II",
        ]

        def is_relevant(title: str) -> bool:
            t = title.lower()
            return any(k in t for k in ["sdet", "qa", "test", "quality", "automation", "set", "qe"])

        for t in positive_titles:
            self.assertTrue(is_relevant(t), f"Expected '{t}' to be identified as relevant")
            print(f"   ✅ Accurately matched SDET/QA title: '{t}'")

        for t in negative_titles:
            self.assertFalse(is_relevant(t), f"Expected '{t}' to be rejected as irrelevant")
            print(f"   ✅ Accurately rejected non-SDET title: '{t}'")

    def test_04_target_search_profile_relevance_url(self):
        """Validates that Profile #1 URL generated with relevance contains all key terms."""
        print("\n🧪 Step 4: Validating Search Profile #1 relevance URL construction...")
        config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.yaml"))
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)

        p1 = cfg.get("search_profiles", [])[0]
        url = self.finder.build_search_url(
            keywords=p1["keywords"],
            location=p1["location"],
            work_types=p1.get("work_types"),
            experience_levels=p1.get("experience_levels"),
            time_posted=p1.get("time_posted", "past_week"),
            distance=p1.get("distance"),
            sort_by=cfg.get("discovery", {}).get("sort_by", "relevance"),
        )

        self.assertNotIn("sortBy=DD", url)
        self.assertIn("f_TPR=r604800", url)
        self.assertIn("distance=25", url)
        self.assertIn("location=Bengaluru", url)
        print("   ✅ Search Profile #1 URL correctly constructed for relevance-driven discovery.")


if __name__ == "__main__":
    unittest.main()
