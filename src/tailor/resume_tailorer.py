from __future__ import annotations

import json
import os
from typing import Any

from src.resume_store.models import ResumeProfile
from src.tailor.fabrication_detector import FabricationDetector
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
        self.fabrication_detector = FabricationDetector(self.master_profile, self.knowledge_bank)

    def extract_keywords(self, text: str) -> list[str]:
        """Extracts key tech stack keywords from job text."""
        known_keywords = [
            "REST Assured",
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
        Passed through deterministic FabricationDetector verification gate.
        """
        job_reqs = job_payload.get("job_details", {}).get("requirements", "")
        keywords = self.extract_keywords(job_reqs)
        job_payload["matched_keywords"] = keywords

        # Clone master profile data
        tailored_data = json.loads(json.dumps(self.master_data))

        # Partition Master Knowledge Vault by normalized company name
        master_vault = self.knowledge_bank.get("master_achievements_vault", [])
        vault_by_company: dict[str, list[dict]] = {}
        for item in master_vault:
            c_name = item.get("company", "").strip()
            norm = "Value Labs" if "Value Labs" in c_name else c_name
            vault_by_company.setdefault(norm, []).append(item)

        any_ai_applied = False
        total_custom_bullets = 0

        # Tailor each experience block strictly within its own company scope
        for exp in tailored_data.get("experience_history", []):
            comp_raw = exp.get("company", "").strip()
            comp_norm = "Value Labs" if "Value Labs" in comp_raw else comp_raw
            comp_vault = vault_by_company.get(comp_norm, [])
            canonical_bullets = exp.get("achievements", [])
            tailored_bullets = []

            # 1. AI Tailoring: Only if this company has vault variants to choose from/polish
            if self.use_ai and self.llm_provider and len(comp_vault) > len(canonical_bullets):
                try:
                    ai_bullets = self.llm_provider.generate_company_tailored_bullets(
                        company_name=comp_norm,
                        job_description=job_reqs,
                        profile=self.master_profile,
                        company_vault=comp_vault,
                    )
                    # Validate against both Tool Fabrication AND Cross-Company Contamination
                    clean_ai = self.fabrication_detector.validate_company_bullets(comp_norm, ai_bullets)
                    if clean_ai and len(clean_ai) >= 2:
                        tailored_bullets = clean_ai
                        any_ai_applied = True
                        total_custom_bullets += len(clean_ai)
                except Exception as e:
                    print(f"⚠️ AI tailoring skipped for {comp_raw} (using company heuristics): {e}")

            # 2. Heuristic Reordering: If AI was skipped/rejected, reorder THIS COMPANY'S own achievements
            if not tailored_bullets:
                clean_canon = self.fabrication_detector.validate_company_bullets(comp_norm, canonical_bullets)
                matching = [a for a in clean_canon if any(kw.lower() in a.lower() for kw in keywords)]
                non_matching = [a for a in clean_canon if a not in matching]
                tailored_bullets = matching + non_matching

            exp["achievements"] = tailored_bullets

        job_payload["tailoring_method"] = "ai_grounded_star" if any_ai_applied else "heuristic_reordered"
        job_payload["tailored_bullets_count"] = total_custom_bullets

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
