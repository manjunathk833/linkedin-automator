from __future__ import annotations

import os
from abc import ABC, abstractmethod

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

from src.resume_store.models import ResumeProfile


class TailoredBulletsResponse(BaseModel):
    tailored_bullets: list[str] = Field(
        description="List of 2-4 customized experience bullet points matching the job description."
    )


class ScreeningAnswerResponse(BaseModel):
    answer: str = Field(description="Concise, factual answer to the screening question based on candidate profile.")


class LLMProvider(ABC):
    @abstractmethod
    def generate_tailored_bullets(self, job_description: str, profile: ResumeProfile) -> list[str]:
        pass

    @abstractmethod
    def answer_screening_question(self, question: str, profile: ResumeProfile) -> str:
        pass


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

    def generate_tailored_bullets(self, job_description: str, profile: ResumeProfile) -> list[str]:
        if not self.is_available():
            raise RuntimeError("Gemini API key not configured or client unavailable.")

        prompt = f"""
        You are an expert technical resume editor.
        Candidate Name: {profile.personal_details.full_name}
        Headline: {profile.personal_details.label}
        Summary: {profile.personal_details.summary}

        Job Description:
        {job_description}

        Candidate Experience Highlights:
        {[exp.achievements for exp in profile.experience_history]}

        Select and rewrite 3-4 bullet points from the candidate's actual experience that best align with the job requirements.
        Do NOT invent fake companies or false claims. Return concise, impactful achievement bullets.
        """

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config={
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
                "response_mime_type": "application/json",
                "response_schema": ScreeningAnswerResponse,
            },
        )
        parsed = ScreeningAnswerResponse.model_validate_json(response.text)
        return parsed.answer


class OllamaLLMProvider(LLMProvider):
    def __init__(self, model_name: str = "qwen2.5:7b"):
        self.model_name = model_name

    def generate_tailored_bullets(self, job_description: str, profile: ResumeProfile) -> list[str]:
        import ollama

        prompt = f"""
        Candidate: {profile.personal_details.full_name}
        Job Description: {job_description}
        Actual Achievements: {[exp.achievements for exp in profile.experience_history]}

        Select 3 bullet points matching the job description. Return JSON matching schema: {{"tailored_bullets": ["bullet1", "bullet2", "bullet3"]}}
        """

        response = ollama.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
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
            format=ScreeningAnswerResponse.model_json_schema(),
        )
        parsed = ScreeningAnswerResponse.model_validate_json(response["message"]["content"])
        return parsed.answer


class HybridLLMProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, local_model: str = "qwen2.5:7b"):
        self.gemini = GeminiLLMProvider(api_key=api_key)
        self.ollama = OllamaLLMProvider(model_name=local_model)

    def generate_tailored_bullets(self, job_description: str, profile: ResumeProfile) -> list[str]:
        if self.gemini.is_available():
            try:
                print("✨ Using Primary Gemini API Provider...")
                return self.gemini.generate_tailored_bullets(job_description, profile)
            except Exception as e:
                print(f"⚠️ Gemini API failed: {e}. Falling back to Ollama...")

        print("🦙 Using Local Ollama Fallback Provider...")
        return self.ollama.generate_tailored_bullets(job_description, profile)

    def answer_screening_question(self, question: str, profile: ResumeProfile) -> str:
        if self.gemini.is_available():
            try:
                print("✨ Using Primary Gemini API Provider...")
                return self.gemini.answer_screening_question(question, profile)
            except Exception as e:
                print(f"⚠️ Gemini API failed: {e}. Falling back to Ollama...")

        print("🦙 Using Local Ollama Fallback Provider...")
        return self.ollama.answer_screening_question(question, profile)
