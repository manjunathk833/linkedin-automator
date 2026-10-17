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


def extract_company_name(job_payload: dict[str, Any]) -> str:
    """Extracts company name from payload across all schema variations."""
    details = job_payload.get("job_details") or {}
    company = (
        job_payload.get("company_name")
        or job_payload.get("company")
        or details.get("company")
        or details.get("company_name")
        or ""
    )
    return str(company).strip()


def extract_job_title(job_payload: dict[str, Any]) -> str:
    """Extracts job title from payload across all schema variations."""
    details = job_payload.get("job_details") or {}
    title = (
        job_payload.get("job_title")
        or job_payload.get("title")
        or details.get("title")
        or details.get("job_title")
        or "Senior SDET"
    )
    return str(title).strip()


def extract_location(job_payload: dict[str, Any]) -> str:
    """Extracts job location from payload across all schema variations."""
    details = job_payload.get("job_details") or {}
    location = job_payload.get("location") or details.get("location") or ""
    return str(location).strip()


def extract_job_url(job_payload: dict[str, Any]) -> str:
    """Extracts job posting URL from payload across all schema variations."""
    details = job_payload.get("job_details") or {}
    url = (
        job_payload.get("job_url")
        or job_payload.get("url")
        or details.get("job_url")
        or details.get("url")
        or details.get("external_url")
        or ""
    )
    return str(url).strip()


def clean_job_url(raw_url: str) -> str:
    """Cleans tracking query parameters from job URLs while preserving essential routing."""
    if not raw_url:
        return ""
    # Standardize clean LinkedIn job view link: https://www.linkedin.com/jobs/view/<id>/
    m = re.match(r"(https?://(?:www\.)?linkedin\.com/jobs/view/\d+/?)", raw_url)
    if m:
        return m.group(1).rstrip("/") + "/"

    # For standard web URLs, strip marketing & tracking query parameters
    try:
        parsed = urllib.parse.urlparse(raw_url)
        if parsed.query:
            query_params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            tracking_keys = {
                "utm_source",
                "utm_medium",
                "utm_campaign",
                "utm_term",
                "utm_content",
                "ref",
                "source",
                "gh_src",
                "trackingId",
                "refId",
                "alternateChannel",
            }
            # For career portals where job ID is already in the path (e.g. /opportunity/8236753), gh_jid is redundant
            if any(token in parsed.path for token in ["/opportunity/", "/jobs/", "/job/"]):
                tracking_keys.add("gh_jid")
            filtered_query = {k: v for k, v in query_params.items() if k not in tracking_keys}
            if not filtered_query:
                return urllib.parse.urlunparse(parsed._replace(query=""))
            return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(filtered_query, doseq=True)))
    except Exception:
        pass
    return raw_url


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

    # 2. Check URL or job_id for common Workday/Greenhouse req patterns (e.g. R170647, 8045905, 26WD100857, R28268)
    url = extract_job_url(job_payload)
    job_id = job_payload.get("job_id") or job_payload.get("id") or ""
    combined_str = f"{job_id} {url}"

    # Pattern: R12345 or 26WD123456 (handling preceding underscore, slash, hyphen, or boundary)
    m = re.search(r"(?:^|[^a-zA-Z0-9])(R\d{4,}|[0-9]{2}WD[0-9]{4,})(?:[^a-zA-Z0-9]|$)", combined_str, re.IGNORECASE)
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
    tokens = clean_id.split("_")
    if tokens and tokens[-1] and len(tokens[-1]) >= 4 and tokens[-1].isalnum():
        return tokens[-1].upper()

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
        Generates a concise LinkedIn connection request note citing the exact Req ID,
        clean job posting URL, and proof of work, strictly capped at 300 characters.
        """
        company = extract_company_name(job_payload) or "your team"
        raw_title = extract_job_title(job_payload) or "SDET"
        req_id = extract_requisition_id(job_payload)
        job_url = clean_job_url(extract_job_url(job_payload))
        name = recipient_name.strip() if recipient_name and recipient_name.lower() != "there" else "there"
        portfolio = CANDIDATE_PORTFOLIO.replace("https://", "").rstrip("/")

        # Normalize title for concise rendering
        title = raw_title if len(raw_title) <= 28 else raw_title[:25] + "..."

        if job_url:
            # Format A: Include both job link and portfolio if within character limit
            note = (
                f"Hi {name}, I'm an SDET ({CANDIDATE_EXPERIENCE}) specializing in Playwright & API testing. "
                f"Saw the {title} role (Req: {req_id}) at {company}: {job_url} - "
                f"would love to connect and share my portfolio ({portfolio}) if open to referring!"
            )
            # Format B: Streamline call-to-action to keep portfolio + job URL within 300 chars
            if len(note) > max_chars:
                note = (
                    f"Hi {name}, I'm an SDET ({CANDIDATE_EXPERIENCE}) specializing in Playwright & API testing. "
                    f"Saw the {title} role (Req: {req_id}) at {company}: {job_url} - "
                    f"open to referring? Portfolio: {portfolio}"
                )
            # Format C: For long URLs (e.g. Workday >100 chars), prioritize the direct job link
            if len(note) > max_chars:
                note = (
                    f"Hi {name}, I'm an SDET ({CANDIDATE_EXPERIENCE}) specializing in Playwright & API testing. "
                    f"Saw the {title} opening (Req: {req_id}) at {company}: {job_url} - "
                    f"would love to connect if open to referring!"
                )
            # Format D: Shorten phrasing if still exceeding
            if len(note) > max_chars:
                diff = len(note) - max_chars + 3
                short_title = title[:-diff] + "..." if len(title) > diff + 4 else "SDET"
                note = (
                    f"Hi {name}, I'm an SDET ({CANDIDATE_EXPERIENCE}) in Playwright & API testing. "
                    f"Saw the {short_title} opening at {company}: {job_url} - "
                    f"would love to connect if open to referring!"
                )
        else:
            # Fallback if no job URL available
            note = (
                f"Hi {name}, I'm an SDET ({CANDIDATE_EXPERIENCE}) specializing in Playwright, TypeScript & API "
                f"contract testing. Saw the open {title} role (Req: {req_id}) at {company} and would love to "
                f"connect and share my portfolio ({portfolio}) if you're open to referring!"
            )
            if len(note) > max_chars:
                diff = len(note) - max_chars + 3
                truncated_title = title[:-diff] + "..." if len(title) > diff + 4 else "SDET"
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
        direct job posting link, portfolio link, and referral ask, strictly capped at 1,000 characters.
        """
        company = extract_company_name(job_payload) or "your team"
        title = extract_job_title(job_payload) or "Senior SDET"
        req_id = extract_requisition_id(job_payload)
        job_url = clean_job_url(extract_job_url(job_payload))
        name = recipient_name.strip() if recipient_name and recipient_name.lower() != "there" else "there"

        job_url_line = f"Job Posting: {job_url}\n" if job_url else ""

        pitch = (
            f"Hi {name},\n\n"
            f"I hope you're having a great week.\n\n"
            f"I saw the {title} opening (Req #{req_id}) at {company} and wanted to reach out. "
            f"As an SDET with {CANDIDATE_EXPERIENCE} specializing in distributed test automation, "
            f"I believe my background aligns well with your team's engineering standards:\n\n"
            f"• Modular Playwright + TypeScript test execution with Docker CI sharding.\n"
            f"• Asynchronous Kafka event stream validation and Pact/WireMock API contract testing.\n"
            f"• CI/CD pipeline automation reducing regression feedback cycles.\n\n"
            f"{job_url_line}"
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
        quoted_company = urllib.parse.quote(f'"{clean_company}"') if clean_company else ""

        # Clean location to extract city or country if available
        loc_token = ""
        indian_hubs = [
            "bengaluru",
            "bangalore",
            "pune",
            "hyderabad",
            "india",
            "delhi",
            "noida",
            "gurgaon",
            "gurugram",
            "chennai",
            "mumbai",
        ]
        if location and any(k in location.lower() for k in indian_hubs):
            loc_token = "%20India"

        comp_token = f"%20{quoted_company}" if quoted_company else ""

        return {
            "engineering_managers": f"https://www.linkedin.com/search/results/people/?keywords=Engineering%20Manager{comp_token}{loc_token}&origin=GLOBAL_SEARCH_HEADER",
            "qa_leads": f"https://www.linkedin.com/search/results/people/?keywords=Quality%20Engineering%20Manager{comp_token}{loc_token}&origin=GLOBAL_SEARCH_HEADER",
            "tech_leads": f"https://www.linkedin.com/search/results/people/?keywords=Staff%20SDET{comp_token}{loc_token}&origin=GLOBAL_SEARCH_HEADER",
            "alumni": f"https://www.linkedin.com/search/results/people/?keywords=%22Value%20Labs%22{comp_token}{loc_token}&origin=GLOBAL_SEARCH_HEADER",
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
        company = extract_company_name(job_payload)
        title = extract_job_title(job_payload)
        location = extract_location(job_payload)
        job_url = clean_job_url(extract_job_url(job_payload))

        conn_note = cls.generate_connection_note(job_payload, recipient_name=recipient_name)
        inmail = cls.generate_inmail_pitch(job_payload, recipient_name=recipient_name)
        search_urls = cls.build_linkedin_search_urls(company, location=location)

        return {
            "requisition_id": req_id,
            "company_name": company,
            "job_title": title,
            "job_url": job_url,
            "location": location,
            "connection_note": conn_note,
            "connection_note_chars": len(conn_note),
            "inmail_pitch": inmail,
            "inmail_pitch_chars": len(inmail),
            "search_urls": search_urls,
        }
