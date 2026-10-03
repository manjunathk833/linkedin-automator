"""
Form field mapping heuristics and candidate response resolver.
Parses field labels, attributes, and screening questions to resolve grounded candidate data.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROFILE_PATH = os.path.join(PROJECT_ROOT, "data", "resume_profile.json")


class FormFieldMapper:
    """
    Resolves standard application inputs and screening questions using authentic candidate profile facts.
    """

    def __init__(self, profile_path: str = PROFILE_PATH):
        self.profile_path = profile_path
        self.profile: dict[str, Any] = self._load_profile()

    def _load_profile(self) -> dict[str, Any]:
        if not os.path.exists(self.profile_path):
            return {}
        with open(self.profile_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_contact_info(self) -> dict[str, str]:
        """Returns standard personal details."""
        personal = self.profile.get("personal_details", {})
        full_name = personal.get("full_name", "")
        parts = full_name.split()
        first_name = parts[0] if parts else ""
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

        links = {p.get("network", "").lower(): p.get("url", "") for p in personal.get("profiles", [])}

        return {
            "full_name": full_name,
            "first_name": first_name,
            "last_name": last_name,
            "email": personal.get("email", ""),
            "phone": personal.get("phone", ""),
            "location": personal.get("location", "Bengaluru, Karnataka, India"),
            "city": personal.get("city", "Bengaluru"),
            "country": personal.get("country", "India"),
            "linkedin": links.get("linkedin", ""),
            "github": links.get("github", ""),
            "portfolio": links.get("portfolio", ""),
        }

    def resolve_field_value(self, label: str, field_type: str = "text") -> str | None:
        """
        Determines the appropriate pre-fill answer for a form field label.
        """
        contact = self.get_contact_info()
        norm_label = label.lower().strip()

        # 1. Names
        if re.search(r"\b(first\s*name|given\s*name)\b", norm_label):
            return contact["first_name"]
        if re.search(r"\b(last\s*name|family\s*name|surname)\b", norm_label):
            return contact["last_name"]
        if re.search(r"\b(full\s*name|your\s*name|name)\b", norm_label):
            return contact["full_name"]

        # 2. Contact details
        if re.search(r"\b(email|e-mail)\b", norm_label):
            return contact["email"]
        if re.search(r"\b(phone|mobile|cell|contact\s*number)\b", norm_label):
            return contact["phone"]
        if re.search(r"\b(city|current\s*city)\b", norm_label):
            return contact["city"]
        if re.search(r"\b(location|address)\b", norm_label):
            return contact["location"]

        # 3. URLs
        if re.search(r"\blinkedin\b", norm_label):
            return contact["linkedin"]
        if re.search(r"\bgithub\b", norm_label):
            return contact["github"]
        if re.search(r"\b(portfolio|website|site)\b", norm_label):
            return contact["portfolio"]

        # 4. Standard Experience Questions
        if re.search(r"\b(years\s*of\s*experience|total\s*experience|overall\s*experience)\b", norm_label):
            return "6"
        if re.search(r"\b(java|core\s*java)\b", norm_label) and re.search(r"\b(years|exp)\b", norm_label):
            return "6"
        if re.search(r"\b(rest\s*assured|api\s*testing|api\s*automation)\b", norm_label) and re.search(
            r"\b(years|exp)\b", norm_label
        ):
            return "6"
        if re.search(r"\b(selenium|ui\s*automation)\b", norm_label) and re.search(r"\b(years|exp)\b", norm_label):
            return "4"
        if re.search(r"\b(python)\b", norm_label) and re.search(r"\b(years|exp)\b", norm_label):
            return "3"
        if re.search(r"\b(jenkins|ci/cd|cicd)\b", norm_label) and re.search(r"\b(years|exp)\b", norm_label):
            return "5"

        # 5. Authorization & Sponsorship (India)
        if re.search(r"\b(legally\s*authorized|authorized\s*to\s*work|right\s*to\s*work)\b", norm_label):
            return "Yes"
        if re.search(
            r"\b(require\s*sponsorship|visa\s*sponsorship|sponsorship\s*now\s*or\s*in\s*the\s*future)\b", norm_label
        ):
            return "No"

        # 6. Notice period
        if re.search(r"\b(notice\s*period|how\s*soon|joining\s*time)\b", norm_label):
            return "Immediate / 15-30 days"

        return None
