#!/usr/bin/env python3
"""
Regenerates data/resume_profile.json, data/profile/allowed_tools_whitelist.json and
data/master_knowledge_bank.json from the master resume (Manjunath_HK_Master_Resume.json).

Equivalent to: python main.py resume sync [--dry-run]

Workflow:
  1. Edit the resume visually in rxresu.me.
  2. Export -> JSON, save over Manjunath_HK_Master_Resume.json in the repo root.
  3. Run this script (or `python main.py resume sync`).
"""

from __future__ import annotations

import argparse
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.resume_store.master_sync import format_report, run_sync


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print the report without writing files")
    args = parser.parse_args()
    report = run_sync(write=not args.dry_run)
    print(format_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
