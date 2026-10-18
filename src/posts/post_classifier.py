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
    r"\b(?:Job\s*(?:Code|ID|#)|Requisition\s*(?:ID|#)?|Req\s*(?:ID|#|Number|No\b))[:\s#]*([A-Za-z0-9_-]{3,20})\b",
    re.IGNORECASE,
)

COMMON_FALSE_JOB_CODES = {
    "required",
    "requirements",
    "responsibilities",
    "qualifications",
    "experience",
    "skills",
    "location",
    "details",
    "hybrid",
    "remote",
    "onsite",
    "bangalore",
    "bengaluru",
    "gurgaon",
    "noida",
    "hyderabad",
    "pune",
    "mumbai",
    "india",
    "and",
    "or",
    "with",
    "for",
    "the",
    "role",
    "code",
    "titles",
    "overview",
    "not",
    "none",
    "na",
    "apply",
    "dm",
    "link",
    "here",
    "below",
}

TECH_TOOL_KEYWORDS = {
    "docker",
    "postman",
    "gitlab",
    "github",
    "kafka",
    "elastic",
    "elasticsearch",
    "jira",
    "atlassian",
    "selenium",
    "playwright",
    "cypress",
    "kubernetes",
    "k8s",
    "aws",
    "azure",
    "gcp",
    "python",
    "java",
    "typescript",
    "javascript",
    "sql",
    "rest api",
    "testng",
    "pytest",
    "robot framework",
    "bdd",
    "cucumber",
    "appium",
    "jenkins",
    "ci/cd",
    "linux",
}

NON_COMPANY_WORDS = {
    "india",
    "bengaluru",
    "bangalore",
    "remote",
    "pune",
    "hyderabad",
    "delhi",
    "gurgaon",
    "noida",
    "mumbai",
    "chennai",
    "us",
    "usa",
    "worldwide",
    "global",
    "confidential",
    "stealth",
    "various",
    "multiple",
    "urgent",
    "immediate",
    "hiring",
    "openings",
    "opportunities",
    "referrals",
    "jobs",
    "team",
    "client",
    "product company",
    "recruitment",
    "career",
    "careers",
    "tech enterprise",
    "exciting",
    "excited",
    "several",
    "some",
    "our",
    "your",
    "my",
    "our team",
    "your team",
    "my team",
    "if your team",
    "new",
    "open",
    "right",
}

# Strict word-boundary affirmative team hiring regex (prevents 'your team' matching 'our team')
AFFIRMATIVE_HIRING_REGEX = re.compile(
    r"\b(?:we\s+are\s+hiring|we're\s+hiring|my\s+team\s+is\s+hiring|\bour\s+team\s+is\s+hiring|i\s+am\s+hiring|i'm\s+hiring|\bwe\s+at\b|\bjoin\s+our\s+team\b|for\s+my\s+team|for\s+our\s+team|dm\s+me\s+your\s+resume|dm\s+your\s+resume|send\s+your\s+resume|share\s+your\s+resume|share\s+your\s+cv|actively\s+looking\s+for\s+(?:an?\s+)?(?:senior\s+|lead\s+)?(?:sdet|qa|engineer|candidate))\b",
    re.IGNORECASE,
)

# Small caps translation map for LinkedIn unicode stylings (e.g. Oᴘᴇɴ ᴛᴏ Wᴏʀᴋ)
SMALL_CAPS_MAP = str.maketrans("ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ", "abcdefghijklmnopqrstuvwxyz")

# Author headline job seeker badges (strong signal that the author themselves is seeking work)
HEADLINE_JOB_SEEKER_MARKERS = [
    "#opentowork",
    "open to work",
    "open for work",
    "looking for new opportunities",
    "looking for job",
    "seeking new role",
    "actively seeking opportunities",
    "immediate joiner seeking",
    "open for opportunities",
]

# Conditional job seeker phrases where the author is asking the reader / network for a job
CONDITIONAL_SEEKER_PHRASES = [
    "if your team is hiring",
    "if you are hiring",
    "if anyone is hiring",
    "if someone is hiring",
    "if your company is hiring",
    "if you have openings",
    "if you have an opening",
    "if you have any openings",
    "let me know if you are hiring",
    "let me know if your team is hiring",
    "i lost my job",
    "i have lost my job",
    "i'm looking for my next",
    "i am looking for my next",
    "looking for my next role",
    "looking for my next opportunity",
    "exploring new opportunities",
    "exploring opportunities",
    "refer me",
    "can anyone refer me",
    "can someone refer me",
    "a referral would mean a lot",
    "a repost would also help",
    "a repost would help",
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
    "i have lost my job",
    "i lost my job",
    "looking for my next role",
    "looking for my next opportunity",
    "exploring new opportunities",
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
                if item.get("is_dream_org") is True:
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

    def clean_single_url(self, raw_url: str) -> str:
        """Sanitizes an individual URL by isolating tokens and stripping trailing artifacts."""
        if not raw_url:
            return ""
        u = raw_url.strip(" \t\r\n<>\"'()[]{}")
        if not u.startswith("http"):
            return ""

        # Strict lnkd.in shortlink isolation: https://lnkd.in/XXXXXXXX
        lnkd_match = re.match(r"^(https?://(?:www\.)?lnkd\.in/)([a-zA-Z0-9_-]+)", u, re.IGNORECASE)
        if lnkd_match:
            base = lnkd_match.group(1)
            token = lnkd_match.group(2)
            # Strip common concatenated trailing words attached to links without spaces
            token = re.sub(
                r"(Follow|Apply|Note|Post|Click|If|Here|Link|Share)$",
                "",
                token,
                flags=re.IGNORECASE,
            )
            if len(token) > 8:
                token = token[:8]
            return f"{base}{token}"

        # Truncate at first non-ASCII character (emojis, unicode boxes, ellipses)
        u = re.split(r"[^\x20-\x7E]", u)[0]
        # Strip common trailing concatenated action buttons/words
        u = re.sub(
            r"(Follow|Apply|Note|Post|Click|If|Here|Link|Share)$",
            "",
            u,
            flags=re.IGNORECASE,
        )
        u = u.rstrip(".,;:!?)]}\"'\\/-")
        return u

    def extract_links(self, text: str, additional_links: list[str] | None = None) -> list[str]:
        """Extracts and sanitizes actionable external URLs (careers, forms, ATS links)."""
        raw_candidates = list(additional_links or [])
        if text:
            raw_candidates.extend(URL_REGEX.findall(text))

        cleaned = []
        for raw in raw_candidates:
            u_clean = self.clean_single_url(raw)
            if not u_clean or len(u_clean) < 10:
                continue
            # Filter out internal linkedin image/media and author profile links
            if any(
                k in u_clean.lower()
                for k in ["licdn.com", "media.licdn", "static.licdn", "linkedin.com/in/", "linkedin.com/company/"]
            ):
                continue
            if u_clean not in cleaned:
                cleaned.append(u_clean)
        return cleaned

    def extract_job_codes(self, text: str) -> list[str]:
        """Extracts job codes or requisition IDs mentioned in post text."""
        if not text:
            return []
        matches = JOB_CODE_REGEX.findall(text)
        cleaned = []
        for m in matches:
            code = m.strip()
            if len(code) >= 3 and code.lower() not in COMMON_FALSE_JOB_CODES and code not in cleaned:
                cleaned.append(code)
        return cleaned

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
        if re.search(r"\bhr\b", headline_lower) or any(
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
                "staffing",
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
                "quality engineering",
                "qa specialist",
                "quality assurance",
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
        import unicodedata

        headline_lower = (author_headline or "").lower()
        # Normalize unicode fonts (e.g. mathematical bold/sans/small caps commonly used on LinkedIn)
        raw_text_norm = unicodedata.normalize("NFKD", post_text or "").translate(SMALL_CAPS_MAP)
        text_lower = raw_text_norm.lower()
        combined = f"{headline_lower} {text_lower}"

        # 1. Reject if author headline explicitly badges as job seeker
        for marker in HEADLINE_JOB_SEEKER_MARKERS:
            if marker in headline_lower:
                return False, f"Author is a job seeker ({marker} in headline)"

        has_affirmative_hiring = bool(AFFIRMATIVE_HIRING_REGEX.search(text_lower))

        # 1b. Reject if post text explicitly has job seeker badges or hashtags (#opentowork)
        # Distinguish from hirers stating "if you're open to work, DM me"
        author_open_to_work = False
        if (
            "#opentowork" in text_lower
            or "#openforwork" in text_lower
            or ("open to work" in text_lower or "open for work" in text_lower)
            and not re.search(r"\b(?:if\s+you(?:'re|\s+are)|anyone(?:\s+who\s+is)?)\s+open\s+to\s+work\b", text_lower)
        ):
            author_open_to_work = True

        if author_open_to_work and not has_affirmative_hiring:
            return False, "Author is seeking opportunities (#OpenToWork in post text)."

        # 1c. Reject if post contains conditional inquiries ("if your team is hiring", "if you are hiring")
        for cond in CONDITIONAL_SEEKER_PHRASES:
            if cond in text_lower and not has_affirmative_hiring:
                return False, f"Job seeker conditional inquiry detected: '{cond}'"

        # 2. Reject EdTech Commercial Spam
        for marker in COMMERCIAL_SPAM_MARKERS:
            if marker in combined:
                return False, f"Commercial training/placement spam detected: '{marker}'"

        # 3. Check for Active Hiring / Referral Intent
        # Strip conditional phrases ("if your team is hiring") so bare "is hiring" won't falsely trigger
        text_for_hiring = re.sub(
            r"\bif\s+(?:your\s+team|you|anyone|someone|your\s+company)\s+is\s+hiring\b",
            "",
            combined,
            flags=re.IGNORECASE,
        )
        text_for_hiring = re.sub(r"\byour\s+team\s+is\s+hiring\b", "", text_for_hiring, flags=re.IGNORECASE)
        has_hiring_intent = any(marker in text_for_hiring for marker in HIRING_INTENT_MARKERS) or has_affirmative_hiring

        # 4. First-Person Job Seeker Filter (Author seeking employment for themselves)
        if not has_hiring_intent:
            for marker in FIRST_PERSON_SEEKER_MARKERS:
                if marker in text_lower:
                    return False, f"Job seeker self-promotion marker detected: '{marker}'"
            return False, "No active hiring or referral intent detected."

        # If they have first-person seeker markers AND lack explicit team hiring ("we are hiring", "my team"), reject
        if any(m in text_lower for m in FIRST_PERSON_SEEKER_MARKERS) and not has_affirmative_hiring:
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

    def _sanitize_company_candidate(self, candidate: str) -> str | None:
        """Cleans and validates a potential company name candidate."""
        if not candidate:
            return None
        # Strip leading and trailing punctuation
        c = re.sub(r"^[\s\-_|•\.,;:!?/]+", "", candidate).strip()
        c = re.sub(r"[\s\-_|•\.,;:!?/]+$", "", c).strip()
        c_lower = c.lower()
        if len(c) < 2 or len(c) > 35:
            return None

        # Strip leading conversational words / prepositions / pronouns
        c = re.sub(
            r"^(?:if\s+your\s+team|if\s+you|if\s+|your\s+|our\s+|my\s+|the\s+|a\s+|an\s+|several\s+|multiple\s+|various\s+|some\s+|right\s+|new\s+|open\s+|team\s+|excited\s+|exciting\s+)",
            "",
            c,
            flags=re.IGNORECASE,
        ).strip()
        c = re.sub(r"^[\s\-_|•\.,;:!?/]+", "", c).strip()
        c_lower = c.lower()
        if not c or len(c) < 2:
            return None

        if c_lower in NON_COMPANY_WORDS:
            return None
        # Disallow pure tech tools unless explicitly validated with employer preposition
        if c_lower in TECH_TOOL_KEYWORDS:
            return None

        # Reject conversational fragments
        if any(
            bad in c_lower
            for bad in [
                "if your team",
                "your team",
                "our team",
                "my team",
                "several exciting",
                "exciting opportunities",
                "multiple roles",
                "open opportunities",
                "job openings",
            ]
        ):
            return None
        return c

    def extract_company_name(self, author_headline: str, post_text: str) -> tuple[str, bool]:
        """
        Extracts company name from author headline or post text with strict tech-tool disambiguation.
        Returns: (company_name, is_dream_org)
        """
        headline = author_headline or ""
        text = post_text or ""

        # 1. Author headline employment: e.g. "Senior SDET @ Swiggy", "QA Lead at Okta | Ex-MSFT"
        match = re.search(r"(?:at|@)\s+([A-Za-z0-9\s&.-]{2,35}?)(?:\s*(?:[|•\-,(]|#|$))", headline, re.IGNORECASE)
        if match:
            cand = self._sanitize_company_candidate(match.group(1))
            if cand:
                is_dream = cand.lower() in self.dream_companies
                return cand.title(), is_dream

        # 2. Post text explicit hiring triggers:
        # e.g. "Swiggy is actively hiring", "Blitz is Hiring", "IRIS Software – Multiple Job Openings"
        patterns = [
            r"(?<!if\s)(?<!your\s)\b([A-Za-z0-9\s&.-]{2,25})\s+is\s+(?:actively\s+)?hiring\b",
            r"(?:🚀|📢|🔥|✨|👉|📍)\s*([A-Za-z0-9\s&.-]{2,25})\s*(?:–|-|:)\s*(?:Multiple|Job|Hiring|Openings|Referrals)",
            r"\b(?:hiring for|join our team at|openings at|referrals for|we at)\s+([A-Za-z0-9\s&.-]{2,25})\b",
            r"team at\s+([A-Za-z0-9\s&.-]{2,25})\s+is\s+expanding",
        ]
        for pat in patterns:
            p_match = re.search(pat, text, re.IGNORECASE)
            if p_match:
                cand = self._sanitize_company_candidate(p_match.group(1))
                if cand:
                    is_dream = cand.lower() in self.dream_companies
                    return cand.title(), is_dream

        # 3. Contextual Dream Org Mention (Only when preceded by explicit hiring/referral verbs)
        for dream in self.dream_companies:
            if dream in TECH_TOOL_KEYWORDS:
                # Require explicit employment marker for dual-purpose names (e.g. Postman, Docker)
                pat = rf"\b(?:at|@|referrals? for|join|hiring for)\s+{re.escape(dream)}\b"
                if re.search(pat, headline, re.IGNORECASE) or re.search(pat, text, re.IGNORECASE):
                    return dream.title(), True
            else:
                pat = rf"\b{re.escape(dream)}\b"
                if re.search(pat, headline, re.IGNORECASE) or re.search(pat, text, re.IGNORECASE):
                    return dream.title(), True

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

        raw_links = raw_post.get("dom_links", [])
        emails = self.extract_emails(post_text)
        links = self.extract_links(post_text, additional_links=raw_links)
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
