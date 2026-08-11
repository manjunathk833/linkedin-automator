from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, EmailStr, HttpUrl

# --- Enums ---


class WorkPreference(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    FLEXIBLE = "flexible"


class LanguageFluency(str, Enum):
    NATIVE = "native"
    FLUENT = "fluent"
    PROFESSIONAL = "professional"
    INTERMEDIATE = "intermediate"
    BEGINNER = "beginner"


# --- Sub-models ---


class SocialProfile(BaseModel):
    network: str  # e.g. "LinkedIn", "GitHub", "Twitter", "Portfolio"
    username: str | None = None
    url: HttpUrl


class PersonalDetails(BaseModel):
    full_name: str
    label: str | None = None  # Headline, e.g. "Senior Software Engineer"
    email: EmailStr
    phone: str
    location: str
    summary: str | None = None  # Professional summary paragraph
    profiles: list[SocialProfile] = []


class WorkExperience(BaseModel):
    role: str
    company: str
    company_url: HttpUrl | None = None
    start_date: date
    end_date: date | None = None  # None means present
    summary: str | None = None  # High-level role description
    achievements: list[str]
    tech_tags: list[str]


class Education(BaseModel):
    institution: str
    area: str  # Field of study, e.g. "Computer Science"
    study_type: str  # e.g. "Bachelor", "Master", "PhD"
    start_date: date | None = None
    end_date: date | None = None
    gpa: str | None = None
    courses: list[str] = []
    highlights: list[str] = []


class Project(BaseModel):
    name: str
    description: str | None = None
    url: HttpUrl | None = None
    start_date: date | None = None
    end_date: date | None = None
    highlights: list[str] = []
    tech_tags: list[str] = []


class Certification(BaseModel):
    name: str
    issuer: str
    issue_date: date | None = None
    url: HttpUrl | None = None


class Award(BaseModel):
    title: str
    awarder: str
    award_date: date | None = None
    summary: str | None = None


class Language(BaseModel):
    language: str
    fluency: LanguageFluency


class VolunteerWork(BaseModel):
    organization: str
    role: str
    start_date: date | None = None
    end_date: date | None = None
    summary: str | None = None
    highlights: list[str] = []


class Publication(BaseModel):
    name: str
    publisher: str | None = None
    release_date: date | None = None
    url: HttpUrl | None = None
    summary: str | None = None


class EasyApplyAnswers(BaseModel):
    # Work authorization (country-specific)
    authorization_to_work: dict[str, bool] = {}  # e.g. {"US": true, "UK": false}
    sponsorship_needed: bool = False

    # Compensation
    salary_expectations_min: int | None = None
    salary_expectations_max: int | None = None
    salary_currency: str = "USD"

    # Availability
    notice_period: str = ""
    start_date_available: str | None = None  # e.g. "Immediately", "2 weeks"

    # Location & mobility
    current_location: str = ""
    willing_to_relocate: bool = False
    work_preference: WorkPreference = WorkPreference.FLEXIBLE

    # Security
    clearance_level: str | None = None  # e.g. "Secret", "Top Secret", None

    # Education shorthand
    highest_education_level: str | None = None  # e.g. "Master's", "Bachelor's"

    # EEO (voluntary, US compliance)
    gender: str | None = None
    race_ethnicity: str | None = None
    veteran_status: str | None = None
    disability_status: str | None = None

    # Free text
    cover_letter_default: str | None = None  # Default "Why this role?" text


# --- Root Model ---


class ResumeProfile(BaseModel):
    personal_details: PersonalDetails
    experience_history: list[WorkExperience]
    education: list[Education] = []
    projects: list[Project] = []
    certifications: list[Certification] = []
    awards: list[Award] = []
    languages: list[Language] = []
    volunteer: list[VolunteerWork] = []
    publications: list[Publication] = []
    skills_matrix: (
        dict[str, list[str]] | dict[str, int]
    )  # skill category -> List[str] OR skill name -> years of experience
    easy_apply_answers: EasyApplyAnswers

    def get_years_of_experience(self, skill: str) -> int:
        """Look up years of experience for a given skill (case-insensitive)."""
        # If flat dict mapping skill -> yoe
        for k, v in self.skills_matrix.items():
            if isinstance(v, int) and k.lower() == skill.lower():
                return v
            elif isinstance(v, list):
                for item in v:
                    if item.lower() == skill.lower():
                        # Infer yoe from total experience if present in list
                        return int(self.get_total_experience_years())
        return 0

    def get_projects_by_tag(self, tag: str) -> list[Project]:
        """Return all projects that use a given tech tag."""
        return [p for p in self.projects if tag.lower() in [t.lower() for t in p.tech_tags]]

    def get_total_experience_years(self) -> float:
        """Calculate total professional experience in years."""
        total_days = 0
        for exp in self.experience_history:
            end = exp.end_date or date.today()
            total_days += (end - exp.start_date).days
        return round(total_days / 365.25, 1)
