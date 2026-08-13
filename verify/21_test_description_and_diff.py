from __future__ import annotations

import os
import sys

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scraper.job_finder import LinkedInJobFinder
from src.ui.app import compute_resume_diff


def test_description_and_diff():
    print("==================================================")
    print("  Testing Job Description Cleaning & Resume Diff Engine")
    print("==================================================")

    finder = LinkedInJobFinder(use_ai=False)

    # 1. Test Description Cleaning
    print("\n🔍 Step 1: Testing clean_job_description()...")
    raw_desc = """
    Software Engineering Architect/PMTS-SDET
    Salesforce
    Bengaluru, Karnataka, India (Hybrid)
    Share
    Show more options
    Over 100 people clicked apply
    Promoted by hirer
    Responses managed off LinkedIn
    We are seeking a Senior SDET to lead API & UI automation using Java, Python, and REST Assured.
    """
    cleaned = finder.clean_job_description(raw_desc)
    print(f"Cleaned Description:\n{cleaned}")

    assert "Share" not in cleaned
    assert "Show more options" not in cleaned
    assert "We are seeking a Senior SDET" in cleaned
    print("✅ Job description noise cleaning verified!")

    # 2. Test Resume Diff Tagging
    print("\n🔍 Step 2: Testing compute_resume_diff()...")
    master_profile = {
        "experience_history": [
            {
                "role": "Senior Engineer - QE",
                "company": "Value Labs",
                "achievements": ["Built framework with REST Assured."],
            }
        ]
    }
    payload = {
        "tailored_resume": {
            "experience_history": [
                {
                    "role": "Senior Engineer - QE",
                    "company": "Value Labs",
                    "achievements": [
                        "Architected 1000+ AI-tailored test cases with REST Assured and Playwright.",
                        "Built framework with REST Assured.",
                    ],
                }
            ]
        }
    }
    diff_res = compute_resume_diff(payload, master_profile)
    diff_bullets = diff_res["tailored_resume"]["experience_history"][0]["achievements_diff"]

    print(f"Diff Bullets: {diff_bullets}")
    assert diff_bullets[0]["is_tailored"] is True
    assert diff_bullets[1]["is_tailored"] is False
    print("✅ Resume diff tagging verified!")

    print("\n" + "=" * 50)
    print("✅ JOB DESCRIPTION FIX & RESUME DIFF ENGINE VERIFIED SUCCESSFULLY!")
    print("=" * 50)


if __name__ == "__main__":
    test_description_and_diff()
