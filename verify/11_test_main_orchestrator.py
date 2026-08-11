import json
import os
import subprocess
import sys

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import load_config


def test_orchestrator_pipeline():
    print("==================================================")
    print("  Testing Sprint 5: Master Orchestrator (main.py)")
    print("==================================================")

    # 1. Test config.yaml loading
    print("\n🔍 Step 1: Testing config.yaml loading...")
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    config = load_config(config_path)

    assert "search_profiles" in config
    assert len(config["search_profiles"]) >= 1
    assert "resume_path" in config
    assert "browser_profile_dir" in config
    print(f"✅ Loaded {len(config['search_profiles'])} search profile(s) from config.yaml!")
    print(f"   Top Profile: {config['search_profiles'][0]}")

    # 2. Test CLI Help Output
    print("\n🔍 Step 2: Testing main.py CLI Parser...")
    cmd = [sys.executable, "main.py", "--help"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0
    assert "search" in result.stdout
    assert "--login" in result.stdout
    assert "--apply" in result.stdout
    print("✅ main.py CLI help output validated successfully!")

    # 3. Test application_history.json structure
    print("\n🔍 Step 3: Testing data/application_history.json...")
    hist_path = os.path.join(os.path.dirname(__file__), "..", "data", "application_history.json")
    assert os.path.exists(hist_path)
    with open(hist_path, "r") as f:
        hist_data = json.load(f)
    assert isinstance(hist_data, list)
    print(f"✅ Application history DB loaded with {len(hist_data)} record(s)!")

    print("\n" + "=" * 50)
    print("✅ MASTER ORCHESTRATOR PIPELINE VERIFIED SUCCESSFULLY!")
    print("=" * 50)


if __name__ == "__main__":
    test_orchestrator_pipeline()
