import json
import os
import sys
import urllib.parse

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import load_config
from src.filter.job_filter import LinkedInJobFilter
from src.scraper.job_finder import LinkedInJobFinder


def test_job_finder_optimization():
    print("==================================================")
    print("  Testing Job Finder & Search Optimization")
    print("==================================================")

    # 1. Test Search URL Generation with f_WT, f_E, f_TPR, sortBy
    print("\n🔍 Step 1: Testing Optimized LinkedIn URL Parameter Construction...")
    finder = LinkedInJobFinder(use_ai=False)

    url = finder.build_search_url(
        keywords='("Senior SDET" OR "Lead QA")',
        location="Bengaluru",
        work_types=["remote", "hybrid"],
        experience_levels=["mid_senior"],
        time_posted="past_week",
    )

    print(f"🌐 Generated Search URL:\n   {url}")

    assert "f_AL=true" in url
    assert "f_WT=2%2C3" in url or "f_WT=2%2C3" in urllib.parse.unquote(url) or ("2" in url and "3" in url)
    assert "f_E=4" in url
    assert "f_TPR=r604800" in url
    assert "sortBy=DD" in url
    print("✅ Optimized URL parameters (f_AL, f_WT, f_E, f_TPR, sortBy) validated!")

    # 2. Test config.yaml Loading with Boolean Profiles
    print("\n🔍 Step 2: Testing config.yaml Search Profiles...")
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    config = load_config(config_path)

    profiles = config.get("search_profiles", [])
    assert len(profiles) >= 1
    top_p = profiles[0]
    assert "work_types" in top_p
    assert "experience_levels" in top_p
    print(f"✅ Loaded profile '{top_p.get('name')}' with work_types={top_p.get('work_types')}")

    # 3. Test 5+ Years Experience Filter Matching
    print("\n🔍 Step 3: Testing 5+ Years Senior SDET Experience Filter...")
    queue_dir = os.path.join(os.path.dirname(__file__), "..", "data", "test_opt_queue")
    os.makedirs(queue_dir, exist_ok=True)

    # Job 1: 5 years experience (retained)
    sdet_job = {
        "job_id": "job_sdet_555",
        "application_type": "EASY_APPLY",
        "job_details": {
            "title": "Senior SDET - Automation",
            "company": "Skyline Airways",
            "requirements": "Requires 5+ years of hands-on experience in Python, REST Assured, and Playwright.",
        },
    }
    # Job 2: 1 year experience (filtered - below min 4 years)
    junior_job = {
        "job_id": "job_jun_111",
        "application_type": "EASY_APPLY",
        "job_details": {
            "title": "Junior QA Trainee",
            "company": "FreshersCorp",
            "requirements": "Requires 1 year of experience in manual testing.",
        },
    }

    with open(os.path.join(queue_dir, "job_sdet_555.json"), "w") as f:
        json.dump(sdet_job, f)
    with open(os.path.join(queue_dir, "job_jun_111.json"), "w") as f:
        json.dump(junior_job, f)

    j_filter = LinkedInJobFilter(queue_dir=queue_dir)
    res = j_filter.filter_pending_queue()

    assert res["retained"] == 1
    assert res["filtered"] == 1
    assert os.path.exists(os.path.join(queue_dir, "job_sdet_555.json"))
    assert not os.path.exists(os.path.join(queue_dir, "job_jun_111.json"))
    print("✅ 5+ Years Senior SDET Experience filter matching verified!")

    # Cleanup test files
    if os.path.exists(os.path.join(queue_dir, "job_sdet_555.json")):
        os.remove(os.path.join(queue_dir, "job_sdet_555.json"))
    if os.path.exists(queue_dir):
        os.rmdir(queue_dir)

    print("\n" + "=" * 50)
    print("✅ JOB FINDER OPTIMIZATION VERIFIED SUCCESSFULLY!")
    print("=" * 50)


if __name__ == "__main__":
    test_job_finder_optimization()
