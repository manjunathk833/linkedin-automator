from __future__ import annotations

import json
import os
from typing import Any

from src.resume_store.models import ResumeProfile
from src.tailor.llm_provider import HybridLLMProvider


class ResumeTailorer:
    def __init__(
        self,
        master_resume_path: str = "data/resume_profile.json",
        knowledge_bank_path: str = "data/master_knowledge_bank.json",
        use_ai: bool = True,
    ):
        self.master_resume_path = os.path.abspath(master_resume_path)
        with open(self.master_resume_path, "r") as f:
            self.master_data = json.load(f)
        self.master_profile = ResumeProfile(**self.master_data)

        self.knowledge_bank_path = os.path.abspath(knowledge_bank_path)
        self.knowledge_bank = {}
        if os.path.exists(self.knowledge_bank_path):
            try:
                with open(self.knowledge_bank_path, "r") as f:
                    self.knowledge_bank = json.load(f)
            except Exception as e:
                print(f"⚠️ Could not load Master Knowledge Bank: {e}")

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
            "Microservices",
        ]
        text_lower = text.lower()
        matched = [kw for kw in known_keywords if kw.lower() in text_lower]
        return matched if matched else ["API Testing", "Automation", "Python", "Java"]

    def tailor_job_payload(self, job_payload: dict[str, Any]) -> dict[str, Any]:
        """
        Enriches a raw job payload with a tailored resume payload derived from
        master resume profile, master knowledge bank, and matched job requirements.
        """
        job_reqs = job_payload.get("job_details", {}).get("requirements", "")
        keywords = self.extract_keywords(job_reqs)
        job_payload["matched_keywords"] = keywords

        # Clone master profile data
        tailored_data = json.loads(json.dumps(self.master_data))

        # Retrieve Master Knowledge Vault STAR achievements
        master_vault = self.knowledge_bank.get("master_achievements_vault", [])

        # 1. AI or Heuristic STAR bullet point tailoring
        if self.use_ai and self.llm_provider:
            try:
                ai_bullets = self.llm_provider.generate_tailored_bullets(
                    job_reqs, self.master_profile, master_vault=master_vault
                )
                if ai_bullets and len(ai_bullets) > 0 and len(tailored_data.get("experience_history", [])) > 0:
                    print(f"🤖 AI tailored {len(ai_bullets)} top STAR achievements!")
                    tailored_data["experience_history"][0]["achievements"] = ai_bullets
            except Exception as e:
                print(f"⚠️ AI Bullet tailoring skipped (using heuristic): {e}")

        # Reorder achievements putting matching keywords first as heuristic baseline
        for exp in tailored_data.get("experience_history", []):
            achievements = exp.get("achievements", [])
            matching = [a for a in achievements if any(kw.lower() in a.lower() for kw in keywords)]
            non_matching = [a for a in achievements if a not in matching]
            exp["achievements"] = matching + non_matching

        # 2. Attach JSON Resume Standard Schema Metadata
        tailored_data["$schema"] = "https://raw.githubusercontent.com/jsonresume/resume-schema/v1.0.0/schema.json"
        tailored_data["basics"] = {
            "name": self.master_profile.personal_details.full_name,
            "label": self.master_profile.personal_details.label,
            "email": self.master_profile.personal_details.email,
            "phone": self.master_profile.personal_details.phone,
            "summary": self.master_profile.personal_details.summary,
            "location": {"address": self.master_profile.personal_details.location},
        }

        # Embed tailored payload into job structure
        job_payload["tailored_resume"] = tailored_data
        return job_payload
