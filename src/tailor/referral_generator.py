"""
Referral Reconnaissance & Dual-Funnel Outreach Engine.
Formulates high-conversion, proof-of-work referral requests citing exact Requisition IDs
and candidate architecture metrics while strictly enforcing platform character limits
(<300 chars for LinkedIn Connection Requests, <1000 chars for InMail pitches).
"""

from __future__ import annotations

import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any

CANDIDATE_PORTFOLIO = "https://manjunathhk.netlify.app/"
CANDIDATE_LINKEDIN = "https://www.linkedin.com/in/manjunath-h-k-ab30b1146/"
CANDIDATE_NAME = "Manjunath H K"
CANDIDATE_EXPERIENCE = "~6.8 YOE"
CANDIDATE_PAST_COMPANIES = ("value labs", "valuelabs", "dunzo", "tata elxsi")
CANDIDATE_ALMA_MATER = ("sjce", "sri jayachamarajendra", "jss science and technology", "jssstu")
INFLUENCER_KEYWORDS = (
    "top voice",
    "influencer",
    "youtuber",
    "content creator",
    "keynote speaker",
    "tedx",
    "newsletter",
    "10k+",
    "20k+",
    "50k+",
    "100k+",
    "followers",
)


def parse_follower_count(text: str | int | None) -> int:
    """Parses follower counts like '12,400 followers', '15.2K followers', or integer values."""
    if isinstance(text, int):
        return text
    if not text or not isinstance(text, str):
        return 0
    m = re.search(r"(\d+(?:[\.,]\d+)?)\s*([kKmM])?\+?\s*followers", text, re.IGNORECASE)
    if not m:
        # Check bare number string if passed directly
        m2 = re.fullmatch(r"\s*(\d+(?:,\d+)*)\s*", text)
        if m2:
            return int(m2.group(1).replace(",", ""))
        return 0
    raw_num = m.group(1).replace(",", "")
    suffix = (m.group(2) or "").lower()
    try:
        val = float(raw_num)
        if suffix == "k":
            return int(val * 1000)
        if suffix == "m":
            return int(val * 1_000_000)
        return int(val)
    except Exception:
        return 0


def is_verified_current_employee(headline: str, target_company: str, experience_text: str = "") -> bool:
    """Verifies that a lead is currently employed at `target_company` and NOT a former ('Ex-') employee."""
    comp = (target_company or "").strip().lower()
    if not comp:
        return False
    hl = (headline or "").strip().lower()
    exp = (experience_text or "").strip().lower()
    combined = f"{hl} {exp}".strip()

    # Check if company name is present at all
    comp_tokens = [t for t in re.split(r"[^a-z0-9]+", comp) if len(t) >= 2]
    primary_token = comp_tokens[0] if comp_tokens else comp
    if comp not in combined and primary_token not in combined:
        return False

    # Reject explicit former-employee markers attached to target company (e.g., "Ex-Swiggy", "Ex Swiggy", "Formerly at Swiggy")
    for tok in {comp, primary_token}:
        ex_pattern = rf"\b(ex[-\s]+|former\s+.*?\b|previously\s+.*?\b|past\s+.*?\b|intern\s+at\s+){re.escape(tok)}\b"
        if re.search(ex_pattern, hl):
            # Only allow if they also explicitly state current role "@ <Company>" before the "Ex-" clause
            current_pattern = rf"^(?!.*\bex[-\s]+{re.escape(tok)}).*?(@|at\s+)\s*{re.escape(tok)}\b"
            if not re.search(current_pattern, hl):
                return False

    # Reject if headline starts with "Ex-" or "Former" for that company
    return not re.search(rf"\bex[-\s]*{re.escape(primary_token)}\b", hl)


def score_referral_candidate(candidate: dict[str, Any], target_company: str) -> dict[str, Any]:
    """Scores a potential referral contact (0-100) to prioritize 'Low-Key High-Responders' and reject influencers/ex-employees.

    Expected `candidate` keys:
      - name: str
      - headline: str
      - profile_url: str
      - followers: int | str (optional)
      - activity_snippet / post_text: str (optional)
      - is_post_author: bool (optional)
      - post_url: str (optional)
      - experience_text: str (optional)
      - tenure_months: int (optional)
    """
    headline = str(candidate.get("headline") or "").strip()
    hl_low = headline.lower()
    exp_text = str(candidate.get("experience_text") or "").strip()
    activity = str(candidate.get("activity_snippet") or candidate.get("post_text") or "").strip().lower()
    followers = parse_follower_count(candidate.get("followers") or headline)

    reasons: list[str] = []

    # 1. Hard Reject: Not a verified current employee (e.g. "Ex-Swiggy" or unverified company)
    if not is_verified_current_employee(headline, target_company, experience_text=exp_text):
        return {
            **candidate,
            "eligible": False,
            "responder_score": -100,
            "tier": "REJECTED_NOT_CURRENT_EMPLOYEE",
            "reasons": [f"Not verified as current employee at {target_company} (or matched 'Ex-{target_company}')"],
        }

    # 2. Hard Reject: High-follower LinkedIn Influencer (> 3,000 followers) or Creator/Top Voice headline
    if followers > 3000:
        return {
            **candidate,
            "eligible": False,
            "responder_score": -100,
            "tier": "REJECTED_INFLUENCER",
            "reasons": [f"High follower count ({followers} > 3,000 cap) -> <1% DM response rate"],
        }

    for inf_kw in ("top voice", "influencer", "youtuber", "content creator", "keynote speaker", "tedx"):
        if inf_kw in hl_low:
            return {
                **candidate,
                "eligible": False,
                "responder_score": -100,
                "tier": "REJECTED_INFLUENCER",
                "reasons": [f"Influencer/Creator headline marker ('{inf_kw}') -> low referral conversion"],
            }

    score = 20  # Base score for verified current employee

    # 3. Tier S Boost: Authored a Hiring / Referral Post (+45 pts) or 1st-Degree Connection (+40 pts)
    has_referral_post = bool(
        candidate.get("is_post_author")
        or candidate.get("post_url")
        or re.search(
            r"\b(hiring|happy to refer|dm for referral|open role|we're looking for|drop your resume)\b", activity
        )
    )
    is_first_degree = bool(
        candidate.get("is_first_degree")
        or str(candidate.get("degree") or "").strip().lower() in ("1st", "1")
        or re.search(r"\b1st(\s+degree)?\b", f"{hl_low} {exp_text.lower()}")
    )
    if has_referral_post:
        score += 45
        reasons.append("Authored hiring/referral post (+45)")
    if is_first_degree:
        score += 40
        reasons.append("1st-degree connection (free direct Message unlocked, 0 note cap) (+40)")

    # 4. Shared Warm Affinity: Ex-Dunzo / Ex-Value Labs / Ex-Tata Elxsi / SJCE Alumni (+35 pts)
    combined_bg = f"{hl_low} {exp_text.lower()}"
    if any(co in combined_bg for co in CANDIDATE_PAST_COMPANIES):
        score += 35
        reasons.append("Shared past employer overlap (Value Labs / Dunzo / Tata Elxsi) (+35)")
    elif any(sch in combined_bg for sch in CANDIDATE_ALMA_MATER):
        score += 35
        reasons.append("Shared alma mater (SJCE / JSS) (+35)")

    # 5. Role Relevance: Same-Function Peer IC vs Hiring Manager vs C-Suite
    if re.search(r"\b(vp|vice president|chief|cto|ceo|president|partner)\b", hl_low):
        score -= 30
        reasons.append("Executive/VP title (-30)")
    elif re.search(r"\b(sdet|qa|quality\s*engineer|test\s*engineer|automation\s*engineer)\b", hl_low):
        if re.search(r"\b(manager|lead|staff|principal|architect|head)\b", hl_low):
            score += 25
            reasons.append("QA/SDET Hiring Lead or Architect (+25)")
        else:
            score += 25
            reasons.append("Same-function Peer SDET/QA IC (+25)")
    elif re.search(r"\b(engineering\s*manager|talent\s*acquisition|technical\s*recruiter|recruiter)\b", hl_low):
        score += 20
        reasons.append("Engineering Manager / Technical Recruiter (+20)")
    elif re.search(r"\b(software\s*engineer|sde|member\s*of\s*technical\s*staff|mts|senior\s*engineer)\b", hl_low):
        score += 15
        reasons.append("Peer Software Engineer IC (+15)")

    # 6. Recent Joiner Empathy (< 18 months) (+15 pts)
    tenure = candidate.get("tenure_months")
    if isinstance(tenure, (int, float)) and 1 <= tenure <= 18:
        score += 15
        reasons.append(f"Recent joiner ({int(tenure)} mos) (+15)")

    # 7. Low-Key Follower Sweet Spot (50 to 2,500 followers) (+10 pts)
    if 0 < followers <= 2500:
        score += 10
        reasons.append(f"Low-key follower count ({followers}) (+10)")

    final_score = max(0, min(100, score))
    if has_referral_post:
        tier = "TIER_S_POST_AUTHOR"
    elif final_score >= 70:
        tier = "TIER_A_WARM_PEER_OR_ALUMNI"
    elif final_score >= 45:
        tier = "TIER_B_VERIFIED_PEER"
    else:
        tier = "TIER_C_GENERAL_EMPLOYEE"

    return {
        **candidate,
        "eligible": True,
        "responder_score": final_score,
        "tier": tier,
        "reasons": reasons,
    }


class InterviewRouter:
    """Determines whether a job should be Fast-Sniped immediately, routed via Post-Author DM, or held for a 36h Referral SLA."""

    @staticmethod
    def compute_job_age_hours(job_payload: dict[str, Any]) -> float | None:
        """Calculates job age in hours from `posted_at` timestamp if available."""
        details = job_payload.get("job_details") or {}
        raw_posted = job_payload.get("posted_at") or details.get("posted_at")
        if not raw_posted:
            return None
        try:
            if isinstance(raw_posted, datetime):
                dt = raw_posted
            else:
                dt = datetime.fromisoformat(str(raw_posted).replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            delta = datetime.utcnow() - dt
            return max(0.0, round(delta.total_seconds() / 3600.0, 2))
        except Exception:
            return None

    @classmethod
    def classify_job_strategy(
        cls,
        job_payload: dict[str, Any],
        matched_posts: list[dict[str, Any]] | None = None,
        sla_hours: float = 36.0,
    ) -> dict[str, Any]:
        """Classifies a job into the 3-Tier Interview Routing Matrix."""
        details = job_payload.get("job_details") or {}
        is_dream = bool(job_payload.get("is_dream_org") or details.get("is_dream_org"))
        url = extract_job_url(job_payload).lower()
        source = str(job_payload.get("source") or details.get("source") or "").lower()
        is_workday = "workday" in url or "myworkdayjobs" in url or source == "workday"
        age_hours = cls.compute_job_age_hours(job_payload)

        # Freshness priority boost
        if age_hours is not None and age_hours <= 3.0:
            freshness_badge = "🔥 SNIPER (<3h old)"
            priority_boost = 25
        elif age_hours is not None and age_hours <= 24.0:
            freshness_badge = "⚡ EARLY (<24h old)"
            priority_boost = 15
        elif age_hours is not None and age_hours > 72.0:
            freshness_badge = "🕒 STALE (>72h old)"
            priority_boost = -15
        else:
            freshness_badge = "📅 STANDARD"
            priority_boost = 0

        # Tier 0: Direct Hiring Post Match exists!
        if matched_posts:
            best_post = matched_posts[0]
            return {
                "routing_tier": "TIER_0_POST_AUTHOR",
                "allow_immediate_apply": not (is_dream and is_workday),
                "referral_sla_hours": sla_hours if (is_dream and is_workday) else 0.0,
                "age_hours": age_hours,
                "freshness_badge": freshness_badge,
                "priority_boost": priority_boost + 30,
                "associated_post_url": best_post.get("post_url", ""),
                "post_author_name": best_post.get("author_name", ""),
                "post_author_url": best_post.get("author_profile_url", ""),
                "rationale": "Direct hiring/referral post found -> message post author immediately.",
            }

        # Tier 2: Dream Enterprise or Workday ATS -> Hold for 36h Referral SLA (preserves Workday bonus attribution)
        if is_dream or is_workday:
            return {
                "routing_tier": "TIER_2_REFERRAL_SLA",
                "allow_immediate_apply": False,
                "referral_sla_hours": sla_hours,
                "age_hours": age_hours,
                "freshness_badge": freshness_badge,
                "priority_boost": priority_boost + 10,
                "associated_post_url": "",
                "post_author_name": "",
                "post_author_url": "",
                "rationale": f"Dream Org / Workday source ownership rule -> Scout 3 low-key referrers first; auto-unlock direct apply after {int(sla_hours)}h SLA.",
            }

        # Tier 1: Growth Startup / Scaleup (<24h old) -> Fast-Snipe Immediately
        if age_hours is None or age_hours <= 24.0:
            return {
                "routing_tier": "TIER_1_SNIPER_APPLY",
                "allow_immediate_apply": True,
                "referral_sla_hours": 0.0,
                "age_hours": age_hours,
                "freshness_badge": freshness_badge,
                "priority_boost": priority_boost,
                "associated_post_url": "",
                "post_author_name": "",
                "post_author_url": "",
                "rationale": "Fresh growth/scaleup drop -> Fast-snipe immediately (<3 min) for first-applicant 4x callback multiplier.",
            }

        # Tier 1B: Older Non-Dream role -> Batch apply + ping 2 peers
        return {
            "routing_tier": "TIER_1B_APPLY_AND_PEER_PING",
            "allow_immediate_apply": True,
            "referral_sla_hours": 0.0,
            "age_hours": age_hours,
            "freshness_badge": freshness_badge,
            "priority_boost": priority_boost,
            "associated_post_url": "",
            "post_author_name": "",
            "post_author_url": "",
            "rationale": "Standard growth/scaleup role -> Batch apply immediately + ping 2 low-key team peers.",
        }


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
    def build_linkedin_search_urls(company_name: str, location: str = "", req_id: str = "") -> dict[str, str]:
        """
        Builds pre-scoped LinkedIn People & Content search URLs to identify:
        1. Hiring Posts / Active Referrers for the company (Content Search)
        2. Shared Past-Company & College Alumni (Dunzo, Value Labs, SJCE)
        3. Low-Key Peer SDETs & QA Leads at the target company.
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
        post_kw = urllib.parse.quote(
            f'"{clean_company}" ("hiring" OR "referral" OR "openings") ("SDET" OR "QA" OR "Automation")'
        )
        company_slug = re.sub(r"[^a-z0-9\-]+", "-", clean_company.lower()).strip("-")
        if clean_company.lower() == "swiggy":
            company_slug = "swiggy-in"

        return {
            "company_people_sdet": f"https://www.linkedin.com/company/{company_slug}/people/?keywords=SDET",
            "hiring_posts_content": f"https://www.linkedin.com/search/results/content/?datePosted=%22past-week%22&keywords={post_kw}&sortBy=%22date_posted%22",
            "peer_sdet_ics": f"https://www.linkedin.com/search/results/people/?keywords=Senior%20SDET{comp_token}{loc_token}&origin=GLOBAL_SEARCH_HEADER",
            "ex_dunzo_alumni": f"https://www.linkedin.com/search/results/people/?keywords=%22Dunzo%22{comp_token}{loc_token}&origin=GLOBAL_SEARCH_HEADER",
            "alumni": f"https://www.linkedin.com/search/results/people/?keywords=%22Value%20Labs%22{comp_token}{loc_token}&origin=GLOBAL_SEARCH_HEADER",
            "sjce_alumni": f"https://www.linkedin.com/search/results/people/?keywords=%22SJCE%22{comp_token}{loc_token}&origin=GLOBAL_SEARCH_HEADER",
            "engineering_managers": f"https://www.linkedin.com/search/results/people/?keywords=Engineering%20Manager{comp_token}{loc_token}&origin=GLOBAL_SEARCH_HEADER",
            "qa_leads": f"https://www.linkedin.com/search/results/people/?keywords=Quality%20Engineering%20Manager{comp_token}{loc_token}&origin=GLOBAL_SEARCH_HEADER",
            "tech_leads": f"https://www.linkedin.com/search/results/people/?keywords=Staff%20SDET{comp_token}{loc_token}&origin=GLOBAL_SEARCH_HEADER",
        }

    @staticmethod
    def generate_post_acceptance_dm(
        job_payload: dict[str, Any],
        recipient_name: str = "there",
        associated_post_url: str = "",
    ) -> str:
        """Generates a concise post-acceptance DM (used after a blank connection invite is accepted, bypassing the 5-note/month free cap)."""
        company = extract_company_name(job_payload) or "your company"
        title = extract_job_title(job_payload) or "Senior SDET"
        req_id = extract_requisition_id(job_payload)
        job_url = clean_job_url(extract_job_url(job_payload))
        name = recipient_name.strip() if recipient_name and recipient_name.lower() != "there" else "there"

        post_ref = (
            f"I saw your recent post ({associated_post_url}) and wanted to reach out! " if associated_post_url else ""
        )
        return (
            f"Hi {name}, thanks for connecting! {post_ref}"
            f"I'm a Senior SDET ({CANDIDATE_EXPERIENCE}, currently at Value Labs, previously Dunzo & Tata Elxsi) "
            f"specializing in Java/Python, REST Assured, Selenium & Playwright automation.\n\n"
            f"I'm very interested in the {title} role (Req: {req_id}) at {company}"
            f"{f' ({job_url})' if job_url else ''} and have held off on applying directly so an internal referral can be logged cleanly.\n\n"
            f"Portfolio: {CANDIDATE_PORTFOLIO}\n"
            f"If you're open to referring me, I'd be grateful to share my resume PDF and details!"
        )

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
        post_accept_dm = cls.generate_post_acceptance_dm(job_payload, recipient_name=recipient_name)
        search_urls = cls.build_linkedin_search_urls(company, location=location, req_id=req_id)
        routing = InterviewRouter.classify_job_strategy(job_payload)

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
            "post_acceptance_dm": post_accept_dm,
            "routing_strategy": routing,
            "search_urls": search_urls,
        }
