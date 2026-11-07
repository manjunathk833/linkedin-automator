"""
Master Resume Sync — derives every downstream candidate artifact from the single source of truth
(``Manjunath_HK_Master_Resume.json``, a Reactive Resume export).

Outputs:
* ``data/resume_profile.json``                — Pydantic ``ResumeProfile`` used by tailoring & autofill.
* ``data/profile/allowed_tools_whitelist.json`` — evidence-gated tool registry:
    - ``allowed_tools`` / ``tool_evidence``  (AUTO-GENERATED: tools with evidence in the master resume)
    - ``learning_roadmap``                   (hand-edited: tools being learned — blocked everywhere)
    - ``disallowed_hallucinations``          (hand-edited: never-used tools — blocked everywhere)
* ``data/master_knowledge_bank.json``         — STAR vault rebuilt from master bullets + still-valid,
                                                 correctly-labelled, de-duplicated legacy entries.

Skill graduation: add the project/bullet that uses a roadmap tool to the master resume in rxresu.me,
re-export the JSON, run ``python main.py resume sync`` — the tool moves from ``learning_roadmap`` to
``allowed_tools`` automatically.
"""

from __future__ import annotations

import calendar
import difflib
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from src.resume_store.master_resume import (
    DEFAULT_LEARNING_ROADMAP,
    MASTER_RESUME_PATH,
    PROJECT_ROOT,
    WHITELIST_PATH,
    extract_boundary_texts,
    html_to_bullets,
    html_to_text,
    load_master_resume,
    tool_mentioned,
    visible_items,
)

RESUME_PROFILE_PATH = os.path.join(PROJECT_ROOT, "data", "resume_profile.json")
KNOWLEDGE_BANK_PATH = os.path.join(PROJECT_ROOT, "data", "master_knowledge_bank.json")
NOTES_PATH = os.path.join(PROJECT_ROOT, "data", "candidate_notes.md")

DEFAULT_DISALLOWED = ["cypress", "golang", "go", "rust", "terraform", "ansible"]

# Canonical tool -> alternate spellings that count as the same evidence.
TOOL_ALIASES: dict[str, list[str]] = {
    "selenium webdriver": ["selenium"],
    "selenium": ["selenium webdriver"],
    "kubernetes": ["k8s", "kubectl"],
    "github copilot": ["copilot"],
    "cucumber bdd": ["cucumber"],
    "rest assured": ["restassured"],
    "postgresql": ["postgres"],
    "gcp": ["google cloud"],
    "allure": ["allure reports"],
    "testrail": ["testrail api"],
    "ekam framework": ["ekam"],
    "ollama": [],
}

# Non-tool engineering concepts that are always allowed (never "fabricated").
GENERIC_TERMS = [
    "rest api",
    "microservices",
    "api testing",
    "json",
    "xml",
    "e2e",
    "shift-left",
    "ci/cd",
    "sql",
    "bdd",
    "agile",
    "scrum",
    "page object model",
    "pom",
    "regression",
    "smoke",
    "code review",
]

# Experience-company -> label used by the tailorer's vault partitioning.
VAULT_COMPANY_LABELS = {"valuelabs": "Value Labs", "value labs": "Value Labs"}

ROADMAP_SECTION_RE = re.compile(r"^#{1,6}\s*learning roadmap", re.IGNORECASE)


# ----------------------------------------------------------------------------- utils
def _norm_company(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _vault_label(company: str) -> str:
    return VAULT_COMPANY_LABELS.get(company.strip().lower(), company.strip())


def _to_date(ym: str | None, end: bool = False) -> str | None:
    if not ym:
        return None
    parts = ym.split("-")
    year = int(parts[0])
    month = int(parts[1]) if len(parts) > 1 else (12 if end else 1)
    day = calendar.monthrange(year, month)[1] if end else 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def _canonical_tool(raw: str) -> str:
    """'Kafka (event-log monitoring)' -> 'kafka'."""
    return re.sub(r"\s*\(.*?\)\s*", " ", raw).strip().lower()


def _near_duplicate(a: str, b: str, threshold: float = 0.7, jaccard_threshold: float = 0.5) -> bool:
    """Paraphrase-tolerant duplicate check (sequence ratio OR word-set Jaccard overlap)."""
    na = re.sub(r"[^a-z0-9 ]+", " ", a.lower())
    nb = re.sub(r"[^a-z0-9 ]+", " ", b.lower())
    if difflib.SequenceMatcher(None, na, nb).ratio() >= threshold:
        return True
    wa = {w for w in na.split() if len(w) > 2}
    wb = {w for w in nb.split() if len(w) > 2}
    if not wa or not wb:
        return False
    return len(wa & wb) / len(wa | wb) >= jaccard_threshold


def _read_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _atomic_write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def notes_sections(notes_text: str) -> list[tuple[str, str]]:
    """
    Returns (section_heading, bullet) pairs from candidate_notes.md. Sub-headings nested under a
    'Learning Roadmap' heading inherit that roadmap heading, so the whole block stays excluded.
    """
    section = ""
    roadmap_level: int | None = None
    out: list[tuple[str, str]] = []
    for line in notes_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            heading = stripped.lstrip("#").strip()
            if roadmap_level is not None and level > roadmap_level:
                continue  # nested under the roadmap block: keep roadmap section label
            roadmap_level = level if is_roadmap_section(heading) else None
            section = heading
            continue
        if stripped.startswith("- ") and len(stripped) > 5:
            out.append((section, stripped[2:].strip()))
    return out


def is_roadmap_section(heading: str) -> bool:
    return bool(ROADMAP_SECTION_RE.match(f"## {heading}"))


# ----------------------------------------------------------------------------- vocabulary & evidence
def _is_practice_category(name: str) -> bool:
    return "practice" in name.lower()


def practice_terms(master: dict[str, Any]) -> list[str]:
    """Keywords listed under a 'Practices' skills category (methodologies, not tools)."""
    terms: set[str] = set()
    for skill in visible_items(master, "skills"):
        if _is_practice_category(skill.get("name", "")):
            for kw in skill.get("keywords", []):
                terms.add(kw.strip().lower())
    return sorted(terms)


def build_tool_vocabulary(master: dict[str, Any], extra: list[str] | None = None) -> list[str]:
    vocab: set[str] = set()
    for skill in visible_items(master, "skills"):
        if _is_practice_category(skill.get("name", "")):
            continue
        for kw in skill.get("keywords", []):
            vocab.add(_canonical_tool(kw))
    for t in extra or []:
        if t and t.strip():
            vocab.add(_canonical_tool(t))
    practices = set(practice_terms(master))
    return sorted(v for v in vocab if v and v not in practices)


def _mentions(tool: str, text: str, vocabulary: list[str]) -> bool:
    """
    True when `tool` (or an alias) is mentioned in `text`, ignoring mentions that are only part of a
    longer vocabulary tool (e.g. 'Azure' inside 'Azure DevOps', 'GitHub' inside 'GitHub AI API').
    """
    stripped = text
    aliases = [a.lower() for a in TOOL_ALIASES.get(tool, [])]
    for longer in vocabulary:
        if longer in aliases:
            continue
        if longer != tool and len(longer) > len(tool) and tool_mentioned(tool, longer):
            stripped = re.sub(rf"(?<!\w){re.escape(longer)}(?!\w)", " ", stripped, flags=re.IGNORECASE)
    return any(tool_mentioned(s, stripped) for s in [tool, *TOOL_ALIASES.get(tool, [])])


def compute_tool_evidence(master: dict[str, Any], vocabulary: list[str]) -> dict[str, list[str]]:
    """Maps tool -> sorted boundaries (employer / project:<name> / skills) where the master resume mentions it."""
    pairs = extract_boundary_texts(master)
    evidence: dict[str, set[str]] = {}
    for tool in vocabulary:
        for boundary, text in pairs:
            if boundary in ("headline", "summary", "certifications", "awards"):
                continue
            if _mentions(tool, text, vocabulary):
                evidence.setdefault(tool, set()).add(boundary)
    return {t: sorted(b) for t, b in sorted(evidence.items())}


# ----------------------------------------------------------------------------- resume_profile
# Display short forms appended to the derived skills_matrix so exact-match lookups work
# ("Selenium WebDriver" -> also "Selenium"; "Kafka (event-log monitoring)" -> also "Kafka").
SKILL_SHORT_FORMS: dict[str, list[str]] = {
    "selenium webdriver": ["Selenium"],
    "cucumber bdd": ["Cucumber", "BDD"],
    "github copilot": ["Copilot"],
}


def _expand_skill_forms(keywords: list[str]) -> list[str]:
    out: list[str] = []
    for kw in keywords:
        forms = [kw]
        base = re.sub(r"\s*\(.*?\)", "", kw).strip()
        if base and base != kw:
            forms.append(base)
        forms.extend(SKILL_SHORT_FORMS.get(base.lower(), []))
        for f in forms:
            if f.lower() not in {o.lower() for o in out}:
                out.append(f)
    return out


def build_resume_profile(master: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    basics = master.get("basics", {})

    profiles = []
    for cf in basics.get("customFields", []):
        link = cf.get("link", "")
        if not link:
            continue
        network = "LinkedIn" if "linkedin" in link else "GitHub" if "github" in link else cf.get("text", "Link")
        username = link.rstrip("/").split("/")[-1] or None
        profiles.append({"network": network, "username": username, "url": link})
    website = (basics.get("website") or {}).get("url")
    if website:
        profiles.append({"network": "Portfolio", "username": None, "url": website})

    experience = []
    for exp in visible_items(master, "experience"):
        dates = exp.get("dates") or {}
        roles = exp.get("roles") or []
        role_title = exp.get("position") or (roles[0].get("position") if roles else "")
        summary = ""
        if len(roles) > 1:
            summary = "Career progression: " + "; ".join(
                f"{r.get('position')} ({r.get('period', '')})" for r in roles if r.get("position")
            )
        bullets = html_to_bullets(exp.get("description"))
        for r in roles:
            bullets.extend(html_to_bullets(r.get("description")))
        experience.append(
            {
                "role": role_title,
                "company": exp.get("company", ""),
                "company_url": None,
                "start_date": _to_date(dates.get("start")),
                "end_date": None if dates.get("present") else _to_date(dates.get("end"), end=True),
                "summary": summary,
                "achievements": bullets,
                "tech_tags": [],
            }
        )

    education = []
    for edu in visible_items(master, "education"):
        dates = edu.get("dates") or {}
        degree = edu.get("degree", "")
        m = re.match(r"^(B\.E\.|B\.Tech|M\.Tech|M\.S\.|B\.Sc|M\.Sc|MBA)\s*(.*)$", degree)
        education.append(
            {
                "institution": edu.get("school", ""),
                "area": (m.group(2) if m else edu.get("area") or degree).strip(),
                "study_type": m.group(1) if m else degree,
                "start_date": _to_date(dates.get("start")),
                "end_date": _to_date(dates.get("end"), end=True),
                "gpa": edu.get("grade") or None,
                "courses": [],
                "highlights": [],
            }
        )

    projects = []
    for proj in visible_items(master, "projects"):
        dates = proj.get("dates") or {}
        desc = html_to_text(proj.get("description"))
        stack = []
        m = re.search(r"Stack:\s*(.+?)\.?$", desc)
        if m:
            stack = [s.strip() for s in m.group(1).split(",") if s.strip()]
        projects.append(
            {
                "name": proj.get("name", ""),
                "description": desc,
                "url": (proj.get("website") or {}).get("url") or None,
                "start_date": _to_date(dates.get("start")),
                "end_date": None if dates.get("present") else _to_date(dates.get("end"), end=True),
                "highlights": [s.strip() for s in re.split(r"(?<=[.;])\s+", desc) if s.strip()],
                "tech_tags": stack,
            }
        )

    certifications = [
        {
            "name": c.get("title", ""),
            "issuer": c.get("issuer", ""),
            "issue_date": _to_date((c.get("dates") or {}).get("start")),
            "url": (c.get("website") or {}).get("url") or None,
        }
        for c in visible_items(master, "certifications")
    ]
    awards = [
        {
            "title": a.get("title", ""),
            "awarder": a.get("awarder", ""),
            "award_date": _to_date((a.get("dates") or {}).get("start")),
            "summary": html_to_text(a.get("description")) or None,
        }
        for a in visible_items(master, "awards")
    ]

    skills_matrix = {
        s.get("name", "Skills"): _expand_skill_forms(s.get("keywords", [])) for s in visible_items(master, "skills")
    }

    profile = {
        "personal_details": {
            "full_name": basics.get("name", ""),
            "label": basics.get("headline", ""),
            "email": basics.get("email", ""),
            "phone": re.sub(r"[\s\-()]", "", basics.get("phone", "")),
            "location": basics.get("location", ""),
            "summary": html_to_text(master.get("summary", {}).get("content")),
            "profiles": profiles,
        },
        "experience_history": experience,
        "education": education,
        "projects": projects,
        "certifications": certifications,
        "awards": awards,
        "languages": existing.get("languages", []),
        "volunteer": existing.get("volunteer", []),
        "publications": existing.get("publications", []),
        "skills_matrix": skills_matrix,
        "easy_apply_answers": existing.get("easy_apply_answers", {}),
    }
    return profile


def attach_tech_tags(profile: dict[str, Any], evidence: dict[str, list[str]], skills_matrix: dict) -> None:
    """Fills experience tech_tags with display-cased tools whose evidence includes that employer."""
    display = {}
    for kws in skills_matrix.values():
        for kw in kws:
            display.setdefault(_canonical_tool(kw), re.sub(r"\s*\(.*?\)", "", kw).strip())
    for exp in profile["experience_history"]:
        comp = _norm_company(exp["company"])
        tags = []
        for tool, boundaries in evidence.items():
            if any(
                _norm_company(b) == comp or (b.startswith("project:") and comp in _norm_company(b)) for b in boundaries
            ):
                tags.append(display.get(tool, tool.title()))
        exp["tech_tags"] = sorted(set(tags))


# ----------------------------------------------------------------------------- knowledge bank
def _metric_of(text: str) -> str:
    m = re.search(r"[^.;]*\d+(?:,\d{3})*\+?%?[^.;]*", text)
    return m.group(0).strip()[:160] if m else ""


def _legacy_company_to_employer(label: str, employers: dict[str, str]) -> str | None:
    """Maps legacy vault labels to a real employer (or None to drop)."""
    low = label.lower()
    if "value" in low or "mosaic" in low:
        return employers.get("valuelabs")
    if "dunzo" in low or "merchant service" in low or "gcp" in low:
        return employers.get("dunzo")
    if "tata" in low or "ott" in low:
        return employers.get("tataelxsi")
    return None


def build_knowledge_bank(
    master: dict[str, Any],
    evidence: dict[str, list[str]],
    roadmap: list[str],
    vocabulary: list[str],
    existing_bank: dict[str, Any] | None = None,
    notes_sha256: str | None = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    existing_bank = existing_bank or {}
    employers = {_norm_company(e.get("company", "")): e.get("company", "") for e in visible_items(master, "experience")}

    def tools_in(text: str) -> list[str]:
        return sorted(t for t in vocabulary if _mentions(t, text, vocabulary))

    vault: list[dict[str, Any]] = []
    for boundary, text in extract_boundary_texts(master):
        if boundary in ("headline", "summary", "skills", "certifications", "awards"):
            continue
        if boundary.startswith("project:"):
            # Project names carry their employer, e.g. "PNR Linking (ValueLabs, Mosaic Portfolio)"
            owner = next((emp for key, emp in employers.items() if key in _norm_company(boundary)), None)
            if not owner:
                continue
            company, domain = owner, boundary.split(":", 1)[1]
        else:
            company = boundary
            m = re.match(r"^([^:]{3,60}):\s", text)
            domain = m.group(1) if m else "Experience"
        vault.append(
            {
                "domain": domain,
                "company": _vault_label(company),
                "star_achievement": text,
                "tools": tools_in(text),
                "metric": _metric_of(text),
                "source": "master_resume",
            }
        )

    stats = {"canonical": len(vault), "kept_legacy": 0, "dropped_mislabeled": 0, "dropped_roadmap": 0}
    stats.update({"dropped_no_evidence": 0, "dropped_duplicate": 0})

    for item in existing_bank.get("master_achievements_vault", []):
        if item.get("source") == "master_resume":
            continue
        text = item.get("star_achievement", "")
        employer = _legacy_company_to_employer(item.get("company", ""), employers)
        if not employer:
            stats["dropped_mislabeled"] += 1
            continue
        if any(tool_mentioned(t, text) for t in roadmap):
            stats["dropped_roadmap"] += 1
            continue
        emp_norm = _norm_company(employer)
        unevidenced = [
            t
            for t in tools_in(text)
            if t in evidence
            and not any(
                _norm_company(b) == emp_norm or (b.startswith("project:") and emp_norm in _norm_company(b))
                for b in evidence[t]
            )
        ]
        if unevidenced:
            stats["dropped_no_evidence"] += 1
            continue
        if any(_near_duplicate(text, v["star_achievement"]) for v in vault):
            stats["dropped_duplicate"] += 1
            continue
        vault.append(
            {
                "domain": item.get("domain", "Experience"),
                "company": _vault_label(employer),
                "star_achievement": text,
                "tools": tools_in(text),
                "metric": item.get("metric") or _metric_of(text),
                "source": "legacy_vault",
            }
        )
        stats["kept_legacy"] += 1

    skills_inventory = {
        s.get("name", "Skills"): [re.sub(r"\s*\(.*?\)", "", kw).strip() for kw in s.get("keywords", [])]
        for s in visible_items(master, "skills")
    }
    technical_projects = [
        {
            "project_name": p.get("name", ""),
            "tech_stack": sorted({t for t in tools_in(html_to_text(p.get("description")))}),
            "impact": html_to_text(p.get("description"))[:200],
        }
        for p in visible_items(master, "projects")
    ]
    bank = {
        "version": "2.0.0",
        "candidate_name": master.get("basics", {}).get("name", ""),
        "target_roles": existing_bank.get(
            "target_roles", ["Senior SDET", "Lead SDET", "Test Automation Architect", "Senior QA Automation Engineer"]
        ),
        "generated_from": "Manjunath_HK_Master_Resume.json",
        "master_achievements_vault": vault,
        "extended_skills_inventory": skills_inventory,
        "technical_projects": technical_projects,
        "last_synced_notes_sha256": notes_sha256 or existing_bank.get("last_synced_notes_sha256"),
    }
    return bank, stats


# ----------------------------------------------------------------------------- whitelist registry
def build_whitelist(
    master: dict[str, Any],
    evidence: dict[str, list[str]],
    existing: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Returns (registry, graduated_tools)."""
    existing = existing or {}
    roadmap_prev = [t.lower() for t in existing.get("learning_roadmap", DEFAULT_LEARNING_ROADMAP)]
    graduated = [t for t in roadmap_prev if t in evidence]
    roadmap = [t for t in roadmap_prev if t not in evidence]
    disallowed = [t.lower() for t in existing.get("disallowed_hallucinations", DEFAULT_DISALLOWED)]

    allowed: set[str] = set(GENERIC_TERMS) | set(practice_terms(master))
    for tool in evidence:
        allowed.add(tool)
        allowed.update(a.lower() for a in TOOL_ALIASES.get(tool, []))
    allowed -= set(roadmap) | set(disallowed)

    registry = {
        "candidate_name": master.get("basics", {}).get("name", ""),
        "_readme": (
            "allowed_tools and tool_evidence are AUTO-GENERATED by `python main.py resume sync` from "
            "Manjunath_HK_Master_Resume.json. Do not hand-edit them. To unlock a tool, add the project/bullet "
            "that uses it to the master resume (rxresu.me), re-export, and re-run the sync. Hand-edit only "
            "learning_roadmap (tools being learned, blocked everywhere) and disallowed_hallucinations."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "allowed_tools": sorted(allowed),
        "tool_evidence": evidence,
        "learning_roadmap": roadmap,
        "disallowed_hallucinations": disallowed,
    }
    return registry, graduated


# ----------------------------------------------------------------------------- orchestration
def run_sync(
    master_path: str = MASTER_RESUME_PATH,
    profile_path: str = RESUME_PROFILE_PATH,
    whitelist_path: str = WHITELIST_PATH,
    bank_path: str = KNOWLEDGE_BANK_PATH,
    notes_path: str = NOTES_PATH,
    write: bool = True,
) -> dict[str, Any]:
    master = load_master_resume(master_path)
    if master is None:
        raise FileNotFoundError(
            f"Master resume not found at {master_path}. Export it from rxresu.me (Export → JSON) and save it there."
        )

    old_whitelist = _read_json(whitelist_path, {})
    old_profile = _read_json(profile_path, {})
    old_bank = _read_json(bank_path, {})

    roadmap_prev = [t.lower() for t in old_whitelist.get("learning_roadmap", DEFAULT_LEARNING_ROADMAP)]
    disallowed = [t.lower() for t in old_whitelist.get("disallowed_hallucinations", DEFAULT_DISALLOWED)]
    from src.tailor.fabrication_detector import FabricationDetector

    extra_vocab = (
        list(old_whitelist.get("allowed_tools", []))
        + [t.lower() for t in FabricationDetector.KNOWN_TECH_TOOLS]
        + roadmap_prev
        + list(TOOL_ALIASES)
    )
    vocabulary = build_tool_vocabulary(master, extra_vocab)
    vocabulary = [v for v in vocabulary if v not in disallowed and v not in GENERIC_TERMS]
    evidence = compute_tool_evidence(master, vocabulary)

    registry, graduated = build_whitelist(master, evidence, old_whitelist)
    profile = build_resume_profile(master, old_profile)
    attach_tech_tags(profile, evidence, profile["skills_matrix"])

    notes_text = ""
    if os.path.exists(notes_path):
        with open(notes_path, "r", encoding="utf-8") as f:
            notes_text = f.read()
    notes_sha = hashlib.sha256(notes_text.encode("utf-8")).hexdigest() if notes_text else None
    bank, bank_stats = build_knowledge_bank(
        master, evidence, registry["learning_roadmap"], vocabulary, old_bank, notes_sha
    )

    # Validate profile against the Pydantic schema before writing anything.
    from src.resume_store.models import ResumeProfile

    ResumeProfile(**profile)

    old_allowed = {t.lower() for t in old_whitelist.get("allowed_tools", [])}
    new_allowed = set(registry["allowed_tools"])
    skills_only = sorted(t for t, b in evidence.items() if b == ["skills"])
    notes_gaps = sorted(
        {
            t
            for section, bullet in notes_sections(notes_text)
            if not is_roadmap_section(section)
            for t in vocabulary + registry["learning_roadmap"]
            if _mentions(t, bullet, vocabulary) and t not in new_allowed
        }
    )

    report = {
        "allowed_count": len(new_allowed),
        "newly_allowed": sorted(new_allowed - old_allowed),
        "removed": sorted(old_allowed - new_allowed),
        "graduated": graduated,
        "roadmap_blocked": registry["learning_roadmap"],
        "skills_only_tools": skills_only,
        "notes_tools_not_on_resume": notes_gaps,
        "knowledge_bank": bank_stats | {"vault_size": len(bank["master_achievements_vault"])},
        "experience_count": len(profile["experience_history"]),
    }

    if write:
        _atomic_write_json(profile_path, profile)
        _atomic_write_json(whitelist_path, registry)
        _atomic_write_json(bank_path, bank)
    return report


def format_report(report: dict[str, Any]) -> str:
    kb = report["knowledge_bank"]
    lines = [
        "🔄 Master Resume Sync Report",
        f"✅ Allowed tools (evidence in master resume): {report['allowed_count']}",
    ]
    for t in report["graduated"]:
        lines.append(f"🎓 Graduated from learning roadmap: {t}")
    if report["newly_allowed"]:
        lines.append(f"🆕 Newly allowed: {', '.join(report['newly_allowed'])}")
    if report["removed"]:
        lines.append(f"➖ No longer allowed (no evidence in master resume): {', '.join(report['removed'])}")
    lines.append(f"🚫 Still blocked (learning roadmap): {', '.join(report['roadmap_blocked']) or 'none'}")
    if report["skills_only_tools"]:
        lines.append(
            "ℹ️  Listed in Skills but not used in any bullet (tailoring cannot put these in job bullets): "
            + ", ".join(report["skills_only_tools"])
        )
    for t in report["notes_tools_not_on_resume"]:
        lines.append(
            f"⚠️  Mentioned in candidate_notes.md but NOT on master resume: {t} — add it in rxresu.me to enable."
        )
    lines.append(
        f"📚 Knowledge bank: {kb['vault_size']} entries ({kb['canonical']} from master, {kb['kept_legacy']} legacy kept; "
        f"dropped {kb['dropped_mislabeled']} mislabeled, {kb['dropped_roadmap']} roadmap, "
        f"{kb['dropped_no_evidence']} no-evidence, {kb['dropped_duplicate']} duplicates)"
    )
    return "\n".join(lines)
