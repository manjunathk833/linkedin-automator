"""
Verification Gate 76: Posts Scouting Optimization, Disclaimer Rejection & Syndicated Content Deduplication.
Tests:
1. Disclaimer rejection: Reposts with disclaimers ('neither I nor the company...', 'not able to refer') are rejected.
2. CAD/BIM non-SDET tool rejection: Civil/structural modelers mentioning Autodesk Revit are rejected from SDET/QA.
3. Conversational phrase rejection: 'two great startup roles' is not extracted as a company name.
4. Content hash deduplication: Syndicated agency bot posts with identical text are deduplicated in SQLite.
5. Expanded default queries & timeframe: Default queries include location-scoped terms and default to 'past-week'.
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.posts.post_classifier import PostClassifier
from src.posts.post_tracker import DEFAULT_SEARCH_QUERIES
from src.storage.database import ApplicationDatabase


class TestPostsOptimizationAndDeduplication(unittest.TestCase):
    test_db_path = PROJECT_ROOT / "data" / "test_hiring_posts_gate76.db"

    @classmethod
    def setUpClass(cls):
        if cls.test_db_path.exists():
            cls.test_db_path.unlink()
        cls.classifier = PostClassifier()
        cls.db = ApplicationDatabase(db_path=str(cls.test_db_path))

    @classmethod
    def tearDownClass(cls):
        if cls.test_db_path.exists():
            try:
                cls.test_db_path.unlink()
            except Exception:
                pass

    def test_01_disclaimer_rejection(self):
        """Verifies that reposts stating the author cannot refer or is not hiring are rejected."""
        disclaimer_post = (
            "*Repost of a Role from my feed or network; neither I nor the company I am part of "
            "Hive Quality Engineering Limited are involved in the hiring process for this role or are able to support/refer applicants."
        )
        is_valid, reason = self.classifier.is_hiring_post("Quality Engineering Leader", disclaimer_post)
        self.assertFalse(is_valid, "Post with disclaimer should be rejected")
        self.assertIn("disclaimer", reason.lower())

    def test_02_non_sdet_cad_tool_rejection(self):
        """Verifies that civil/architectural Revit MEP modelers are rejected and not flagged as Autodesk SDETs."""
        cad_post = (
            "We're hiring: Revit MEP Modeler / BIM Technician (Mechanical, Electrical, Plumbing) | Houston, TX\n"
            "Struvek is a structural, civil and BIM engineering firm supporting AEC teams on commercial projects.\n"
            "Requirements: 3+ years experience with Revit, AutoCAD, and BIM workflows. Apply now: https://struvek.com/careers"
        )
        is_valid, reason = self.classifier.is_hiring_post("HR at Struvek", cad_post)
        self.assertFalse(is_valid, "Civil/CAD modeling role must be rejected")
        self.assertIn("cad/bim", reason.lower())

    def test_03_conversational_phrase_rejection_in_company(self):
        """Verifies that conversational phrases like 'two great startup roles' are not extracted as company names."""
        post_text = (
            "I’m hiring for two great startup roles 👇\n"
            "Senior Algorithm Developer & Senior SDET in Test Automation.\n"
            "Well-funded deep-tech startup | Hybrid Bangalore.\n"
            "DM me your resume or apply at https://startup.io/jobs"
        )
        company, is_dream = self.classifier.extract_company_name("Technical Recruiter", post_text)
        self.assertNotEqual(company.lower(), "two great startup roles")
        self.assertFalse(is_dream)

    def test_04_content_hash_deduplication(self):
        """Verifies that syndicated agency posts with identical content are deduplicated in SQLite."""
        post1 = {
            "post_id": "post_bot_account_1",
            "author_name": "Agency Bot 1",
            "author_headline": "IT Recruiter",
            "company_name": "Velion IT",
            "is_dream_org": False,
            "post_url": "https://linkedin.com/feed/update/urn:li:activity:1111111111111111111/",
            "post_text": "🚨 URGENT HIRING | SDET – TOSCA / SELENIUM / JAVA / AI 🚨 Location: Gurgaon. Openings: 3. Exp: 4-6 yrs. Email: velionit@gmail.com",
            "posted_at_relative": "1h",
            "extracted_emails": ["velionit@gmail.com"],
            "extracted_links": [],
            "extracted_job_codes": [],
            "author_role_category": "RECRUITER",
            "quality_score": 60,
            "outreach_status": "NEW",
        }
        post2 = {
            "post_id": "post_bot_account_2",
            "author_name": "Agency Bot 2 (Shreenikaa)",
            "author_headline": "Talent Acquisition",
            "company_name": "Shreenikaa Global",
            "is_dream_org": False,
            "post_url": "https://linkedin.com/feed/update/urn:li:activity:2222222222222222222/",
            "post_text": "🚨 URGENT HIRING | SDET – TOSCA / SELENIUM / JAVA / AI 🚨 Location: Gurgaon. Openings: 3. Exp: 4-6 yrs. Email: velionit@gmail.com",
            "posted_at_relative": "2h",
            "extracted_emails": ["velionit@gmail.com"],
            "extracted_links": [],
            "extracted_job_codes": [],
            "author_role_category": "RECRUITER",
            "quality_score": 60,
            "outreach_status": "NEW",
        }

        saved1 = self.db.save_hiring_post(post1)
        self.assertTrue(saved1, "First post should be saved successfully")

        # Second post with identical text must be rejected as duplicate
        saved2 = self.db.save_hiring_post(post2)
        self.assertFalse(saved2, "Second syndicated post with identical text must be deduplicated")

    def test_05_expanded_queries_and_timeframe(self):
        """Verifies that default queries include location-scoped high-intent terms."""
        self.assertGreaterEqual(len(DEFAULT_SEARCH_QUERIES), 5)
        combined_queries = " ".join(DEFAULT_SEARCH_QUERIES)
        self.assertIn("Bangalore", combined_queries)
        self.assertIn("Software Engineer in Test", combined_queries)
        self.assertIn("Staff SDET", combined_queries)


if __name__ == "__main__":
    unittest.main()
