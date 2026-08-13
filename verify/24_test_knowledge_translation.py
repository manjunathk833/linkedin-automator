from __future__ import annotations

import os
import sys

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.tailor.knowledge_translator import KnowledgeBankTranslator


def test_knowledge_translation():
    print("==================================================")
    print("  Testing AI Knowledge Translator Engine")
    print("==================================================")

    # Setup temp test files
    test_notes = os.path.abspath("verify/test_candidate_notes.md")
    test_bank = os.path.abspath("verify/test_master_bank.json")

    sample_markdown = """# Test Notes
    - Built Locust performance test suite in Python simulating 5,000 concurrent API users, cutting response latency by 35%.
    - Earned AWS Certified Solutions Architect Associate in 2026.
    - Automated Kafka event-driven message verification using Java and REST Assured.
    """

    with open(test_notes, "w") as f:
        f.write(sample_markdown)

    translator = KnowledgeBankTranslator(notes_file=test_notes, bank_file=test_bank, use_ai=False)

    # 1. Test bullet extraction
    bullets = translator.extract_bullet_lines(sample_markdown)
    assert len(bullets) == 3
    print(f"✅ Extracted {len(bullets)} bullet point lines!")

    # 2. Test chunking
    chunks = translator.chunk_bullets(bullets, chunk_size=2)
    assert len(chunks) == 2
    assert len(chunks[0]) == 2
    assert len(chunks[1]) == 1
    print("✅ Chunking logic verified!")

    # 3. Test Translation & Atomic Sync
    res = translator.sync_notes_to_knowledge_bank()
    assert res["status"] == "SUCCESS"
    assert res["added"] == 3
    assert os.path.exists(test_bank)
    print(f"✅ Synced {res['added']} items into test bank!")

    # 4. Test Deduplication (Run sync again)
    res_dedup = translator.sync_notes_to_knowledge_bank()
    assert res_dedup["added"] == 0
    print("✅ MD5 Hash Deduplication verified! (0 duplicates added on re-sync)")

    # Cleanup temp test files
    if os.path.exists(test_notes):
        os.remove(test_notes)
    if os.path.exists(test_bank):
        os.remove(test_bank)

    print("\n" + "=" * 50)
    print("✅ AI KNOWLEDGE TRANSLATOR ENGINE VERIFIED SUCCESSFULLY!")
    print("=" * 50)


if __name__ == "__main__":
    test_knowledge_translation()
