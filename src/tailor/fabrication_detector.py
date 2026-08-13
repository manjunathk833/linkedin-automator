from __future__ import annotations

import re
from typing import Any, ClassVar

from src.resume_store.models import ResumeProfile


class FabricationDetector:
    """
    Zero-Cost Deterministic Post-Generation Verification Gate.
    Verifies that AI-generated bullets do not claim experience with tools or technologies
    that the candidate has never used.
    """

    KNOWN_TECH_TOOLS: ClassVar[list[str]] = [
        "Playwright",
        "Cypress",
        "Puppeteer",
        "WebdriverIO",
        "Robot Framework",
        "Protractor",
        "Golang",
        "Go",
        "C#",
        ".NET",
        "Ruby",
        "Kotlin",
        "Swift",
        "GraphQL",
        "Kubernetes",
    ]

    def __init__(self, profile: ResumeProfile, master_knowledge_bank: dict[str, Any] | None = None):
        self.profile = profile
        self.knowledge_bank = master_knowledge_bank or {}
        self.allowed_tools = self._build_allowed_tools_set()

    def _build_allowed_tools_set(self) -> set[str]:
        """Collects all authentic tools from ResumeProfile and Master Knowledge Bank."""
        tools = set()

        # 1. Skills Matrix
        if isinstance(self.profile.skills_matrix, dict):
            for category_tools in self.profile.skills_matrix.values():
                for t in category_tools:
                    tools.add(t.strip().lower())

        # 2. Experience History Tech Tags & Achievements
        for exp in self.profile.experience_history:
            for t in exp.tech_tags:
                tools.add(t.strip().lower())

        # 3. Master Knowledge Bank Vault & Extended Skills
        vault = self.knowledge_bank.get("master_achievements_vault", [])
        for item in vault:
            for t in item.get("tools", []):
                tools.add(t.strip().lower())

        ext_skills = self.knowledge_bank.get("extended_skills_inventory", {})
        for cat_list in ext_skills.values():
            if isinstance(cat_list, list):
                for t in cat_list:
                    tools.add(t.strip().lower())

        return tools

    def check_bullet(self, bullet: str) -> dict[str, Any]:
        """
        Inspects a single bullet for tool fabrication.
        Returns dict with is_valid (bool) and list of fabricated_tools (if any).
        """
        fabricated = []

        # Check against known external tools that candidate does NOT have in allowed set
        for tool in self.KNOWN_TECH_TOOLS:
            tool_lower = tool.lower()
            # Strict word-boundary matching to prevent false positives (e.g. "go" in "google")
            pattern = rf"\b{re.escape(tool_lower)}\b"
            if re.search(pattern, bullet.lower()) and tool_lower not in self.allowed_tools:
                fabricated.append(tool)

        is_valid = len(fabricated) == 0
        return {
            "is_valid": is_valid,
            "fabricated_tools": fabricated,
            "bullet": bullet,
        }

    def validate_all_bullets(self, bullets: list[str]) -> list[str]:
        """
        Filters out any fabricated bullets, logging a warning for discarded items.
        Returns only authentic, grounded bullets.
        """
        clean_bullets = []
        for bullet in bullets:
            res = self.check_bullet(bullet)
            if res["is_valid"]:
                clean_bullets.append(bullet)
            else:
                print(f"🚨 FABRICATION DETECTED & STRIPPED: Discarded bullet claiming {res['fabricated_tools']}:")
                print(f'   "{bullet[:90]}..."')
        return clean_bullets
