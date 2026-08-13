from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from src.tailor.llm_provider import HybridLLMProvider


class KnowledgeBankTranslator:
    def __init__(
        self,
        notes_file: str = "data/candidate_notes.md",
        bank_file: str = "data/master_knowledge_bank.json",
        use_ai: bool = True,
    ):
        self.notes_file = os.path.abspath(notes_file)
        self.bank_file = os.path.abspath(bank_file)
        self.use_ai = use_ai
        self.llm_provider = HybridLLMProvider() if use_ai else None

    def extract_bullet_lines(self, notes_text: str) -> list[str]:
        """Extracts bullet point lines starting with '-' from candidate_notes.md."""
        lines = notes_text.split("\n")
        bullets = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- ") and len(stripped) > 5:
                bullets.append(stripped[2:].strip())
        return bullets

    def chunk_bullets(self, bullets: list[str], chunk_size: int = 5) -> list[list[str]]:
        """Splits bullets into chunks of N items to respect API rate limits."""
        return [bullets[i : i + chunk_size] for i in range(0, len(bullets), chunk_size)]

    def generate_achievement_hash(self, star_text: str) -> str:
        """Generates a deterministic MD5 hash for deduplication."""
        norm = star_text.strip().lower()
        return hashlib.md5(norm.encode("utf-8")).hexdigest()

    def sync_notes_to_knowledge_bank(self) -> dict[str, Any]:
        """
        Translates free-form bullet points in candidate_notes.md into structured STAR
        entries in master_knowledge_bank.json with batch chunking, MD5 dedup, and atomic writing.
        """
        if not os.path.exists(self.notes_file):
            print(f"⚠️ Notes file not found: {self.notes_file}")
            return {"status": "SKIPPED", "added": 0}

        with open(self.notes_file, "r") as f:
            notes_content = f.read()

        bullets = self.extract_bullet_lines(notes_content)
        if not bullets:
            print("ℹ️ No bullet points found in candidate_notes.md.")
            return {"status": "NO_BULLETS", "added": 0}

        # Load existing Master Knowledge Bank
        bank_data = {"version": "1.0.0", "master_achievements_vault": []}
        if os.path.exists(self.bank_file):
            try:
                with open(self.bank_file, "r") as f:
                    bank_data = json.load(f)
            except Exception as e:
                print(f"⚠️ Could not load existing bank file: {e}")

        existing_vault = bank_data.setdefault("master_achievements_vault", [])
        existing_hashes = {self.generate_achievement_hash(item.get("star_achievement", "")) for item in existing_vault}

        # Process in chunks of 5
        chunks = self.chunk_bullets(bullets, chunk_size=5)
        added_count = 0

        for chunk_idx, chunk in enumerate(chunks):
            chunk_text = "\n".join([f"- {b}" for b in chunk])
            print(f"\n🔄 Translating Batch #{chunk_idx + 1} ({len(chunk)} bullet(s))...")

            parsed_items = None
            if self.use_ai and self.llm_provider:
                try:
                    parsed_items = self.llm_provider.translate_notes(chunk_text)
                except Exception as e_ai:
                    print(f"⚠️ AI translation skipped (using fallback): {e_ai}")

            if not parsed_items:
                parsed_items = []
                for b in chunk:
                    # Extract tools heuristic
                    tools = []
                    for kw in [
                        "Python",
                        "Java",
                        "REST Assured",
                        "Azure DevOps",
                        "Ollama",
                        "GitHub AI",
                        "Locust",
                        "Kafka",
                        "Playwright",
                    ]:
                        if kw.lower() in b.lower():
                            tools.append(kw)
                    parsed_items.append(
                        {
                            "domain": "Tooling & Automation Architecture",
                            "company": "Personal / Tooling",
                            "star_achievement": b,
                            "tools": tools if tools else ["Automation"],
                            "metric": "Engineering ROI / Tooling Optimization",
                        }
                    )

            for item in parsed_items:
                star_text = item.get("star_achievement", "")
                a_hash = self.generate_achievement_hash(star_text)

                if a_hash not in existing_hashes:
                    existing_vault.append(item)
                    existing_hashes.add(a_hash)
                    added_count += 1
                    print(f"  ✨ Added new STAR achievement: {star_text[:70]}...")
                else:
                    print(f"  ⏭️  Skipping duplicate achievement: {star_text[:50]}...")

        # Atomic Write via temp file and os.replace()
        tmp_file = f"{self.bank_file}.tmp"
        with open(tmp_file, "w") as f:
            json.dump(bank_data, f, indent=2)

        os.replace(tmp_file, self.bank_file)
        print(f"\n🔒 Atomically updated {self.bank_file} (Added {added_count} new item(s)).")

        return {"status": "SUCCESS", "added": added_count, "total_vault_size": len(existing_vault)}
