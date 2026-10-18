"""
High-Precision NLP & Heuristic Classifier for LinkedIn Hiring Posts.
Evaluates author persona across Engineers, Leads, and Recruiters;
extracts contact channels (emails, ATS links, job codes);
eliminates job-seeker/commercial noise; and computes quality scores.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TARGET_COMPANIES_PATH = PROJECT_ROOT / "data" / "config" / "target_companies.json"

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", re.IGNORECASE)
URL_REGEX = re.compile(r"https?://[^\s<>\"'()]+", re.IGNORECASE)
JOB_CODE_REGEX = re.compile(
    r"\b(?:Job\s*Code|Req(?:\s*ID)?|Requisition(?:\s*ID)?|Job\s*ID)[:\s#]*([A-Za-z0-9_-]{4,20})\b", re.IGNORECASE
)

# Author headline job seeker badges (strong signal that the author themselves is seeking work)
HEADLINE_JOB_SEEKER_MARKERS = [
    "#opentowork",
    "open to work",
    "looking for new opportunities",
    "looking for job",
    "seeking new role",
    "actively seeking opportunities",
    "immediate joiner seeking",
    "open for opportunities",
]

# First-person job seeker phrases in post text (author asking for a job or referral for themselves)
FIRST_PERSON_SEEKER_MARKERS = [
    "i am looking for a job",
    "i'm looking for a job",
    "i am actively looking for a job",
    "i am looking for a new role",
    "i'm looking for a new role",
    "i am looking for opportunities",
    "i am actively looking for opportunities",
    "i am seeking new opportunities",
    "i'm seeking new opportunities",
    "please refer me",
    "can anyone refer me",
    "can someone refer me",
    "need a referral for myself",
    "i got laid off",
    "i was recently laid off",
    "i have been laid off",
    "looking for an opportunity for myself",
]

# Explicit hiring & referral intent markers (author is hiring or offering team referrals)
HIRING_INTENT_MARKERS = [
    "we are hiring",
    "we're hiring",
    "i am hiring",
    "i'm hiring",
    "my team is hiring",
    "our team is hiring",
    "actively hiring",
    "is hiring",
    "hiring for",
    "looking for an sdet",
    "looking for sdet",
    "looking for qa",
    "looking for automation",
    "looking for test",
    "looking for candidates",
    "actively looking for",
    "openings for",
    "opening for",
    "open role",
    "open roles",
    "open position",
    "open positions",
    "referral",
    "referrals",
    "referrals open",
    "referral open",
    "dm for referral",
    "dm for referrals",
    "happy to refer",
    "can refer",
    "referring for",
    "dm me your resume",
    "dm me",
    "reach out",
    "send your resume",
    "send resume",
    "share cv",
    "share your cv",
    "share your profile",
    "drop your resume",
    "drop your cv",
    "comment interested",
    "hiring drive",
    "immediate openings",
    "walk-in drive",
    "walkin drive",
]

COMMERCIAL_SPAM_MARKERS = [
    "100% placement",
    "placement guarantee",
    "free masterclass",
    "register here",
    "enroll now",
    "batch starting",
    "demo class",
    "course curriculum",
    "training institute",
    "upskill now",
]

PROMOTION_MARKERS = [
    "happy to share that i joined",
    "thrilled to share my promotion",
    "celebrating 5 years",
    "celebrating 1 year",
    "excited to start my new role as",
]

# Core SDET / QA relevance terms
ROLE_RELEVANCE_TERMS = [
    "sdet",
    "software engineer in test",
    "software development engineer in test",
    "set",
    "qa automation",
    "automation engineer",
    "test engineer",
    "test architect",
    "qa lead",
    "lead sdet",
    "sdet lead",
    "quality engineering",
    "lead automation",
    "playwright",
    "selenium",
]


class PostClassifier:
    """
    Classifies, cleans, and enriches LinkedIn hiring posts.
    Ensures broad inclusivity for Engineers, Leads, and Recruiters while strictly filtering noise.
    """

    def __init__(self, target_companies_path: Path | str | None = None):
        self.target_companies_path = Path(target_companies_path or TARGET_COMPANIES_PATH)
        self.dream_companies: set[str] = set()
        self._load_target_companies()

    def _load_target_companies(self) -> None:
        """Loads target enterprises and dream orgs from configuration."""
        if not self.target_companies_path.exists():
            return
        try:
            with open(self.target_companies_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                name = item.get("name") or item.get("company")
                if name:
                    self.dream_companies.add(name.strip().lower())
        except Exception:
            pass

    def extract_emails(self, text: str) -> list[str]:
        """Extracts unique clean email addresses from post content."""
        if not text:
            return []
        matches = EMAIL_REGEX.findall(text)
        cleaned = []
        for m in matches:
            m_clean = m.strip(".,;:!?()[]{}")
            if (
                "@" in m_clean
                and not m_clean.endswith((".png", ".jpg", ".jpeg", ".gif"))
                and m_clean.lower() not in [c.lower() for c in cleaned]
            ):
                cleaned.append(m_clean)
        return cleaned

    def extract_links(self, text: str) -> list[str]:
        """Extracts actionable external URLs (careers, forms, ATS links)."""
        if not text:
            return []
        matches = URL_REGEX.findall(text)
        cleaned = []
        for u in matches:
            u_clean = u.strip(".,;:!?()[]{}")
            # Filter out internal linkedin image/media links
            if any(k in u_clean for k in ["licdn.com", "media.licdn", "static.licdn"]):
                continue
            if u_clean not in cleaned:
                cleaned.append(u_clean)
        return cleaned

    def extract_job_codes(self, text: str) -> list[str]:
        """Extracts job codes or requisition IDs mentioned in post text."""
        if not text:
            return []
        matches = JOB_CODE_REGEX.findall(text)
        return list(dict.fromkeys(m.strip() for m in matches if len(m.strip()) >= 4))

    def classify_author_role(self, author_headline: str, post_text: str) -> str:
        """
        Classifies author role category without restricting to recruiters.
        Categories:
          - RECRUITER: HR, Talent Acquisition, Sourcer, Recruiter, People Partner
          - LEADER: Engineering Manager, QA Lead, Director, VP, Founder, Architect
          - ENGINEER: SDET, Software Engineer in Test, QA Automation, Test Engineer
          - PEER: Other company employees sharing referral opportunities
        """
        f"{author_headline} {post_text}".lower()
        headline_lower = (author_headline or "").lower()

        # Recruiter check
        if any(
            k in headline_lower
            for k in [
                "recruiter",
                "talent acquisition",
                "ta lead",
                "sourcer",
                "people partner",
                "human resources",
                "hr manager",
                "hr lead",
                "talent partner",
                "technical recruiter",
                "campus recruiter",
                "hiring specialist",
            ]
        ):
            return "RECRUITER"

        # Leader / Manager / Lead check
        if any(
            k in headline_lower
            for k in [
                "engineering manager",
                "qa lead",
                "lead sdet",
                "sdet lead",
                "director",
                "head of",
                "vp",
                "vice president",
                "founder",
                "co-founder",
                "lead test",
                "lead automation",
                "test lead",
                "tech lead",
                "engineering lead",
                "qa manager",
                "test manager",
                "principal sdet",
                "staff sdet",
                "test architect",
                "lead qa",
            ]
        ):
            return "LEADER"

        # Engineer check
        if any(
            k in headline_lower
            for k in [
                "sdet",
                "software engineer in test",
                "software development engineer in test",
                "automation engineer",
                "test engineer",
                "qa engineer",
                "quality engineer",
                "qa automation",
                "set",
                "senior sdet",
                "software engineer",
                "developer",
            ]
        ):
            return "ENGINEER"

        return "PEER"

    def is_hiring_post(self, author_headline: str, post_text: str) -> tuple[bool, str]:
        """
        Determines whether a post is a genuine hiring/referral lead.
        Ensures posts by SDETs, QA Leads, Engineering Managers, and Peers
        are NOT accidentally dropped by generic job-seeker keywords.
        Returns: (is_valid, reason)
        """
        headline_lower = (author_headline or "").lower()
        text_lower = (post_text or "").lower()
        combined = f"{headline_lower} {text_lower}"

        # 1. Reject if author headline explicitly badges as job seeker
        for marker in HEADLINE_JOB_SEEKER_MARKERS:
            if marker in headline_lower:
                return False, f"Author is a job seeker ({marker} in headline)"

        # 2. Reject EdTech Commercial Spam
        for marker in COMMERCIAL_SPAM_MARKERS:
            if marker in combined:
                return False, f"Commercial training/placement spam detected: '{marker}'"

        # 3. Check for Active Hiring / Referral Intent
        has_hiring_intent = any(marker in combined for marker in HIRING_INTENT_MARKERS)

        # 4. First-Person Job Seeker Filter (Author seeking employment for themselves)
        # If someone explicitly writes "I am looking for a job" and has NO hiring intent
        if not has_hiring_intent:
            for marker in FIRST_PERSON_SEEKER_MARKERS:
                if marker in text_lower:
                    return False, f"Job seeker self-promotion marker detected: '{marker}'"
            return False, "No active hiring or referral intent detected."

        # If they have first-person seeker markers AND lack explicit team hiring ("we are hiring", "my team"), reject
        if any(m in text_lower for m in FIRST_PERSON_SEEKER_MARKERS) and not any(
            team_signal in text_lower
            for team_signal in ["we are hiring", "we're hiring", "my team", "our team", "hiring for"]
        ):
            return False, "Author is seeking a referral/job rather than offering one."

        # 5. Reject Pure Celebration / Promotion Announcements without Hiring Intent
        for marker in PROMOTION_MARKERS:
            if marker in text_lower and not any(
                k in text_lower for k in ["we are hiring", "we're hiring", "my team is hiring", "openings", "referral"]
            ):
                return False, f"Promotion / joining celebration post: '{marker}'"

        # 6. Check for SDET / QA Role Relevance
        has_role = any(term in combined for term in ROLE_RELEVANCE_TERMS)
        if not has_role:
            return False, "Post does not mention SDET, QA, or Test Automation roles."

        return True, "Valid SDET/QA hiring or referral post."

    def extract_company_name(self, author_headline: str, post_text: str) -> tuple[str, bool]:
        """
        Extracts company name from headline or text and flags whether it is a Dream Org.
        Returns: (company_name, is_dream_org)
        """
        combined = f"{author_headline} {post_text}"
        combined_lower = combined.lower()

        # 1. Match against known dream companies first
        for dream in self.dream_companies:
            if dream in combined_lower:
                return dream.title(), True

        # 2. Check headline patterns: e.g. "SDET @ Okta", "Talent Acquisition at Angel One"
        match = re.search(
            r"(?:at|@)\s+([A-Za-z0-9\s&.-]{2,30}?)(?:\s*[|•\-,(]|$)", author_headline or "", re.IGNORECASE
        )
        if match:
            candidate = match.group(1).strip()
            if (
                candidate
                and len(candidate) > 1
                and candidate.lower() not in ["india", "bengaluru", "bangalore", "remote"]
            ):
                is_dream = candidate.lower() in self.dream_companies
                return candidate.title(), is_dream

        # 3. Check post text patterns: e.g. "Okta is hiring", "We at Angel One are looking"
        text_match = re.search(
            r"\b(?:at|we at|join our team at)\s+([A-Za-z0-9\s&.-]{2,25})\b", post_text or "", re.IGNORECASE
        )
        if text_match:
            candidate = text_match.group(1).strip()
            if (
                candidate
                and len(candidate) > 1
                and candidate.lower() not in ["india", "bengaluru", "bangalore", "remote"]
            ):
                is_dream = candidate.lower() in self.dream_companies
                return candidate.title(), is_dream

        return "Tech Enterprise", False

    def compute_quality_score(
        self,
        is_dream_org: bool,
        emails: list[str],
        links: list[str],
        job_codes: list[str],
        posted_at_relative: str,
        role_category: str,
    ) -> int:
        """
        Calculates a 0-100 quality score for prioritising the lead.
        """
        score = 40  # Base score for passing hiring + SDET filter

        if is_dream_org:
            score += 25
        if emails:
            score += 15
        if job_codes or links:
            score += 10

        # Freshness bonus
        rel = (posted_at_relative or "").lower()
        if "h" in rel or "m" in rel:  # Hours or minutes
            score += 10
        elif "1d" in rel or "2d" in rel:
            score += 5

        # Role authority bonus (Leads & Peers offering direct team referrals have high conversion)
        if role_category in ["LEADER", "ENGINEER"] or role_category == "RECRUITER":
            score += 5

        return min(score, 100)

    def process_raw_post(self, raw_post: dict[str, Any]) -> dict[str, Any] | None:
        """
        Validates, enriches, and formats a raw scraped post.
        Returns None if the post is filtered out as noise.
        """
        author_name = raw_post.get("author_name", "Unknown").strip()
        author_headline = raw_post.get("author_headline", "").strip()
        post_text = raw_post.get("post_text", "").strip()
        posted_at_relative = raw_post.get("posted_at_relative", "").strip()
        post_url = raw_post.get("post_url", "").strip()
        author_profile_url = raw_post.get("author_profile_url", "").strip()

        is_valid, _reason = self.is_hiring_post(author_headline, post_text)
        if not is_valid:
            return None

        emails = self.extract_emails(post_text)
        links = self.extract_links(post_text)
        job_codes = self.extract_job_codes(post_text)
        role_category = self.classify_author_role(author_headline, post_text)
        company_name, is_dream_org = self.extract_company_name(author_headline, post_text)
        quality_score = self.compute_quality_score(
            is_dream_org, emails, links, job_codes, posted_at_relative, role_category
        )

        post_id = raw_post.get("post_id")
        if not post_id:
            import hashlib

            post_id = (
                f"post_{hashlib.md5((post_url or (author_name + post_text[:100])).encode('utf-8')).hexdigest()[:12]}"
            )

        return {
            "post_id": post_id,
            "author_name": author_name,
            "author_headline": author_headline,
            "author_profile_url": author_profile_url,
            "company_name": company_name,
            "is_dream_org": is_dream_org,
            "post_url": post_url,
            "post_text": post_text,
            "posted_at_relative": posted_at_relative,
            "extracted_emails": emails,
            "extracted_links": links,
            "extracted_job_codes": job_codes,
            "author_role_category": role_category,
            "quality_score": quality_score,
            "outreach_status": "NEW",
        }
