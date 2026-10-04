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

    COMPANY_EXCLUSIVE_MARKERS: ClassVar[dict[str, list[str]]] = {
        "Value Labs": ["mosaic", "harness", "airline"],
        "Dunzo": ["ekam", "merchant service", "google metrics explorer"],
        "Tata Elxsi": [
            "appium",
            "testrail",
            "charles proxy",
            "burp suite",
            "ott app",
            "app store",
        ],
    }

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

    def check_company_contamination(self, company: str, bullet: str) -> dict[str, Any]:
        """
        Validates that a bullet assigned to a specific company does not claim achievements
        or exclusive tools that belong to another company.
        """
        bullet_lower = bullet.lower()
        violating_companies = []
        for other_comp, markers in self.COMPANY_EXCLUSIVE_MARKERS.items():
            if other_comp.lower() not in company.lower():
                for marker in markers:
                    pattern = rf"\b{re.escape(marker)}\b"
                    if re.search(pattern, bullet_lower):
                        violating_companies.append(f"{other_comp} (marker: '{marker}')")
                        break

        is_clean = len(violating_companies) == 0
        return {
            "is_clean": is_clean,
            "violating_companies": violating_companies,
            "company": company,
            "bullet": bullet,
        }

    def validate_company_bullets(self, company: str, bullets: list[str]) -> list[str]:
        """
        Filters bullets for both general tool fabrication AND cross-company contamination.
        Ensures that bullets assigned to 'company' strictly originate from that company's experience.
        """
        unfabricated = self.validate_all_bullets(bullets)
        clean_company_bullets = []
        for bullet in unfabricated:
            contam = self.check_company_contamination(company, bullet)
            if contam["is_clean"]:
                clean_company_bullets.append(bullet)
            else:
                print(
                    f"🚨 CROSS-COMPANY CONTAMINATION BLOCKED: Bullet for '{company}' claimed experience from {contam['violating_companies']}:"
                )
                print(f'   "{bullet[:90]}..."')
        return clean_company_bullets
