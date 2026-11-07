"""
Standardized Ingestion Filtering Engine.
Centralized heuristics for SDET/QA role qualification, negative title exclusion,
and strict geographical/remote location matching across all ATS providers.
"""

from __future__ import annotations

import re
from typing import Any

# Positive matches for Software Development Engineer in Test & QA roles
POSITIVE_SDET_REGEX = re.compile(
    r"\b("
    r"sdet|"
    r"software development engineer in test|"
    r"software engineer in test|"
    r"software (?:development |dev\.? )?engineer[\s,-]+(?:[ivx123]+[\s,-]+)?test|"
    r"engineer in quality|"
    r"qa\b|"
    r"qe\b|"
    r"quality assurance|"
    r"quality engineer|"
    r"quality analyst|"
    r"test[\s,-]+automation|"
    r"automation testing|"
    r"playwright automation|"
    r"automation engineer|"
    r"automation architect|"
    r"automation(?: technical)? lead|"
    r"test engineer|"
    r"testing engineer|"
    r"software test(?:ing)?|"
    r"testing services|"
    r"platform testing|"
    r"test lead|"
    r"api tester|"
    r"test development engineer|"
    r"test infrastructure|"
    r"mobile qa|"
    r"ai qa|"
    r"ai test|"
    r"llm evaluation|"
    r"evaluation engineer|"
    r"ai quality|"
    r"genai qa|"
    r"ml quality|"
    r"agentic qa|"
    r"qa lead\s*[-,\s]\s*ai|"
    r"devsecops qa|"
    r"security automation engineer|"
    r"ai red team|"
    r"red teaming|"
    r"browser automation engineer"
    r")\b",
    re.IGNORECASE,
)

# Negative exclusions: Non-SDET engineering, management, IT operations, or business roles
NEGATIVE_TITLE_REGEX = re.compile(
    r"\b("
    r"product manager|"
    r"program manager|"
    r"project manager|"
    r"engineering manager|"
    r"director|"
    r"vp\b|"
    r"vice president|"
    r"head of|"
    r"it automation|"
    r"it support|"
    r"internal it|"
    r"desktop support|"
    r"compliance|"
    r"financial automation|"
    r"revenue automation|"
    r"finance|"
    r"accounting|"
    r"tax|"
    r"sales|"
    r"account manager|"
    r"account executive|"
    r"customer success|"
    r"marketing|"
    r"recruiter|"
    r"recruiting|"
    r"talent acquisition|"
    r"people analytics|"
    r"hr\b|"
    r"search quality|"
    r"database automation|"
    r"automation specialist|"
    r"operations specialist|"
    r"dcsc|"
    r"soc analyst|"
    r"soc l1|"
    r"soc l2|"
    r"grc|"
    r"information security auditor|"
    r"iam administrator|"
    r"penetration tester|"
    r"ethical hacker|"
    r"dataset reviewer|"
    r"data annotator|"
    r"ai trainer|"
    r"manual tester|"
    r"plc|"
    r"fpga|"
    r"dft|"
    r"typst|"
    r"network\s+automation|"
    r"it\s+infrastructure|"
    r"post-silicon|"
    r"high\s+speed\s+io|"
    r"bluetooth\s+automation"
    r")\b",
    re.IGNORECASE,
)

# Indian tech hubs and geography
INDIAN_LOCATIONS_REGEX = re.compile(
    r"\b("
    r"bengaluru|"
    r"bangalore|"
    r"hyderabad|"
    r"pune|"
    r"gurgaon|"
    r"gurugram|"
    r"noida|"
    r"delhi|"
    r"delhi ncr|"
    r"chennai|"
    r"mumbai|"
    r"karnataka|"
    r"telangana|"
    r"maharashtra|"
    r"tamil nadu|"
    r"india|"
    r"ind\b"
    r")\b",
    re.IGNORECASE,
)

# Explicit foreign countries / overseas hubs to reject unless matched with an Indian office
FOREIGN_LOCATION_REGEX = re.compile(
    r"\b("
    r"usa|"
    r"united states|"
    r"u\.s\.|"
    r"u\.s\.a\.|"
    r"us\b|"
    r"america|"
    r"canada|"
    r"ontario|"
    r"quebec|"
    r"british columbia|"
    r"uk\b|"
    r"united kingdom|"
    r"great britain|"
    r"england|"
    r"london|"
    r"germany|"
    r"deutschland|"
    r"berlin|"
    r"munich|"
    r"australia|"
    r"sydney|"
    r"melbourne|"
    r"singapore|"
    r"netherlands|"
    r"amsterdam|"
    r"france|"
    r"paris|"
    r"spain|"
    r"madrid|"
    r"barcelona|"
    r"brazil|"
    r"sao paulo|"
    r"japan|"
    r"tokyo|"
    r"ireland|"
    r"dublin|"
    r"poland|"
    r"warsaw|"
    r"israel|"
    r"tel aviv|"
    r"california|"
    r"san francisco|"
    r"san jose|"
    r"santa clara|"
    r"sunnyvale|"
    r"mountain view|"
    r"palo alto|"
    r"new york|"
    r"seattle|"
    r"washington|"
    r"dc\b|"
    r"maryland|"
    r"virginia|"
    r"texas|"
    r"austin|"
    r"chicago|"
    r"illinois|"
    r"los angeles|"
    r"boston|"
    r"massachusetts|"
    r"denver|"
    r"colorado|"
    r"toronto|"
    r"vancouver|"
    r"montreal"
    r")\b",
    re.IGNORECASE,
)

# Verified worldwide / global remote indicators
GLOBAL_REMOTE_REGEX = re.compile(
    r"\b("
    r"worldwide|"
    r"anywhere|"
    r"global remote|"
    r"work from anywhere|"
    r"remote - global|"
    r"remote - apac|"
    r"remote - emea/apac|"
    r"all locations"
    r")\b",
    re.IGNORECASE,
)

# Strict legal, citizenship, security clearance, or geographic exclusivity restrictions
JURISDICTION_RESTRICTIONS_REGEX = re.compile(
    r"\b("
    r"us citizens? only|"
    r"u\.s\. citizens? only|"
    r"security clearance|"
    r"ts/sci|"
    r"polygraph|"
    r"us or canada only|"
    r"must be located in the us|"
    r"must be based in the us|"
    r"must reside in (?:the )?(?:us|usa|united states|canada|uk|eu)|"
    r"us resident only|"
    r"us residency required|"
    r"authorized to work in the us without sponsorship|"
    r"authorized to work in the us only|"
    r"w-?2 only|"
    r"c2c not allowed|"
    r"no c2c|"
    r"no corp-to-corp|"
    r"itar|"
    r"fedramp|"
    r"must be based in north america|"
    r"north america only|"
    r"latin america only|"
    r"latam only|"
    r"must be based in the uk|"
    r"uk residents? only|"
    r"eu residents? only|"
    r"european union only"
    r")\b",
    re.IGNORECASE,
)

# Foreign Currency Regex for global remote compensation detection
FOREIGN_CURRENCY_REGEX = re.compile(
    r"(?:"
    r"\$\s?\d{2,3}(?:,\d{3})+(?:\s?-\s?\$\s?\d{2,3}(?:,\d{3})+)?|"
    r"\$\d{2,3}[kK]\s?-\s?\$\d{2,3}[kK]|"
    r"\bUSD\s?\d{2,3}[kK]?|"
    r"\b(?:EUR|€|GBP|£)\s?\d{2,3}[kK,]+|"
    r"\$\d{2,3}\s?/\s?(?:hr|hour)"
    r")",
    re.IGNORECASE,
)

# Cross-Border EOR & B2B Signal Regex
EOR_B2B_REGEX = re.compile(
    r"\b("
    r"deel|"
    r"oyster\s?hr|"
    r"remote\.com|"
    r"multiplier|"
    r"papaya\s?global|"
    r"b2b\s+contract(?:or)?|"
    r"independent\s+contractor|"
    r"work\s+from\s+anywhere|"
    r"global\s+remote|"
    r"async-first|"
    r"anywhere in the world"
    r")\b",
    re.IGNORECASE,
)


def has_jurisdiction_restriction(text: str | None) -> bool:
    """
    Evaluates whether job requirements or descriptions contain legal or geographic
    exclusivity clauses (e.g. US citizenship, security clearance, or North America only)
    that render international remote candidates ineligible.
    """
    if not text or not text.strip():
        return False
    if not JURISDICTION_RESTRICTIONS_REGEX.search(text):
        return False

    # Check for hard legal/clearance locks (citizenship, clearance, ITAR, FedRAMP, W2 only, C2C exclusion)
    is_hard_lock = bool(
        re.search(
            r"\b(us citizens? only|u\.s\. citizens? only|security clearance|ts/sci|polygraph|itar|fedramp|w-?2 only|no c2c|no corp-to-corp)\b",
            text,
            re.IGNORECASE,
        )
    )
    if is_hard_lock:
        return True

    # If general location restriction exists (e.g. must reside in US/EU) but India or Bengaluru is co-listed
    return not re.search(r"\b(india|bengaluru|bangalore)\b", text, re.IGNORECASE)


def is_sdet_title(title: str | None) -> bool:
    """
    Evaluates whether a role title represents an authentic SDET / QA / Test Automation position,
    enforcing negative exclusions against IT support, management, and unrelated business roles.
    """
    if not title or not title.strip():
        return False
    clean_title = title.strip()
    # 1. Enforce negative exclusions first
    if NEGATIVE_TITLE_REGEX.search(clean_title):
        return False
    # 2. Check for positive SDET / QA qualification
    return bool(POSITIVE_SDET_REGEX.search(clean_title))


def is_india_or_remote_location(
    location_str: str | None,
    allow_unspecified: bool = False,
    text_snippet: str | None = None,
) -> bool:
    """
    Evaluates whether a location string corresponds to an Indian tech hub or a viable Global Remote role,
    strictly rejecting explicit US, UK, Canada, and overseas regions while avoiding blind 'Hybrid' traps.
    """
    if not location_str or not location_str.strip():
        return allow_unspecified
    loc = location_str.strip().lower()

    # Priority 0: Cross-border EOR/B2B override if remote context is present without jurisdiction lock
    if (
        text_snippet
        and re.search(r"\bremote\b", loc, re.IGNORECASE)
        and EOR_B2B_REGEX.search(text_snippet)
        and not has_jurisdiction_restriction(text_snippet)
    ):
        return True

    # Priority 1: Indian tech hub or explicit India reference
    if INDIAN_LOCATIONS_REGEX.search(loc):
        return True

    # Priority 2: Explicit Foreign Country rejection
    if FOREIGN_LOCATION_REGEX.search(loc):
        return False

    # Priority 3: Verified Global Remote
    if GLOBAL_REMOTE_REGEX.search(loc):
        return True

    # Priority 4: Generic Remote without foreign territory
    return bool(re.search(r"\bremote\b", loc, re.IGNORECASE))


def evaluate_global_remote_signal(
    title: str | None,
    location: str | None,
    description: str | None,
    compensation_str: str | None = "",
) -> dict[str, Any]:
    """
    Evaluates 3-stage global remote eligibility:
    1. Foreign Currency / High USD compensation
    2. Cross-Border EOR / B2B Contractor signal
    3. Absence of hard jurisdiction / residency lock
    """
    title_str = str(title or "")
    loc_str = str(location or "").lower()
    full_text = f"{title_str} {location or ''} {description or ''} {compensation_str or ''}"

    has_currency = bool(FOREIGN_CURRENCY_REGEX.search(full_text))
    has_eor = bool(EOR_B2B_REGEX.search(full_text))
    has_jurisdiction = has_jurisdiction_restriction(full_text)

    is_remote_context = "remote" in loc_str or bool(GLOBAL_REMOTE_REGEX.search(loc_str))

    reasons: list[str] = []
    if has_currency:
        reasons.append("Matches USD/EUR foreign currency compensation")
    if has_eor:
        reasons.append("Matches EOR / B2B contractor signal (Deel/Oyster/B2B/global remote)")
    if has_jurisdiction:
        reasons.append("Flagged with jurisdiction or residency restriction")

    # Global remote override rule:
    # If remote context is present, has EOR/B2B signal, and NO jurisdiction lock
    is_usd_eor = is_remote_context and has_eor and not has_jurisdiction
    eligible = is_usd_eor or is_india_or_remote_location(location, text_snippet=full_text)

    return {
        "is_usd_eor_remote": is_usd_eor,
        "has_foreign_currency": has_currency,
        "has_eor_signal": has_eor,
        "has_jurisdiction_lock": has_jurisdiction,
        "eligible": eligible,
        "reasons": reasons,
    }


def is_global_remote_eligible(
    location_str: str | None,
    text_snippet: str | None = None,
    allow_unspecified: bool = False,
) -> bool:
    """
    Determines whether a requisition is eligible for an international remote contractor
    based in India ($50k-$65k USD band).
    Checks both location string viability and filters out explicit legal/residency restrictions.
    """
    # 1. Reject if requirements or description contain hard jurisdiction locks
    if text_snippet and has_jurisdiction_restriction(text_snippet):
        return False

    # 2. Check for EOR / B2B global remote override
    if (
        text_snippet
        and location_str
        and re.search(r"\bremote\b", location_str, re.IGNORECASE)
        and EOR_B2B_REGEX.search(text_snippet)
    ):
        return True

    # 3. Evaluate location viability
    return is_india_or_remote_location(location_str, allow_unspecified=allow_unspecified, text_snippet=text_snippet)


def is_linkedin_posting_fresh_and_unsaturated(
    text: str | None,
    max_days: int = 3,
    is_sniper_24h: bool = False,
) -> tuple[bool, str]:
    """
    Inspects LinkedIn top-card / list-card metadata (first 800 characters of detail text)
    to enforce strict freshness and saturation invariants across all LinkedIn channels:
    1. Rejects any posting/reposting whose header age exceeds `effective_max_days`
       (`1` day for `sniper_fresh_24h`, `3` days for other channels).
    2. Rejects any recycled 'Reposted' job that is already saturated with
       'Over 100 people clicked apply' or 'Over 100 applicants'.
    Returns (is_valid, reason).
    """
    if not text or not text.strip():
        return True, "empty_metadata"

    effective_max_days = 1 if is_sniper_24h else max_days
    header_text = text[:800]

    # 1. Check relative age anchored to LinkedIn metadata separators ('·', 'Reposted', 'Posted', or line start)
    age_pattern = re.compile(
        r"(?:·|\b(?:re)?posted\b|^\s*)\s*(?:reposted\s+)?(\d+)\s+(minute|hour|day|week|month|year)s?\s+ago\b",
        re.IGNORECASE | re.MULTILINE,
    )
    for match in age_pattern.finditer(header_text):
        num = int(match.group(1))
        unit = match.group(2).lower()
        if unit in ("week", "month", "year"):
            return False, f"stale_age_{num}_{unit}s_ago"
        if unit == "day" and num > effective_max_days:
            return False, f"stale_age_{num}_days_ago"

    # 2. Check recycled Reposted + Over 100 applicants saturation
    is_reposted = bool(re.search(r"\breposted\b", header_text, re.IGNORECASE))
    is_saturated = bool(
        re.search(
            r"\bover\s+100\s+(?:people\s+clicked\s+apply|applicants)\b",
            header_text,
            re.IGNORECASE,
        )
    )
    if is_reposted and is_saturated:
        return False, "reposted_and_saturated_over_100_applicants"

    return True, "fresh"
