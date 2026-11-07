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
        """Extracts bullet point lines starting with '-' from candidate_notes.md (skipping the Learning Roadmap)."""
        return [bullet for _, bullet in self.extract_sectioned_bullets(notes_text)]

    def extract_sectioned_bullets(self, notes_text: str) -> list[tuple[str, str]]:
        """
        Returns (employer_label, bullet) pairs. The employer label is the heading the bullet sits under
        (e.g. '## Value Labs (Jun 2023 – Present)' -> 'Value Labs'). Bullets under a
        'Learning Roadmap' heading (and its sub-headings) are excluded — they are never synced.
        """
        from src.resume_store.master_sync import is_roadmap_section, notes_sections

        out = []
        for section, bullet in notes_sections(notes_text):
            if is_roadmap_section(section):
                continue
            label = section.split("(")[0].strip()
            out.append((label, bullet))
        return out

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

        notes_sha256 = hashlib.sha256(notes_content.encode("utf-8")).hexdigest()

        sectioned = self.extract_sectioned_bullets(notes_content)
        bullets = [b for _, b in sectioned]
        if not bullets:
            print("ℹ️ No bullet points found in candidate_notes.md.")
            return {"status": "NO_BULLETS", "added": 0}

        from src.resume_store.master_resume import load_learning_roadmap, tool_mentioned

        roadmap = load_learning_roadmap()
        known_employers = {
            "value labs": "Value Labs",
            "valuelabs": "Value Labs",
            "dunzo": "Dunzo",
            "tata elxsi": "Tata Elxsi",
        }

        # Load existing Master Knowledge Bank
        bank_data: dict[str, Any] = {"version": "1.0.0", "master_achievements_vault": []}
        if os.path.exists(self.bank_file):
            try:
                with open(self.bank_file, "r") as f:
                    bank_data = json.load(f)
            except Exception as e:
                print(f"⚠️ Could not load existing bank file: {e}")

        existing_vault = bank_data.setdefault("master_achievements_vault", [])
        if bank_data.get("last_synced_notes_sha256") == notes_sha256 and existing_vault:
            print("ℹ️ candidate_notes.md is unchanged since last sync — skipping redundant LLM translation.")
            return {"status": "SUCCESS", "added": 0, "total_vault_size": len(existing_vault)}

        existing_hashes = {self.generate_achievement_hash(item.get("star_achievement", "")) for item in existing_vault}

        from src.resume_store.master_sync import _near_duplicate

        # Group bullets by employer section so every chunk maps to exactly one boundary,
        # then process in chunks of 5 to respect API rate limits.
        by_section: dict[str, list[str]] = {}
        for label, bullet in sectioned:
            by_section.setdefault(label, []).append(bullet)
        chunks: list[tuple[str, list[str]]] = [
            (label, chunk) for label, items in by_section.items() for chunk in self.chunk_bullets(items, chunk_size=5)
        ]
        added_count = 0

        for chunk_idx, (section_label, chunk) in enumerate(chunks):
            chunk_text = "\n".join([f"- {b}" for b in chunk])
            print(f"\n🔄 Translating Batch #{chunk_idx + 1} ({len(chunk)} bullet(s))...")
            employer = known_employers.get(section_label.lower())

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
                        "Docker",
                        "Kubernetes",
                        "Dynatrace",
                        "Kibana",
                        "Harness",
                        "Selenium",
                    ]:
                        if kw.lower() in b.lower():
                            tools.append(kw)
                    parsed_items.append(
                        {
                            "domain": "Tooling & Automation Architecture",
                            "company": employer or "Personal / Tooling",
                            "star_achievement": b,
                            "tools": tools if tools else ["Automation"],
                            "metric": "Engineering ROI / Tooling Optimization",
                        }
                    )

            for item in parsed_items:
                # Employer label comes deterministically from the notes heading, never from the LLM.
                if employer:
                    item["company"] = employer

                star_text = item.get("star_achievement", "")
                # Evidence-gated rule: learning-roadmap tools are never banked.
                blocked = [
                    t
                    for t in roadmap
                    if tool_mentioned(t, star_text) or t in {x.lower() for x in item.get("tools", [])}
                ]
                if blocked:
                    print(f"  🚫 Skipping roadmap-tool achievement {blocked}: {star_text[:60]}...")
                    continue

                a_hash = self.generate_achievement_hash(star_text)
                if a_hash in existing_hashes or any(
                    _near_duplicate(star_text, v.get("star_achievement", "")) for v in existing_vault
                ):
                    print(f"  ⏭️  Skipping duplicate achievement: {star_text[:50]}...")
                    continue
                existing_vault.append(item)
                existing_hashes.add(a_hash)
                added_count += 1
                print(f"  ✨ Added new STAR achievement: {star_text[:70]}...")

        # Atomic Write via temp file and os.replace()
        bank_data["last_synced_notes_sha256"] = notes_sha256
        tmp_file = f"{self.bank_file}.tmp"
        with open(tmp_file, "w") as f:
            json.dump(bank_data, f, indent=2)

        os.replace(tmp_file, self.bank_file)
        print(f"\n🔒 Atomically updated {self.bank_file} (Added {added_count} new item(s)).")

        return {"status": "SUCCESS", "added": added_count, "total_vault_size": len(existing_vault)}
