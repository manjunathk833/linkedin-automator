import json
import os
import sys

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.resume_store.models import ResumeProfile
from src.scraper.job_finder import LinkedInJobFinder
from src.tailor.resume_tailorer import ResumeTailorer


def test_job_finder_and_tailorer():
    print("==================================================")
    print("  Testing Job Finder & Resume Tailorer Pipeline")
    print("==================================================")

    finder = LinkedInJobFinder()
    tailorer = ResumeTailorer()

    # 1. Test Search URL Generation
    url = finder.build_search_url("Senior SDET", "Remote")
    print(f"🌐 Search URL generated: {url}")
    assert "keywords=Senior+SDET" in url or "keywords=Senior%2BSDET" in url
    assert "f_AL=true" in url
    print("✅ Search URL with Easy Apply filter validated!")

    # 2. Test Raw Job Payload Processing
    raw_job = {
        "job_id": "job_scraped_999",
        "application_type": "EASY_APPLY",
        "job_details": {
            "title": "Lead SDET - Automation & Performance",
            "company": "Skyline Airlines",
            "location": "Bengaluru, India",
            "requirements": "Looking for an expert in Python, REST Assured, Playwright, and BDD to build our E2E microservices testing suite.",
        },
    }

    # 3. Test Keyword Extraction
    reqs = raw_job["job_details"]["requirements"]
    keywords = tailorer.extract_keywords(reqs)
    print(f"\n🔍 Extracted keywords from job reqs: {keywords}")
    assert "Python" in keywords
    assert "REST Assured" in keywords
    assert "Playwright" in keywords
    print("✅ Keyword extraction test passed!")

    # 4. Test Resume Tailoring Payload Enrichment
    tailored_job = tailorer.tailor_job_payload(raw_job)
    assert "tailored_resume" in tailored_job
    print("\n✅ Tailored payload successfully attached!")

    # Validate attached tailored resume against Pydantic schema
    profile = ResumeProfile(**tailored_job["tailored_resume"])
    assert profile.personal_details.full_name == "Manjunath H K"
    print(f"   Tailored for profile: {profile.personal_details.full_name}")
    print(f"   Top experience role: {profile.experience_history[0].role} @ {profile.experience_history[0].company}")
    print("✅ Pydantic validation of tailored resume passed!")

    # 5. Test Saving to Pending Queue
    queue_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "pending_queue"))
    saved_file = finder.save_job_to_queue(tailored_job, queue_dir)
    assert os.path.exists(saved_file)
    print(f"\n💾 Saved tailored job to queue: {saved_file}")

    # Verify contents
    with open(saved_file, "r") as f:
        saved_data = json.load(f)
    assert saved_data["job_id"] == "job_scraped_999"

    # Cleanup test job
    os.remove(saved_file)
    print("🧹 Test cleanup completed.")

    print("\n" + "=" * 50)
    print("✅ JOB FINDER & RESUME TAILORED PIPELINE VERIFIED!")
    print("=" * 50)


if __name__ == "__main__":
    test_job_finder_and_tailorer()
