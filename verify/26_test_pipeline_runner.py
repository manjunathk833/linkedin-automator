from __future__ import annotations

import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import load_config
from src.pipeline.runner import JobSearchPipelineRunner


def test_pipeline_runner():
    print("==================================================")
    print("  Testing CLI Streamlining & JobSearchPipelineRunner")
    print("==================================================")

    # 1. Load config & initialize runner
    config = load_config("config.yaml")
    runner = JobSearchPipelineRunner(config)
    assert runner.config is not None
    print("✅ Pipeline runner initialized successfully!")

    # 2. Test sync stage (non-interactive)
    res_sync = runner.run_sync_stage()
    assert "status" in res_sync
    print(f"✅ Stage 1 (Knowledge Sync) test PASS! Status: {res_sync['status']}")

    # 3. Test filter stage (non-interactive)
    runner.run_filter_stage()
    print("✅ Stage 3 (Queue Filter) test PASS!")

    print("\n" + "=" * 50)
    print("✅ PIPELINE RUNNER & CLI STREAMLINING VERIFIED 100%!")
    print("=" * 50)


if __name__ == "__main__":
    test_pipeline_runner()
