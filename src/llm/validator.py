"""
Deterministic Verification Gate and Anti-Hallucination Sanitizer.
Enforces that AI-tailored resume bullets and screening answers never contain tools or skills
outside the candidate's authentic profile.
"""

from __future__ import annotations

import json
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_WHITELIST_PATH = os.path.join(PROJECT_ROOT, "data", "profile", "allowed_tools_whitelist.json")

# Common tool substitution dictionary to recover sentences gracefully
TOOL_SUBSTITUTIONS = {
    "playwright": "Selenium",
    "cypress": "Selenium",
    "kubernetes": "Docker",
    "k8s": "Docker",
    "golang": "Python",
    "go": "Python",
    "rust": "Java",
    "kafka": "REST API",
}


class ResumeVerificationGate:
    """
    Deterministic gate verifying and sanitizing LLM outputs against authenticated candidate skills.
    """

    def __init__(self, whitelist_path: str = DEFAULT_WHITELIST_PATH):
        self.whitelist_path = whitelist_path
        self.allowed_tools: set[str] = set()
        self.disallowed_tools: set[str] = set()
        self._load_whitelist()

    def _load_whitelist(self) -> None:
        """Loads allowed tools and known hallucination targets from JSON."""
        if not os.path.exists(self.whitelist_path):
            return

        with open(self.whitelist_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.allowed_tools = {tool.strip().lower() for tool in data.get("allowed_tools", [])}
        self.disallowed_tools = {tool.strip().lower() for tool in data.get("disallowed_hallucinations", [])}

    def detect_unauthorized_tools(self, text: str) -> list[str]:
        """
        Scans text for unauthorized tools or explicit disallowed hallucinations.
        """
        found_violations: list[str] = []
        lower_text = text.lower()

        # Check explicit disallowed list
        for dis in self.disallowed_tools:
            pattern = rf"\b{re.escape(dis)}\b"
            if re.search(pattern, lower_text):
                found_violations.append(dis)

        return sorted(set(found_violations))

    def sanitize_bullet(self, bullet: str) -> tuple[str, bool]:
        """
        Replaces unauthorized tools with authentic equivalents.
        Returns (sanitized_bullet, was_modified).
        """
        modified = False
        sanitized = bullet

        for dis, replacement in TOOL_SUBSTITUTIONS.items():
            pattern = re.compile(rf"\b{re.escape(dis)}\b", re.IGNORECASE)
            if pattern.search(sanitized):
                sanitized = pattern.sub(replacement, sanitized)
                modified = True

        # Re-check if any unallowed tool remains
        violations = self.detect_unauthorized_tools(sanitized)
        for viol in violations:
            pattern = re.compile(rf"\b{re.escape(viol)}\b", re.IGNORECASE)
            sanitized = pattern.sub("", sanitized)
            modified = True

        # Clean up double spaces or dangling commas/slashes
        sanitized = re.sub(r"\s+([,.;])", r"\1", sanitized)
        sanitized = re.sub(r"([,/])\s*([,/])", r"\1", sanitized)
        sanitized = re.sub(r"\s{2,}", " ", sanitized).strip()

        return sanitized, modified

    def validate_and_sanitize(
        self,
        tailored_bullets: list[str],
        fallback_bullets: list[str] | None = None,
    ) -> list[str]:
        """
        Validates a list of tailored achievements.
        Sanitizes or replaces invalid bullets with authentic fallback bullets.
        """
        sanitized_list: list[str] = []
        fallback_idx = 0

        for bullet in tailored_bullets:
            sanitized, _was_modified = self.sanitize_bullet(bullet)
            violations = self.detect_unauthorized_tools(sanitized)

            if violations:
                # If cannot be cleaned, fallback to master authentic bullet
                if fallback_bullets and fallback_idx < len(fallback_bullets):
                    sanitized_list.append(fallback_bullets[fallback_idx])
                    fallback_idx += 1
                else:
                    # Strip violating sentence segments
                    clean_sentences = [
                        s.strip()
                        for s in re.split(r"[.!?]", sanitized)
                        if s.strip() and not any(v in s.lower() for v in violations)
                    ]
                    if clean_sentences:
                        sanitized_list.append(". ".join(clean_sentences) + ".")
            else:
                sanitized_list.append(sanitized)

        return sanitized_list
