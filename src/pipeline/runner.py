from __future__ import annotations

from typing import Any

import uvicorn

from src.filter.job_filter import LinkedInJobFilter
from src.scraper.job_finder import LinkedInJobFinder
from src.tailor.knowledge_translator import KnowledgeBankTranslator


class JobSearchPipelineRunner:
    """
    Decoupled Orchestrator executing the end-to-end job discovery, AI tailoring,
    experience filtering, and dashboard approval pipeline.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.use_ai = config.get("llm", {}).get("use_ai", True)

    def run_sync_stage(self) -> dict[str, Any]:
        """Stage 1: Ingests candidate_notes.md and translates to master_knowledge_bank.json."""
        print("\n" + "=" * 60)
        print("  STAGE 1: TRANSLATING CANDIDATE NOTES TO KNOWLEDGE BANK")
        print("=" * 60)
        translator = KnowledgeBankTranslator(use_ai=self.use_ai)
        res = translator.sync_notes_to_knowledge_bank()
        print(f"✅ STAGE 1 COMPLETE: Added {res.get('added', 0)} new STAR achievement(s).\n")
        return res

    async def run_search_stage(self) -> list[dict[str, Any]]:
        """Stage 2: Runs 4-channel discovery (Search, Recommended, Posts, Similar) + AI tailoring."""
        profiles = self.config.get("search_profiles", [])
        discovery_cfg = self.config.get("discovery", {})
        if not profiles:
            print("⚠️ No search_profiles found in config.yaml.")
            return []

        print("\n" + "=" * 60)
        print("  STAGE 2: RUNNING 10X MULTI-CHANNEL DISCOVERY & AI TAILORING")
        print("=" * 60)
        finder = LinkedInJobFinder(use_ai=self.use_ai)
        jobs = await finder.search_all_channels(profiles, discovery_config=discovery_cfg)
        print(f"🎉 STAGE 2 COMPLETE: {len(jobs)} job(s) tailored & queued in data/pending_queue/\n")
        return jobs

    def run_filter_stage(self):
        """Stage 3: Runs standalone experience-level threshold filter on pending queue."""
        print("\n" + "=" * 60)
        print("  STAGE 3: RUNNING EXPERIENCE-LEVEL FILTER ENGINE")
        print("=" * 60)
        job_filter = LinkedInJobFilter()
        job_filter.filter_pending_queue()
        print("✅ STAGE 3 COMPLETE: Queue filtering finished.\n")

    def run_dashboard_stage(self):
        """Stage 4: Launches FastAPI Approval Gate Web Dashboard on http://127.0.0.1:8000."""
        print("\n" + "=" * 60)
        print("  STAGE 4: LAUNCHING APPROVAL GATE DASHBOARD")
        print("  Access UI at: http://127.0.0.1:8000")
        print("=" * 60 + "\n")
        uvicorn.run("src.ui.app:app", host="127.0.0.1", port=8000, reload=True)

    async def run_full_pipeline(self, skip_sync: bool = False, launch_ui: bool = True):
        """Orchestrates Stages 1 -> 2 -> 3 -> 4 sequentially in a single execution."""
        print("\n" + "🚀 " + "=" * 58)
        print("  STARTING ONE-SHOT AUTOMATED JOB SEARCH & TAILORING PIPELINE")
        print("=" * 60)

        # Stage 1: Sync Notes
        if not skip_sync:
            self.run_sync_stage()
        else:
            print("\n⏭️  Skipping Stage 1 (Knowledge Sync requested skip)")

        # Stage 2: Search & Tailor
        await self.run_search_stage()

        # Stage 3: Filter Queue
        self.run_filter_stage()

        # Stage 4: Dashboard
        if launch_ui:
            self.run_dashboard_stage()
        else:
            print("\n💡 Pipeline complete! (Dashboard launch skipped via --no-dashboard)")
            print("👉 Run `python main.py dashboard` anytime to approve pending jobs.")
