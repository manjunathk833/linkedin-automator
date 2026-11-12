"""
Centralized Anti-Slop & Ground-Truth Guard for ATS Form Autofill.

Enforces four non-negotiable preventative invariants across all form fillers
(`ATSAssistedFiller`, `UniversalBatchFormFiller`, `AutofillLogger`):
1. Roadmap & Disallowed Tool Block: Blocks `learning_roadmap` (DeepEval, RAGAS, Promptfoo,
   Garak, TypeScript, WireMock, Pact, etc.) and `disallowed_hallucinations` (Cypress,
   Golang, Rust, Terraform, Ansible) in outbound text/textarea values and learned mappings.
2. Cross-Type Sanity Validation: Blocks non-URL text in LinkedIn/GitHub/Portfolio URL fields,
   blocks city/location strings in salary/CTC/compensation fields, and enforces numeric values
   on numeric inputs.
3. Ambiguous / Placeholder / UUID Key Quarantine: Blocks generic labels ("yes", "no", "month",
   "year", "type response", "start typing...", "please specify", raw `cards[...][fieldN]` UUIDs)
   from polluting `learned_field_mappings.json`.
4. Cross-Company Resume Filename Guard: Blocks uploading another company's tailored resume PDF
   (`Manjunath_HK_<OtherCo>_...pdf`) to a different company's portal.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from src.resume_store.master_resume import DEFAULT_LEARNING_ROADMAP, WHITELIST_PATH

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DISALLOWED_TOOLS = ["cypress", "golang", "rust", "terraform", "ansible"]

GENERIC_COMPANY_STOPWORDS = {
    "india",
    "global",
    "tech",
    "technology",
    "technologies",
    "center",
    "centre",
    "capability",
    "digital",
    "careers",
    "career",
    "inc",
    "corp",
    "corporation",
    "ltd",
    "limited",
    "private",
    "pvt",
    "llc",
    "group",
    "services",
    "solutions",
    "systems",
    "software",
    "engineering",
    "health",
    "healthcare",
    "partners",
    "labs",
    "lab",
    "the",
    "and",
}

AMBIGUOUS_LEARNED_LABEL_BLOCKLIST = {
    "yes",
    "no",
    "true",
    "false",
    "month",
    "year",
    "day",
    "date",
    "from",
    "to",
    "other",
    "select",
    "select one",
    "choose",
    "type response",
    "type your response",
    "start typing",
    "start typing...",
    "specify",
    "please specify",
    "if yes specify",
    "less than 6 months",
    "90 days or less",
    "he/him",
    "she/her",
    "they/them",
    "role description",
    "description",
    "summary",
    "linkedin",
    "github",
    "portfolio",
    "website",
    "country",
    "city",
    "state",
    "location",
    "skills",
}

UUID_OR_RAW_KEY_RE = re.compile(
    r"(\bcards\s*[\[\s]|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|\bfield\d+\b)",
    re.IGNORECASE,
)


class AutofillGroundTruthGuard:
    """Validates outbound autofill values, learned mappings, and resume attachments against ground truth."""

    def __init__(self, whitelist_path: str | Path | None = None) -> None:
        self.whitelist_path = Path(whitelist_path or WHITELIST_PATH)
        self.roadmap_tools, self.disallowed_tools = self._load_blocked_tools()

    def _load_blocked_tools(self) -> tuple[list[str], list[str]]:
        roadmap = list(DEFAULT_LEARNING_ROADMAP)
        disallowed = list(DEFAULT_DISALLOWED_TOOLS)
        if self.whitelist_path.exists():
            try:
                data = json.loads(self.whitelist_path.read_text(encoding="utf-8"))
                if isinstance(data.get("learning_roadmap"), list):
                    roadmap = [str(t).strip().lower() for t in data["learning_roadmap"] if str(t).strip()]
                if isinstance(data.get("disallowed_hallucinations"), list):
                    disallowed = [
                        str(t).strip().lower()
                        for t in data["disallowed_hallucinations"]
                        if str(t).strip() and str(t).strip().lower() != "go"
                    ]
            except Exception:
                pass
        return roadmap, disallowed

    def validate_field_value(
        self,
        label: str,
        value: str,
        control_type: str = "text",
    ) -> tuple[bool, str]:
        """Validates that `value` is grounded and type-consistent with `label` and `control_type`."""
        lbl = (label or "").strip()
        lbl_low = lbl.lower()
        val = str(value or "").strip()
        val_low = val.lower()
        ctype = (control_type or "text").strip().lower()

        if not val:
            return False, "Empty value"

        # 1. Roadmap & Disallowed Hallucination Tool Scan (applies to free-text/narrative answers)
        if ctype in ("text", "textarea", "input", "") and len(val) >= 3:
            for rm_tool in self.roadmap_tools:
                if re.search(rf"(?<!\w){re.escape(rm_tool)}(?!\w)", val_low):
                    return False, f"Blocked learning_roadmap tool mention: '{rm_tool}'"
            for dis_tool in self.disallowed_tools:
                if re.search(rf"(?<!\w){re.escape(dis_tool)}(?!\w)", val_low):
                    return False, f"Blocked disallowed_hallucinations tool mention: '{dis_tool}'"
            if re.search(r"^role\s*description\b", lbl_low) and (
                (len(val) < 120 and "•" not in val) or "specializing in ui, api, and ai/llm test automation" in val_low
            ):
                return False, "Blocked 1-line ungrounded slop stub in Role Description"

        # 2. URL / Profile Link Sanity Check (only when control is a text/url input, not a 'How did you hear' checkbox)
        if ctype in ("text", "url", "input", "textarea"):
            is_profile_url_label = bool(
                re.search(
                    r"\b(linkedin\s*(profile|url|link|account)?|github\s*(profile|url|link)?|portfolio\s*(url|link|website)?|personal\s*(website|url))\b",
                    lbl_low,
                )
            )
            if (
                is_profile_url_label
                and not re.search(r"hear|source|consent", lbl_low)
                and not re.search(r"(https?://|linkedin\.com|github\.com|netlify\.app)", val_low)
            ):
                return False, f"Non-URL value '{val[:40]}' rejected for profile URL field '{lbl[:50]}'"

        # 3. Compensation / Salary / CTC Sanity Check (reject city/location strings like 'Bengaluru')
        if ctype in ("text", "number", "numeric", "textarea", "input"):
            is_comp_label = bool(
                re.search(
                    r"\b(compensation|salary|ctc|desired\s*pay|target\s*base|base\s*pay|annual\s*pay|remuneration)\b",
                    lbl_low,
                )
            )
            if (
                is_comp_label
                and not re.search(r"\d", val)
                and val_low not in ("na", "n/a", "negotiable", "as per company standards")
            ):
                return False, f"Non-numeric value '{val[:40]}' rejected for compensation field '{lbl[:50]}'"

        # 4. Strict Numeric Input Check
        if ctype in ("number", "numeric") and not re.match(r"^\d+(\.\d+)?$", val):
            return False, f"Non-numeric value '{val[:40]}' rejected for numeric control '{lbl[:50]}'"

        return True, "ok"

    def validate_learned_mapping(
        self,
        label: str,
        value: str,
        control_type: str = "text",
    ) -> tuple[bool, str]:
        """Validates whether a Phase B custom question + answer is safe to persist/reuse across orgs."""
        raw_lbl = (label or "").strip()
        if not raw_lbl:
            return False, "Empty label"

        if UUID_OR_RAW_KEY_RE.search(raw_lbl):
            return False, f"Raw attribute / UUID key rejected: '{raw_lbl[:60]}'"

        norm_lbl = re.sub(r"[^a-z0-9\s/+-]", " ", raw_lbl.lower())
        norm_lbl = re.sub(r"\s+", " ", norm_lbl).strip()

        if norm_lbl in AMBIGUOUS_LEARNED_LABEL_BLOCKLIST:
            return False, f"Ambiguous or generic label rejected: '{norm_lbl}'"

        if len(norm_lbl) < 10:
            return False, f"Label too short/ambiguous for cross-portal learning: '{norm_lbl}'"

        # Reject fabricated ML Research YOE claims or ungrounded multi-sentence essays
        if re.search(r"\b(ml\s*research|machine\s*learning\s*research|applied\s*ml)\b", norm_lbl):
            return False, f"Out-of-domain ML research experience claim rejected: '{norm_lbl}'"

        # Reject job-specific night-shift or non-Bengaluru relocation commitments from global auto-reuse
        if re.search(r"\b(3\s*30\s*am|night\s*shift|graveyard\s*shift)\b", norm_lbl):
            return False, f"Job-specific night-shift question must not be globally auto-reused: '{norm_lbl}'"
        if re.search(r"\brelocat(e|ing)\s+to\s+(?!bengaluru|bangalore|karnataka)\w+", norm_lbl):
            return False, f"Non-Bengaluru relocation question must not be globally auto-reused: '{norm_lbl}'"

        if (
            "nondeterministic false-negative rate" in str(value or "").lower()
            or "500 stratified" in str(value or "").lower()
        ):
            return False, "Ungrounded fabricated audit narrative rejected"

        return self.validate_field_value(raw_lbl, value, control_type=control_type)

    def validate_resume_for_company(
        self,
        resume_pdf_path: str | os.PathLike[str] | None,
        company: str = "",
    ) -> tuple[bool, str]:
        """Ensures a company-named tailored PDF is never uploaded to a different company's portal."""
        if not resume_pdf_path:
            return False, "Missing resume_pdf_path"

        fname = os.path.basename(str(resume_pdf_path))
        fname_low = fname.lower()
        if not fname_low.endswith(".pdf"):
            return False, f"Resume attachment is not a PDF: '{fname}'"

        # Generic canonical Master Resume or synthetic test fixtures are valid for any company
        canonical_generic_names = {
            "manjunath_hk_resume.pdf",
            "manjunath_hk_master_resume.pdf",
            "resume.pdf",
            "dummy_resume.pdf",
            "test_resume.pdf",
            "tailored_resume.pdf",
        }
        if fname_low in canonical_generic_names or not (company or "").strip():
            return True, "ok"

        # Extract slug between 'Manjunath_HK_' and '_Resume.pdf' / '_Tailored.pdf'
        m = re.match(r"^manjunath_hk_(.+?)_(?:resume|tailored|cv)\.pdf$", fname_low)
        if not m:
            return True, "ok"

        slug_part = m.group(1)
        # Strip trailing numeric job ID if present (e.g. 'transunion_global_capability_19042838')
        slug_tokens = [
            tok
            for tok in re.split(r"[^a-z0-9]+", slug_part)
            if len(tok) >= 3 and not tok.isdigit() and tok not in GENERIC_COMPANY_STOPWORDS
        ]
        comp_tokens = [
            tok
            for tok in re.split(r"[^a-z0-9]+", company.lower())
            if len(tok) >= 3 and not tok.isdigit() and tok not in GENERIC_COMPANY_STOPWORDS
        ]

        if not slug_tokens or not comp_tokens:
            return True, "ok"

        for st in slug_tokens:
            for ct in comp_tokens:
                if st == ct or (len(st) >= 4 and len(ct) >= 4 and (st in ct or ct in st)):
                    return True, "ok"

        return (
            False,
            f"Cross-company PDF mismatch: file '{fname}' (tokens={slug_tokens}) does not match target company '{company}' (tokens={comp_tokens})",
        )
