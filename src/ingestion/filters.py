"""
Standardized Ingestion Filtering Engine.
Centralized heuristics for SDET/QA role qualification, negative title exclusion,
and strict geographical/remote location matching across all ATS providers.
"""

from __future__ import annotations

import re

# Positive matches for Software Development Engineer in Test & QA roles
POSITIVE_SDET_REGEX = re.compile(
    r"\b("
    r"sdet|"
    r"software development engineer in test|"
    r"software engineer in test|"
    r"qa\b|"
    r"qe\b|"
    r"quality assurance|"
    r"quality engineer|"
    r"test automation|"
    r"automation engineer|"
    r"automation architect|"
    r"test engineer|"
    r"testing engineer|"
    r"test infrastructure|"
    r"mobile qa"
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
    r"dcsc"
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
    r"must reside in the united states|"
    r"us resident only|"
    r"us residency required|"
    r"authorized to work in the us without sponsorship|"
    r"authorized to work in the us only|"
    r"w2 only|"
    r"c2c not allowed|"
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


def has_jurisdiction_restriction(text: str | None) -> bool:
    """
    Evaluates whether job requirements or descriptions contain legal or geographic
    exclusivity clauses (e.g. US citizenship, security clearance, or North America only)
    that render international remote candidates ineligible.
    """
    if not text or not text.strip():
        return False
    return bool(JURISDICTION_RESTRICTIONS_REGEX.search(text))


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


def is_india_or_remote_location(location_str: str | None, allow_unspecified: bool = False) -> bool:
    """
    Evaluates whether a location string corresponds to an Indian tech hub or a viable Global Remote role,
    strictly rejecting explicit US, UK, Canada, and overseas regions while avoiding blind 'Hybrid' traps.
    """
    if not location_str or not location_str.strip():
        return allow_unspecified
    loc = location_str.strip().lower()

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

    # 2. Evaluate location viability
    return is_india_or_remote_location(location_str, allow_unspecified=allow_unspecified)
