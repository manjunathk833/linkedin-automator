from __future__ import annotations

import os
from abc import ABC, abstractmethod

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

from src.resume_store.models import ResumeProfile


class TailoredBulletsResponse(BaseModel):
    tailored_bullets: list[str] = Field(
        description="List of 3-4 STAR-formatted customized experience bullet points matching the job description."
    )


class ScreeningAnswerResponse(BaseModel):
    answer: str = Field(description="Concise, factual answer to the screening question based on candidate profile.")


class ParsedAchievement(BaseModel):
    domain: str = Field(
        description="Domain or technical category (e.g., Performance Testing, API Automation, Cloud Certification)"
    )
    company: str = Field(description="Associated company or 'Personal / Certification'")
    star_achievement: str = Field(description="STAR formatted accomplishment bullet point")
    tools: list[str] = Field(description="Extracted list of technical tools and frameworks")
    metric: str = Field(description="Extracted quantitative metric or outcome")


class ParsedKnowledgeResponse(BaseModel):
    achievements: list[ParsedAchievement] = Field(description="List of parsed STAR achievements from raw notes")


class LLMProvider(ABC):
    @abstractmethod
    def generate_tailored_bullets(
        self, job_description: str, profile: ResumeProfile, master_vault: list[dict] | None = None
    ) -> list[str]:
        pass

    @abstractmethod
    def answer_screening_question(self, question: str, profile: ResumeProfile) -> str:
        pass

    @abstractmethod
    def translate_notes(self, raw_notes: str) -> list[dict]:
        pass


GROUNDED_STAR_PROMPT = """
You are a Senior SDET Talent Architect and Technical Resume Editor.
Your task is to select and polish the candidate's authentic technical achievements to match a target Job Description (JD).

### ABSOLUTE GROUNDING MANDATES (ZERO FABRICATION & ZERO HALLUCINATION):
1. NO TOOL HALLUCINATION: You may ONLY use tools, frameworks, and languages that appear in the Candidate's Master Vault or Resume Profile.
2. UNSUPPORTED JD KEYWORDS: If the Target JD asks for a tool the candidate has NOT used (e.g., Playwright, Cypress, Go, C#), NEVER claim experience with that tool. Instead, highlight the candidate's closest authentic equivalent (e.g. REST Assured, Selenium, Appium, Python, Java).
3. FACTUAL METRICS & COMPANIES: Never invent companies, dates, or quantitative outcomes not present in the Candidate's Vault.

### GOOD vs BAD EXAMPLES:

❌ BAD (FABRICATED):
- Raw Candidate Skill: REST Assured, Java, Postman
- Target JD Requirement: Playwright, Cypress, TypeScript
- Fabricated Output: "Spearheaded web UI automation using Playwright and Cypress..." <-- REJECTED! Candidate never used Playwright!

✅ GOOD (GROUNDED & TRUTHFUL):
- Raw Candidate Skill: REST Assured, Java, Postman
- Target JD Requirement: Playwright, Cypress, TypeScript
- Grounded Output: "PNR Linking & SSR [REST Assured · ReadyAPI · BDD · Java]: Architected scalable API test automation suites cutting execution effort by 93% across airline microservice domains." <-- VALID! Grounded in authentic experience!

### CANDIDATE PROFILE:
Candidate: {candidate_name}
Summary: {candidate_summary}

### CANDIDATE MASTER KNOWLEDGE VAULT:
{candidate_vault_text}

### TARGET JOB DESCRIPTION:
{job_description}

Select 3-4 authentic STAR bullet points from the Candidate Vault that best match the Target JD requirements.
Return JSON strictly adhering to the schema.
"""


TRANSLATION_PROMPT = """
You are an expert SDET Resume Knowledge Architect.
Your task is to convert raw candidate notes into structured STAR achievement objects.

### RAW CANDIDATE NOTES:
{raw_notes}

Convert each note into a structured JSON achievement containing:
- domain: Classified technical domain (e.g., Performance Testing, API Automation, Event-Driven Architecture, Cloud Certification)
- company: Associated company name (e.g. Value Labs, Dunzo, Tata Elxsi) or "Personal / Certification"
- star_achievement: STAR-formatted bullet point [Action Verb] + [Tools] + [Outcome]
- tools: Array of tech tools (e.g. ["Locust", "Python", "API"])
- metric: Extracted metric or ROI outcome (e.g. "35% latency reduction")

Return JSON matching schema.
"""


class GeminiLLMProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model_name: str = "gemini-3.6-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self.client = None

        if self.api_key:
            try:
                os.environ["GEMINI_API_KEY"] = self.api_key
                from google import genai

                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"⚠️ Failed to initialize Gemini Client: {e}")

    def is_available(self) -> bool:
        return self.client is not None

    def generate_tailored_bullets(
        self, job_description: str, profile: ResumeProfile, master_vault: list[dict] | None = None
    ) -> list[str]:
        if not self.is_available():
            raise RuntimeError("Gemini API key not configured or client unavailable.")

        vault_source = master_vault if master_vault else [exp.achievements for exp in profile.experience_history]

        prompt = GROUNDED_STAR_PROMPT.format(
            candidate_name=profile.personal_details.full_name,
            candidate_summary=profile.personal_details.summary,
            candidate_vault_text=str(vault_source),
            job_description=job_description,
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={
                "temperature": 0.0,
                "response_mime_type": "application/json",
                "response_schema": TailoredBulletsResponse,
            },
        )
        parsed = TailoredBulletsResponse.model_validate_json(response.text)
        return parsed.tailored_bullets

    def answer_screening_question(self, question: str, profile: ResumeProfile) -> str:
        if not self.is_available():
            raise RuntimeError("Gemini API key not configured or client unavailable.")

        prompt = f"""
        Answer the following recruiter screening question concisely and factually based ONLY on the candidate profile.

        Question: {question}

        Candidate Profile:
        Name: {profile.personal_details.full_name}
        Experience: {profile.get_total_experience_years()} years in SDET, API & UI Automation.
        Key Skills: {list(profile.skills_matrix.keys()) if isinstance(profile.skills_matrix, dict) else profile.skills_matrix}
        Location: {profile.personal_details.location}

        Return a direct, professional 1-2 sentence response.
        """

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={
                "temperature": 0.0,
                "response_mime_type": "application/json",
                "response_schema": ScreeningAnswerResponse,
            },
        )
        parsed = ScreeningAnswerResponse.model_validate_json(response.text)
        return parsed.answer

    def translate_notes(self, raw_notes: str) -> list[dict]:
        if not self.is_available():
            raise RuntimeError("Gemini API key not configured or client unavailable.")

        prompt = TRANSLATION_PROMPT.format(raw_notes=raw_notes)
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={
                "temperature": 0.0,
                "response_mime_type": "application/json",
                "response_schema": ParsedKnowledgeResponse,
            },
        )
        parsed = ParsedKnowledgeResponse.model_validate_json(response.text)
        return [item.model_dump() for item in parsed.achievements]


class OllamaLLMProvider(LLMProvider):
    def __init__(self, model_name: str = "qwen2.5:7b"):
        self.model_name = model_name

    def generate_tailored_bullets(
        self, job_description: str, profile: ResumeProfile, master_vault: list[dict] | None = None
    ) -> list[str]:
        import ollama

        vault_source = master_vault if master_vault else [exp.achievements for exp in profile.experience_history]

        prompt = GROUNDED_STAR_PROMPT.format(
            candidate_name=profile.personal_details.full_name,
            candidate_summary=profile.personal_details.summary,
            candidate_vault_text=str(vault_source),
            job_description=job_description,
        )

        response = ollama.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0},
            format=TailoredBulletsResponse.model_json_schema(),
        )
        parsed = TailoredBulletsResponse.model_validate_json(response["message"]["content"])
        return parsed.tailored_bullets

    def answer_screening_question(self, question: str, profile: ResumeProfile) -> str:
        import ollama

        prompt = f"""
        Question: {question}
        Candidate: {profile.personal_details.full_name}, {profile.get_total_experience_years()} years SDET experience.
        Return JSON matching schema: {{"answer": "Your 1-2 sentence answer."}}
        """

        response = ollama.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0},
            format=ScreeningAnswerResponse.model_json_schema(),
        )
        parsed = ScreeningAnswerResponse.model_validate_json(response["message"]["content"])
        return parsed.answer

    def translate_notes(self, raw_notes: str) -> list[dict]:
        import ollama

        prompt = TRANSLATION_PROMPT.format(raw_notes=raw_notes)
        response = ollama.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0},
            format=ParsedKnowledgeResponse.model_json_schema(),
        )
        parsed = ParsedKnowledgeResponse.model_validate_json(response["message"]["content"])
        return [item.model_dump() for item in parsed.achievements]


class HybridLLMProvider(LLMProvider):
    """
    Primary: Gemini Free Tier (gemini-3.6-flash).
    Fallback: Local Ollama (qwen2.5:7b) if Gemini encounters rate limits or offline network.
    """

    def __init__(self):
        self.gemini = GeminiLLMProvider()
        self.ollama = OllamaLLMProvider()

    def generate_tailored_bullets(
        self, job_description: str, profile: ResumeProfile, master_vault: list[dict] | None = None
    ) -> list[str]:
        if self.gemini.is_available():
            try:
                print("✨ Using Primary Gemini API Provider...")
                return self.gemini.generate_tailored_bullets(job_description, profile, master_vault=master_vault)
            except Exception as e:
                print(f"⚠️ Gemini API failed: {e}. Falling back to Ollama...")

        try:
            print("🦙 Using Local Ollama Fallback Provider...")
            return self.ollama.generate_tailored_bullets(job_description, profile, master_vault=master_vault)
        except Exception as e_ollama:
            print(f"⚠️ Local Ollama also failed: {e_ollama}")
            raise

    def answer_screening_question(self, question: str, profile: ResumeProfile) -> str:
        if self.gemini.is_available():
            try:
                return self.gemini.answer_screening_question(question, profile)
            except Exception:
                pass
        return self.ollama.answer_screening_question(question, profile)

    def translate_notes(self, raw_notes: str) -> list[dict]:
        if self.gemini.is_available():
            try:
                print("✨ Translating candidate notes via Gemini API...")
                return self.gemini.translate_notes(raw_notes)
            except Exception as e:
                print(f"⚠️ Gemini Translation failed: {e}. Falling back to Ollama...")

        try:
            print("🦙 Translating candidate notes via Local Ollama...")
            return self.ollama.translate_notes(raw_notes)
        except Exception as e_ollama:
            print(f"⚠️ Ollama Translation failed: {e_ollama}")
            raise
