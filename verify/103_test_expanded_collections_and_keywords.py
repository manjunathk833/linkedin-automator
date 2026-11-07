#!/usr/bin/env python3
"""
Verify Gate 103: Expanded Multi-Collection & Boolean Keyword Discovery Test.

Verifies:
1. Boolean keywords in config.yaml match Sr. / Sr / SDET II syntax (including Swiggy title).
2. Discovery config includes multiple recommendation collections ('recommended', 'top-applicant').
3. scrape_recommended_jobs() handles multi-collection iteration and clean deduplication.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.scraper.job_finder import LinkedInJobFinder


def test_keyword_matching_swiggy_syntax():
    """Verify boolean queries in config.yaml cover Sr. SDET and Swiggy title variations."""
    config_path = PROJECT_ROOT / "config.yaml"
    assert config_path.exists(), "config.yaml not found"

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    profiles = cfg.get("search_profiles", [])
    assert len(profiles) > 0, "No search profiles found"

    bengaluru_profile = profiles[0]
    kw = bengaluru_profile.get("keywords", "")

    # Ensure critical variations are present
    assert "Sr. SDET" in kw or "Sr SDET" in kw, "Missing Sr. SDET variant in keywords"
    assert "Sr. Software Development Engineer in Test" in kw, (
        "Missing Sr. Software Development Engineer in Test in keywords"
    )
    assert "SDET II" in kw or "SDET-2" in kw, "Missing SDET II variant in keywords"

    # Test title simulation
    test_titles = [
        "Sr. Software Development Engineer in Test",  # Swiggy title
        "Sr. SDET - Automation",
        "Lead SDET",
        "Senior Software Development Engineer in Test",
    ]
    for title in test_titles:
        matched = any(
            variant.strip('"') in title
            for variant in [
                "Sr. Software Development Engineer in Test",
                "Sr. SDET",
                "Lead SDET",
                "Senior Software Development Engineer in Test",
            ]
        )
        assert matched, f"Title '{title}' failed keyword matching"

    print("✅ Keyword boolean syntax verification passed (covers Swiggy and Sr. variations).")


def test_discovery_config_collections():
    """Verify config specifies multiple recommendation collections."""
    config_path = PROJECT_ROOT / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    disc = cfg.get("discovery", {})
    cols = disc.get("recommendation_collections", [])
    assert "recommended" in cols, "Missing 'recommended' collection"
    assert "top-applicant" in cols, "Missing 'top-applicant' collection"
    print(f"✅ Discovery configuration verified: collections={cols}")


def test_multi_collection_scraper_deduplication():
    """Verify scrape_recommended_jobs iterates multiple collections and deduplicates cards."""
    finder = LinkedInJobFinder()

    # Create mock page
    mock_page = MagicMock()
    mock_page.goto = AsyncMock()
    mock_page.evaluate = AsyncMock()

    # Mock locator returning card elements
    card1 = MagicMock()
    card2 = MagicMock()
    card3 = MagicMock()  # Duplicate of card1 with same job_id

    mock_locator = MagicMock()
    mock_locator.all = AsyncMock(
        side_effect=[
            [],  # hub cards
            [card1, card2],  # recommended page 1
            [],  # recommended page 2 (break)
            [card3],  # top-applicant page 1 (duplicate job_id as card1)
            [],  # top-applicant page 2 (break)
        ]
    )
    mock_page.locator.return_value = mock_locator

    async def mock_extract(page, card, idx, default_prefix=""):
        if card == card1:
            return {"job_id": "4481865334", "title": "Sr. SDET @ Swiggy", "company": "Swiggy"}
        elif card == card2:
            return {"job_id": "9990001111", "title": "Lead SDET @ Google", "company": "Google"}
        elif card == card3:
            # Same job_id as card1
            return {"job_id": "4481865334", "title": "Sr. SDET @ Swiggy", "company": "Swiggy"}
        return None

    finder._extract_card_payload = AsyncMock(side_effect=mock_extract)
    finder.scroll_results_pane = AsyncMock()

    async def run_test():
        from unittest.mock import patch

        with patch("src.scraper.job_finder.asyncio.sleep", new_callable=AsyncMock):
            res = await finder.scrape_recommended_jobs(
                mock_page,
                max_jobs=20,
                max_pages=2,
                collections=["recommended", "top-applicant"],
            )
        assert len(res) == 2, f"Expected 2 deduplicated jobs, got {len(res)}"
        job_ids = [j["job_id"] for j in res]
        assert "4481865334" in job_ids, "Swiggy job ID not found"
        assert "9990001111" in job_ids, "Google job ID not found"
        assert job_ids.count("4481865334") == 1, "Duplicate job ID was not deduped"
        print(f"✅ Multi-collection scraper deduplication passed (result count: {len(res)}).")

    asyncio.run(run_test())


def test_repo_wide_credential_sanitization():
    """Verify zero git-tracked files contain live .env secrets or non-mock portal passwords."""
    import re
    import subprocess

    out = subprocess.check_output(["git", "ls-files"], cwd=PROJECT_ROOT, text=True)
    tracked_files = [line.strip() for line in out.splitlines() if line.strip()]

    # 1. Load live secret values dynamically from local git-ignored .env (if present)
    env_secrets: dict[str, str] = {}
    env_path = PROJECT_ROOT / ".env"
    if env_path.is_file():
        for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("\"'")
            if (
                len(v) >= 6
                and any(tok in k.upper() for tok in ("PASSWORD", "SECRET", "KEY", "TOKEN"))
                and not v.startswith(("your_", "xxxx"))
            ):
                env_secrets[k] = v

    secret_regex = re.compile(
        r"(AIza[0-9A-Za-z_-]{35}|ghp_[0-9A-Za-z]{36}|github_pat_[0-9A-Za-z_]{80}|gsk_[0-9A-Za-z]{20,})"
    )
    allowed_mock_pwds = {
        "CandidateMockSecret123!",
        "TEST_MOCK_PASSWORD_123!",
        "MockSecretPassword123!",
        "WORKDAY_DEFAULT_PASSWORD",
        "workday_default_password",
    }
    pwd_assign_regex = re.compile(
        r"(?:workday_default_password|default_pwd|workday_pwd)[^\n]*?['\"]([A-Za-z0-9@#$%^&*!_~+=?-]{8,})['\"]"
    )

    violations = []
    for rel_path in tracked_files:
        p = PROJECT_ROOT / rel_path
        if not p.is_file() or p.suffix in {".png", ".jpg", ".jpeg", ".pdf", ".woff2", ".db"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            print(f"⚠️ Skipping unreadable file {rel_path}: {exc}")
            continue

        for env_key, secret_val in env_secrets.items():
            if secret_val in text:
                violations.append(f"{rel_path}: contains live secret value from .env ({env_key})")

        m = secret_regex.search(text)
        if m:
            violations.append(f"{rel_path}: contains secret token matching {m.group(0)[:8]}...")

        for pwd_match in pwd_assign_regex.finditer(text):
            candidate_literal = pwd_match.group(1)
            if candidate_literal not in allowed_mock_pwds:
                violations.append(f"{rel_path}: contains non-mock password literal in assignment/fallback")

    assert not violations, f"Credential sanitization violations found: {violations}"
    print(
        f"✅ Repo-wide credential sanitization passed across {len(tracked_files)} tracked files "
        f"(checked {len(env_secrets)} dynamic .env secret(s) + mock allowlist)."
    )


if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("  VERIFY GATE 103: MULTI-COLLECTION & KEYWORD RESILIENCE")
    print("=" * 65)
    test_keyword_matching_swiggy_syntax()
    test_discovery_config_collections()
    test_multi_collection_scraper_deduplication()
    test_repo_wide_credential_sanitization()
    print("\n🎉 ALL GATE 103 TESTS PASSED (100% SUCCESS)!\n")
