"""
Master Resume (Reactive Resume JSON) — Single Source of Truth helpers.

The candidate edits their resume visually in rxresu.me, exports the JSON over
``Manjunath_HK_Master_Resume.json`` (repo root, gitignored), and runs
``python main.py resume sync``. Everything downstream (``data/resume_profile.json``,
``allowed_tools`` in ``data/profile/allowed_tools_whitelist.json``) is derived from it.

This module provides:
* loading + HTML-to-text helpers for the rx schema,
* per-boundary text extraction (employer / project / skills / summary),
* an ATS integrity checker used by ``verify/110_test_master_resume_integrity.py``.
"""

from __future__ import annotations

import html
import json
import os
import re
from typing import Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MASTER_RESUME_PATH = os.path.join(PROJECT_ROOT, "Manjunath_HK_Master_Resume.json")
WHITELIST_PATH = os.path.join(PROJECT_ROOT, "data", "profile", "allowed_tools_whitelist.json")

# Tools the candidate is still learning. Blocked in every boundary until they appear
# in the master resume (see `learning_roadmap` in allowed_tools_whitelist.json).
DEFAULT_LEARNING_ROADMAP: list[str] = [
    "typescript",
    "wiremock",
    "pact",
    "deepeval",
    "ragas",
    "promptfoo",
    "garak",
    "pyrit",
    "langsmith",
    "langfuse",
    "owasp llm",
]

# Characters that older ATS parsers mangle (arrows, check marks, stars, tildes, ligature glyphs).
UNSAFE_ATS_GLYPHS: dict[str, str] = {
    "→": "right arrow",
    "➔": "heavy arrow",
    "➤": "arrowhead",
    "►": "pointer",
    "❯": "chevron",
    "✓": "check mark",
    "✔": "check mark",
    "★": "star",
    "☆": "star",
    "~": "tilde",
    "\ufb01": "fi ligature",
    "\ufb02": "fl ligature",
    "->": "ascii arrow",
}

REQUIRED_SECTIONS = ("experience", "skills", "education")


# ----------------------------------------------------------------------------- loading
def load_master_resume(path: str | None = None) -> dict[str, Any] | None:
    """Returns the parsed master resume JSON, or None when absent (e.g. clean CI clone)."""
    target = path or MASTER_RESUME_PATH
    if not os.path.exists(target):
        return None
    with open(target, "r", encoding="utf-8") as f:
        return json.load(f)


def load_learning_roadmap(whitelist_path: str | None = None) -> list[str]:
    """Reads `learning_roadmap` from the whitelist registry, falling back to the default list."""
    target = whitelist_path or WHITELIST_PATH
    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        roadmap = data.get("learning_roadmap")
        if isinstance(roadmap, list):
            return [str(t).strip().lower() for t in roadmap if str(t).strip()]
    except (OSError, json.JSONDecodeError):
        pass
    return list(DEFAULT_LEARNING_ROADMAP)


# ----------------------------------------------------------------------------- html
def html_to_text(fragment: str | None) -> str:
    """Strips HTML tags and entities, collapsing whitespace."""
    if not fragment:
        return ""
    text = re.sub(r"<br\s*/?>", " ", fragment)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return " ".join(text.split()).strip()


def html_to_bullets(fragment: str | None) -> list[str]:
    """Returns <li> items as plain text; falls back to <p> paragraphs when no list exists."""
    if not fragment:
        return []
    items = re.findall(r"<li[^>]*>(.*?)</li>", fragment, flags=re.DOTALL)
    if not items:
        items = re.findall(r"<p[^>]*>(.*?)</p>", fragment, flags=re.DOTALL)
    return [t for t in (html_to_text(i) for i in items) if t]


def visible_items(data: dict[str, Any], section: str) -> list[dict[str, Any]]:
    sec = data.get("sections", {}).get(section, {})
    if sec.get("hidden"):
        return []
    return [i for i in sec.get("items", []) if not i.get("hidden")]


# ----------------------------------------------------------------------------- boundaries
def extract_boundary_texts(data: dict[str, Any]) -> list[tuple[str, str]]:
    """
    Returns (boundary, text) pairs. Boundary is the employer name for experience items,
    ``project:<name>`` for projects, plus ``summary``, ``headline``, ``skills``,
    ``certifications`` and ``awards``.
    """
    out: list[tuple[str, str]] = []
    basics = data.get("basics", {})
    if basics.get("headline"):
        out.append(("headline", basics["headline"]))
    summary = data.get("summary", {})
    if not summary.get("hidden") and summary.get("content"):
        out.append(("summary", html_to_text(summary["content"])))

    for exp in visible_items(data, "experience"):
        company = exp.get("company", "").strip()
        for bullet in html_to_bullets(exp.get("description")):
            out.append((company, bullet))
        for role in exp.get("roles", []) or []:
            for bullet in html_to_bullets(role.get("description")):
                out.append((company, bullet))

    for proj in visible_items(data, "projects"):
        name = proj.get("name", "").strip()
        for bullet in html_to_bullets(proj.get("description")):
            out.append((f"project:{name}", bullet))

    for skill in visible_items(data, "skills"):
        kws = ", ".join(skill.get("keywords", []))
        out.append(("skills", f"{skill.get('name', '')}: {kws}"))

    for cert in visible_items(data, "certifications"):
        out.append(("certifications", f"{cert.get('title', '')} {html_to_text(cert.get('description'))}"))
    for award in visible_items(data, "awards"):
        out.append(("awards", f"{award.get('title', '')} {html_to_text(award.get('description'))}"))
    return out


def all_visible_text(data: dict[str, Any]) -> str:
    parts = [t for _, t in extract_boundary_texts(data)]
    basics = data.get("basics", {})
    parts.extend(str(basics.get(k, "")) for k in ("name", "location", "email", "phone"))
    parts.extend(cf.get("text", "") for cf in basics.get("customFields", []))
    for exp in visible_items(data, "experience"):
        parts.append(exp.get("position", ""))
        parts.extend(r.get("position", "") for r in exp.get("roles", []) or [])
    return "\n".join(parts)


def tool_mentioned(tool: str, text: str) -> bool:
    """Whole-token match (hyphenated forms like 'Copilot-based' count as a mention)."""
    return re.search(rf"(?<!\w){re.escape(tool.lower())}(?!\w)", text.lower()) is not None


# ----------------------------------------------------------------------------- integrity
def check_integrity(data: dict[str, Any], roadmap: list[str] | None = None) -> list[str]:
    """
    Returns a list of human-readable ATS / authenticity issues. Empty list == clean.
    """
    issues: list[str] = []
    roadmap = roadmap if roadmap is not None else load_learning_roadmap()
    basics = data.get("basics", {})

    # 1. Required sections present and populated
    for section in REQUIRED_SECTIONS:
        if not visible_items(data, section):
            issues.append(f"Section '{section}' is missing, hidden or empty.")
    summary = data.get("summary", {})
    if summary.get("hidden") or not html_to_text(summary.get("content")):
        issues.append("Professional summary is missing or hidden.")

    # 2. Contact block
    for key in ("name", "email", "phone", "location"):
        if not str(basics.get(key, "")).strip():
            issues.append(f"basics.{key} is empty.")

    # 3. Profile links must show the URL as visible text (parsers drop hyperlink-only labels)
    for cf in basics.get("customFields", []):
        if cf.get("link") and not re.search(r"\.[a-z]{2,}/?", cf.get("text", "").lower()):
            issues.append(f"Profile link '{cf.get('text')}' hides its URL; use visible text like 'github.com/user'.")
    website = basics.get("website", {}) or {}
    if website.get("url") and not re.search(r"\.[a-z]{2,}", str(website.get("label", "")).lower()):
        issues.append("Website label hides its URL; set label to the visible domain.")

    # 4. Unsafe glyphs anywhere in visible text
    text = all_visible_text(data)
    for glyph, name in UNSAFE_ATS_GLYPHS.items():
        if glyph in text:
            issues.append(f"Unsafe ATS glyph {name} ({glyph!r}) found in resume text.")

    # 5. Experience dates + clean titles
    for exp in visible_items(data, "experience"):
        dates = exp.get("dates") or {}
        if not dates.get("start"):
            issues.append(f"Experience '{exp.get('company')}' has no structured start date.")
        if not exp.get("position") and not exp.get("roles"):
            issues.append(f"Experience '{exp.get('company')}' has no position or roles.")

    # 6. Duplicate bullets (normalised) across the whole resume
    seen: dict[str, str] = {}
    for boundary, bullet in extract_boundary_texts(data):
        if boundary in ("skills", "headline"):
            continue
        norm = re.sub(r"[^a-z0-9]+", " ", bullet.lower()).strip()
        if len(norm) < 40:
            continue
        if norm in seen:
            issues.append(f"Duplicate text in '{boundary}' and '{seen[norm]}': {bullet[:70]}...")
        else:
            seen[norm] = boundary

    # 7. Learning-roadmap tools must not appear anywhere
    for tool in roadmap:
        if tool_mentioned(tool, text):
            issues.append(f"Learning-roadmap tool '{tool}' appears in the master resume.")

    return issues
