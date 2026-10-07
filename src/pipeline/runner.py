from __future__ import annotations

from typing import Any

import uvicorn

from src.filter.job_filter import LinkedInJobFilter
from src.ingestion.ats_discovery import ATSDiscoveryCoordinator
from src.scraper.job_finder import LinkedInJobFinder
from src.tailor.knowledge_translator import KnowledgeBankTranslator


class JobSearchPipelineRunner:
    """
    Decoupled Orchestrator executing the end-to-end job discovery, AI tailoring,
    experience filtering, and dashboard approval pipeline across all sources.
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

    async def run_search_stage(
        self,
        source: str = "all",
        headless: bool | None = None,
    ) -> list[dict[str, Any]]:
        """
        Stage 2: Runs unified multi-source discovery (Direct Keyless ATS + LinkedIn Multi-Channel)
        with AI resume tailoring and cross-source deduplication.
        """
        discovery_cfg = dict(self.config.get("discovery", {}))
        if headless is not None:
            discovery_cfg["headless"] = headless

        target_source = (source or discovery_cfg.get("source", "all")).lower().strip()
        print("\n" + "=" * 60)
        print(f"  STAGE 2: UNIFIED JOB DISCOVERY & AI TAILORING (Target: {target_source.upper()})")
        print("=" * 60)

        ats_saved_paths: list[str] = []
        linkedin_jobs: list[dict[str, Any]] = []

        # -------------------------------------------------------------
        # TRACK 1: DIRECT KEYLESS ATS INGESTION (Greenhouse, Lever, Ashby)
        # -------------------------------------------------------------
        if target_source in ["all", "ats", "trio"]:
            print("\n" + "-" * 55)
            print("  🌐 [TRACK 1] DIRECT KEYLESS ATS INGESTION (Greenhouse, Lever, Ashby)")
            print("-" * 55)
            try:
                coordinator = ATSDiscoveryCoordinator(use_ai=self.use_ai)
                listings = await coordinator.ingest_all_sources(filter_sdet=True)
                ats_saved_paths = coordinator.save_listings_to_queue(listings, tailor=True)
                print(f"✅ Track 1 Complete: {len(ats_saved_paths)} enterprise role(s) queued.\n")
            except Exception as e:
                print(f"⚠️ Track 1 (ATS Ingestion) encountered warning: {e}\n")

        # -------------------------------------------------------------
        # TRACK 2: LINKEDIN MULTI-CHANNEL DISCOVERY (Search, Rec, Posts, Sim)
        # -------------------------------------------------------------
        if target_source in ["all", "linkedin"]:
            print("\n" + "-" * 55)
            print("  💼 [TRACK 2] LINKEDIN MULTI-CHANNEL STEALTH DISCOVERY")
            print("-" * 55)
            profiles = self.config.get("search_profiles", [])
            if profiles:
                try:
                    finder = LinkedInJobFinder(use_ai=self.use_ai)
                    linkedin_jobs = await finder.search_all_channels(profiles, discovery_config=discovery_cfg)
                    print(f"✅ Track 2 Complete: {len(linkedin_jobs)} LinkedIn job(s) queued.\n")
                except Exception as e:
                    print(f"⚠️ Track 2 (LinkedIn Discovery) encountered warning: {e}\n")
            else:
                print("ℹ️ No search_profiles found in config.yaml for LinkedIn.\n")

        total_seeded = len(ats_saved_paths) + len(linkedin_jobs)
        print("=" * 60)
        print(f"🎉 STAGE 2 COMPLETE: {total_seeded} total job(s) staged in data/pending_queue/")
        print(f"   • Direct Enterprise ATS Jobs: {len(ats_saved_paths)}")
        print(f"   • LinkedIn Multi-Channel Jobs: {len(linkedin_jobs)}")
        print("=" * 60 + "\n")

        return linkedin_jobs

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

    async def run_full_pipeline(
        self,
        skip_sync: bool = False,
        launch_ui: bool = True,
        source: str = "all",
        headless: bool = False,
    ):
        """Orchestrates Stages 1 -> 2 -> 3 -> 4 sequentially across all sources."""
        print("\n" + "🚀 " + "=" * 58)
        print("  STARTING ONE-SHOT AUTOMATED UNIFIED JOB SEARCH & TAILORING PIPELINE")
        print("=" * 60)

        # Stage 1: Sync Notes
        if not skip_sync:
            self.run_sync_stage()
        else:
            print("\n⏭️  Skipping Stage 1 (Knowledge Sync requested skip)")

        # Stage 2: Unified Search & Tailor
        await self.run_search_stage(source=source, headless=headless)

        # Stage 3: Filter Queue
        self.run_filter_stage()

        # Stage 4: Dashboard
        if launch_ui:
            self.run_dashboard_stage()
        else:
            print("\n💡 Pipeline complete! (Dashboard launch skipped via --no-dashboard)")
            print("👉 Run `python main.py dashboard` anytime to approve pending jobs.")
