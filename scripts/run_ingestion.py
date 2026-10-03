"""
CLI Runner for Multi-Source Ingestion.
Fetches public ATS listings across target companies without browser overhead.
After queuing, deterministically tailors each job payload against the master resume.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ingestion.ats_discovery import ATSDiscoveryCoordinator


async def run_ingestion_cli():
    parser = argparse.ArgumentParser(description="Multi-Source ATS Ingestion Engine")
    parser.add_argument(
        "--queue",
        action="store_true",
        default=False,
        help="Queue discovered jobs into data/pending_queue for dashboard review",
    )
    args = parser.parse_args()

    coordinator = ATSDiscoveryCoordinator()
    listings = await coordinator.ingest_all_sources(filter_sdet=True)

    print("\n" + "=" * 60)
    print(f"  DISCOVERED {len(listings)} RELEVANT ROLES ACROSS TARGET ENTERPRISES")
    print("=" * 60)

    for idx, item in enumerate(listings[:15], 1):
        print(f"[{idx}] {item.job_title} @ {item.company_name} ({item.location})")
        print(f"    Source: {item.source.upper()} | URL: {item.url}")

    if len(listings) > 15:
        print(f"... and {len(listings) - 15} more roles.")

    if args.queue:
        saved = coordinator.save_listings_to_queue(listings)
        print(f"\n💾 Queued {len(saved)} jobs into data/pending_queue/")

        # Deterministically tailor each queued job against the master resume
        from src.tailor.resume_tailorer import ResumeTailorer

        tailorer = ResumeTailorer(use_ai=False)
        tailored_count = 0
        os.path.join(PROJECT_ROOT, "data", "pending_queue")

        for filepath in saved:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    raw_payload = json.load(f)

                # Skip if already tailored
                if "tailored_resume" in raw_payload:
                    tailored_count += 1
                    continue

                # Use description as requirements fallback for keyword matching
                jd = raw_payload.get("job_details", {})
                if not jd.get("requirements") and jd.get("description"):
                    jd["requirements"] = ATSDiscoveryCoordinator._extract_requirements_text(jd["description"])

                tailored_payload = tailorer.tailor_job_payload(raw_payload)

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(tailored_payload, f, indent=2)
                tailored_count += 1
            except Exception as e:
                print(f"⚠️ Tailoring failed for {os.path.basename(filepath)}: {e}")

        print(f"✅ Tailored {tailored_count}/{len(saved)} jobs with grounded resume data.")


if __name__ == "__main__":
    asyncio.run(run_ingestion_cli())
