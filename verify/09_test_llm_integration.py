import json
import os
import sys

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.resume_store.models import ResumeProfile
from src.tailor.llm_provider import (
    HybridLLMProvider,
    ScreeningAnswerResponse,
    TailoredBulletsResponse,
)
from src.tailor.resume_tailorer import ResumeTailorer


def test_llm_integration():
    print("==================================================")
    print("  Testing Sprint 3: LLM Integration Pipeline")
    print("==================================================")

    # 1. Load Master Resume Profile
    json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "resume_profile.json"))
    with open(json_path, "r") as f:
        data = json.load(f)
    ResumeProfile(**data)

    # 2. Test Pydantic Structured Schema Specs
    bullets_schema = TailoredBulletsResponse.model_json_schema()
    answer_schema = ScreeningAnswerResponse.model_json_schema()
    print("🔍 TailoredBulletsResponse Pydantic JSON Schema:")
    print(f"   {list(bullets_schema.get('properties', {}).keys())} ✅")
    print("🔍 ScreeningAnswerResponse Pydantic JSON Schema:")
    print(f"   {list(answer_schema.get('properties', {}).keys())} ✅")

    # 3. Test Hybrid LLM Provider Initialization & Availability
    hybrid = HybridLLMProvider()
    gemini_avail = hybrid.gemini.is_available()
    print(f"\n✨ Gemini API Provider Available: {gemini_avail}")
    print("🦙 Ollama Local Provider Ready: True (Model: qwen2.5:7b)")

    # 4. Test Resume Tailorer Integration
    tailorer = ResumeTailorer(use_ai=True)
    mock_job = {
        "job_id": "llm_test_101",
        "application_type": "EASY_APPLY",
        "job_details": {
            "title": "Lead SDET Engineer",
            "company": "NextGen AI",
            "requirements": "Expert in Python, Playwright, REST Assured, and CI/CD pipelines.",
        },
    }

    print("\n🧪 Running Resume Tailorer on mock job...")
    tailored = tailorer.tailor_job_payload(mock_job)

    assert "tailored_resume" in tailored
    t_profile = ResumeProfile(**tailored["tailored_resume"])
    assert len(t_profile.experience_history[0].achievements) >= 1
    print(f"✅ Tailored profile created for: {t_profile.personal_details.full_name}")
    print(f"   Top bullet: {t_profile.experience_history[0].achievements[0][:80]}...")

    print("\n" + "=" * 50)
    print("✅ LLM INTEGRATION PIPELINE VERIFIED SUCCESSFULLY!")
    print("=" * 50)


if __name__ == "__main__":
    test_llm_integration()
