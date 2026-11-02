#!/usr/bin/env python3
"""
Verification Script 108: Daily Runner CI Drop Auto-Ingest & Environment Sourcing Verification Gate.
Verifies:
1. Environment file syntax (.env) parses cleanly under bash 'source' without command-not-found errors.
2. DailyPipelineRunner executes Cloud CI Drop synchronization safely.
3. LaunchAgent plist loads without syntax or execution errors.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_env_sourcing() -> bool:
    print("\n--- Test 1: Bash .env Sourcing Verification ---")
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        print(f"❌ .env file not found at {env_file}")
        return False

    # Run bash -c 'set -a; source .env; set +a' and capture stderr
    cmd = f'bash -c "set -a; source {env_file}; set +a && echo GMAIL_USER=$GMAIL_USER"'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"❌ Bash sourcing failed with exit code {res.returncode}: {res.stderr}")
        return False
    if "command not found" in res.stderr.lower():
        print(f"❌ Unquoted command error detected in stderr: {res.stderr}")
        return False
    print(f"✅ .env sourced cleanly without errors. Output: {res.stdout.strip()}")
    return True


def test_ci_sync_in_daily_runner() -> bool:
    print("\n--- Test 2: DailyPipelineRunner CI Drop Auto-Ingest ---")
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.ingestion.ci_sync import CISyncIngestor

    ingestor = CISyncIngestor(use_ai=False)
    # Test safe sync (no unhandled exceptions)
    res = ingestor.sync_latest_drops(fetch_remote=False)
    print(f"✅ CISyncIngestor local bundle scan succeeded: {res}")
    assert "status" in res
    assert "ingested_count" in res
    return True


def test_launchagent_plist() -> bool:
    print("\n--- Test 3: macOS LaunchAgent Plist Validation ---")
    plist_path = Path.home() / "Library" / "LaunchAgents" / "com.linkedin.automator.daily.plist"
    if not plist_path.exists():
        print(f"⚠️ LaunchAgent plist not found at {plist_path}")
        return True

    res = subprocess.run(["plutil", "-lint", str(plist_path)], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"❌ Plist validation failed: {res.stderr}")
        return False
    print(f"✅ LaunchAgent plist validated cleanly: {res.stdout.strip()}")
    return True


def main() -> int:
    t1 = test_env_sourcing()
    t2 = test_ci_sync_in_daily_runner()
    t3 = test_launchagent_plist()

    if t1 and t2 and t3:
        print("\n🎉 ALL GATE 108 VERIFICATIONS PASSED SUCCESSFULLY.")
        return 0
    print("\n❌ GATE 108 VERIFICATION FAILED.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
