"""
Referral Reconnaissance & Dual-Funnel Outreach Engine.
Formulates high-conversion, proof-of-work referral requests citing exact Requisition IDs
and candidate architecture metrics while strictly enforcing platform character limits
(<300 chars for LinkedIn Connection Requests, <1000 chars for InMail pitches).
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

CANDIDATE_PORTFOLIO = "https://manjunathhk.netlify.app/"
CANDIDATE_LINKEDIN = "https://www.linkedin.com/in/manjunath-h-k-ab30b1146/"
CANDIDATE_NAME = "Manjunath H K"
CANDIDATE_EXPERIENCE = "~6.8 YOE"


def extract_requisition_id(job_payload: dict[str, Any]) -> str:
    """
    Deterministically resolves external requisition ID from payload metadata,
    bullet fields, or job URLs.
    """
    # 1. Direct explicit requisition ID
    if job_payload.get("requisition_id"):
        return str(job_payload["requisition_id"]).strip()

    job_details = job_payload.get("job_details", {})
    bullet_fields = job_details.get("bullet_fields") or []
    if bullet_fields and isinstance(bullet_fields, list) and bullet_fields[0]:
        return str(bullet_fields[0]).strip()

    # 2. Check URL or job_id for common Workday/Greenhouse req patterns (e.g. R170647, 8045905, 26WD100857)
    url = job_payload.get("job_url") or job_payload.get("url") or ""
    job_id = job_payload.get("job_id") or job_payload.get("id") or ""
    combined_str = f"{job_id} {url}"

    # Pattern: R123456 or 26WD123456
    m = re.search(r"\b(R\d{5,}|[0-9]{2}WD[0-9]{5,})\b", combined_str, re.IGNORECASE)
    if m:
        return m.group(1).upper()

    # Pattern: Greenhouse/Lever numeric ID
    m = re.search(r"gh_jid=(\d{6,})", combined_str)
    if m:
        return m.group(1)

    m = re.search(r"/jobs/(\d{6,})", combined_str)
    if m:
        return m.group(1)

    # Fallback to sanitized suffix of job_id if alphanumeric
    clean_id = re.sub(r"^(workday|greenhouse|lever|ashby|linkedin)_", "", job_id)
    if clean_id and len(clean_id) >= 5 and clean_id.isalnum():
        return clean_id

    return "open req"


class ReferralNoteGenerator:
    """Generates tailored LinkedIn Connection Notes and InMail pitches for Dream Org referrals."""

    @staticmethod
    def generate_connection_note(
        job_payload: dict[str, Any],
        recipient_name: str = "there",
        max_chars: int = 300,
    ) -> str:
        """
        Generates a concise LinkedIn connection request note citing the exact Req ID
        and proof of work, strictly capped at 300 characters.
        """
        company = (job_payload.get("company_name") or "your team").strip()
        raw_title = (job_payload.get("job_title") or "SDET").strip()
        req_id = extract_requisition_id(job_payload)

        # Truncate title if overly verbose to stay well within 300 chars
        title = raw_title if len(raw_title) <= 30 else raw_title[:27] + "..."
        name = recipient_name.strip() if recipient_name and recipient_name.lower() != "there" else "there"

        note = (
            f"Hi {name}, I'm an SDET ({CANDIDATE_EXPERIENCE}) specializing in Playwright, TypeScript & API "
            f"contract testing. Saw the open {title} role (Req: {req_id}) at {company} and would love to "
            f"connect and share my portfolio ({CANDIDATE_PORTFOLIO.replace('https://', '')}) if you're open to referring!"
        )

        # Enforce hard length boundary (< 300 chars)
        if len(note) > max_chars:
            diff = len(note) - max_chars + 3
            truncated_title = title[:-diff] + "..."
            note = (
                f"Hi {name}, I'm an SDET ({CANDIDATE_EXPERIENCE}) specializing in Playwright & API testing. "
                f"Saw the {truncated_title} (Req: {req_id}) at {company} & would love to connect if open to referring!"
            )

        return note[:max_chars].strip()

    @staticmethod
    def generate_inmail_pitch(
        job_payload: dict[str, Any],
        recipient_name: str = "there",
        max_chars: int = 1000,
    ) -> str:
        """
        Generates a comprehensive InMail or direct message pitch detailing candidate architecture highlights,
        portfolio link, and referral ask, strictly capped at 1,000 characters.
        """
        company = (job_payload.get("company_name") or "your team").strip()
        title = (job_payload.get("job_title") or "Senior SDET").strip()
        req_id = extract_requisition_id(job_payload)
        name = recipient_name.strip() if recipient_name and recipient_name.lower() != "there" else "there"

        pitch = (
            f"Hi {name},\n\n"
            f"I hope you're having a great week.\n\n"
            f"I saw the {title} opening (Req #{req_id}) at {company} and wanted to reach out. "
            f"As an SDET with {CANDIDATE_EXPERIENCE} specializing in distributed test automation, "
            f"I believe my background aligns well with your team's engineering standards:\n\n"
            f"• Modular Playwright + TypeScript test execution with Docker CI sharding.\n"
            f"• Asynchronous Kafka event stream validation and Pact/WireMock API contract testing.\n"
            f"• CI/CD pipeline automation reducing regression feedback cycles.\n\n"
            f"Portfolio & Architecture: {CANDIDATE_PORTFOLIO}\n"
            f"LinkedIn: {CANDIDATE_LINKEDIN}\n\n"
            f"Would you be open to reviewing my profile or referring me internally for this position? "
            f"Happy to share my resume directly.\n\n"
            f"Best regards,\n"
            f"{CANDIDATE_NAME}"
        )

        return pitch[:max_chars].strip()

    @staticmethod
    def build_linkedin_search_urls(company_name: str, location: str = "") -> dict[str, str]:
        """
        Builds pre-scoped LinkedIn People search URLs to identify Engineering Managers,
        Quality Engineering Leads, and Alumni at the target company.
        """
        clean_company = company_name.strip()
        quoted_company = urllib.parse.quote(f'"{clean_company}"')

        # Clean location to extract city or country if available
        loc_token = ""
        if location and any(k in location.lower() for k in ["bengaluru", "bangalore", "pune", "hyderabad", "india"]):
            loc_token = "%20India"

        return {
            "engineering_managers": f"https://www.linkedin.com/search/results/people/?keywords=Engineering%20Manager%20{quoted_company}{loc_token}&origin=GLOBAL_SEARCH_HEADER",
            "qa_leads": f"https://www.linkedin.com/search/results/people/?keywords=Quality%20Engineering%20Manager%20{quoted_company}{loc_token}&origin=GLOBAL_SEARCH_HEADER",
            "tech_leads": f"https://www.linkedin.com/search/results/people/?keywords=Staff%20SDET%20{quoted_company}{loc_token}&origin=GLOBAL_SEARCH_HEADER",
            "alumni": f"https://www.linkedin.com/search/results/people/?keywords=%22Value%20Labs%22%20{quoted_company}&origin=GLOBAL_SEARCH_HEADER",
        }

    @classmethod
    def generate_referral_pack(
        cls,
        job_payload: dict[str, Any],
        recipient_name: str = "there",
    ) -> dict[str, Any]:
        """
        Generates full referral reconnaissance pack including connection note,
        InMail pitch, requisition ID, and targeted search URLs.
        """
        req_id = extract_requisition_id(job_payload)
        company = job_payload.get("company_name", "")
        location = job_payload.get("location", "")

        conn_note = cls.generate_connection_note(job_payload, recipient_name=recipient_name)
        inmail = cls.generate_inmail_pitch(job_payload, recipient_name=recipient_name)
        search_urls = cls.build_linkedin_search_urls(company, location=location)

        return {
            "requisition_id": req_id,
            "company_name": company,
            "job_title": job_payload.get("job_title", ""),
            "connection_note": conn_note,
            "connection_note_chars": len(conn_note),
            "inmail_pitch": inmail,
            "inmail_pitch_chars": len(inmail),
            "search_urls": search_urls,
        }
