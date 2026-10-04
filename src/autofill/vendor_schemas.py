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
    ai_tools_usage: str = "I design or automate workflows with AI tools (e.g. prompt engineering, building AI bots/agents, automating workflows)"
    ai_acknowledgment: bool = True
    how_did_you_hear: str = "LinkedIn"
    government_official: bool = False
    relative_government_official: bool = False
    conflict_of_interest: bool = False
    senior_referral: bool = False
    data_privacy_receipt_confirmed: bool = True


class MasterVoluntaryEEOC(BaseModel):
    """Demographics and voluntary disclosures."""

    gender: str = "Male"
    race_ethnicity: str = "Asian"
    hispanic_latino: str = "No"
    veteran_status: str = "I am not a protected veteran"
    disability_status: str = "No, I do not have a disability"


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


class ATSVendorPattern:
    """Canonical ATS vendor pattern identifiers."""

    GREENHOUSE_STANDARD = "GREENHOUSE_STANDARD"
    LEVER_STANDARD = "LEVER_STANDARD"
    ASHBY_STANDARD = "ASHBY_STANDARD"
    WORKDAY_STANDARD = "WORKDAY_STANDARD"
    LINKEDIN_EASY_APPLY = "LINKEDIN_EASY_APPLY"
    OKTA_BRANDED_GREENHOUSE = "OKTA_BRANDED_GREENHOUSE"
    DATABRICKS_CUSTOM_GREENHOUSE = "DATABRICKS_CUSTOM_GREENHOUSE"
    COINBASE_CUSTOM_GREENHOUSE = "COINBASE_CUSTOM_GREENHOUSE"
    ORACLE_CLOUD_HCM = "ORACLE_CLOUD_HCM"
    GENERIC_ATS_FALLBACK = "GENERIC_ATS_FALLBACK"


VENDOR_SCHEMAS: dict[str, dict[str, Any]] = {
    ATSVendorPattern.ORACLE_CLOUD_HCM: {
        "vendor_name": "Oracle Cloud HCM",
        "url_identifiers": ["oraclecloud.com", "fa.ocs.oraclecloud.com"],
        "url_patterns": [
            r"oraclecloud\.com/hcmUI/CandidateExperience",
            r".*\.fa\.ocs\.oraclecloud\.com",
        ],
        "dom_fingerprints": [
            "button.apply-now-button",
            "input#primary-email-0",
            "label.legal-disclaimer-container",
            ".application-container",
        ],
        "selectors": {
            "apply_button": [
                "button.apply-now-button.apply-now-button--apply-now",
                "button:has-text('Apply Now')",
                "button:has-text('Apply')",
            ],
            "cookie_accept": [
                "button#onetrust-accept-btn-handler",
                "button:has-text('Accept All')",
                "button:has-text('Accept Cookies')",
            ],
            "email": [
                "input#primary-email-0",
                "input[type='email']",
                "input[name*='email']",
            ],
            "consent_checkbox": [
                "label.legal-disclaimer-container input[type='checkbox']",
                "input[type='checkbox']#legal-terms",
                "input[type='checkbox']",
            ],
            "next_button": [
                "button:has-text('Next')",
                "button.next-button",
                "button[type='submit']",
            ],
            "resume": [
                "input[type='file'][name*='resume']",
                "input[type='file']",
            ],
            "title": [
                "label:has-text('Mr.')",
                "input[type='radio'][value='Mr.']",
                "input[type='radio'][value='MR']",
            ],
            "first_name": [
                "input[name*='firstName' i]",
                "input#first-name",
                "input[aria-label*='First Name' i]",
            ],
            "last_name": [
                "input[name*='lastName' i]",
                "input#last-name",
                "input[aria-label*='Last Name' i]",
            ],
            "middle_name": [
                "input[name*='middleName' i]",
                "input#middle-name",
                "input[aria-label*='Middle Name' i]",
            ],
            "phone": [
                "input[type='tel']",
                "input[name*='phone' i]",
                "input[aria-label*='Phone' i]",
            ],
            "website": [
                "input[name*='link' i]",
                "input[aria-label*='Link' i]",
                "input[placeholder*='Link' i]",
            ],
            "linkedin": [
                "input[name*='linkedin' i]",
                "input[aria-label*='LinkedIn' i]",
            ],
        },
    },
    ATSVendorPattern.OKTA_BRANDED_GREENHOUSE: {
        "vendor_name": "Okta Branded Greenhouse",
        "url_identifiers": ["okta.com"],
        "url_patterns": [r"okta\.com/.*/careers/", r"okta\.com/company/careers"],
        "dom_fingerprints": ["#edit-first-name", "#edit-resume-upload", "#okta-job-application"],
        "selectors": {
            "first_name": [
                "input#edit-first-name",
                "input[name='first_name']",
            ],
            "last_name": [
                "input#edit-last-name",
                "input[name='last_name']",
            ],
            "email": [
                "input#edit-email",
                "input[name='email']",
            ],
            "phone": [
                "input#edit-phone",
                "input[name='phone']",
            ],
            "resume": [
                "input#edit-resume-upload",
                "input#edit-resume",
                "input[type='file'][name*='resume']",
                "input[type='file']",
            ],
            "linkedin": [
                "input#edit-question-69483961",
                "div.form-item:has(label:has-text('LinkedIn Profile')) input",
                "input[name*='69483961']",
            ],
            "website": [
                "input#edit-question-69483962",
                "div.form-item:has(label:has-text('Website')) input",
                "input[name*='69483962']",
            ],
            "work_authorization": [
                "select#edit-question-69483963",
                "div.form-item:has(label:has-text('authorized to work')) select",
                "select[name*='69483963']",
            ],
            "visa_sponsorship": [
                "select#edit-question-69483964",
                "div.form-item:has(label:has-text('require Visa Sponsorship')) select",
                "select[name*='69483964']",
            ],
            "conflict_relatives": [
                "select#edit-question-69483965",
                "div.form-item:has(label:has-text('family members')) select",
                "select[name*='69483965']",
            ],
            "outside_activities": [
                "select#edit-question-69483967",
                "div.form-item:has(label:has-text('outside business activity')) select",
                "select[name*='69483967']",
            ],
            "previous_employment": [
                "select#edit-question-69483969",
                "div.form-item:has(label:has-text('employed by Okta')) select",
                "select[name*='69483969']",
            ],
            "consent_privacy": [
                "input#edit-question-69483970-753704919",
                "input[id*='69483970']",
                "div.form-item:has(label:has-text('I acknowledge')) input[type='checkbox']",
            ],
            "consent_evaluation": [
                "input#edit-question-69483971-753704920",
                "input[id*='69483971']",
                "div.form-item:has(label:has-text('Yes')) input[type='checkbox']",
            ],
            "eeoc_gender": [
                "select#edit-compliance-section-gender-0",
                "select[name*='gender']",
            ],
            "eeoc_race": [
                "select#edit-compliance-section-race-0",
                "select[name*='race']",
            ],
            "eeoc_veteran": [
                "select#edit-compliance-section-veteran-status-0",
                "select[name*='veteran']",
            ],
            "eeoc_disability": [
                "select#edit-compliance-section-disability-status-0",
                "select[name*='disability']",
            ],
        },
    },
    ATSVendorPattern.DATABRICKS_CUSTOM_GREENHOUSE: {
        "vendor_name": "Databricks Custom Greenhouse",
        "url_identifiers": ["databricks.com"],
        "url_patterns": [r"databricks\.com/.*/careers/", r"databricks\.com/company/careers"],
        "dom_fingerprints": ["iframe#grnhse_iframe", "iframe[src*='greenhouse.io']"],
        "selectors": {
            "first_name": ["input#first_name", "input[name='first_name']"],
            "last_name": ["input#last_name", "input[name='last_name']"],
            "preferred_name": ["input#preferred_name", "input[name='preferred_name']"],
            "email": ["input#email", "input[name='email']"],
            "country": ["input#country"],
            "phone": ["input#phone", "input[name='phone']"],
            "location": ["input#candidate-location"],
            "resume": ["input#resume[type='file']", "input[type='file'][name*='resume']", "input[type='file']"],
            "linkedin": ["input#question_35489440002", "input[aria-label*='LinkedIn' i]"],
            "current_firm": [
                "input#question_35489441002",
                "input[aria-label*='Current firm' i]",
            ],
            "work_authorization": [
                "input#question_35489442002",
                ".field-wrapper:has(label:has-text('authorized to work')) input",
                "input[aria-label*='authorized to work' i]",
            ],
            "previously_worked": [
                "input#question_35489443002",
                ".field-wrapper:has(label:has-text('worked for Databricks')) input",
                "input[aria-label*='worked for Databricks' i]",
            ],
        },
    },
    ATSVendorPattern.COINBASE_CUSTOM_GREENHOUSE: {
        "vendor_name": "Coinbase Custom Greenhouse",
        "url_identifiers": ["coinbase.com", "for=coinbase"],
        "url_patterns": [r"coinbase\.com/.*careers", r"job-boards\.greenhouse\.io/embed/job_app.*for=coinbase"],
        "dom_fingerprints": [
            "#first_name",
            "#last_name",
            "#email",
            "#phone",
            "#country",
            "#candidate-location",
            "input[type='file']",
        ],
        "selectors": {
            "first_name": ["input#first_name", "input[name='first_name']"],
            "last_name": ["input#last_name", "input[name='last_name']"],
            "email": ["input#email", "input[name='email']"],
            "phone": ["input#phone", "input[name='phone']"],
            "location": ["input#candidate-location", "div#candidate-location"],
            "phone_country": ["input#country", "div#country"],
            "resume": ["input#resume", "input[type='file'][name*='resume']", "input[type='file']"],
            "linkedin": ["input[name*='linkedin' i]", "input[id*='linkedin' i]"],
            "website": ["input[name*='website' i]", "input[id*='website' i]"],
        },
    },
    ATSVendorPattern.GREENHOUSE_STANDARD: {
        "vendor_name": "Greenhouse Standard",
        "url_identifiers": ["greenhouse.io"],
        "url_patterns": [r"boards\.greenhouse\.io", r"job-boards\.greenhouse\.io", r"greenhouse\.io"],
        "dom_fingerprints": ["form#application_form", "input#first_name"],
        "selectors": {
            "first_name": ["input#first_name", "input[name='first_name']"],
            "last_name": ["input#last_name", "input[name='last_name']"],
            "email": ["input#email", "input[name='email']"],
            "phone": ["input#phone", "input[name='phone']"],
            "resume": ["input[type='file'][name*='resume']", "input#resume"],
            "linkedin": ["input#job_application_answers_attributes_0_text_value", "input[id*='linkedin']"],
            "website": ["input[id*='website']", "input[id*='portfolio']"],
        },
    },
    ATSVendorPattern.LEVER_STANDARD: {
        "vendor_name": "Lever Standard",
        "url_identifiers": ["lever.co"],
        "url_patterns": [r"jobs\.lever\.co", r"lever\.co"],
        "dom_fingerprints": ["form#application-form", "input[name='name']"],
        "selectors": {
            "full_name": ["input[name='name']"],
            "email": ["input[name='email']"],
            "phone": ["input[name='phone']"],
            "org": ["input[name='org']"],
            "resume": ["input[type='file'][name='resume']"],
            "linkedin": ["input[name='urls[LinkedIn]']"],
            "github": ["input[name='urls[GitHub]']"],
            "portfolio": ["input[name='urls[Portfolio]']"],
        },
    },
    ATSVendorPattern.ASHBY_STANDARD: {
        "vendor_name": "Ashby Standard",
        "url_identifiers": ["ashbyhq.com"],
        "url_patterns": [r"jobs\.ashbyhq\.com", r"ashbyhq\.com"],
        "dom_fingerprints": ["input[name='name']", "input[type='file']"],
        "selectors": {
            "name": ["input[name='name']"],
            "email": ["input[name='email']"],
            "phone": ["input[name='phone']"],
            "resume": ["input[type='file']"],
        },
    },
    ATSVendorPattern.WORKDAY_STANDARD: {
        "vendor_name": "Workday Standard",
        "url_identifiers": ["workday.com", "myworkdayjobs.com"],
        "url_patterns": [r"myworkdayjobs\.com", r"workday"],
        "dom_fingerprints": ["[data-automation-id='legalNameSection_firstName']"],
        "selectors": {
            "first_name": ["[data-automation-id='legalNameSection_firstName']"],
            "last_name": ["[data-automation-id='legalNameSection_lastName']"],
            "email": ["[data-automation-id='email']"],
            "phone": ["[data-automation-id='phone-number']"],
        },
    },
    ATSVendorPattern.LINKEDIN_EASY_APPLY: {
        "vendor_name": "LinkedIn Easy Apply",
        "url_identifiers": ["linkedin.com"],
        "url_patterns": [r"linkedin\.com"],
        "dom_fingerprints": [".jobs-easy-apply-modal"],
        "selectors": {
            "phone": ["input[id*='phoneNumber']"],
            "email": ["input[id*='email']"],
            "resume": ["input[type='file']"],
        },
    },
}


def classify_ats_pattern(url: str) -> str:
    """Classifies an ATS application URL into an explicit ATS vendor pattern.

    Returns one of the constants from ATSVendorPattern.
    """
    clean_url = (url or "").lower().strip()

    # 1. Custom / Branded Organization ATS Pages
    if "databricks.com" in clean_url and ("careers" in clean_url or "gh_jid" in clean_url):
        return ATSVendorPattern.DATABRICKS_CUSTOM_GREENHOUSE
    if "okta.com" in clean_url and "careers" in clean_url:
        return ATSVendorPattern.OKTA_BRANDED_GREENHOUSE
    if "coinbase.com" in clean_url or ("job-boards.greenhouse.io" in clean_url and "for=coinbase" in clean_url):
        return ATSVendorPattern.COINBASE_CUSTOM_GREENHOUSE

    # 2. Standard ATS Job Boards
    if (
        "oraclecloud.com" in clean_url
        or "fa.ocs.oraclecloud.com" in clean_url
        or "candidateexperience" in clean_url
        or ("akamai" in clean_url and ("job" in clean_url or "career" in clean_url))
    ):
        return ATSVendorPattern.ORACLE_CLOUD_HCM
    if "greenhouse.io" in clean_url:
        return ATSVendorPattern.GREENHOUSE_STANDARD
    if "lever.co" in clean_url:
        return ATSVendorPattern.LEVER_STANDARD
    if "ashbyhq.com" in clean_url:
        return ATSVendorPattern.ASHBY_STANDARD
    if "workday" in clean_url or "myworkdayjobs.com" in clean_url:
        return ATSVendorPattern.WORKDAY_STANDARD
    if "linkedin.com" in clean_url:
        return ATSVendorPattern.LINKEDIN_EASY_APPLY

    return ATSVendorPattern.GENERIC_ATS_FALLBACK


def get_vendor_schema(pattern: str) -> dict[str, Any]:
    """Retrieves selector mapping and metadata for a given vendor pattern."""
    return VENDOR_SCHEMAS.get(pattern, {})
