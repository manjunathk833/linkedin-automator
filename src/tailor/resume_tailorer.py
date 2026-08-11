import json
import os
from typing import Any

from src.resume_store.models import ResumeProfile
from src.tailor.llm_provider import HybridLLMProvider


class ResumeTailorer:
    def __init__(self, master_resume_path: str = "data/resume_profile.json", use_ai: bool = True):
        self.master_resume_path = os.path.abspath(master_resume_path)
        with open(self.master_resume_path, "r") as f:
            self.master_data = json.load(f)
        self.master_profile = ResumeProfile(**self.master_data)
        self.use_ai = use_ai
        self.llm_provider = HybridLLMProvider() if use_ai else None

    def extract_keywords(self, text: str) -> list[str]:
        """Extracts key tech stack keywords from job text."""
        known_keywords = [
            "REST Assured",
            "Playwright",
            "Python",
            "Java",
            "FastAPI",
            "Selenium",
            "Appium",
            "Cucumber",
            "BDD",
            "Kibana",
            "GCP",
            "Docker",
            "Jenkins",
            "Azure DevOps",
            "PostgreSQL",
            "Allure",
            "Postman",
            "ReadyAPI",
            "Groovy",
        ]
        text_lower = text.lower()
        matched = [kw for kw in known_keywords if kw.lower() in text_lower]
        return matched if matched else ["API Testing", "Automation", "Python", "Java"]

    def tailor_job_payload(self, job_payload: dict[str, Any]) -> dict[str, Any]:
        """
        Enriches a raw job payload with a tailored resume payload derived from
        master resume profile and matched job requirements.
        """
        job_reqs = job_payload.get("job_details", {}).get("requirements", "")
        keywords = self.extract_keywords(job_reqs)

        # Clone master profile data
        tailored_data = json.loads(json.dumps(self.master_data))

        # 1. AI or Heuristic bullet point tailoring
        if self.use_ai and self.llm_provider:
            try:
                ai_bullets = self.llm_provider.generate_tailored_bullets(job_reqs, self.master_profile)
                if ai_bullets and len(ai_bullets) > 0 and len(tailored_data.get("experience_history", [])) > 0:
                    print(f"🤖 AI tailored {len(ai_bullets)} top achievements!")
                    tailored_data["experience_history"][0]["achievements"] = ai_bullets
            except Exception as e:
                print(f"⚠️ AI Bullet tailoring skipped (using heuristic): {e}")

        # Reorder achievements putting matching keywords first as heuristic baseline
        for exp in tailored_data.get("experience_history", []):
            achievements = exp.get("achievements", [])
            matching = [a for a in achievements if any(kw.lower() in a.lower() for kw in keywords)]
            non_matching = [a for a in achievements if a not in matching]
            exp["achievements"] = matching + non_matching

        # Embed tailored payload into job structure
        job_payload["tailored_resume"] = tailored_data
        return job_payload
