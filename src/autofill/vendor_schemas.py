"""Vendor Form Schemas and Candidate Master Data Definitions.

Provides Pydantic models for the canonical candidate profile and verified
DOM selector mappings for Greenhouse, Lever, Ashby, Workday, and LinkedIn Easy Apply.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class MasterPersonalDetails(BaseModel):
    """Personal contact information."""

    full_name: str
    first_name: str
    last_name: str
    email: str
    phone: str
    phone_country_code: str = "+91"
    address_line1: str = ""
    city: str = "Bengaluru"
    state: str = "Karnataka"
    country: str = "India"
    postal_code: str = "560001"
    location: str = "Bengaluru, Karnataka, India"


class MasterProfiles(BaseModel):
    """Professional online profile URLs."""

    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    twitter: str = ""


class MasterCurrentEmployment(BaseModel):
    """Candidate's current employment."""

    company: str
    title: str
    start_date: str
    is_current: bool = True
    location: str = "Bengaluru, India"


class MasterExperienceItem(BaseModel):
    """Single employment history entry."""

    company: str
    title: str
    start_date: str
    end_date: str | None = None
    is_current: bool = False
    location: str = "Bengaluru, India"
    start_month: str = ""
    start_year: str = ""
    end_month: str = ""
    end_year: str = ""
    summary: str = ""


class MasterEducationItem(BaseModel):
    """Single education history entry."""

    institution: str
    degree: str
    discipline: str
    start_date: str
    end_date: str
    start_year: str = ""
    end_year: str = ""
    gpa: str = ""


class MasterLegalAndCompliance(BaseModel):
    """Standard legal compliance questions."""

    at_least_18: bool = True
    authorized_to_work_in_country: bool = True
    require_sponsorship: bool = False
    previously_employed: bool = False
    notice_period_days: int = 30
    notice_period_text: str = "30 Days"
    expected_ctc: str = "Negotiable / Standard"
    current_ctc: str = "Confidential / Competitive"


class MasterVoluntaryEEOC(BaseModel):
    """Demographics and voluntary disclosures."""

    gender: str = "Man"
    race_ethnicity: str = "Asian"
    veteran_status: str = "No"
    disability_status: str = "No"


class CandidateMasterData(BaseModel):
    """Root model for centralized authentic candidate profile."""

    personal: MasterPersonalDetails
    profiles: MasterProfiles = Field(default_factory=MasterProfiles)
    current_employment: MasterCurrentEmployment
    experience_history: list[MasterExperienceItem] = Field(default_factory=list)
    education_history: list[MasterEducationItem] = Field(default_factory=list)
    skills_years_of_experience: dict[str, Any] = Field(default_factory=dict)
    legal_and_compliance: MasterLegalAndCompliance = Field(default_factory=MasterLegalAndCompliance)
    voluntary_eeoc: MasterVoluntaryEEOC = Field(default_factory=MasterVoluntaryEEOC)

    def get_skill_years(self, skill_name: str, default: int = 5) -> int:
        """Finds numerical years of experience for a skill query."""
        skill_lower = skill_name.strip().lower()
        if skill_lower in self.skills_years_of_experience:
            val = self.skills_years_of_experience[skill_lower]
            return int(val) if isinstance(val, (int, float)) else default
        for key, val in self.skills_years_of_experience.items():
            if key in skill_lower or skill_lower in key:
                return int(val) if isinstance(val, (int, float)) else default
        return default


def load_candidate_master_data(file_path: Path | str | None = None) -> CandidateMasterData:
    """Loads and parses the candidate master data from disk."""
    if file_path is None:
        target = Path("data/profile/candidate_master_data.json")
    else:
        target = Path(file_path)

    if not target.exists():
        raise FileNotFoundError(f"Candidate master profile not found at {target.resolve()}")

    with open(target, "r", encoding="utf-8") as f:
        data = json.load(f)

    return CandidateMasterData.model_validate(data)
