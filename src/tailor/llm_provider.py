from __future__ import annotations

import datetime
import os
import time
from abc import ABC, abstractmethod
from typing import ClassVar

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

from src.resume_store.models import ResumeProfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(PROJECT_ROOT, "data", "logs")
LLM_LOG_FILE = os.path.join(LOG_DIR, "llm_requests.log")


def log_llm_request(
    provider: str,
    model: str,
    operation: str,
    status: str,
    duration_ms: float,
    details: str = "",
) -> None:
    """Logs LLM API request execution outcomes (success, failure, duration, errors) for easy diagnostics."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        log_line = (
            f"[{timestamp}] [{provider}] [{model}] [{operation}] "
            f"STATUS={status} DURATION={duration_ms:.1f}ms DETAILS={details}\n"
        )
        with open(LLM_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"⚠️ Could not write to LLM log: {e}")


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
    def generate_company_tailored_bullets(
        self, company_name: str, job_description: str, profile: ResumeProfile, company_vault: list[dict]
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


COMPANY_SCOPED_STAR_PROMPT = """
You are a Senior SDET Talent Architect and Technical Resume Editor.
Your task is to select and polish the candidate's authentic technical achievements for a SPECIFIC COMPANY ROLE to match a target Job Description (JD).

### ABSOLUTE GROUNDING & COMPANY BOUNDARY MANDATES:
1. STRICT COMPANY BOUNDARY: You are tailoring achievements SPECIFICALLY for the candidate's tenure at: {company_name}.
   You may ONLY select and polish achievements from the {company_name} Vault provided below.
   You must NEVER claim or incorporate achievements, projects, or tools from other employers.
2. NO TOOL HALLUCINATION: You may ONLY use tools, frameworks, and languages that appear in the {company_name} Vault.
3. FACTUAL METRICS & OUTCOMES: Never invent projects, dates, or metrics not present in the Vault.

### CANDIDATE:
Candidate: {candidate_name}
Target Role Tenure: {company_name}

### AUTHENTIC ACHIEVEMENTS VAULT FOR {company_name} ONLY:
{company_vault_text}

### TARGET JOB DESCRIPTION:
{job_description}

Select and polish 3 authentic STAR bullet points from the {company_name} Vault that best highlight the candidate's fit for the Target JD.
Return JSON strictly adhering to schema.
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
    _last_request_time: float = 0.0
    MIN_REQUEST_INTERVAL: float = 4.0  # Enforces maximum 15 requests per minute ceiling
    _model_cooldowns: ClassVar[dict[str, float]] = {}  # Tracks temporary quota exhaustion per model

    def __init__(self, api_key: str | None = None, model_name: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "models/gemini-flash-lite-latest")
        self.client = None

        if self.api_key:
            try:
                os.environ["GEMINI_API_KEY"] = self.api_key
                from google import genai

                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"⚠️ Failed to initialize Gemini Client: {e}")

    @classmethod
    def _is_model_in_cooldown(cls, model: str) -> bool:
        expiry = cls._model_cooldowns.get(model, 0.0)
        return time.time() < expiry

    @classmethod
    def _set_model_cooldown(cls, model: str, duration_sec: float = 60.0) -> None:
        cls._model_cooldowns[model] = time.time() + duration_sec
        print(f"🔒 [Circuit Breaker] Placed {model} in cooldown for {duration_sec:.0f}s due to quota limits.")

    def is_available(self) -> bool:
        return self.client is not None

    def _pace_request(self) -> None:
        """Enforces a strict 4.0-second delay between requests to guarantee adherence to 15 RPM limit."""
        now = time.time()
        elapsed = now - GeminiLLMProvider._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL and GeminiLLMProvider._last_request_time > 0.0:
            sleep_duration = self.MIN_REQUEST_INTERVAL - elapsed
            print(f"⏳ Rate Pacer: Pausing {sleep_duration:.2f}s to respect 15 RPM Gemini free tier limits...")
            time.sleep(sleep_duration)
        GeminiLLMProvider._last_request_time = time.time()

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

        models_to_try = [self.model_name]
        for fallback in [
            "models/gemini-flash-lite-latest",
            "models/gemini-flash-latest",
            "models/gemini-3.5-flash",
            "gemini-3.8-flash",
        ]:
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        last_error = None
        for current_model in models_to_try:
            if self._is_model_in_cooldown(current_model):
                continue
            for attempt in range(2):
                self._pace_request()
                start_time = time.time()
                try:
                    response = self.client.models.generate_content(
                        model=current_model,
                        contents=prompt,
                        config={
                            "temperature": 0.0,
                            "response_mime_type": "application/json",
                            "response_schema": TailoredBulletsResponse,
                        },
                    )
                    duration_ms = (time.time() - start_time) * 1000.0
                    parsed = TailoredBulletsResponse.model_validate_json(response.text)
                    bullets = parsed.tailored_bullets
                    log_llm_request(
                        "Gemini",
                        current_model,
                        "generate_tailored_bullets",
                        "SUCCESS",
                        duration_ms,
                        details=f"bullets={len(bullets)}",
                    )
                    print(
                        f"✅ [Gemini] Successfully tailored {len(bullets)} bullets in {duration_ms:.0f}ms (model: {current_model})"
                    )
                    return bullets
                except Exception as e:
                    last_error = e
                    duration_ms = (time.time() - start_time) * 1000.0
                    err_str = str(e)
                    log_llm_request(
                        "Gemini",
                        current_model,
                        "generate_tailored_bullets",
                        "FAILED",
                        duration_ms,
                        details=err_str[:250].replace("\n", " "),
                    )
                    print(f"⚠️ [Gemini] Attempt {attempt + 1} failed on {current_model}: {err_str[:120]}")
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        self._set_model_cooldown(current_model, 60.0)
                        break
                    if ("503" in err_str or "UNAVAILABLE" in err_str) and attempt == 0:
                        backoff = 2.0
                        print(
                            f"⏳ Gemini transient demand spike encountered. Backing off {backoff:.1f}s before retry..."
                        )
                        time.sleep(backoff)
                        continue
                    break

        raise last_error or RuntimeError("Gemini failed to generate tailored bullets.")

    def generate_company_tailored_bullets(
        self, company_name: str, job_description: str, profile: ResumeProfile, company_vault: list[dict]
    ) -> list[str]:
        if not self.is_available():
            raise RuntimeError("Gemini API key not configured or client unavailable.")

        prompt = COMPANY_SCOPED_STAR_PROMPT.format(
            candidate_name=profile.personal_details.full_name,
            company_name=company_name,
            company_vault_text=str(company_vault),
            job_description=job_description,
        )

        models_to_try = [self.model_name]
        for fallback in [
            "models/gemini-flash-lite-latest",
            "models/gemini-flash-latest",
            "models/gemini-3.5-flash",
            "gemini-3.8-flash",
        ]:
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        last_error = None
        for current_model in models_to_try:
            if self._is_model_in_cooldown(current_model):
                continue
            for attempt in range(2):
                self._pace_request()
                start_time = time.time()
                try:
                    response = self.client.models.generate_content(
                        model=current_model,
                        contents=prompt,
                        config={
                            "temperature": 0.0,
                            "response_mime_type": "application/json",
                            "response_schema": TailoredBulletsResponse,
                        },
                    )
                    duration_ms = (time.time() - start_time) * 1000.0
                    parsed = TailoredBulletsResponse.model_validate_json(response.text)
                    bullets = parsed.tailored_bullets
                    log_llm_request(
                        "Gemini",
                        current_model,
                        f"generate_company_tailored_bullets[{company_name}]",
                        "SUCCESS",
                        duration_ms,
                        details=f"bullets={len(bullets)}",
                    )
                    print(
                        f"✅ [Gemini] Successfully tailored {len(bullets)} bullets for {company_name} in {duration_ms:.0f}ms (model: {current_model})"
                    )
                    return bullets
                except Exception as e:
                    last_error = e
                    duration_ms = (time.time() - start_time) * 1000.0
                    err_str = str(e)
                    log_llm_request(
                        "Gemini",
                        current_model,
                        f"generate_company_tailored_bullets[{company_name}]",
                        "FAILED",
                        duration_ms,
                        details=err_str[:250].replace("\n", " "),
                    )
                    print(
                        f"⚠️ [Gemini] Attempt {attempt + 1} failed on {current_model} for {company_name}: {err_str[:120]}"
                    )
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        self._set_model_cooldown(current_model, 60.0)
                        break
                    if ("503" in err_str or "UNAVAILABLE" in err_str) and attempt == 0:
                        backoff = 2.0
                        print(
                            f"⏳ Gemini transient demand spike encountered. Backing off {backoff:.1f}s before retry..."
                        )
                        time.sleep(backoff)
                        continue
                    break

        raise last_error or RuntimeError(f"Gemini failed to generate tailored bullets for {company_name}.")

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

        self._pace_request()
        start_time = time.time()
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    "temperature": 0.0,
                    "response_mime_type": "application/json",
                    "response_schema": ScreeningAnswerResponse,
                },
            )
            duration_ms = (time.time() - start_time) * 1000.0
            parsed = ScreeningAnswerResponse.model_validate_json(response.text)
            log_llm_request(
                "Gemini",
                self.model_name,
                "answer_screening_question",
                "SUCCESS",
                duration_ms,
                details=f"ans_len={len(parsed.answer)}",
            )
            return parsed.answer
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000.0
            log_llm_request(
                "Gemini",
                self.model_name,
                "answer_screening_question",
                "FAILED",
                duration_ms,
                details=str(e)[:250].replace("\n", " "),
            )
            raise

    def translate_notes(self, raw_notes: str) -> list[dict]:
        if not self.is_available():
            raise RuntimeError("Gemini API key not configured or client unavailable.")

        prompt = TRANSLATION_PROMPT.format(raw_notes=raw_notes)
        self._pace_request()
        start_time = time.time()
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    "temperature": 0.0,
                    "response_mime_type": "application/json",
                    "response_schema": ParsedKnowledgeResponse,
                },
            )
            duration_ms = (time.time() - start_time) * 1000.0
            parsed = ParsedKnowledgeResponse.model_validate_json(response.text)
            achievements = [item.model_dump() for item in parsed.achievements]
            log_llm_request(
                "Gemini",
                self.model_name,
                "translate_notes",
                "SUCCESS",
                duration_ms,
                details=f"items={len(achievements)}",
            )
            return achievements
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000.0
            log_llm_request(
                "Gemini",
                self.model_name,
                "translate_notes",
                "FAILED",
                duration_ms,
                details=str(e)[:250].replace("\n", " "),
            )
            raise


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

        start_time = time.time()
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.0},
                format=TailoredBulletsResponse.model_json_schema(),
            )
            duration_ms = (time.time() - start_time) * 1000.0
            parsed = TailoredBulletsResponse.model_validate_json(response["message"]["content"])
            log_llm_request(
                "Ollama",
                self.model_name,
                "generate_tailored_bullets",
                "SUCCESS",
                duration_ms,
                details=f"bullets={len(parsed.tailored_bullets)}",
            )
            return parsed.tailored_bullets
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000.0
            log_llm_request(
                "Ollama",
                self.model_name,
                "generate_tailored_bullets",
                "FAILED",
                duration_ms,
                details=str(e)[:250].replace("\n", " "),
            )
            raise

    def generate_company_tailored_bullets(
        self, company_name: str, job_description: str, profile: ResumeProfile, company_vault: list[dict]
    ) -> list[str]:
        import ollama

        prompt = COMPANY_SCOPED_STAR_PROMPT.format(
            candidate_name=profile.personal_details.full_name,
            company_name=company_name,
            company_vault_text=str(company_vault),
            job_description=job_description,
        )

        start_time = time.time()
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.0},
                format=TailoredBulletsResponse.model_json_schema(),
            )
            duration_ms = (time.time() - start_time) * 1000.0
            parsed = TailoredBulletsResponse.model_validate_json(response["message"]["content"])
            log_llm_request(
                "Ollama",
                self.model_name,
                f"generate_company_tailored_bullets[{company_name}]",
                "SUCCESS",
                duration_ms,
                details=f"bullets={len(parsed.tailored_bullets)}",
            )
            return parsed.tailored_bullets
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000.0
            log_llm_request(
                "Ollama",
                self.model_name,
                f"generate_company_tailored_bullets[{company_name}]",
                "FAILED",
                duration_ms,
                details=str(e)[:250].replace("\n", " "),
            )
            raise

    def answer_screening_question(self, question: str, profile: ResumeProfile) -> str:
        import ollama

        prompt = f"""
        Question: {question}
        Candidate: {profile.personal_details.full_name}, {profile.get_total_experience_years()} years SDET experience.
        Return JSON matching schema: {{"answer": "Your 1-2 sentence answer."}}
        """

        start_time = time.time()
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.0},
                format=ScreeningAnswerResponse.model_json_schema(),
            )
            duration_ms = (time.time() - start_time) * 1000.0
            parsed = ScreeningAnswerResponse.model_validate_json(response["message"]["content"])
            log_llm_request(
                "Ollama",
                self.model_name,
                "answer_screening_question",
                "SUCCESS",
                duration_ms,
                details=f"ans_len={len(parsed.answer)}",
            )
            return parsed.answer
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000.0
            log_llm_request(
                "Ollama",
                self.model_name,
                "answer_screening_question",
                "FAILED",
                duration_ms,
                details=str(e)[:250].replace("\n", " "),
            )
            raise

    def translate_notes(self, raw_notes: str) -> list[dict]:
        import ollama

        prompt = TRANSLATION_PROMPT.format(raw_notes=raw_notes)
        start_time = time.time()
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.0},
                format=ParsedKnowledgeResponse.model_json_schema(),
            )
            duration_ms = (time.time() - start_time) * 1000.0
            parsed = ParsedKnowledgeResponse.model_validate_json(response["message"]["content"])
            achievements = [item.model_dump() for item in parsed.achievements]
            log_llm_request(
                "Ollama",
                self.model_name,
                "translate_notes",
                "SUCCESS",
                duration_ms,
                details=f"items={len(achievements)}",
            )
            return achievements
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000.0
            log_llm_request(
                "Ollama",
                self.model_name,
                "translate_notes",
                "FAILED",
                duration_ms,
                details=str(e)[:250].replace("\n", " "),
            )
            raise


class HybridLLMProvider(LLMProvider):
    """
    Primary: Gemini Free Tier (models/gemini-flash-lite-latest) with 4-second rate pacer, circuit breaker, and request logging.
    Fallback: Local Ollama (qwen2.5:7b) if Gemini encounters persistent network outages.
    """

    def __init__(self, model_name: str | None = None):
        self.gemini = GeminiLLMProvider(model_name=model_name or "models/gemini-flash-lite-latest")
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

    def generate_company_tailored_bullets(
        self, company_name: str, job_description: str, profile: ResumeProfile, company_vault: list[dict]
    ) -> list[str]:
        if self.gemini.is_available():
            try:
                print(f"✨ Using Primary Gemini API Provider for {company_name}...")
                return self.gemini.generate_company_tailored_bullets(
                    company_name, job_description, profile, company_vault
                )
            except Exception as e:
                print(f"⚠️ Gemini API failed for {company_name}: {e}. Falling back to Ollama...")

        try:
            print(f"🦙 Using Local Ollama Fallback Provider for {company_name}...")
            return self.ollama.generate_company_tailored_bullets(company_name, job_description, profile, company_vault)
        except Exception as e_ollama:
            print(f"⚠️ Local Ollama also failed for {company_name}: {e_ollama}")
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
